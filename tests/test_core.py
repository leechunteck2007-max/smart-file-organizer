import unittest, tempfile, shutil, json, ctypes, os

from pathlib import Path

from unittest.mock import patch

from app.config.settings import defaults, validate, PROFILES

from app.database.store import Store

from app.safety.policy import SafetyPolicy, RISK_DIRS

from app.scanner.scanner import scan, sha256

from app.classifier.rule_based import RuleBasedClassifier

from app.core.models import MovePlan

from app.actions.move import MoveEngine, exclusive_move

from app.undo.engine import UndoEngine

from app.duplicates.detect import detect

from app.watcher.stability import StabilityTracker

from scripts.generate_synthetic import generate



class CoreTests(unittest.TestCase):

    def setUp(self):

        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)

        # Fixtures live in Windows Temp. Only this test process removes AppData protection

        # so it can exercise actual Windows moves on synthetic files.

        self.patch=patch('app.safety.policy.RISK_DIRS',RISK_DIRS-{'appdata'});self.patch.start()

        self.settings=defaults();self.settings['folders']=[str(self.root/'Downloads')];self.settings['library']=str(self.root/'Library')

        self.policy=SafetyPolicy(self.settings);self.db=Store(self.root/'state'/'history.sqlite');self.mover=MoveEngine(self.db,self.policy)

    def tearDown(self):self.db.close();self.patch.stop();self.tmp.cleanup()

    def file(self,name='report.pdf',content=b'fake report'):

        p=self.root/'Downloads'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content);return p

    def plans(self):

        records,errors=scan(self.settings['folders'],self.policy)

        classifier=RuleBasedClassifier(self.settings,self.policy)

        return [MovePlan(r,c,c.suggested_destination) for r in records for c in [classifier.classify(r)]]

    def test_defaults(self):self.assertFalse(defaults()['auto']);self.assertFalse(defaults()['paused'])

    def test_profiles(self):

        for p in PROFILES:self.assertEqual(validate(dict(profile=p))['profile'],p)

    def test_config_persistence(self):self.db.save(self.settings);self.assertEqual(self.db.load(),self.settings)

    def test_auto_threshold_cannot_be_lowered_unsafely(self):
        with self.assertRaises(ValueError):validate(dict(threshold=80))
    def test_screenshot_executable_not_auto_confident(self):
        self.file('ScreenshotSetup.exe');self.assertLess(self.plans()[0].classification.confidence,95)
    def test_unknown_keyword_not_auto_confident(self):
        self.file('Screenshot.xyz');self.assertEqual(self.plans()[0].classification.category,'Unclassified')
    def test_low_confidence_rule_inbox(self):
        self.settings['rules']=[dict(pattern='*.pdf',category='Work',confidence=65)];self.file();self.assertEqual(self.plans()[0].classification.category,'Inbox')
    def test_invalid_threshold(self):

        with self.assertRaises(ValueError):validate(dict(threshold=101))

    def test_invalid_rule(self):

        with self.assertRaises(ValueError):validate(dict(rules=[dict(pattern='*',category='../Windows',confidence=100)]))

    def test_drive_scan_rejected(self):

        with self.assertRaises(ValueError):validate(dict(folders=['C:\\']))

    def test_scanner_no_hash(self):

        self.file();p=self.plans()[0];self.assertEqual(p.file.hash,'');self.assertEqual(p.file.size,11)

    def test_overlapping_scan(self):

        self.file();records,_=scan([str(self.root),str(self.root/'Downloads')],self.policy)

        self.assertEqual(sum(r.filename=='report.pdf' for r in records),1)

    def test_download_ignored(self):self.file('large.crdownload');self.assertEqual(self.plans(),[])

    def test_project_asset(self):

        self.file('Website/package.json');self.file('Website/assets/logo.png')

        p=next(p for p in self.plans() if p.file.filename=='logo.png');self.assertTrue(p.file.project_member);self.assertEqual(p.destination,'')

        with self.assertRaises(ValueError):self.mover.execute(p.file.current_path,self.root/'Library'/'logo.png','test',99)

    def test_project_above_selected(self):

        self.file('Website/package.json');self.file('Website/assets/logo.png');self.settings['folders']=[str(self.root/'Downloads/Website/assets')]

        self.assertTrue(self.plans()[0].file.project_member)

    def test_project_markers(self):

        for marker in ['Cargo.toml','go.mod','project.sln','sketch.ino','model.prj','src']:

            parent=self.root/marker.replace('.','_');parent.mkdir();(parent/marker).touch()

            self.assertIsNotNone(self.policy.project_root(parent/'logo.png'))

    def test_system_protection(self):

        self.assertTrue(self.policy.veto(Path('C:/Windows/System32/test.png')))

        self.assertTrue(self.policy.veto(self.root/'Windows'/'test.pdf'))

    def test_protected_no_traversal(self):

        self.file('Windows/System32/x.pdf');records,errors=scan(self.settings['folders'],self.policy)

        self.assertEqual(records,[]);self.assertIn('ProtectedSubtreeSkipped',errors)

    def test_user_protection(self):

        p=self.file();self.settings['protected']=[str(p.parent)];self.assertTrue(self.policy.veto(p))

    def test_app_assets(self):

        self.file('App/runtime.dll');p=self.file('App/logo.png');self.assertTrue(self.policy.veto(p))

    def test_portable_app_assets(self):
        self.file('PortableApp/player.exe');p=self.file('PortableApp/Screenshot.png');self.assertTrue(self.policy.veto(p))
    def test_unknown(self):self.file('abc.xyz');self.assertEqual(self.plans()[0].classification.category,'Unclassified')

    def test_profile_context(self):

        self.settings['profile']='Teacher';self.file('Physics Chapter 4.pptx');c=self.plans()[0].classification

        self.assertEqual(c.category,'Teaching');self.assertEqual(c.confidence,94);self.assertIn('physics',c.reason)

    def test_rule_safety_priority(self):

        self.settings['rules']=[dict(pattern='*',category='Photos',confidence=100)];self.file('p/package.json');self.file('p/logo.png')

        self.assertTrue(all(p.classification.confidence==0 for p in self.plans()))

    def test_user_rule(self):

        self.settings['rules']=[dict(pattern='*.pdf',category='Education/Notes',confidence=96)];self.file();self.assertEqual(self.plans()[0].classification.category,'Education')

    def test_safe_move_and_undo(self):

        src=self.file();p=self.plans()[0];self.mover.move(p);dst=Path(self.db.history()[0]['destination']);self.assertFalse(src.exists());self.assertEqual(dst.read_bytes(),b'fake report')

        UndoEngine(self.mover).undo(self.db.history()[0]);self.assertTrue(src.exists());self.assertFalse(dst.exists())

    def test_collision(self):

        src=self.file();p=self.plans()[0];dst=Path(p.destination);dst.parent.mkdir(parents=True);dst.write_bytes(b'original')

        self.mover.move(p);self.assertEqual(dst.read_bytes(),b'original');self.assertTrue(dst.with_name('report (2).pdf').exists())

    def test_atomic_collision(self):

        a=self.file('a.pdf');b=self.file('b.pdf')

        with self.assertRaises(OSError):exclusive_move(a,b)

        self.assertTrue(a.exists());self.assertEqual(b.read_bytes(),b'fake report')

    def test_undo_collision(self):

        src=self.file();self.mover.move(self.plans()[0]);action=self.db.history()[0];src.write_bytes(b'new')

        with self.assertRaises(FileExistsError):UndoEngine(self.mover).undo(action)

        self.assertEqual(src.read_bytes(),b'new')

    def test_undo_modified(self):

        self.file();self.mover.move(self.plans()[0]);a=self.db.history()[0];Path(a['destination']).write_bytes(b'changed')

        with self.assertRaises(ValueError):UndoEngine(self.mover).undo(a)

        self.assertEqual(Path(a['destination']).read_bytes(),b'changed')

    def test_stale_preview(self):

        src=self.file();p=self.plans()[0];src.write_bytes(b'changed size')

        with self.assertRaises(ValueError):self.mover.move(p)

        self.assertTrue(src.exists())

    def test_destination_escape(self):

        src=self.file();p=self.plans()[0];p.destination=str(self.root/'escape.pdf')

        with self.assertRaises(ValueError):self.mover.move(p)

        self.assertTrue(src.exists())

    def test_hardlink(self):

        src=self.file();os.link(src,src.with_name('alias.pdf'))

        with self.assertRaises(ValueError):self.mover.move(self.plans()[0])

    def test_exact_duplicates(self):

        self.file('a.pdf',b'123');self.file('b.pdf',b'123');self.file('c.pdf',b'456')

        groups,errors=detect([p.file for p in self.plans()]);self.assertEqual(len(groups),1);self.assertEqual(groups[0].savings,3);self.assertEqual(len(groups[0].files),2)

    def test_watcher_stability(self):

        self.file();records=[p.file for p in self.plans()];tracker=StabilityTracker(10)

        self.assertEqual(tracker.ready(records,0),[]);self.assertEqual(tracker.ready(records,9),[]);self.assertEqual(len(tracker.ready(records,10)),1);self.assertEqual(tracker.ready(records,20),[])

    def test_watcher_change(self):

        self.file();r=self.plans()[0].file;t=StabilityTracker(10);t.ready([r],0);r.size+=1;t.ready([r],9);self.assertEqual(t.ready([r],10),[]);self.assertEqual(len(t.ready([r],19)),1)

    def test_database_intent_recovery(self):

        self.file();self.mover.move(self.plans()[0]);a=self.db.history()[0]

        self.db.connection.execute("UPDATE actions SET status='PREPARED',undo_available=0 WHERE id=?",(a['id'],));self.db.connection.commit();self.mover.recover();self.assertEqual(self.db.history()[0]['undo_available'],1)

    def test_locked_file(self):

        src=self.file();p=self.plans()[0];kernel=ctypes.WinDLL('kernel32',use_last_error=True)

        create=kernel.CreateFileW;create.restype=ctypes.c_void_p;create.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]

        h=create(str(src),0x40000000,0,None,3,0x80,None)

        self.assertNotEqual(h,ctypes.c_void_p(-1).value)

        try:

            with self.assertRaises(OSError):self.mover.move(p)

            self.assertTrue(src.exists())

        finally:

            close=kernel.CloseHandle;close.argtypes=[ctypes.c_void_p];close(h)

    def test_synthetic_ten_users(self):

        root=self.root/'Synthetic';count=generate(root);self.assertGreaterEqual(count,500)

        self.settings['folders']=[str(root)];plans=self.plans();self.assertGreaterEqual(len(plans),500)

        self.assertTrue(all(p.file.protected for p in plans if p.file.filename=='logo.png'))

        self.assertFalse(any('System32' in p.file.current_path for p in plans))

        groups,_=detect([p.file for p in plans]);self.assertTrue(groups)

    def test_project_created_after_preview(self):

        src=self.file();p=self.plans()[0];self.file('package.json')

        with self.assertRaises(ValueError):self.mover.move(p)

        self.assertTrue(src.exists())

    def test_missing_source_logged(self):

        src=self.file();p=self.plans()[0];src.unlink()

        with self.assertRaises(OSError):self.mover.move(p)

        self.assertEqual(self.db.history()[0]['status'],'FAILED')

    def test_disk_space_refused(self):

        src=self.file();p=self.plans()[0]

        with patch('app.actions.move.shutil.disk_usage',return_value=type('Disk',(),{'free':0})()):

            with self.assertRaises(OSError):self.mover.move(p)

        self.assertTrue(src.exists())

    def test_original_folder_missing_undo(self):

        src=self.file();self.mover.move(self.plans()[0]);action=self.db.history()[0];src.parent.rmdir()

        with self.assertRaises(ValueError):UndoEngine(self.mover).undo(action)

        self.assertTrue(Path(action['destination']).exists())

    def test_controlled_gui_flow(self):

        import tkinter as tk

        from app.ui.desktop import Desktop

        from app.core.service import Service

        state=self.root/'gui-controlled';service=Service(state);service.settings.update(self.settings);service.settings['onboarded']=True;service.save();service.store.close()

        for i in range(5):self.file(f'Screenshot {i}.png',f'synthetic image {i}'.encode())

        root=tk.Tk();ui=Desktop(root,state);ui.scanned(scan(self.settings['folders'],ui.service.policy))

        with patch('app.ui.desktop.messagebox.askyesno',return_value=True),patch('app.ui.desktop.messagebox.showinfo'):

            ui.move_plans(list(ui.service.plans),controlled=True)

            actions=[a for a in ui.service.store.history() if a['undo_available']]

            self.assertEqual(len(actions),5);self.assertFalse(ui.service.settings['controlled_verified'])

            ui.undo_actions(actions);self.assertTrue(ui.service.settings['controlled_verified'])

        self.assertTrue(all((self.root/'Downloads'/f'Screenshot {i}.png').exists() for i in range(5)));ui.close()

    def test_wizard_all_pages(self):

        import tkinter as tk, time

        from app.ui.desktop import Desktop

        from app.core.service import Service

        state=self.root/'wizard';service=Service(state);service.settings.update(self.settings);service.settings['onboarded']=True;service.save();service.store.close();self.file()

        root=tk.Tk();ui=Desktop(root,state);ui.wizard();root.update()

        def find(widget,text):

            for child in widget.winfo_children():

                if isinstance(child, __import__('tkinter').ttk.Button) and child.cget('text')==text:return child

                result=find(child,text)

                if result:return result

        with patch('app.ui.desktop.messagebox.showinfo'):

            for i in range(7):

                end=time.monotonic()+5

                while ui.busy and time.monotonic()<end:root.update();time.sleep(.02)

                button=find(root,'Next');self.assertIsNotNone(button);button.invoke();root.update()

            find(root,'Finish').invoke();root.update()

        self.assertTrue(ui.service.settings['onboarded']);self.assertEqual(len(ui.service.plans),1);ui.close()

    def test_auto_opt_in_gate(self):

        import tkinter as tk

        from app.ui.desktop import Desktop

        from app.core.service import Service

        state=self.root/'auto';service=Service(state);service.settings.update(self.settings);service.settings['onboarded']=True;service.save();service.store.close()

        root=tk.Tk();ui=Desktop(root,state);ui.auto.set(True)

        with patch('app.ui.desktop.messagebox.showerror'):ui.save_settings()

        self.assertFalse(ui.service.settings['auto']);ui.close()

    def test_pause_resume_persist(self):

        import tkinter as tk

        from app.ui.desktop import Desktop

        root=tk.Tk();ui=Desktop(root,self.root/'pause');ui.pause();self.assertTrue(ui.service.store.load()['paused']);ui.pause();self.assertFalse(ui.service.store.load()['paused']);ui.close()

    def test_gui_launch(self):

        import tkinter as tk

        from app.ui.desktop import Desktop

        root=tk.Tk();ui=Desktop(root,self.root/'gui-state');root.update();self.assertEqual(len(ui.pages),7);ui.close()



if __name__=='__main__':unittest.main()
