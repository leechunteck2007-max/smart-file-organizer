const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('organizer', {
  snapshot: () => ipcRenderer.invoke('snapshot'),
  selectLibrary: () => ipcRenderer.invoke('select-library'),
  scanControl: action => ipcRenderer.invoke('scan-control',action),
  options: value => ipcRenderer.invoke('options',value),
  excludeFolder: () => ipcRenderer.invoke('exclude-folder'),
  organizeAll: token => ipcRenderer.invoke('organize-all',token),
  openFiles: sessionId => ipcRenderer.invoke('open-files',sessionId),
  scan: () => ipcRenderer.invoke('scan'),
  restore: (sessionId, actionId) => ipcRenderer.invoke('restore', {sessionId,actionId}),
  viewReport: sessionId => ipcRenderer.invoke('view-report', sessionId),
  generateReport: sessionId => ipcRenderer.invoke('report', sessionId),
  onProgress: callback => {const listener=(_event,data)=>callback(data);ipcRenderer.on('progress',listener);return()=>ipcRenderer.removeListener('progress',listener);}
});
