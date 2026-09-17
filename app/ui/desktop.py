import json, os, time, threading, queue
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from app import __version__
from app.core.service import Service
from app.core.models import MovePlan
from app.config.settings import PROFILES, validate
from app.watcher.stability import StabilityTracker
from app.duplicates.detect import detect

class Desktop:
    def __init__(self, root, state):
        self.root = root; self.service = Service(state); self.tracker = StabilityTracker(15)
        self.busy = False; self.results = queue.Queue(); self.closed = False
        root.title('Universal File Librarian • '+__version__); root.geometry('1250x760'); root.minsize(900, 600)
        style = ttk.Style(); style.theme_use('clam')
        style.configure('TButton', padding=7); style.configure('Treeview', rowheight=28)
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        ttk.Label(root, text='Universal File Librarian', style='Title.TLabel').pack(anchor='w', padx=20, pady=(16,4))
        ttk.Label(root, text='Preview first. Projects protected. No automatic deletion.  •  '+__version__).pack(anchor='w', padx=20)
        self.status = tk.StringVar(value='Ready — Auto Organize is OFF by default')
        self.tabs = ttk.Notebook(root); self.tabs.pack(fill='both', expand=True, padx=16, pady=12)
        self.pages = {}
        for name in ['Home','Organize','Review','Duplicates','History','Rules','Settings']:
            frame = ttk.Frame(self.tabs, padding=12); self.tabs.add(frame, text=name); self.pages[name] = frame
        self.build_home(); self.build_plans('Organize'); self.build_plans('Review'); self.build_duplicates()
        self.build_history(); self.build_rules(); self.build_settings()
        ttk.Label(root, textvariable=self.status).pack(anchor='w', padx=20, pady=(0,12))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll_results); root.after(5000, self.watch)
        self.refresh()
        if not self.service.settings['onboarded']: root.after(200, self.wizard)
    def buttons(self, parent, pairs):
        bar = ttk.Frame(parent); bar.pack(fill='x', pady=8)
        for title, command in pairs: ttk.Button(bar,text=title,command=command).pack(side='left',padx=3)
    def table(self, parent, columns):
        box=ttk.Frame(parent); box.pack(fill='both',expand=True)
        tree=ttk.Treeview(box,columns=columns,show='headings',selectmode='extended')
        for col in columns: tree.heading(col,text=col); tree.column(col,width=150,minwidth=90)
        y=ttk.Scrollbar(box,orient='vertical',command=tree.yview); x=ttk.Scrollbar(box,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        tree.grid(row=0,column=0,sticky='nsew'); y.grid(row=0,column=1,sticky='ns'); x.grid(row=1,column=0,sticky='ew')
        box.rowconfigure(0,weight=1); box.columnconfigure(0,weight=1); return tree
    def build_home(self):
        f=self.pages['Home']; self.summary=tk.StringVar()
        ttk.Label(f,textvariable=self.summary,font=('Segoe UI',13),justify='left').pack(anchor='w',pady=18)
        self.buttons(f,[('Organize Now',self.scan),('Review Suggestions',lambda:self.tabs.select(self.pages['Review'])),('Pause / Resume',self.pause),('Controlled Test (5–20 files)',self.controlled)])
        ttk.Label(f,text='The Agent monitors selected folders while this window is open. Closing the app stops it.\nStart with copied test files; approve only destinations you have reviewed.',wraplength=800).pack(anchor='w',pady=15)
    def build_plans(self,name):
        f=self.pages[name]
        self.buttons(f,[('Scan / Preview',self.scan),('Approve Selected',lambda:self.approve(name)),('Approve All Safe',self.approve_all),('Reject',lambda:self.decide(name,'Reject')),('Ignore',lambda:self.decide(name,'Ignore')),('Change Destination',lambda:self.change(name))])
        tree=self.table(f,['File','Current Location','Category','Destination','Confidence','Reason','Status'])
        setattr(self,'tree_'+name,tree)
    def build_duplicates(self):
        f=self.pages['Duplicates']; self.buttons(f,[('Find Exact Duplicates',self.duplicates),('Keep / Review',self.keep_duplicate),('Open Location',self.open_duplicate)])
        self.duptree=self.table(f,['Group','File','SHA-256','Potential Savings'])
    def build_history(self):
        f=self.pages['History']; self.buttons(f,[('Refresh',self.refresh),('Undo Selected',self.undo_selected),('Undo Last',self.undo_last),('Undo Today',self.undo_today)])
        self.histtree=self.table(f,['Time','Action','From','To','Reason','Result','Undo','Error'])
    def build_rules(self):
        f=self.pages['Rules']; ttk.Label(f,text='Filename glob rules (for example *.pdf). Safety and project protection always take priority.').pack(anchor='w')
        self.pattern=tk.StringVar(value='*receipt*'); self.category=tk.StringVar(value='Finance/Receipts'); self.ruleconf=tk.IntVar(value=95)
        line=ttk.Frame(f); line.pack(fill='x',pady=10)
        for title,var in [('Pattern',self.pattern),('Relative category',self.category),('Confidence',self.ruleconf)]:
            ttk.Label(line,text=title).pack(side='left'); ttk.Entry(line,textvariable=var,width=22).pack(side='left',padx=5)
        self.buttons(f,[('Add Rule',self.add_rule),('Remove Selected',self.remove_rule)])
        self.ruletree=self.table(f,['Pattern','Category','Confidence'])
    def build_settings(self):
        f=self.pages['Settings']; s=self.service.settings
        self.profile=tk.StringVar(value=s['profile']); self.library=tk.StringVar(value=s['library'])
        self.auto=tk.BooleanVar(value=s['auto']); self.threshold=tk.IntVar(value=s['threshold']); self.startpaused=tk.BooleanVar(value=s['startup_paused']); self.dupenabled=tk.BooleanVar(value=s['duplicates'])
        line=ttk.Frame(f); line.pack(fill='x')
        ttk.Label(line,text='Profile').pack(side='left'); ttk.Combobox(line,textvariable=self.profile,values=PROFILES,state='readonly').pack(side='left',padx=8)
        ttk.Label(line,text='Auto threshold (95–100)').pack(side='left'); ttk.Spinbox(line,from_=95,to=100,textvariable=self.threshold,width=5).pack(side='left',padx=8)
        ttk.Checkbutton(f,text='Auto Organize high-confidence new files (explicit opt-in)',variable=self.auto).pack(anchor='w',pady=8)
        ttk.Checkbutton(f,text='Start paused on launch (no Windows startup registration)',variable=self.startpaused).pack(anchor='w')
        ttk.Checkbutton(f,text='Enable duplicate detection',variable=self.dupenabled).pack(anchor='w')
        ttk.Label(f,text='File Library').pack(anchor='w',pady=(12,0)); ttk.Entry(f,textvariable=self.library).pack(fill='x')
        self.buttons(f,[('Choose Library',self.choose_library),('Add Monitored Folder',self.add_folder),('Remove Folder',self.remove_folder),('Add Protected Folder',self.protect)])
        self.folders=tk.Listbox(f,height=6); self.folders.pack(fill='x')
        for p in s['folders']: self.folders.insert('end',p)
        self.buttons(f,[('Save Settings',self.save_settings),('Export Settings',self.export_settings),('Import Settings',self.import_settings),('Export Diagnostic Report',self.diagnostic)])
        ttk.Label(f,text='Settings and history are local. Exported settings contain paths; diagnostics exclude paths and contents.').pack(anchor='w')
    def refresh(self):
        s=self.service; today=datetime.now().date()
        actions=s.store.history(); count=sum(a['type']=='MOVE' and a['status']=='SUCCESS' and datetime.fromisoformat(a['timestamp']).astimezone().date()==today for a in actions)
        self.summary.set(f"Agent: {'Paused' if s.settings['paused'] else 'Running'}    Auto Organize: {'ON' if s.settings['auto'] else 'OFF'}\n\nFiles organized today: {count}\nNeeds review: {sum(p.classification.confidence<80 for p in s.plans)}\nUnclassified: {sum(p.classification.category=='Unclassified' for p in s.plans)}\nDuplicate groups: {len(s.groups)}\nLast scan: {s.last_scan or 'Not scanned'}")
        for name in ['Organize','Review']:
            tree=getattr(self,'tree_'+name); tree.delete(*tree.get_children())
            for i,p in enumerate(s.plans):
                if name=='Review' and p.classification.confidence>=80: continue
                c=p.classification
                tree.insert('', 'end',iid=str(i),values=(p.file.filename,p.file.current_path,c.category+'/'+c.subcategory,p.destination,c.confidence,c.reason,p.status))
        self.histtree.delete(*self.histtree.get_children())
        for a in actions: self.histtree.insert('','end',iid=a['id'],values=(a['timestamp'],a['type'],a['source'],a['destination'],a['reason'],a['status'],bool(a['undo_available']),a['error']))
        self.ruletree.delete(*self.ruletree.get_children())
        for i,r in enumerate(s.settings['rules']): self.ruletree.insert('','end',iid=str(i),values=(r['pattern'],r['category'],r['confidence']))
    def background(self, operation, callback):
        if self.busy: return
        self.busy=True; self.status.set('Working…')
        def work():
            try: self.results.put((callback,operation(),None))
            except Exception as exc: self.results.put((callback,None,exc))
        threading.Thread(target=work,daemon=True).start()
    def poll_results(self):
        try:
            callback,value,error=self.results.get_nowait(); self.busy=False
            if error: self.error(error)
            else: callback(value)
        except queue.Empty: pass
        if not self.closed: self.root.after(100,self.poll_results)
    def scan(self):
        # Worker reads metadata only; SQLite remains on the GUI thread.
        from app.scanner.scanner import scan
        self.background(lambda:scan(self.service.settings['folders'],self.service.policy),self.scanned)
    def scanned(self,result):
        records,errors=result; s=self.service; ignored=s.store.ignored()
        s.plans=[MovePlan(r,s.classifier.classify(r),'') for r in records if r.current_path not in ignored]
        for p in s.plans:p.destination=p.classification.suggested_destination
        s.errors=errors; s.last_scan=datetime.now().isoformat(timespec='seconds')
        self.status.set(f'Preview: {len(s.plans)} files; {len(errors)} skipped/errors. No files moved.'); self.refresh()
    def selected(self,name): return [self.service.plans[int(i)] for i in getattr(self,'tree_'+name).selection()]
    def approve(self,name): self.move_plans(self.selected(name))
    def approve_all(self): self.move_plans([p for p in self.service.plans if not p.file.protected and p.classification.confidence>=self.service.settings['review_threshold'] and p.status=='Awaiting approval'])
    def move_plans(self,plans,controlled=False):
        if self.busy: return
        plans=[p for p in plans if not p.file.protected and p.status=='Awaiting approval']
        if not plans:return
        if not self.service.settings['controlled_verified']: controlled=True
        if controlled and not 5<=len(plans)<=20: self.error(ValueError('Select 5–20 safe files'));return
        detail='\n'.join(p.file.filename+' → '+p.destination for p in plans[:20])
        if not messagebox.askyesno('Confirm approved moves',f'Move {len(plans)} files? Review the preview table first.\n\n{detail}\n\nUndo is available if files remain unchanged.'):return
        action_ids=[]
        for p in plans:
            try:
                action_ids.append(self.service.mover.move(p)); p.status='Moved'
            except Exception as exc: p.status='Failed: '+str(exc)
        if controlled and len(action_ids)==len(plans): self.service.record_controlled(action_ids)
        self.refresh();self.status.set('Approved operations finished. Inspect History for results.')
        if controlled: messagebox.showinfo('Controlled test','Moves verified with SHA-256. Open History and Undo these actions, then verify original locations.')
    def controlled(self):
        self.tabs.select(self.pages['Organize']);messagebox.showinfo('Controlled Test','Select 5–20 copied or explicitly chosen personal files in Organize. A confirmation will precede the move.')
        self.buttons(self.pages['Organize'],[('Confirm Controlled Selection',lambda:self.move_plans(self.selected('Organize'),True))])
    def decide(self,name,status):
        for p in self.selected(name): self.service.store.decision(p.file.current_path,status);p.status=status
        self.refresh()
    def change(self,name):
        plans=self.selected(name)
        if not plans:return
        destination=filedialog.askdirectory(title='Choose destination within File Library')
        if destination:
            for p in plans:
                candidate=str(Path(destination)/p.file.filename); veto=self.service.policy.valid_destination(candidate)
                if veto:self.error(ValueError(veto));return
                p.destination=candidate;p.status='Awaiting approval'
            self.refresh()
    def duplicates(self):
        if not self.service.settings['duplicates']:self.error(ValueError('Duplicate detection disabled'));return
        self.background(lambda:detect([p.file for p in self.service.plans if p.status!='Moved']),self.duplicates_done)
    def duplicates_done(self,result):
        self.service.groups,errors=result;self.service.errors+=errors;self.duptree.delete(*self.duptree.get_children())
        for i,g in enumerate(self.service.groups):
            for j,path in enumerate(g.files):self.duptree.insert('','end',iid=f'{i}:{j}',values=(i+1,path,g.hash,g.savings))
        self.status.set(f'{len(self.service.groups)} confirmed groups. No deletion.');self.refresh()
    def keep_duplicate(self):self.status.set('Keep / Review: duplicates retained. No deletion is available in this alpha.')
    def open_duplicate(self):
        selected=self.duptree.selection()
        if selected:
            i,j=map(int,selected[0].split(':'));path=Path(self.service.groups[i].files[j]).parent
            if path.is_dir():os.startfile(str(path))
    def undo_actions(self,actions):
        if not actions or self.busy:return
        if not messagebox.askyesno('Confirm Undo',f'Restore {len(actions)} action(s)? Collisions and modified files will be blocked.'):return
        for action in actions:
            try:self.service.undo.undo(action)
            except Exception as exc:self.error(exc)
        if self.service.verify_controlled_undo(): self.status.set('Controlled move and Undo verified. Broader testing unlocked.')
        self.refresh()
    def undo_selected(self):
        selected=set(self.histtree.selection());self.undo_actions([a for a in self.service.store.history() if a['id'] in selected])
    def undo_last(self):self.undo_actions([a for a in self.service.store.history() if a['undo_available']][:1])
    def undo_today(self):self.undo_actions([a for a in self.service.store.history() if a['undo_available'] and datetime.fromisoformat(a['timestamp']).astimezone().date()==datetime.now().date()])
    def pause(self):self.service.settings['paused']=not self.service.settings['paused'];self.service.save();self.refresh()
    def watch(self):
        if not self.closed and not self.busy and self.service.settings['onboarded'] and not self.service.settings['paused']:
            from app.scanner.scanner import scan
            self.background(lambda:scan(self.service.settings['folders'],self.service.policy),self.watched)
        if not self.closed:self.root.after(5000,self.watch)
    def watched(self,result):
        records,errors=result; s=self.service; s.errors+=errors
        ready=self.tracker.ready(records,time.monotonic());ignored=s.store.ignored()
        known={p.file.current_path:p for p in s.plans}
        for r in ready:
            if r.current_path in ignored:continue
            old=known.get(r.current_path)
            if old and old.status!='Awaiting approval':continue
            c=s.classifier.classify(r);p=MovePlan(r,c,c.suggested_destination)
            if old:s.plans[s.plans.index(old)]=p
            else:s.plans.append(p)
            if s.settings['auto'] and s.settings['controlled_verified'] and c.confidence>=s.settings['threshold'] and not r.protected:
                try:s.mover.move(p);p.status='Moved automatically'
                except Exception as exc:p.status='Review: '+str(exc)
        self.status.set('Monitoring selected folders — '+('paused' if s.settings['paused'] else 'active'));self.refresh()
    def choose_library(self):
        path=filedialog.askdirectory()
        if path:self.library.set(path)
    def add_folder(self):
        path=filedialog.askdirectory()
        if path and path not in self.folders.get(0,'end'):self.folders.insert('end',path)
    def remove_folder(self):
        for i in reversed(self.folders.curselection()):self.folders.delete(i)
    def protect(self):
        path=filedialog.askdirectory(title='Never move files within this folder')
        if path:self.service.settings['protected'].append(path);self.service.save();self.status.set('Protected folder saved')
    def save_settings(self):
        try:
            s=dict(self.service.settings);s.update(profile=self.profile.get(),folders=list(self.folders.get(0,'end')),library=self.library.get(),auto=self.auto.get(),threshold=self.threshold.get(),startup_paused=self.startpaused.get(),duplicates=self.dupenabled.get())
            s=validate(s)
            if s['auto'] and not s['controlled_verified']: raise ValueError('Complete a controlled 5–20 file move and Undo before enabling Auto Organize')
            if s['auto'] and not self.service.settings['auto'] and not messagebox.askyesno('Enable Auto Organize','Allow high-confidence stable files in selected folders to move automatically? Safety still vetoes protected files.'):self.auto.set(False);return
            self.service.settings=s;self.service.save();self.tracker=StabilityTracker(15);self.refresh();self.status.set('Settings saved; rescan to update previews.')
        except Exception as exc:self.error(exc)
    def export_settings(self):self.export_json(self.service.settings,'settings.json')
    def export_json(self,value,name):
        path=filedialog.asksaveasfilename(initialfile=name,defaultextension='.json')
        if path:
            try:Path(path).write_text(json.dumps(value,indent=2),encoding='utf-8')
            except Exception as exc:self.error(exc)
    def import_settings(self):
        path=filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if not path:return
        try:
            data=validate(json.loads(Path(path).read_text(encoding='utf-8')));data['auto']=False;data['controlled_verified']=False;data['controlled_actions']=[]
            self.service.settings=data;self.service.save();messagebox.showinfo('Imported','Settings imported with Auto OFF. Restart the app to refresh settings controls.');self.refresh()
        except Exception as exc:self.error(exc)
    def diagnostic(self):self.export_json(self.service.diagnostic(),'diagnostic.json')
    def add_rule(self):
        try:
            s=dict(self.service.settings);s['rules']=s['rules']+[dict(pattern=self.pattern.get(),category=self.category.get(),confidence=self.ruleconf.get())]
            self.service.settings=validate(s);self.service.save();self.refresh()
        except Exception as exc:self.error(exc)
    def remove_rule(self):
        for i in sorted(map(int,self.ruletree.selection()),reverse=True):self.service.settings['rules'].pop(i)
        self.service.save();self.refresh()
    def wizard(self):
        w=tk.Toplevel(self.root);w.title('Welcome • First Run');w.geometry('650x490');w.transient(self.root);w.grab_set()
        body=ttk.Frame(w,padding=24);body.pack(fill='both',expand=True);step=[0]
        titles=['Welcome','Choose your profile','Choose monitored folders','Choose File Library','Safety','Initial Scan','Preview','Finish']
        school=tk.StringVar();programme=tk.StringVar();year=tk.StringVar();courses=tk.StringVar()
        def show():
            for child in body.winfo_children():child.destroy()
            n=step[0];ttk.Label(body,text=f'{n+1}/8  {titles[n]}',style='Title.TLabel').pack(anchor='w',pady=12)
            if n==0:ttk.Label(body,text='Organize files with explained suggestions and reversible moves.\nStart with a small test folder.').pack(anchor='w')
            elif n==1:
                ttk.Combobox(body,textvariable=self.profile,values=PROFILES,state='readonly').pack(anchor='w')
                for label,var in [('School (optional)',school),('Programme (optional)',programme),('Year (optional)',year),('Courses, comma separated (optional)',courses)]:
                    ttk.Label(body,text=label).pack(anchor='w');ttk.Entry(body,textvariable=var).pack(fill='x')
            elif n==2:
                ttk.Label(body,text='No whole-drive scan. Choose folders explicitly in Settings.').pack(anchor='w')
                self.buttons(body,[('Add Folder',self.add_folder)])
                ttk.Label(body,text='Selected: '+(', '.join(self.folders.get(0,'end')) or 'None yet'),wraplength=550).pack(anchor='w')
                for name in ['Downloads','Desktop','Documents','Pictures']:
                    p=Path.home()/name
                    if p.is_dir():ttk.Button(body,text='Add '+name,command=lambda p=p:self.folders.insert('end',str(p)) if str(p) not in self.folders.get(0,'end') else None).pack(anchor='w')
            elif n==3:
                ttk.Entry(body,textvariable=self.library).pack(fill='x');ttk.Button(body,text='Choose Library',command=self.choose_library).pack(anchor='w')
            elif n==4:ttk.Label(body,text='Files are never permanently deleted automatically.\nDelete operations are disabled.\nProjects, system folders, application dependencies and links are protected.\nAuto Organize starts OFF. Every manual move requires confirmation.\nCross-drive moves are disabled in this alpha.',wraplength=550).pack(anchor='w')
            elif n==5:
                self.service.settings['student']=dict(school=school.get(),programme=programme.get(),year=year.get(),courses=[c.strip() for c in courses.get().split(',') if c.strip()])
                self.save_settings();self.scan();ttk.Label(body,text='Read-only scan started. No files will be moved.\nWait for the status bar to finish before advancing.').pack(anchor='w')
            elif n==6:
                ttk.Label(body,text='Inspect the Organize table after finishing.\nEach file has confidence, a reason and a proposed destination.\nYou can approve, reject, ignore or change the destination.').pack(anchor='w')
                ttk.Button(body,text='Show Preview',command=lambda:self.tabs.select(self.pages['Organize'])).pack(anchor='w')
            elif n==7:ttk.Label(body,text='Ready to review suggestions.\nStart with 5–20 copied files and test Undo in History.').pack(anchor='w')
            def advance():
                if n==5 and self.busy:return
                if n==7:self.service.settings['onboarded']=True;self.service.save();w.destroy();return
                step[0]+=1;show()
            self.buttons(body,[('Back',lambda:(step.__setitem__(0,max(0,n-1)),show())),('Finish' if n==7 else 'Next',advance)])
        show()
    def error(self,exc):self.status.set(str(exc));messagebox.showerror('Action stopped safely',str(exc))
    def close(self):
        self.closed=True;self.service.store.close();self.root.destroy()
