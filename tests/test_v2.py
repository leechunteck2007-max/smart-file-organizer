import json,os,tempfile,threading,time,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from app.safety.policy import RISK_DIRS
from app.smart.v2 import V2Service
from app.smart.discovery import discover
from app.smart.progressive import ScanControl,ScanCancelled
from scripts.generate_smart_synthetic import pdf
class V2Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.home=self.root/'User';self.home.mkdir();self.downloads=self.home/'Downloads';self.downloads.mkdir();self.mock=patch('app.safety.policy.RISK_DIRS',RISK_DIRS-{'appdata'});self.mock.start();self.service=V2Service(self.root/'state');self.service.configure(library=str(self.root/'Library'));self.storage=dict(profile=self.home,known=[('Downloads',self.downloads)],volumes=[])
 def tearDown(self):self.service.store.close();self.mock.stop();self.temp.cleanup()
 def file(self,name,data=b'SYNTHETIC'):
  p=self.downloads/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p
 def scan(self,content=False):return self.service.scan_computer(content,storage=self.storage)
 def test_two_click_organize_one_file_no_gate(self):
  p=self.file('Screenshot 2026-09-17.png',b'IMAGE');r=self.scan();a=self.service.organize_all(r['token']);s=a['sessions'][0];self.assertEqual(s['organized'],1);self.assertTrue(Path(s['report']).is_file());self.assertFalse(p.exists());self.assertFalse(self.service.restore(s['id'])['restore_errors']);self.assertEqual(p.read_bytes(),b'IMAGE');self.assertFalse((self.root/'Library').exists())
 def test_organized_tax_and_trip_retained(self):
  p=self.file('Taxes/2025/tax.pdf');q=self.file('Japan Trip 2025/photo.jpg');r=self.scan();self.assertEqual(r['totals']['already_organized'],2);self.assertTrue(all(not p['destination'] for p in r['plans']));self.service.organize_all(r['token']);self.assertTrue(p.exists());self.assertTrue(q.exists())
 def test_system_application_project_pruned(self):
  self.file('Windows/System32/personal.pdf');self.file('Application/runtime.dll');self.file('Application/photo.jpg');self.file('Website/package.json');self.file('Website/assets/logo.png');r=self.scan();self.assertEqual(r['totals']['projects'],1);self.assertFalse(r['plans']);self.assertGreaterEqual(r['totals']['protected_trees'],3)
 def test_duplicate_quarantine_and_canonical_organized_same_session(self):
  a=self.file('a.txt',b'SAME');b=self.file('a-copy.txt',b'SAME');r=self.scan();self.assertEqual(r['totals']['cleanup_candidates'],1);s=self.service.organize_all(r['token'])['sessions'][0];self.assertEqual(s['organized'],2);self.assertEqual(len(list((self.root/'Library').rglob('*.txt'))),2);self.assertIn('Confirmed Duplicates',s['files'][0]['destination']);self.assertFalse(self.service.restore(s['id'])['restore_errors']);self.assertEqual(a.read_bytes(),b.read_bytes())
 def test_old_family_not_cleanup(self):
  p=self.file('family.jpg',b'FAMILY');os.utime(p,(1,1));self.assertFalse(self.scan()['cleanup'])
 def test_old_setup_quarantined(self):
  p=self.file('ChromeSetup.exe',b'INERT');os.utime(p,(1,1));s=self.service.organize_all(self.scan()['token'])['sessions'][0];self.assertIn('Review Before Delete',s['files'][0]['destination']);self.assertIn('unknown',s['files'][0]['reason'])
 def test_medium_confidence_broad_and_original_name(self):
  self.file('report.docx',b'NOT OFFICE');r=self.scan();p=r['plans'][0];self.assertEqual(p['name'],p['file']);self.assertEqual(p['category'],'Work/Reports')
 def test_rename_off_preserves_extension_name(self):
  self.file('Screenshot 2026-09-17.PNG');self.service.options(automatic_rename=False);p=self.scan()['plans'][0];self.assertEqual(p['file'],p['name'])
 def test_course_cluster_tutorial(self):
  self.file('EEE101 Lecture 01.pdf',b'ONE');self.file('EEE101 Tutorial 02.pdf',b'TWO');r=self.scan();p=next(p for p in r['plans'] if 'Tutorial' in p['file']);self.assertEqual(p['category'],'Education/EEE101/Tutorials');self.assertEqual(p['name'],'EEE101_Tutorial_02.pdf')
 def test_unknown_stays(self):
  p=self.file('secret.xyz');r=self.scan();self.assertFalse(r['plans'][0]['destination']);self.service.organize_all(r['token']);self.assertTrue(p.exists())
 def test_excluded_folder_veto(self):
  p=self.file('Excluded/document.pdf');self.service.options(ignored=[str(p.parent)]);r=self.scan();self.assertFalse(r['plans'])
 def test_cancel_discards_token(self):
  self.file('a.pdf');original=self.service.progress
  def progress(event):
   if event['stage']=='Discovering personal files':self.service.control.cancelled.set()
  self.service.progress=progress;r=self.scan();self.assertTrue(r['cancelled']);self.assertFalse(r['token']);self.assertTrue((self.downloads/'a.pdf').exists())
 def test_pause_resume_cancel(self):
  c=ScanControl();c.paused.set();done=[];thread=threading.Thread(target=lambda:(c.checkpoint(),done.append(True)));thread.start();time.sleep(.15);self.assertFalse(done);c.paused.clear();thread.join(2);self.assertEqual(done,[True]);c.cancelled.set()
  with self.assertRaises(ScanCancelled):c.checkpoint()
 def test_settings_expire_scan(self):
  self.file('a.pdf');r=self.scan();self.service.options(theme='dark')
  with self.assertRaises(ValueError):self.service.organize_all(r['token'])
 def test_source_changed_skipped_and_reported(self):
  p=self.file('a.txt',b'OLD');r=self.scan();p.write_bytes(b'CHANGED');s=self.service.organize_all(r['token'])['sessions'][0];self.assertEqual(s['organized'],0);self.assertEqual(len(s['failures']),1);self.assertEqual(p.read_bytes(),b'CHANGED')
 def test_undo_collision_never_overwrites(self):
  p=self.file('a.txt',b'OLD');s=self.service.organize_all(self.scan()['token'])['sessions'][0];p.write_bytes(b'NEW');r=self.service.restore(s['id']);self.assertTrue(r['restore_errors']);self.assertEqual(p.read_bytes(),b'NEW')
 def test_content_cache(self):
  pdf(self.downloads/'invoice.pdf','Invoice 2026-09-17 Total 100');r=self.scan(True);self.assertEqual(r['plans'][0]['name'],'2026-09_Invoice.pdf')
  with patch('app.smart.v2.inspect_document',side_effect=AssertionError('cache missed')):self.scan(True)
 def test_unknown_profile_directory_not_eligible(self):
  p=self.home/'Mystery';p.mkdir();(p/'state.bin').write_bytes(b'APP');r=self.scan();self.assertTrue(any(a['kind']=='UNKNOWN_RISK' for a in r['storage']));self.assertFalse(r['plans'])
 def test_additional_curated_root_preserved(self):
  folder=self.home/'Japan Trip 2025';folder.mkdir();photo=folder/'IMG_1234.jpg';photo.write_bytes(b'FAMILY');r=self.scan();self.assertEqual(r['totals']['already_organized'],1);self.assertFalse(r['plans'][0]['destination']);self.service.organize_all(r['token']);self.assertTrue(photo.exists())
 def test_external_and_excluded_drive(self):
  drive=self.root/'External';drive.mkdir();(drive/'doc.pdf').write_bytes(b'DOC');settings=dict(self.service.settings,external_drives=False)
  _,roots=discover(self.service.policy,settings,profile=self.home,known=[],volumes=[dict(path=str(drive),external=True,type=2)]);self.assertNotIn(str(drive),roots)
 def test_destination_identical_quarantined_instead_of_suffix(self):
  p=self.file('a.txt',b'SAME');destination=self.root/'Library'/'Documents'/'a.txt';destination.parent.mkdir(parents=True);destination.write_bytes(b'SAME');s=self.service.organize_all(self.scan()['token'])['sessions'][0];self.assertEqual(s['quarantined'],1);self.assertIn('Confirmed Duplicates',s['files'][0]['destination']);self.assertEqual(destination.read_bytes(),b'SAME');self.service.restore(s['id']);self.assertEqual(p.read_bytes(),b'SAME')
 def test_destination_different_collision_preserves_both(self):
  self.file('a.txt',b'SOURCE');destination=self.root/'Library'/'Documents'/'a.txt';destination.parent.mkdir(parents=True);destination.write_bytes(b'EXISTING');s=self.service.organize_all(self.scan()['token'])['sessions'][0];self.assertEqual(s['quarantined'],0);self.assertNotEqual(s['files'][0]['destination'],str(destination));self.assertEqual(destination.read_bytes(),b'EXISTING')
 def test_executable_unknown_protected(self):
  p=self.file('game.exe',b'INERT');r=self.scan();self.assertTrue(r['plans'][0]['protected']);self.assertFalse(r['plans'][0]['destination']);self.service.organize_all(r['token']);self.assertTrue(p.exists())
 def test_data_drive_positive_personal_and_excluded(self):
  drive=self.root/'DataDrive';drive.mkdir();(drive/'document.pdf').write_bytes(b'DOC')
  volume=dict(path=str(drive),external=False,type=3)
  with patch.dict(os.environ,{'SystemDrive':'Z:'}):
   _,roots=discover(self.service.policy,self.service.settings,profile=self.home,known=[],volumes=[volume]);self.assertIn(str(drive),roots)
   self.service.options(excluded_drives=[str(drive)])
   _,roots=discover(self.service.policy,self.service.settings,profile=self.home,known=[],volumes=[volume]);self.assertNotIn(str(drive),roots)
 def test_other_volume_uses_local_library(self):
  self.assertEqual(str(self.service.library_for('D:\\Downloads\\photo.jpg')),'D:\\File Library')
 def test_report_summary_safety_operations_appendix(self):
  self.file('Screenshot 2026-09-17.png',b'IMAGE');s=self.service.organize_all(self.scan()['token'])['sessions'][0]
  with zipfile.ZipFile(s['report']) as z:
   xml=z.read('word/document.xml').decode();self.assertIn('Safety and exclusions',xml);self.assertIn('Eligible personal files',xml);self.assertIn('Action',xml)
  self.assertEqual(len(json.loads(Path(s['report']).with_suffix('.json').read_text())['files']),1)
  kinds={r[0] for r in self.service.store.connection.execute('SELECT type FROM session_operations')};self.assertTrue({'CREATE DIRECTORY','MOVE','RENAME'}<=kinds)
 def test_thousands_synthetic_safe_automatic_and_undo(self):
  # 6000 files across messy, organized, system, application and project trees.
  originals={}
  for n in range(6000):
   if n<1000:name=f'Screenshot 2026-09-17 ({n}).png'
   elif n<3000:name=f'Japan Trip 2025/photo{n}.jpg'
   elif n<4000:name=f'Windows/System32/file{n}.pdf'
   elif n<5000:name=f'Application/file{n}.jpg'
   else:name=f'Developer/assets/file{n}.png'
   p=self.file(name,f'UNIQUE SYNTHETIC {n}'.encode());originals[p]=p.read_bytes()
  self.file('Application/runtime.dll',b'INERT');self.file('Developer/package.json',b'{}')
  r=self.scan();self.assertEqual(r['totals']['ready'],1000);self.assertEqual(r['totals']['already_organized'],2000);self.assertEqual(r['totals']['projects'],1)
  # Report layout is verified separately with small representative sessions.
  with patch.object(self.service,'generate_report',return_value=None):s=self.service.organize_all(r['token'])['sessions'][0]
  self.assertEqual(s['organized'],1000);self.assertEqual(self.service.store.connection.execute("SELECT COUNT(*) FROM actions WHERE status='SUCCESS'").fetchone()[0],1000)
  self.assertFalse(self.service.restore(s['id'])['restore_errors'])
  for p,data in originals.items():self.assertEqual(p.read_bytes(),data)
 def test_ten_computer_simulations(self):
  from scripts.generate_v2_synthetic import generate,NAMES
  target=self.root/'computers';self.assertEqual(sum(generate(target).values()),6000)
  for name in NAMES:
   base=target/name
   r=self.service.scan_computer(False,dict(profile=base/'User',known=[(name,base)],volumes=[]))
   self.assertFalse(any(p['protected'] and p['destination'] for p in r['plans']))
   self.assertFalse(any('Development' in p['source'] or 'System32' in p['source'] or '\\Application\\' in p['source'] for p in r['plans'] if p['destination']))
   if name in {'Already Organized','Family','Photo Heavy'}:self.assertEqual(r['totals']['ready'],0)
if __name__=='__main__':unittest.main()
