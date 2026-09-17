"""Generate realistic, safe test documents without executing any downloaded data."""
from pathlib import Path
import sys
import zipfile
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def pdf(path, text):
    encoded=text.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
    stream=f'BT /F1 12 Tf 50 750 Td ({encoded}) Tj ET'.encode('ascii')
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    data=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(data));data+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(data);data+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()
    for offset in offsets[1:]:data+=f'{offset:010} 00000 n \n'.encode()
    data+=f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)


def generate(root):
    root=Path(root)
    for user in range(1,7):
        downloads=root/f'TestUser{user:02}'/'Downloads';downloads.mkdir(parents=True,exist_ok=True)
        for n in range(1,11):pdf(downloads/f'EEE101 lecture({n})final.pdf',f'EEE101 Lecture {n} Circuit analysis')
        pdf(downloads/'invoice-final-new2.pdf','Invoice Date 2026-09-17 Invoice number 1001 Total 120')
        pdf(downloads/'Bank Statement.pdf','Bank Statement Account activity')
        for n in range(12):(downloads/f'IMG_{8300+n}.jpg').write_bytes(f'FAKE IMAGE {user} {n}'.encode())
        (downloads/'Screenshot 2026-09-17.png').write_bytes(b'FAKE SCREENSHOT')
        (downloads/'ChromeSetup.exe').write_bytes(b'FAKE INSTALLER NEVER EXECUTE')
        (downloads/'manual.xyz').write_bytes(b'UNKNOWN')
        (downloads/'large.crdownload').write_bytes(b'DOWNLOADING')
        pdf(downloads/'report.pdf','Unique user report '+str(user))
        (downloads/'report-copy.pdf').write_bytes((downloads/'report.pdf').read_bytes())
        for rel in ['WebsiteProject/package.json','WebsiteProject/assets/logo.png','WebsiteProject/src/app.js','Windows/System32/system.dll']:
            p=downloads/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'SYNTHETIC PROTECTED')
    return sum(p.is_file() for p in root.rglob('*'))


if __name__=='__main__':print(generate(ROOT/'test_data'/'smart'))
