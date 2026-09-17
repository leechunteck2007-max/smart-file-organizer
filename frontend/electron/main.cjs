const { app, BrowserWindow, ipcMain, dialog, shell, session } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
let win, engine, sequence=0, cached, busy=false;
const pending = new Map();
const folderAllowlist = new Set();
const customState = process.argv.find(arg=>arg.startsWith('--state-dir='))?.slice(12);
const state = customState ? path.resolve(customState) : path.join(app.getPath('appData').replace(/Roaming$/i,'Local'),'SmartFileOrganizer');
fs.mkdirSync(state,{recursive:true});
app.setName('SmartFileOrganizer');
app.setPath('userData',path.join(state,'DesktopState'));
const packagedEngine = path.join(process.resourcesPath,'engine','SmartFileEngine.exe');
const root = path.resolve(__dirname,'../..');
const frontendPath = path.join(__dirname,'../dist/index.html');
const selfTest = process.argv.includes('--self-test');
if(!app.requestSingleInstanceLock())app.quit();
app.on('second-instance',()=>{if(win){win.restore();win.focus();}});
app.enableSandbox();
function rpc(command,params={}){
  return new Promise((resolve,reject)=>{
    const id=++sequence;pending.set(id,{resolve,reject});
    engine.stdin.write(JSON.stringify({id,command,params})+'\n',error=>{if(error){pending.delete(id);reject(error);}});
  });
}
function checkSender(event){
  if(event.sender!==win.webContents || !event.senderFrame?.url.startsWith('file:'))throw Error('Untrusted request');
}
function handler(channel,operation){ipcMain.handle(channel,async(event,...args)=>{
  checkSender(event);
  if(busy)throw Error('Please wait for the current step to finish');
  busy=true;
  try{return await operation(...args);}finally{busy=false;}
});}
function ids(value){if(!Array.isArray(value)||value.length>10000||value.some(v=>typeof v!=='string'))throw Error('Invalid selection');return value;}
function decorate(result){
  cached=result;
  const suggested=['downloads','desktop','documents','pictures'].map(name=>({name:name[0].toUpperCase()+name.slice(1),path:app.getPath(name)})).filter(folder=>fs.existsSync(folder.path));
  suggested.forEach(folder=>folderAllowlist.add(folder.path));
  result.settings.folders.forEach(folder=>folderAllowlist.add(folder));
  return {...result,suggested};
}
app.whenReady().then(async()=>{
  engine=fs.existsSync(packagedEngine)?spawn(packagedEngine,['--state-dir',state],{windowsHide:true}):spawn(process.env.SMART_PYTHON||'python',[process.env.SMART_ENGINE_SCRIPT||path.join(root,'smart_engine.py'),'--state-dir',state],{windowsHide:true});
  fs.mkdirSync(state,{recursive:true});
  engine.stderr.on('data',data=>fs.appendFileSync(path.join(state,'engine-stderr.log'),data));
  readline.createInterface({input:engine.stdout}).on('line',line=>{
    try{
      const message=JSON.parse(line);
      if(message.event==='progress'){if(win&&!win.isDestroyed())win.webContents.send('progress',message.data);return;}
      const request=pending.get(message.id);if(!request)return;pending.delete(message.id);
      message.ok?request.resolve(message.data):request.reject(Error(message.error));
    }catch(error){fs.appendFileSync(path.join(state,'engine-stderr.log'),String(error)+'\n');}
  });
  const engineFailed=()=>{pending.forEach(r=>r.reject(Error('The file engine stopped. Close and reopen the app.')));pending.clear();};
  engine.on('error',engineFailed);engine.on('exit',engineFailed);
  win=new BrowserWindow({width:1280,height:860,minWidth:960,minHeight:650,backgroundColor:'#F8F9F6',title:'Smart File Organizer',autoHideMenuBar:true,show:false,webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true}});
  win.on('close',event=>{if(busy){event.preventDefault();dialog.showMessageBox(win,{message:'Please wait for this step to finish before closing.',buttons:['OK']});}});
  win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  win.webContents.on('will-navigate',event=>event.preventDefault());
  win.webContents.session.setPermissionRequestHandler((_webContents,_permission,callback)=>callback(false));
  session.defaultSession.webRequest.onBeforeRequest((details,callback)=>callback({cancel:!details.url.startsWith('file:')&&!details.url.startsWith('data:')&&!details.url.startsWith('devtools:')}));
  handler('snapshot',async()=>decorate(await rpc('snapshot')));
  handler('select-library',async()=>{
    const result=await dialog.showOpenDialog(win,{title:'Choose File Library',properties:['openDirectory','createDirectory']});
    return decorate(await rpc(result.canceled?'snapshot':'configure',result.canceled?{}:{library:result.filePaths[0]}));
  });
  handler('scan',async()=>decorate(await rpc('scan')));
  ipcMain.handle('scan-control',async(event,action)=>{checkSender(event);if(!['pause','resume','cancel'].includes(action))throw Error('Invalid control');return rpc('scan_control',{action});});
  handler('options',async value=>decorate(await rpc('options',value)));
  handler('exclude-folder',async()=>{const result=await dialog.showOpenDialog(win,{title:'Exclude folder',properties:['openDirectory']});return decorate(await rpc(result.canceled?'snapshot':'options',result.canceled?{}:{ignored:[...new Set([...(cached?.settings.ignored||[]),result.filePaths[0]])]}));});
  handler('organize-all',async token=>{if(typeof token!=='string'||token!==cached?.token)throw Error('Scan changed; scan again');return decorate(await rpc('organize_all',{token}));});
  handler('open-files',async id=>{const snapshot=await rpc('snapshot');const session=snapshot.sessions.find(s=>s.id===id);if(!session)throw Error('Session unavailable');const file=session.files.find(f=>fs.existsSync(path.dirname(f.destination)));let target=file?path.dirname(file.destination):snapshot.settings.library;if(file){for(const part of file.category.split('/').filter(Boolean))target=path.dirname(target);}if(!fs.existsSync(target)||!fs.statSync(target).isDirectory())throw Error('Library unavailable');const error=await shell.openPath(target);if(error)throw Error(error);return true;});
  handler('restore',async request=>{
    if(typeof request.sessionId!=='string')throw Error('Invalid session');
    return decorate(await rpc('restore',{session_id:request.sessionId,action_id:request.actionId||null}));
  });
  handler('report',async id=>decorate(await rpc('report',{session_id:id})));
  handler('view-report',async id=>{
    const snapshot=await rpc('snapshot');const report=snapshot.sessions.find(s=>s.id===id)?.report;
    if(!report||path.extname(report).toLowerCase()!=='.docx'||path.dirname(path.resolve(report))!==path.resolve(state,'Reports')||!fs.existsSync(report))throw Error('Report unavailable');
    const error=await shell.openPath(report);if(error)throw Error(error);return true;
  });
  if(selfTest){
    win.webContents.on('console-message',(_event,_level,message)=>fs.appendFileSync(path.join(state,'renderer.log'),message+'\n'));
  }
  await win.loadFile(frontendPath);win.show();
  if(selfTest){
    await new Promise(resolve=>setTimeout(resolve,900));
    const test=await win.webContents.executeJavaScript(`({title:document.title,text:document.body.innerText,bridge:typeof window.organizer?.scan,errors:window.__renderErrors||[]})`);
    const image=await win.webContents.capturePage();fs.writeFileSync(path.join(state,'home.png'),image.toPNG());
    fs.writeFileSync(path.join(state,'desktop-test.json'),JSON.stringify(test,null,2));
    app.exit(test.bridge==='function'&&test.text.replace(/\s+/g,' ').includes('Your computer, organized.')&&test.errors.length===0?0:1);
  }
}).catch(error=>{fs.mkdirSync(state,{recursive:true});fs.writeFileSync(path.join(state,'startup-error.log'),error.stack||String(error));dialog.showErrorBox('Smart File Organizer could not start',String(error));app.exit(1);});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',event=>{
  if(busy){event.preventDefault();dialog.showMessageBox(win,{message:'Please wait for this step to finish before closing.',buttons:['OK']});return;}
  if(engine)engine.stdin.end();
});
