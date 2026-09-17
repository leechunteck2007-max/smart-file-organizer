"""Stateful preview, organization sessions, cleanup approval and undo."""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import time
import uuid

from app.actions.move import MoveEngine
from app.core.models import MovePlan
from app.database.store import Store
from app.safety.policy import SafetyPolicy, under
from app.scanner.scanner import scan, sha256
from app.undo.engine import UndoEngine
from app.smart.inspect import inspect_document
from app.smart.understand import FileUnderstanding
from app.smart.cleanup import cleanup_candidates


class SmartService:
    def __init__(self, state, progress=None):
        self.state = Path(state)
        self.store = Store(self.state / 'organizer.sqlite')
        self.settings = dict(folders=[], library=str(Path.home()/'File Library'), protected=[], ignored=[],
                             controlled_verified=False, controlled_actions=[], last_scan='', scanned=0)
        self.settings.update({k:v for k,v in self.store.load().items() if k in self.settings})
        self.store.connection.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, created TEXT, payload TEXT, report TEXT, report_error TEXT);
            CREATE TABLE IF NOT EXISTS session_actions (
                session_id TEXT, action_id TEXT UNIQUE);
        ''')
        self.store.connection.commit()
        self.policy = SafetyPolicy(self.settings, self.state)
        self.mover = MoveEngine(self.store, self.policy)
        self.mover.recover()
        self.recover_sessions()
        self.undo_engine = UndoEngine(self.mover)
        self.plans = {}
        self.cleanup = []
        self.errors = []
        self.records = []
        self.scan_token = ''
        self.progress = progress or (lambda value: None)

    def configure(self, folders=None, library=None):
        if folders is not None:
            if not isinstance(folders, list) or len(folders)>30:
                raise ValueError('Choose at most 30 folders')
            for folder in folders:
                p = Path(folder)
                if not p.is_absolute() or not p.is_dir() or p.parent == p or str(p).startswith('\\\\'):
                    raise ValueError('Choose an existing local user folder, not a drive or network share')
                if self.policy.directory_veto(p):
                    raise ValueError('This folder is protected; choose a personal inbox folder')
            self.settings['folders'] = list(dict.fromkeys(folders))
        if library is not None:
            p = Path(library)
            if not p.is_absolute() or p.parent==p or str(p).startswith('\\\\'):
                raise ValueError('Choose a local File Library folder')
            self.policy.clear_cache()
            if self.policy.veto(p/'File.pdf', destination=True):
                raise ValueError('This library location is protected')
            self.settings['library'] = str(p)
        self.store.save(self.settings)
        self.plans = {}
        self.cleanup = []
        self.scan_token = ''
        return self.snapshot()

    def recover_sessions(self):
        db=self.store.connection
        history={a['id']:a for a in self.store.history()}
        for row in db.execute('SELECT * FROM sessions').fetchall():
            payload=json.loads(row['payload'])
            existing={f['action_id'] for f in payload['files']}
            linked=[r[0] for r in db.execute('SELECT action_id FROM session_actions WHERE session_id=?',(row['id'],))]
            recovered=False
            for action_id in linked:
                action=history.get(action_id)
                if action and action['status']=='SUCCESS' and action_id not in existing:
                    payload['files'].append(dict(action_id=action_id,original=Path(action['source']).name,
                        name=Path(action['destination']).name,source=action['source'],destination=action['destination'],
                        category='Organization',reason=action['reason'],confidence=action['confidence'],size=0))
                    recovered=True
            if recovered:
                payload['organized']=len(payload['files'])
                payload['renamed']=sum(f['original']!=f['name'] for f in payload['files'])
                payload['unchanged']=payload['scanned']-payload['organized']
                db.execute('UPDATE sessions SET payload=?,report_error=? WHERE id=?',
                           (json.dumps(payload),'Interrupted session recovered. Review its files and create a new report.',row['id']))
        db.commit()

    def scan(self, content=True):
        if not self.settings['folders']:
            raise ValueError('Select at least one folder to scan')
        started=time.perf_counter()
        self.progress(dict(stage='Scanning folders',current=0,total=0,file='Collecting file metadata'))
        records, errors = scan(self.settings['folders'], self.policy)
        ignored = self.store.ignored()
        self.records = records
        texts = {}
        for i,record in enumerate(records):
            self.progress(dict(stage='Understanding your files',current=i+1,total=len(records),file=record.filename))
            if content and not record.protected:
                try:
                    text, error = inspect_document(record.current_path)
                    texts[record.id] = text
                    if error: errors.append(error)
                except OSError:
                    errors.append('ContentUnavailable')
        understanding = FileUnderstanding(records, texts, self.policy)
        self.plans = {}
        for record in records:
            classification, name = understanding.analyze(record)
            if record.current_path in ignored:
                continue
            plan = MovePlan(record, classification, classification.suggested_destination)
            self.plans[record.id] = dict(plan=plan, name=name)
        self.progress(dict(stage='Checking exact duplicates',current=len(records),total=len(records),file='Comparing candidate hashes'))
        self.cleanup, groups, duplicate_errors = cleanup_candidates(records)
        self.cleanup = [candidate for candidate in self.cleanup if candidate['source'] not in ignored]
        self.errors = errors + duplicate_errors
        self.settings.update(last_scan=datetime.now().isoformat(timespec='seconds'),scanned=len(records))
        self.store.save(self.settings)
        self.scan_token = str(uuid.uuid4())
        result = self.snapshot()
        result['elapsed'] = round(time.perf_counter()-started,3)
        result['discovered_codes'] = sorted(understanding.codes)
        return result

    def snapshot(self):
        suggestions=[]
        for key,item in self.plans.items():
            p=item['plan'];c=p.classification
            suggestions.append(dict(id=key,file=p.file.filename,source=p.file.current_path,name=item['name'],
                destination=p.destination,category='/'.join(filter(None,[c.category,c.subcategory])),confidence=c.confidence,
                reason=c.reason,size=p.file.size,protected=p.file.protected,status=p.status))
        sessions=self.sessions()
        return dict(settings=self.settings,token=self.scan_token,plans=suggestions,cleanup=self.cleanup,
                    errors=self.errors,sessions=sessions,
                    totals=dict(scanned=self.settings['scanned'],organized=sum(s['organized'] for s in sessions),
                                cleanup_size=sum(c['size'] for c in self.cleanup),
                                needs_review=sum(p['confidence']<80 and not p['protected'] and p['status']=='Awaiting approval' for p in suggestions)))

    def ignore(self, ids):
        for key in ids:
            item=self.plans.get(key)
            if item:
                self.store.decision(item['plan'].file.current_path,'Ignore')
                item['plan'].status='Ignored'
        self.cleanup=[c for c in self.cleanup if c['record_id'] not in ids]
        return self.snapshot()

    def change_destination(self, key, folder):
        item=self.plans[key];p=item['plan']
        if p.file.protected:
            raise ValueError('Protected files stay in place')
        destination=str(Path(folder)/item['name'])
        self.policy.clear_cache()
        veto=self.policy.valid_destination(destination)
        if veto: raise ValueError(veto)
        p.destination=destination
        p.status='Awaiting approval'
        return self.snapshot()

    def organize(self, ids, token, cleanup=False):
        if token != self.scan_token or not token:
            raise ValueError('Preview expired; scan again before organizing')
        ids=list(dict.fromkeys(ids))
        if not ids:
            raise ValueError('Select files to organize')
        selected=[]
        if cleanup:
            candidates={c['id']:c for c in self.cleanup}
            for key in ids:
                if key not in candidates: raise ValueError('Cleanup preview changed; scan again')
                c=candidates[key];item=self.plans[c['record_id']];base=item['plan']
                if c['category']=='Duplicates':
                    canonical=Path(c['canonical'])
                    if not canonical.is_file() or self.policy.veto(canonical) or sha256(canonical)!=c['hash']:
                        raise ValueError('Retained duplicate copy changed or is unavailable; scan again')
                    if sha256(base.file.current_path)!=c['hash']:
                        raise ValueError('Duplicate candidate changed; scan again')
                dest=str(Path(self.settings['library'])/'Review Before Delete'/c['category']/base.file.filename)
                selected.append((c['record_id'],MovePlan(base.file,base.classification,dest),c['reason']))
        else:
            for key in ids:
                if key not in self.plans: raise ValueError('Unknown preview entry')
                p=self.plans[key]['plan']
                if not p.destination or p.file.protected or p.status!='Awaiting approval':
                    raise ValueError('Select only actionable preview entries')
                selected.append((key,p,p.classification.reason))
        if not self.settings['controlled_verified']:
            if self.settings['controlled_actions']:
                raise ValueError('Restore your first test in History before organizing more files')
            if not 5<=len(selected)<=20:
                raise ValueError('For your first test, select 5–20 copied files; then restore them from History')
        session_id=str(uuid.uuid4())
        payload=dict(id=session_id,created=datetime.now(timezone.utc).isoformat(),folders=list(self.settings['folders']),
                     scanned=len(self.records),organized=0,renamed=0,folders_created=0,
                     unchanged=len(self.records),needs_review=sum(p['plan'].classification.confidence<80 and not p['plan'].file.protected for p in self.plans.values()),
                     cleanup_size=sum(c['size'] for c in self.cleanup),cleanup=list(self.cleanup),files=[],failures=[],cleanup_session=cleanup)
        db=self.store.connection
        db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(session_id,payload['created'],json.dumps(payload),'',''))
        db.commit()
        created=set();actions=[]
        for i,(key,p,reason) in enumerate(selected):
            self.progress(dict(stage='Organizing approved files',current=i+1,total=len(selected),file=p.file.filename))
            for parent in Path(p.destination).parents:
                if under(parent,self.settings['library']) and not parent.exists():created.add(str(parent))
            try:
                action=str(uuid.uuid4())
                db.execute('INSERT INTO session_actions VALUES (?,?)',(session_id,action));db.commit()
                action=self.mover.execute(p.file.current_path,p.destination,reason,p.classification.confidence,
                    expected=(p.file.size,p.file.modified_at),action_id=action)
                a=next(a for a in self.store.history() if a['id']==action)
                actions.append(action)
                payload['files'].append(dict(action_id=action,original=p.file.filename,name=Path(a['destination']).name,
                    source=a['source'],destination=a['destination'],category='Review Before Delete/'+Path(p.destination).parent.name if cleanup else p.classification.category+'/'+p.classification.subcategory,
                    reason=reason,confidence=p.classification.confidence,size=p.file.size))
                payload['organized']+=1
                payload['renamed']+=int(p.file.filename!=Path(a['destination']).name)
                self.plans[key]['plan'].status='Organized'
            except Exception as exc:
                payload['failures'].append(dict(file=p.file.filename,error=str(exc)))
                self.plans[key]['plan'].status='Review required'
            payload['folders_created']=sum(Path(p).is_dir() for p in created)
            payload['unchanged']=payload['scanned']-payload['organized']
            db.execute('UPDATE sessions SET payload=? WHERE id=?',(json.dumps(payload),session_id));db.commit()
        self.cleanup=[c for c in self.cleanup if self.plans[c['record_id']]['plan'].status!='Organized']
        if not self.settings['controlled_verified'] and actions:
            self.settings['controlled_actions']=actions;self.store.save(self.settings)
        self.generate_report(session_id)
        return self.snapshot()

    def generate_report(self, session_id):
        from app.smart.report import generate
        db=self.store.connection
        row=db.execute('SELECT * FROM sessions WHERE id=?',(session_id,)).fetchone()
        if not row: raise ValueError('Session not found')
        payload=json.loads(row['payload'])
        try:
            self.progress(dict(stage='Creating your Word report',current=1,total=1,file='Organization report'))
            report=generate(payload,self.state/'Reports')
            db.execute('UPDATE sessions SET report=?,report_error=? WHERE id=?',(str(report),'',session_id))
        except Exception as exc:
            db.execute('UPDATE sessions SET report_error=? WHERE id=?',(str(exc),session_id))
        db.commit()
        return self.snapshot()

    def sessions(self):
        results=[]
        history={a['id']:a for a in self.store.history()}
        for row in self.store.connection.execute('SELECT * FROM sessions ORDER BY created DESC'):
            payload=json.loads(row['payload'])
            ids=[r[0] for r in self.store.connection.execute('SELECT action_id FROM session_actions WHERE session_id=?',(row['id'],))]
            payload.update(report=row['report'],report_error=row['report_error'],actions=[history[i] for i in ids if i in history],
                           undone=bool(ids) and any(history.get(i,{}).get('status')=='SUCCESS' for i in ids) and all(not history.get(i,{}).get('undo_available') for i in ids))
            results.append(payload)
        return results

    def restore(self, session_id, action_id=None):
        session=next((s for s in self.sessions() if s['id']==session_id),None)
        if not session: raise ValueError('Session not found')
        errors=[]
        for action in reversed(session['actions']):
            if not action['undo_available'] or (action_id and action['id']!=action_id):continue
            try:self.undo_engine.undo(action)
            except Exception as exc:errors.append(str(exc))
        controlled=self.settings['controlled_actions']
        actions={a['id']:a for a in self.store.history()}
        if controlled and all(not actions[i]['undo_available'] and Path(actions[i]['source']).is_file() and sha256(actions[i]['source'])==actions[i]['hash'] for i in controlled):
            self.settings['controlled_verified']=len(controlled)>=5
            self.settings['controlled_actions']=[]
            self.store.save(self.settings)
        result=self.snapshot();result['restore_errors']=errors
        return result
