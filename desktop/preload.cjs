const {contextBridge, ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('desktop',{
  saveFile:(name,bytes)=>ipcRenderer.invoke('save-file',{name,bytes}),
  onClose:(callback)=>{const listener=()=>callback();ipcRenderer.on('request-close',listener);return ()=>ipcRenderer.removeListener('request-close',listener);},
  confirmClose:()=>ipcRenderer.send('confirm-close')
});
