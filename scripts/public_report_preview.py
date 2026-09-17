"""Generate a report preview from actual synthetic actions with fictional identity."""
import copy
import getpass
import os
from pathlib import Path
import platform
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.safety.policy import RISK_DIRS
from app.smart.v2 import V2Service
from app.smart.report import generate
from scripts.generate_smart_synthetic import pdf


def main():
    with tempfile.TemporaryDirectory() as directory, patch('app.safety.policy.RISK_DIRS',RISK_DIRS-{'appdata'}):
        base=Path(directory);downloads=base/'Downloads';downloads.mkdir()
        for i in range(1,4):pdf(downloads/f'EEE101 lecture({i})final.pdf',f'EEE101 Lecture {i} Circuit analysis')
        pdf(downloads/'invoice-final-new2.pdf','Invoice Date 2026-09-17 Invoice number 1001')
        (downloads/'invoice.pdf').write_bytes((downloads/'invoice-final-new2.pdf').read_bytes())
        (downloads/'Screenshot 2026-09-17.png').write_bytes(b'SYNTHETIC IMAGE')
        setup=downloads/'ChromeSetup.exe';setup.write_bytes(b'INERT NEVER EXECUTE');os.utime(setup,(1,1))
        service=V2Service(base/'state');service.configure(library=str(base/'File Library'))
        result=service.scan_computer(storage=dict(profile=base,known=[('Downloads',downloads)],volumes=[]))
        session=service.organize_all(result['token'])['sessions'][0]
        def sanitize(value):
            if isinstance(value,str):return value.replace(str(base),'%USERPROFILE%')
            if isinstance(value,list):return [sanitize(v) for v in value]
            if isinstance(value,dict):return {k:sanitize(v) for k,v in value.items()}
            return value
        fictional=sanitize(copy.deepcopy(session))
        with patch.object(getpass,'getuser',return_value='ExampleTester'),patch.object(platform,'node',return_value='EXAMPLE-PC'):
            report=generate(fictional,ROOT/'build/public-report-preview')
        restored=service.restore(session['id'])
        if restored['restore_errors']:raise RuntimeError('Synthetic preview Undo failed')
        service.store.close()
        print(report)


if __name__=='__main__':main()
