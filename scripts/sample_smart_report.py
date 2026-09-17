"""Create the report example from actual synthetic organization actions, then undo."""
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch
import os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.safety.policy import RISK_DIRS
from app.smart.v2 import V2Service
from scripts.generate_smart_synthetic import pdf


def main():
    with tempfile.TemporaryDirectory() as directory, patch('app.safety.policy.RISK_DIRS',RISK_DIRS-{'appdata'}):
        base=Path(directory);downloads=base/'Downloads';downloads.mkdir()
        for i in range(1,4):pdf(downloads/f'EEE101 lecture({i})final.pdf',f'EEE101 Lecture {i} Circuit analysis')
        pdf(downloads/'invoice-final-new2.pdf','Invoice Date 2026-09-17 Invoice number 1001')
        shutil.copy2(downloads/'invoice-final-new2.pdf',downloads/'invoice.pdf')
        (downloads/'Screenshot 2026-09-17.png').write_bytes(b'SYNTHETIC IMAGE')
        installer=downloads/'ChromeSetup.exe';installer.write_bytes(b'SYNTHETIC NEVER EXECUTE');os.utime(installer,(1,1))
        service=V2Service(base/'state');service.configure(folders=[str(downloads)],library=str(base/'Library'))
        result=service.scan_computer(storage=dict(profile=base,known=[('Downloads',downloads)],volumes=[]))
        result=service.organize_all(result['token']);session=result['sessions'][0]
        assert not session['report_error']
        target=ROOT/'docs/samples/Organization_Report_V2_Sample.docx';target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(session['report'],target)
        shutil.copy2(Path(session['report']).with_suffix('.json'),target.with_suffix('.json'))
        restored=service.restore(session['id']);assert not restored['restore_errors']
        service.store.close();print(target)


if __name__=='__main__':main()
