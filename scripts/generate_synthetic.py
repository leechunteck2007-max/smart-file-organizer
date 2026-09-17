from pathlib import Path

USERS=['Student','Teacher','Office','Developer','Personal','Mixed','Messy','PhotoHeavy','DocumentHeavy','DeveloperMessy']
NAMES=['Circuit Analysis Lecture 03.pdf','Assignment 2.docx','Physics Chapter 4.pptx','September Invoice.pdf','Budget 2026.xlsx','IMG_8291.jpg','Screenshot 2026-09-17.png','ChromeSetup.exe','archive.zip','meeting-notes.docx','report-final-final2.pdf','abc.xyz']

def generate(root):
    root=Path(root)
    for i,profile in enumerate(USERS,1):
        user=root/f'TestUser{i:02}_{profile}'
        for n in range(48):
            p=user/'Downloads'/f'{n:03} {NAMES[n%len(NAMES)]}'
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(f'SYNTHETIC ONLY {i} {n}'.encode())
        for name in ['Website/package.json','Website/src/index.js','Website/assets/logo.png','Windows/System32/system.dll','Downloads/largefile.crdownload']:
            p=user/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'SYNTHETIC PROTECTED')
        for name in ['identical-a.pdf','identical-b.pdf']:(user/'Downloads'/name).write_bytes(b'SYNTHETIC IDENTICAL')
    return sum(p.is_file() for p in root.rglob('*'))

if __name__=='__main__':print(generate(Path(__file__).resolve().parents[1]/'test_data'))
