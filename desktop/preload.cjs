const {contextBridge, ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('desktop',{
  connection:()=>ipcRenderer.invoke('connection'),
  saveFile:(name,bytes)=>ipcRenderer.invoke('save-file',{name,bytes}),
  onClose:(callback)=>{const listener=()=>callback();ipcRenderer.on('request-close',listener);return ()=>ipcRenderer.removeListener('request-close',listener);},
  confirmClose:()=>ipcRenderer.send('confirm-close'),
  onBackendError:(callback)=>{const listener=(_,message)=>callback(message);ipcRenderer.on('backend-error',listener);return ()=>ipcRenderer.removeListener('backend-error',listener);}
});
