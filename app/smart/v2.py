"""Scan → organize → done, with safety vetoes instead of mandatory approvals."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from app.core.models import MovePlan
from app.safety.policy import under
from app.smart.service import SmartService
from app.smart.discovery import discover, PERSONAL
from app.smart.progressive import collect,ScanControl,ScanCancelled
from app.smart.inspect import inspect_document
from app.smart.understand import FileUnderstanding,DOCS
from app.smart.cleanup import cleanup_candidates
from app.scanner.scanner import sha256


class V2Service(SmartService):
    def __init__(self,state,progress=None):
        super().__init__(state,progress)
        defaults=dict(excluded_drives=[],external_drives=True,automatic_rename=True,theme='light')
        saved=self.store.load()
        self.settings.update({k:saved.get(k,v) for k,v in defaults.items()})
        self.inventory=[];self.skipped=[];self.projects=set();self.already=set();self.discovered=0
        self.control=ScanControl();self.ready=False;self.cancelled=False
        self.store.connection.executescript('''
            CREATE TABLE IF NOT EXISTS content_cache(path TEXT PRIMARY KEY,size INTEGER,modified REAL,text TEXT);
            CREATE TABLE IF NOT EXISTS session_operations(id TEXT PRIMARY KEY,session_id TEXT,timestamp TEXT,type TEXT,
                source TEXT,destination TEXT,reason TEXT,confidence INTEGER,status TEXT);
        ''');self.store.connection.commit()

    def options(self,**values):
        allowed={'excluded_drives','external_drives','automatic_rename','theme','ignored'}
        if values.keys()-allowed:raise ValueError('Unsupported setting')
        for key,value in values.items():
            if key in {'external_drives','automatic_rename'} and type(value)!=bool:raise ValueError('Boolean required')
            if key=='theme' and value not in {'light','dark','system'}:raise ValueError('Invalid theme')
            if key in {'excluded_drives','ignored'}:
                if not isinstance(value,list) or len(value)>100 or any(not isinstance(p,str) or not Path(p).is_absolute() for p in value):raise ValueError('Absolute local paths required')
        self.settings.update(values);self.store.save(self.settings);self.invalidate()
        return self.snapshot()

    def configure(self,folders=None,library=None):
        result=super().configure(folders,library)
        self.ready=False
        return self.snapshot()

    def invalidate(self):
        self.ready=False;self.scan_token='';self.plans={};self.cleanup=[]

    def scan_computer(self,content=True,storage=None):
        self.invalidate();self.records=[];self.cancelled=False;self.control=ScanControl()
        started=time.perf_counter()
        try:
            self.progress(dict(stage='Discovering storage',current=0,total=0,file='Local drives and user folders'))
            self.policy.clear_cache()
            self.inventory,roots=discover(self.policy,self.settings,**(storage or {}))
            self.settings['folders']=roots
            inboxes={'downloads','desktop','inbox','unsorted','misc','miscellaneous','temp','new folder','to sort'}
            preserve_roots={a['path'] for a in self.inventory if a.get('origin')=='additional' and a['eligible'] and Path(a['path']).name.lower() not in inboxes}
            records,errors,self.already,self.skipped,self.projects,self.discovered=collect(roots,self.policy,self.control,self.progress,preserve_roots=preserve_roots)
            self.records=records;texts={};db=self.store.connection
            candidates=[r for r in records if not r.protected and r.current_path not in self.already]
            inspected=0
            for i,r in enumerate(candidates):
                self.control.checkpoint()
                if i%25==0:self.progress(dict(stage='Understanding your files',current=i,total=len(candidates),file=Path(r.current_path).parent.name,discovered=self.discovered,analyzed=i))
                # Inspect documents only when metadata/name is not already conclusive.
                if not content or r.extension not in DOCS or r.size>10*1024*1024:continue
                cached=db.execute('SELECT * FROM content_cache WHERE path=?',(r.current_path,)).fetchone()
                if cached and cached['size']==r.size and cached['modified']==r.modified_at:texts[r.id]=cached['text'];continue
                if inspected>=500:
                    continue
                # Topic-labelled academic files already carry sufficient metadata.
                import re
                if re.search(r'\b[A-Z]{2,6}\d{2,4}\b.*\b(?:lecture|tutorial|assignment|lab)\b',r.filename,re.I):continue
                inspected+=1
                text,error=inspect_document(r.current_path)
                if error:errors.append(error)
                texts[r.id]=text
                db.execute('INSERT OR REPLACE INTO content_cache VALUES (?,?,?,?)',(r.current_path,r.size,r.modified_at,text[:20000]))
                if i%100==0:db.commit()
            if inspected>=500:errors.append('Content inspection budget reached; remaining files use conservative metadata classification')
            db.commit();understanding=FileUnderstanding(records,texts,self.policy)
            ignored=self.store.ignored()
            for r in records:
                self.control.checkpoint();c,name=understanding.analyze(r)
                if r.protected:
                    c.suggested_destination='';c.category='Protected';c.subcategory='';c.confidence=0
                    c.reason=self.policy.veto(r.current_path) or 'Unknown file or storage risk; unchanged'
                    name=r.filename
                elif r.current_path in self.already:
                    c.suggested_destination='';c.reason='Existing human folder organization retained'
                elif r.current_path in ignored:c.suggested_destination=''
                elif c.confidence<90:
                    name=r.filename
                    if c.confidence>=70:
                        c.category='Photos' if r.extension in {'.png','.jpg','.jpeg','.heic','.webp','.gif'} else 'Documents' if r.extension in DOCS else c.category
                        c.subcategory=''
                        c.suggested_destination=str(Path(self.settings['library'])/c.category/name)
                    else:c.suggested_destination=''
                if not self.settings['automatic_rename']:name=r.filename
                if c.suggested_destination:
                    library=self.library_for(r.current_path)
                    c.suggested_destination=str(library/c.category/c.subcategory/name)
                plan=MovePlan(r,c,c.suggested_destination)
                plan.status='Already organized' if r.current_path in self.already else 'Protected' if r.protected else 'Ready' if plan.destination else 'Unchanged'
                self.plans[r.id]=dict(plan=plan,name=name)
            # Hash only eligible equal-size groups, with pause/cancel checkpoints per chunk.
            eligible=[r for r in candidates if r.current_path not in ignored]
            self.cleanup=self.find_cleanup(eligible)
            self.errors=errors;self.settings.update(last_scan=datetime.now().isoformat(timespec='seconds'),scanned=self.discovered)
            self.store.save(self.settings);self.scan_token=str(uuid.uuid4());self.ready=True
            result=self.snapshot();result['elapsed']=round(time.perf_counter()-started,3);return result
        except ScanCancelled:
            self.invalidate();self.cancelled=True;self.records=[];return self.snapshot()
        except Exception:
            self.invalidate();raise

    def library_for(self,source):
        library=Path(self.settings['library']);source=Path(source)
        # No cross-volume copy/delete fallback. Each data drive gets a local library.
        if source.drive.casefold()!=library.drive.casefold():return Path(source.anchor)/'File Library'
        return library

    def find_cleanup(self,records):
        from collections import defaultdict
        sizes=defaultdict(list)
        for r in records:sizes[r.size].append(r)
        duplicate=[];excluded=set();candidate_groups=[g for g in sizes.values() if len(g)>1]
        for i,group in enumerate(candidate_groups):
            self.control.checkpoint()
            self.progress(dict(stage='Checking duplicate candidates',current=i,total=len(candidate_groups),file='Size matches only',discovered=self.discovered,analyzed=len(records)))
            hashes=defaultdict(list)
            for r in group:
                try:
                    digest=hashlib.sha256()
                    with open(r.current_path,'rb') as handle:
                        for chunk in iter(lambda:handle.read(1024*1024),b''):
                            self.control.checkpoint();digest.update(chunk)
                    st=Path(r.current_path).stat()
                    if (st.st_size,st.st_mtime)!=(r.size,r.modified_at):continue
                    hashes[digest.hexdigest()].append(r)
                except OSError:continue
            for digest,matches in hashes.items():
                if len(matches)<2:continue
                matches.sort(key=lambda r:(len(r.filename),r.current_path.casefold()));canonical=matches[0]
                excluded.update(r.id for r in matches)
                for r in matches[1:]:duplicate.append(dict(id='cleanup:'+r.id,record_id=r.id,file=r.filename,source=r.current_path,
                    category='Confirmed Duplicates',reason='Size and SHA-256 identical to retained copy: '+canonical.current_path,size=r.size,
                    risk='Confirmed identical bytes; usefulness requires review',canonical=canonical.current_path,hash=digest))
        # Installer detection reused without rehashing the entire set.
        # Avoid test-only dependencies in production: apply installer heuristic directly.
        for r in records:
            if r.id in excluded:continue
            age=(time.time()-r.modified_at)/86400;name=r.filename.lower()
            if age>=90 and r.extension in {'.exe','.msi','.iso','.zip','.7z'} and any(w in name for w in ('setup','install')):
                duplicate.append(dict(id='cleanup:'+r.id,record_id=r.id,file=r.filename,source=r.current_path,
                    category='Installers' if r.extension in {'.exe','.msi','.iso'} else 'Archives',reason='Installation-package name and age over 90 days; usage is unknown',size=r.size,risk='Review before deleting; may still be needed',canonical='',hash=''))
        return duplicate

    def snapshot(self):
        # Super constructor calls snapshot only after initialization; tolerate old recovery payloads.
        result=super().snapshot();plans=result['plans'];already=getattr(self,'already',set())
        result.update(storage=getattr(self,'inventory',[]),skipped=getattr(self,'skipped',[]),ready=getattr(self,'ready',False),cancelled=getattr(self,'cancelled',False))
        result['totals'].update(ready=sum(bool(p['destination']) and not p['protected'] and p['status']=='Ready' for p in plans),
            analyzed=sum(not r.protected for r in self.records),already_organized=len(already),protected=sum(r.protected for r in self.records),
            protected_trees=len(getattr(self,'skipped',[]))+sum(not a['eligible'] and not a.get('drive') for a in getattr(self,'inventory',[])),
            projects=len(getattr(self,'projects',set()))+sum(a['kind']=='PROJECT' for a in getattr(self,'inventory',[])),cleanup_candidates=len(self.cleanup),
            unchanged=sum(not p['destination'] and not p['protected'] and p['source'] not in already for p in plans))
        result['plan_count']=len(plans);result['plans']=plans[:500];result['cleanup']=self.cleanup[:500]
        # Complete file/action details stay in SQLite. Avoid unbounded IPC payloads.
        for session in result['sessions']:
            session['action_count']=len(session['actions']);session['actions']=session['actions'][:500];session['files']=session['files'][:500]
        return result

    def journal(self,session,kind,source,destination,reason,confidence,status='SUCCESS'):
        key=str(uuid.uuid4());self.store.connection.execute('INSERT INTO session_operations VALUES (?,?,?,?,?,?,?,?,?)',
            (key,session,datetime.now(timezone.utc).isoformat(),kind,str(source),str(destination),reason,confidence,status));self.store.connection.commit();return key

    def organize_all(self,token):
        if not self.ready or token!=self.scan_token or not token:raise ValueError('Scan your computer again before organizing')
        candidates={c['record_id']:c for c in self.cleanup};selected=[]
        # Quarantine first, while retained canonical paths still exist.
        for key,c in candidates.items():
            item=self.plans[key];base=item['plan'];destination=self.library_for(base.file.current_path)/'Review Before Delete'/c['category']/base.file.filename
            selected.append((key,MovePlan(base.file,base.classification,str(destination)),c['reason'],c))
        selected.extend((key,item['plan'],item['plan'].classification.reason,None) for key,item in self.plans.items()
                        if key not in candidates and item['plan'].destination and not item['plan'].file.protected and item['plan'].status=='Ready')
        sid=str(uuid.uuid4());payload=dict(id=sid,created=datetime.now(timezone.utc).isoformat(),folders=self.settings['folders'],
            scanned=self.discovered,eligible=sum(not r.protected for r in self.records),organized=0,renamed=0,folders_created=0,unchanged=self.discovered,
            protected=sum(r.protected for r in self.records),projects=self.snapshot()['totals']['projects'],protected_directories=self.skipped+[a for a in self.inventory if not a['eligible']],
            needs_review=sum(not i['plan'].destination and not i['plan'].file.protected for i in self.plans.values()),
            cleanup_size=sum(c['size'] for c in self.cleanup),cleanup=[dict(c,review_location='') for c in self.cleanup],files=[],failures=[],cleanup_session=False,v2=True,cleanup_candidates=len(self.cleanup),quarantined=0)
        db=self.store.connection;db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(sid,payload['created'],json.dumps(payload),'',''));db.commit()
        for i,(key,p,reason,cleanup) in enumerate(selected):
            self.progress(dict(stage='Organizing your files',current=i,total=len(selected),file=p.file.filename))
            from contextlib import ExitStack
            guards=ExitStack()
            try:
                if not any(under(p.file.current_path,root) for root in self.settings['folders']):raise ValueError('Outside discovered user-data scope')
                self.policy.clear_cache()
                if self.policy.veto(p.file.current_path) or self.policy.veto(p.destination,True):raise ValueError('Safety veto; unchanged')
                from app.actions.move import read_guard
                guards.enter_context(read_guard(p.file.current_path))
                # Compare occupied destinations before choosing suffix versus duplicate quarantine.
                if not cleanup and Path(p.destination).is_file() and not self.policy.veto(p.destination):
                    from app.actions.move import read_guard
                    guards.enter_context(read_guard(p.destination))
                    if Path(p.destination).stat().st_size==p.file.size and sha256(p.destination)==sha256(p.file.current_path):
                        canonical=p.destination
                        cleanup=dict(id='collision:'+key,record_id=key,file=p.file.filename,source=p.file.current_path,category='Confirmed Duplicates',reason='Size and SHA-256 match the existing organized copy: '+canonical,size=p.file.size,risk='Confirmed identical bytes; review before deleting',canonical=canonical,hash=sha256(canonical),review_location='')
                        reason=cleanup['reason'];payload['cleanup'].append(cleanup.copy());payload['cleanup_candidates']+=1;payload['cleanup_size']+=p.file.size
                        p=MovePlan(p.file,p.classification,str(self.library_for(p.file.current_path)/'Review Before Delete'/'Confirmed Duplicates'/p.file.filename))
                if cleanup and cleanup['canonical']:
                    from app.actions.move import read_guard
                    canonical=Path(cleanup['canonical']);guards.enter_context(read_guard(canonical))
                    if self.policy.veto(canonical) or not canonical.is_file() or sha256(canonical)!=cleanup['hash'] or sha256(p.file.current_path)!=cleanup['hash']:raise ValueError('Duplicate evidence changed; unchanged')
                missing=[];parent=Path(p.destination).parent
                while not parent.exists():missing.append(parent);parent=parent.parent
                for directory in reversed(missing):
                    if self.policy.veto(directory/'probe.pdf',True):raise ValueError('Destination directory protected')
                    op=self.journal(sid,'CREATE DIRECTORY','',directory,'Create required organization folder',100,'PREPARED')
                    directory.mkdir();payload['folders_created']+=1
                    db.execute("UPDATE session_operations SET status='SUCCESS' WHERE id=?",(op,));db.commit()
                action=str(uuid.uuid4());db.execute('INSERT INTO session_actions VALUES (?,?)',(sid,action));db.commit()
                # The existing engine accepts one library; select the source-volume library for this item.
                old=self.settings['library'];self.settings['library']=str(self.library_for(p.file.current_path))
                try:self.mover.execute(p.file.current_path,p.destination,reason,p.classification.confidence,expected=(p.file.size,p.file.modified_at),action_id=action)
                finally:self.settings['library']=old
                a=dict(db.execute('SELECT * FROM actions WHERE id=?',(action,)).fetchone())
                kind='QUARANTINE' if cleanup else 'MOVE'
                self.journal(sid,kind,a['source'],a['destination'],reason,p.classification.confidence)
                if p.file.filename!=Path(a['destination']).name:self.journal(sid,'RENAME',a['source'],a['destination'],reason,p.classification.confidence)
                payload['files'].append(dict(action_id=action,original=p.file.filename,name=Path(a['destination']).name,source=a['source'],destination=a['destination'],category='Review Before Delete/'+cleanup['category'] if cleanup else '/'.join(filter(None,[p.classification.category,p.classification.subcategory])),reason=reason,confidence=p.classification.confidence,size=p.file.size,action=kind))
                if cleanup:
                    next(c for c in payload['cleanup'] if c['id']==cleanup['id'])['review_location']=a['destination'];payload['quarantined']+=1
                payload['organized']+=1;payload['renamed']+=int(p.file.filename!=Path(a['destination']).name);self.plans[key]['plan'].status='Organized'
            except Exception as exc:
                payload['failures'].append(dict(file=p.file.filename,error=str(exc)));self.plans[key]['plan'].status='Unchanged'
            finally:guards.close()
            payload['unchanged']=payload['scanned']-payload['organized']
            if i%25==0 or i==len(selected)-1:
                db.execute('UPDATE sessions SET payload=? WHERE id=?',(json.dumps(payload),sid));db.commit()
        self.ready=False;self.scan_token='';self.generate_report(sid)
        return self.snapshot()

    def restore(self,session_id,action_id=None):
        result=super().restore(session_id,action_id)
        if not action_id:
            rows=self.store.connection.execute("SELECT * FROM session_operations WHERE session_id=? AND type='CREATE DIRECTORY' AND status='SUCCESS' ORDER BY timestamp DESC",(session_id,)).fetchall()
            for row in rows:
                directory=Path(row['destination'])
                # rmdir only empty, recorded folders; never recursive delete.
                try:
                    if directory.is_dir() and not self.policy.veto(directory/'probe.pdf',True):directory.rmdir()
                    if not directory.exists():self.store.connection.execute("UPDATE session_operations SET status='UNDONE' WHERE id=?",(row['id'],))
                except OSError:pass
            self.store.connection.commit()
        return self.snapshot()|{'restore_errors':result.get('restore_errors',[])}
