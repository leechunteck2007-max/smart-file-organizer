"""Development-only UI fixture process. Never included in the portable engine."""
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app.safety.policy as safety
from app.smart.v2 import V2Service
from scripts.generate_smart_synthetic import pdf

safety.RISK_DIRS=safety.RISK_DIRS-{'appdata'}
base=Path(os.environ['SMART_UI_FIXTURE'])
downloads=base/'Downloads';downloads.mkdir(parents=True,exist_ok=True)
for n in range(1,4):pdf(downloads/f'EEE101 Lecture({n})final.pdf',f'EEE101 Lecture {n} Circuit Analysis')
pdf(downloads/'invoice-final-new2.pdf','Invoice Date 2026-09-17 Invoice Total 120')
(downloads/'invoice.pdf').write_bytes((downloads/'invoice-final-new2.pdf').read_bytes())
(downloads/'Screenshot 2026-09-17.png').write_bytes(b'SYNTHETIC IMAGE')
setup=downloads/'ChromeSetup.exe';setup.write_bytes(b'FAKE NEVER EXECUTE');os.utime(setup,(1,1))
(downloads/'manual.xyz').write_bytes(b'SYNTHETIC UNKNOWN')
project=downloads/'Website';(project/'assets').mkdir(parents=True,exist_ok=True)
(project/'package.json').write_text('{}',encoding='utf-8');(project/'assets/logo.png').write_bytes(b'PROJECT IMAGE')
service=V2Service(base/'state');service.configure(folders=[str(downloads)],library=str(base/'File Library'));service.store.close()
import app.smart.discovery as discovery
discovery.known_folders=lambda:[('Downloads',downloads)]
discovery.drives=lambda:[]
# Restrict discovery to this synthetic profile, never the actual home.
import app.smart.v2 as v2
original_discover=v2.discover
v2.discover=lambda policy,settings,**kwargs:original_discover(policy,settings,profile=base,known=[('Downloads',downloads)],volumes=[])
from app.smart_engine import main
# Progress fixtures expose fictional relative folders, never host temp paths.
original_scan=v2.V2Service.scan_computer
def fixture_scan(self,*args,**kwargs):
    original_progress=self.progress
    self.progress=lambda value:original_progress(dict(value,file='Downloads' if value.get('file','').startswith(str(base)) else value.get('file','')))
    try:return original_scan(self,*args,**kwargs)
    finally:self.progress=original_progress
v2.V2Service.scan_computer=fixture_scan
main()
