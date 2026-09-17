"""Prune first, inspect later. No guessed percentage during open-ended discovery."""
import hashlib
import os
from pathlib import Path
import threading
import time
from app.core.models import FileRecord
from app.safety.policy import linked, under, TEMP_EXT
from app.smart.discovery import PERSONAL, area_risk


class ScanCancelled(Exception):pass


class ScanControl:
    def __init__(self):self.paused=threading.Event();self.cancelled=threading.Event()
    def checkpoint(self):
        while self.paused.is_set() and not self.cancelled.is_set():self.cancelled.wait(.1)
        if self.cancelled.is_set():raise ScanCancelled('Scan cancelled. No files were changed.')


def already_organized(path,root):
    relative=Path(path).parent.relative_to(root)
    parts=relative.parts
    messy={'downloads','desktop','inbox','unsorted','misc','miscellaneous','temp','new folder','to sort'}
    # Any meaningful folder beneath a data root represents a human grouping.
    return bool(parts) and parts[-1].lower() not in messy and not parts[-1].lower().startswith('new folder')


def collect(roots,policy,control,progress,limit=250000,preserve_roots=()):
    records=[];errors=[];organized=set();skipped=[];projects=set();seen=set();count=0;last=0
    for folder in roots:
        root=Path(folder)
        if linked(root):continue
        def error(exc):errors.append(type(exc).__name__)
        for current,dirs,names in os.walk(root,followlinks=False,onerror=error):
            control.checkpoint();p=Path(current)
            risk=area_risk(p,policy)
            if risk or under(p,policy.settings['library']) or p.name=='File Library':
                skipped.append(dict(path=str(p),kind=risk or 'PROTECTED'))
                if risk=='PROJECT':projects.add(str(p))
                dirs[:]=[];continue
            dirs[:]=[d for d in dirs if not linked(p/d)]
            for name in names:
                control.checkpoint();file=p/name;key=str(file.absolute()).casefold()
                if key in seen:continue
                seen.add(key);count+=1
                if count>limit:raise ValueError('Scan limit reached (250,000 files). Exclude a drive or folder and scan again; no partial plan can be organized.')
                if time.monotonic()-last>.15:
                    progress(dict(stage='Discovering personal files',current=count,total=0,file=str(p),discovered=count,analyzed=len(records)))
                    last=time.monotonic()
                if linked(file) or file.suffix.lower() in TEMP_EXT:continue
                try:
                    st=file.stat()
                    if not file.is_file():continue
                    # Never hydrate offline/recall-on-open cloud data.
                    if getattr(st,'st_file_attributes',0)&(0x1000|0x40000|0x400000):continue
                    veto=policy.veto(file)
                    if file.suffix.lower()=='.exe' and not any(w in name.lower() for w in ('setup','install')):veto=veto or 'Executable purpose uncertain; unchanged'
                    if file.suffix.lower() not in PERSONAL|{'.exe'}:veto=veto or 'Unknown file format; unchanged'
                    records.append(FileRecord(hashlib.sha256(key.encode()).hexdigest()[:24],name,file.suffix.lower(),st.st_size,st.st_ctime,st.st_mtime,str(file),str(file),protected=bool(veto)))
                    if not veto and (str(root) in preserve_roots or already_organized(file,root)):organized.add(str(file))
                except OSError as exc:error(exc)
    return records,errors,organized,skipped,projects,count
