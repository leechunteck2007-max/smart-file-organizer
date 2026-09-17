"""Ten synthetic computers, 6000 inert files; never reads personal data."""
from pathlib import Path
import json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.generate_smart_synthetic import pdf
NAMES=['Student','Teacher','Office','Developer','Family','Messy Downloads','Photo Heavy','Multi Drive','Mixed Use','Already Organized']
def generate(target):
 target=Path(target);counts={}
 for name in NAMES:
  base=target/name;d=base/'User'/'Downloads';d.mkdir(parents=True,exist_ok=True)
  for n in range(600):
   if n<60:relative=f'Windows/System32/library{n}.dll'
   elif n<120:relative=f'Application/state{n}.db'
   elif n<180:relative=f'Development/src/asset{n}.png'
   elif name=='Already Organized':relative=f'Documents/Taxes/2025/statement{n}.pdf'
   elif name in {'Family','Photo Heavy'}:relative=f'Pictures/Japan Trip 2025/photo{n}.jpg'
   elif name=='Multi Drive':relative=f'Drive D/Downloads/document{n}.txt'
   elif name=='Student':relative=f'User/Downloads/EEE101 Lecture {n}.pdf'
   elif name=='Teacher':relative=f'User/Downloads/lesson plan {n}.docx'
   elif name=='Office':relative=f'User/Downloads/invoice {n}.pdf'
   elif name=='Messy Downloads':relative=f'User/Downloads/Setup-{n}.msi'
   elif name=='Developer':relative=f'Development/assets/image{n}.jpg'
   else:relative=f'User/Downloads/export{n}.txt'
   p=base/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(f'SYNTHETIC INERT {name} {n}'.encode())
   if name=='Messy Downloads' and n>=180:os.utime(p,(1,1))
  counts[name]=600
 (target/'fixture-manifest.json').write_text(json.dumps(dict(files=6000,computers=counts,inert_only=True),indent=2),encoding='utf-8')
 return counts
if __name__=='__main__':print(json.dumps(generate(ROOT/'test_data/v2')))
