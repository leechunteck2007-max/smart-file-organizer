"""Narrow line-based JSON RPC for the desktop parent process."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
from concurrent.futures import ThreadPoolExecutor


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-dir',type=Path)
    parser.add_argument('--extract')
    parser.add_argument('--smoke-test',action='store_true')
    args=parser.parse_args()
    if args.extract:
        from app.smart.inspect import extract_local
        from app.smart.limits import limit_worker_memory
        try:
            limit_worker_memory()
            result=dict(text=extract_local(args.extract),error='')
        except Exception as exc:result=dict(text='',error=type(exc).__name__)
        print(json.dumps(result,ensure_ascii=True));return
    from app.smart.v2 import V2Service
    state=args.state_dir or Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'SmartFileOrganizer'
    state.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(state/'application.log',maxBytes=1000000,backupCount=2,encoding='utf-8')])
    output_lock=threading.Lock()
    def emit(value):
        with output_lock:print(json.dumps(value,ensure_ascii=True),flush=True)
    service=V2Service(state,lambda progress:emit(dict(event='progress',data=progress)))
    if args.smoke_test:
        from datetime import datetime, timezone
        from app.smart.report import generate
        sample=dict(created=datetime.now(timezone.utc).isoformat(),folders=[],scanned=0,organized=0,renamed=0,
                    folders_created=0,unchanged=0,needs_review=0,cleanup_size=0,cleanup=[],files=[],failures=[])
        report=generate(sample,state/'Reports')
        emit(dict(ok=True,data=service.snapshot(),report_created=report.is_file()))
        service.store.close();return
    def handle(request):
        try:
            command=request['command'];params=request.get('params',{})
            if command=='snapshot':result=service.snapshot()
            elif command=='configure':result=service.configure(**params)
            elif command=='scan':result=service.scan_computer()
            elif command=='options':result=service.options(**params)
            elif command=='organize_all':result=service.organize_all(params['token'])
            elif command=='ignore':result=service.ignore(params['ids'])
            elif command=='destination':result=service.change_destination(params['id'],params['folder'])
            elif command=='organize':result=service.organize(params['ids'],params['token'],params.get('cleanup',False))
            elif command=='restore':result=service.restore(params['session_id'],params.get('action_id'))
            elif command=='report':result=service.generate_report(params['session_id'])
            else:raise ValueError('Unsupported command')
            emit(dict(id=request.get('id'),ok=True,data=result))
        except Exception as exc:
            logging.exception('Request failed')
            emit(dict(id=request.get('id'),ok=False,error=str(exc)))
    with ThreadPoolExecutor(max_workers=1) as executor:
        for line in sys.stdin:
            request={}
            try:
                if len(line)>1000000:raise ValueError('Request too large')
                request=json.loads(line)
                if request.get('command')=='scan_control':
                    action=request.get('params',{}).get('action')
                    if action=='pause':service.control.paused.set()
                    elif action=='resume':service.control.paused.clear()
                    elif action=='cancel':service.control.cancelled.set()
                    else:raise ValueError('Invalid scan control')
                    emit(dict(id=request.get('id'),ok=True,data=dict(action=action)))
                else:executor.submit(handle,request)
            except Exception as exc:emit(dict(id=request.get('id'),ok=False,error=str(exc)))
        service.control.cancelled.set()
    service.store.close()


if __name__=='__main__':main()
