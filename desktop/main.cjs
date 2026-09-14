const {app, BrowserWindow, ipcMain, dialog, shell} = require('electron');
const path = require('node:path');
const fs = require('node:fs');
let window, closing = false;
app.setName('圣经讲义');
const root = path.join(__dirname, '..');
if (!app.requestSingleInstanceLock()) app.quit();
app.on('second-instance', () => { if(window) {window.show(); window.focus();} });
function senderAllowed(event) {return window && event.sender === window.webContents;}
ipcMain.handle('save-file',async(event,{name,bytes})=>{
  if(!senderAllowed(event)||!ArrayBuffer.isView(bytes))throw Error('Forbidden');
  const result=await dialog.showSaveDialog(window,{defaultPath:path.basename(name)});
  if(result.canceled)return false;
  await fs.promises.writeFile(result.filePath,bytes);
  return true;
});
app.whenReady().then(async()=>{
  window = new BrowserWindow({width:1400,height:930,minWidth:1040,minHeight:720,backgroundColor:'#f7f6f2',title:'圣经讲义',webPreferences:{preload:path.join(__dirname,'preload.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true}});
  window.webContents.setWindowOpenHandler(({url})=>{if(/^https?:\/\//.test(url))shell.openExternal(url);return {action:'deny'};});
  window.webContents.on('will-navigate',(event,url)=>{event.preventDefault();if(/^https?:\/\//.test(url)&&!url.startsWith('http://127.0.0.1'))shell.openExternal(url);});
  if(app.isPackaged)await window.loadFile(path.join(root,'frontend','dist','index.html'));else await window.loadURL('http://127.0.0.1:5174');
  window.on('close',event=>{if(!closing){event.preventDefault();window.webContents.send('request-close');}});
});
ipcMain.on('confirm-close',event=>{if(senderAllowed(event)){closing=true;app.quit();}});
app.on('before-quit',event=>{if(!closing&&window&&!window.isDestroyed()){event.preventDefault();window.webContents.send('request-close');return;}closing=true;});
app.on('window-all-closed',()=>app.quit());
