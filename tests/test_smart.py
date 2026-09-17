import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from app.safety.policy import RISK_DIRS
from app.scanner.scanner import scan
from app.smart.inspect import extract_local, inspect_document
from app.smart.service import SmartService
from app.smart.understand import FileUnderstanding, safe_name
from scripts.generate_smart_synthetic import pdf, generate


class SmartTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.mock=patch('app.safety.policy.RISK_DIRS',RISK_DIRS-{'appdata'});self.mock.start()
        self.service=SmartService(self.root/'state')
        self.downloads=self.root/'Downloads';self.downloads.mkdir()
        self.service.configure(folders=[str(self.downloads)],library=str(self.root/'Library'))
    def tearDown(self):self.service.store.close();self.mock.stop();self.temp.cleanup()
    def file(self,name,data=b'SYNTHETIC'):
        p=self.downloads/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p
    def batch(self):
        for i in range(5):self.file(f'Screenshot 2026-09-17 ({i}).png',f'IMAGE {i}'.encode())
        return self.service.scan(content=False)
    def test_no_profiles_or_questionnaire(self):
        self.assertNotIn('profile',self.service.settings);self.assertEqual(self.service.settings['folders'],[str(self.downloads)])
    def test_content_timeout_returns_review_code(self):
        import subprocess
        p=self.file('slow.pdf',b'PDF')
        with patch('app.smart.inspect.subprocess.run',side_effect=subprocess.TimeoutExpired('parser',5)):
            text,error=inspect_document(str(p))
        self.assertFalse(text);self.assertEqual(error,'ContentInspectionTimeout')
    def test_extension_case_preserved(self):
        self.file('Screenshot 2026-09-17.PNG');p=self.service.scan(content=False)['plans'][0];self.assertTrue(p['name'].endswith('.PNG'))
    def test_session_recovery_after_move_before_payload_commit(self):
        r=self.batch();result=self.service.organize([p['id'] for p in r['plans']],r['token']);session=result['sessions'][0]
        db=self.service.store.connection;payload=json.loads(db.execute('SELECT payload FROM sessions WHERE id=?',(session['id'],)).fetchone()[0])
        payload['files']=[];payload['organized']=0;db.execute('UPDATE sessions SET payload=? WHERE id=?',(json.dumps(payload),session['id']));db.commit()
        self.service.recover_sessions();s=self.service.sessions()[0];self.assertEqual(s['organized'],5);self.assertEqual(len(s['files']),5);self.assertTrue(s['report_error'])
    def test_pdf_content_extraction(self):
        p=self.downloads/'random.pdf';pdf(p,'Invoice Date 2026-09-17 Invoice Total 100')
        text,error=inspect_document(str(p));self.assertFalse(error);self.assertIn('Invoice',text)
        result=self.service.scan();self.assertEqual(result['plans'][0]['category'],'Finance/Invoices');self.assertEqual(result['plans'][0]['name'],'random.pdf')
    def test_course_structure_and_rename(self):
        pdf(self.downloads/'EEE101 Lecture(3)final.pdf','EEE101 Lecture 3')
        self.file('EEE101 Assignment.docx',b'invalid document')
        result=self.service.scan();p=next(p for p in result['plans'] if 'Lecture' in p['file'])
        self.assertEqual(p['category'],'Education/EEE101/Lectures');self.assertEqual(p['name'],'EEE101_Lecture_03.pdf');self.assertGreaterEqual(p['confidence'],95)
    def test_invoice_content_agreement_rename(self):
        pdf(self.downloads/'invoice-final-new2.pdf','Invoice Date 2026-09-17 Invoice Total 120')
        p=self.service.scan()['plans'][0];self.assertEqual(p['name'],'2026-09_Invoice.pdf')
    def test_low_confidence_keeps_filename(self):
        self.file('lecture(3)final.pdf',b'invalid pdf');p=self.service.scan()['plans'][0];self.assertEqual(p['name'],p['file']);self.assertLess(p['confidence'],95)
    def test_img_is_not_assumed_screenshot(self):
        self.file('IMG_28392.png');p=self.service.scan(content=False)['plans'][0];self.assertEqual(p['category'],'Photos');self.assertEqual(p['name'],p['file'])
    def test_folder_context(self):
        self.file('Invoices/scanned.pdf',b'invalid PDF');p=self.service.scan()['plans'][0];self.assertEqual(p['category'],'Finance/Invoices')
    def test_unknown_not_actionable(self):
        self.file('abc.xyz');p=self.service.scan(content=False)['plans'][0];self.assertFalse(p['destination'])
    def test_projects_never_rename(self):
        self.file('Website/package.json');self.file('Website/assets/Screenshot.png');result=self.service.scan(content=False)
        self.assertTrue(all(p['protected'] and p['name']==p['file'] and not p['destination'] for p in result['plans']))
    def test_node_modules_protects_entire_project(self):
        self.file('Website/node_modules/marker.txt');self.file('Website/logo.png');result=self.service.scan(content=False)
        logo=next(p for p in result['plans'] if p['file']=='logo.png');self.assertTrue(logo['protected']);self.assertFalse(logo['destination'])
    def test_protected_folder_selection(self):
        p=self.root/'Windows';p.mkdir()
        with self.assertRaises(ValueError):self.service.configure(folders=[str(p)])
    def test_drive_scan_refused(self):
        with self.assertRaises(ValueError):self.service.configure(folders=['C:\\'])
    def test_cleanup_exact_hashes(self):
        self.file('a.pdf',b'abc');self.file('b.pdf',b'abc');self.file('c.pdf',b'xyz')
        result=self.service.scan(content=False);self.assertEqual(len(result['cleanup']),1);self.assertEqual(result['cleanup'][0]['category'],'Duplicates')
    def test_old_personal_file_not_cleanup(self):
        p=self.file('family-photo.jpg',b'FAMILY PHOTO');os.utime(p,(1,1));q=self.file('Important.pdf',b'PERSONAL DOCUMENT');os.utime(q,(1,1))
        self.assertEqual(self.service.scan(content=False)['cleanup'],[])
    def test_old_installer_review_not_delete(self):
        p=self.file('ChromeSetup.exe');os.utime(p,(1,1));result=self.service.scan(content=False)
        self.assertEqual(result['cleanup'][0]['category'],'Installers');self.assertTrue(p.exists());self.assertIn('unknown',result['cleanup'][0]['reason'])
    def test_canonical_not_cleanup_package(self):
        a=self.file('Setup.exe',b'abc');b=self.file('Setup-copy.exe',b'abc');os.utime(a,(1,1));os.utime(b,(1,1))
        result=self.service.scan(content=False);self.assertEqual(len(result['cleanup']),1);self.assertEqual(result['cleanup'][0]['category'],'Duplicates')
    def test_controlled_session_word_report_and_undo(self):
        result=self.batch();before={p: p.read_bytes() for p in self.downloads.iterdir()}
        after=self.service.organize([p['id'] for p in result['plans']],result['token']);s=after['sessions'][0]
        self.assertEqual(s['organized'],5);self.assertEqual(s['renamed'],5);self.assertTrue(Path(s['report']).is_file())
        with zipfile.ZipFile(s['report']) as archive:
            xml=archive.read('word/document.xml').decode();self.assertIn('Original File',xml);self.assertIn('Cleanup suggestions',xml);self.assertIn('No files were permanently deleted',xml)
        restored=self.service.restore(s['id']);self.assertTrue(restored['settings']['controlled_verified'])
        for path,data in before.items():self.assertEqual(path.read_bytes(),data)
    def test_no_broader_moves_before_controlled_undo(self):
        r=self.batch();self.service.organize([p['id'] for p in r['plans']],r['token'])
        self.file('new.png');r=self.service.scan(content=False)
        with self.assertRaises(ValueError):self.service.organize([r['plans'][0]['id']],r['token'])
    def test_preview_token_expired(self):
        r=self.batch();self.service.scan(content=False)
        with self.assertRaises(ValueError):self.service.organize([p['id'] for p in r['plans']],r['token'])
    def test_destination_requires_rescan_after_library_change(self):
        r=self.batch();self.service.configure(library=str(self.root/'Another Library'))
        with self.assertRaises(ValueError):self.service.organize([p['id'] for p in r['plans']],r['token'])
    def test_duplicate_cleanup_and_undo(self):
        self.service.settings['controlled_verified']=True
        canonical=self.file('report.pdf',b'exact');extra=self.file('report-copy.pdf',b'exact');r=self.service.scan(content=False)
        after=self.service.organize([r['cleanup'][0]['id']],r['token'],cleanup=True)
        self.assertTrue(canonical.exists());self.assertFalse(extra.exists());a=after['sessions'][0]['actions'][0]
        self.assertIn('Review Before Delete',a['destination']);self.assertEqual(Path(a['destination']).read_bytes(),b'exact')
        self.service.restore(after['sessions'][0]['id']);self.assertEqual(extra.read_bytes(),b'exact')
    def test_duplicate_canonical_changed_blocks_cleanup(self):
        self.service.settings['controlled_verified']=True
        canonical=self.file('a.pdf',b'123');self.file('b.pdf',b'123');r=self.service.scan(content=False);canonical.write_bytes(b'new')
        with self.assertRaises(ValueError):self.service.organize([r['cleanup'][0]['id']],r['token'],cleanup=True)
    def test_undo_modified_file_blocked(self):
        r=self.batch();s=self.service.organize([p['id'] for p in r['plans']],r['token'])['sessions'][0]
        Path(s['actions'][0]['destination']).write_bytes(b'edited');result=self.service.restore(s['id'])
        self.assertTrue(result['restore_errors']);self.assertFalse(result['settings']['controlled_verified'])
    def test_report_failure_is_visible_and_retryable(self):
        r=self.batch()
        with patch('app.smart.report.generate',side_effect=OSError('report denied')):after=self.service.organize([p['id'] for p in r['plans']],r['token'])
        s=after['sessions'][0];self.assertEqual(s['organized'],5);self.assertIn('report denied',s['report_error'])
        s=self.service.generate_report(s['id'])['sessions'][0];self.assertTrue(s['report']);self.assertFalse(s['report_error'])
    def test_docx_pptx_xlsx_inspection(self):
        samples={'.docx':('word/document.xml','<root><t>Lecture EEE101</t></root>'),'.pptx':('ppt/slides/slide1.xml','<root><t>Research paper</t></root>'),'.xlsx':('xl/sharedStrings.xml','<root><t>Invoice</t></root>')}
        for extension,(member,xml) in samples.items():
            p=self.downloads/('sample'+extension)
            with zipfile.ZipFile(p,'w') as archive:archive.writestr(member,xml)
            self.assertTrue(extract_local(str(p)))
    def test_zip_bomb_inspection_refused(self):
        p=self.downloads/'oversize.docx'
        with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr('word/document.xml','x'*3000000)
        with self.assertRaises(ValueError):extract_local(str(p))
    def test_xml_entities_refused(self):
        p=self.downloads/'entity.docx'
        with zipfile.ZipFile(p,'w') as archive:archive.writestr('word/document.xml','<!DOCTYPE a [<!ENTITY b "xx">]><a>&b;</a>')
        with self.assertRaises(ValueError):extract_local(str(p))
    def test_filename_sanitization(self):self.assertEqual(safe_name('CON'),'File');self.assertNotIn(':',safe_name('Invoice:../../bad'))
    def test_progress_is_actual_file_count(self):
        progress=[];self.service.progress=progress.append;self.batch()
        analyzed=[p for p in progress if p['stage']=='Understanding your files'];self.assertEqual(len(analyzed),5);self.assertEqual(analyzed[-1]['current'],5)
    def test_sessions_persist_on_reopen(self):
        r=self.batch();self.service.organize([p['id'] for p in r['plans']],r['token']);self.service.store.close();self.service=SmartService(self.root/'state')
        self.assertEqual(len(self.service.sessions()),1);self.assertTrue(self.service.sessions()[0]['report'])
    def test_smart_synthetic_corpus(self):
        root=self.root/'Messy';count=generate(root);self.assertGreater(count,180)
        self.service.configure(folders=[str(root)])
        r=self.service.scan(content=False);self.assertTrue(any(p['name']=='EEE101_Lecture_03.pdf' for p in r['plans']));self.assertTrue(r['cleanup'])


if __name__=='__main__':unittest.main()
