const {app, BrowserWindow, ipcMain, dialog, shell} = require('electron');
const {spawn} = require('node:child_process');
const {randomBytes} = require('node:crypto');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs');
let backend, window, port, backendError = '', closing = false;
app.setName('圣经讲义');
const key = randomBytes(32).toString('hex');
const root = path.join(__dirname, '..');
if (!app.requestSingleInstanceLock()) app.quit();
app.on('second-instance', () => { if(window) {window.show(); window.focus();} });
function freePort() { return new Promise((resolve,reject) => {const server = net.createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const port=server.address().port;server.close(()=>resolve(port));});}); }
async function launchBackend() {
  port = await freePort();
  const backendName = process.platform === 'win32' ? 'bible-backend.exe' : 'bible-backend';
  const nativeBackendDir = process.platform === 'darwin' ? `backend-${process.arch}` : 'backend';
  const packagedBackendDir = path.join(process.resourcesPath,nativeBackendDir);
  const command = app.isPackaged ? path.join(fs.existsSync(packagedBackendDir) ? packagedBackendDir : path.join(process.resourcesPath,'backend'),backendName) : path.join(root,'backend','.venv','bin','python');
  const args = app.isPackaged ? [] : [path.join(root,'backend','launcher.py')];
  const dataDir = path.join(app.getPath('userData'), 'library');
  fs.mkdirSync(dataDir,{recursive:true,mode:0o700});
  backend = spawn(command,args,{cwd: app.isPackaged ? process.resourcesPath : root,env:{...process.env,BIBLE_APP_KEY:key,BIBLE_PORT:String(port),BIBLE_DATA_DIR:dataDir,PYTHONUNBUFFERED:'1'},stdio:['ignore','pipe','pipe']});
  backend.on('error',()=>{backendError='无法启动 Python 服务。开发环境请先运行 npm run sync:backend；安装版请重新安装应用。';});
  backend.on('exit',()=>{if(!closing) {backendError='本地服务已停止，请重新启动应用。';window?.webContents.send('backend-error',backendError);}});
  // Consume pipes to avoid blocking without persisting credentials or request bodies.
  backend.stdout.on('data',()=>{});
  backend.stderr.on('data',chunk=>{if(!app.isPackaged) process.stderr.write(chunk);});
  for(let i=0;i<150;i++) {
    if(backendError) return;
    try {const r=await fetch(`http://127.0.0.1:${port}/api/status`,{headers:{'X-App-Key':key},signal:AbortSignal.timeout(1000)});if(r.ok)return;}catch{}
    await new Promise(r=>setTimeout(r,300));
  }
  backendError='服务启动超时，请检查 MySQL 连接后重新启动。';
}
function senderAllowed(event) {return window && event.sender === window.webContents;}
ipcMain.handle('connection',event=>{if(!senderAllowed(event))throw Error('Forbidden');return {base:`http://127.0.0.1:${port}/api`,key,error:backendError};});
ipcMain.handle('save-file',async(event,{name,bytes})=>{
  if(!senderAllowed(event)||!ArrayBuffer.isView(bytes))throw Error('Forbidden');
  const result=await dialog.showSaveDialog(window,{defaultPath:path.basename(name)});
  if(result.canceled)return false;
  await fs.promises.writeFile(result.filePath,bytes);
  return true;
});
app.whenReady().then(async()=>{
  await launchBackend();
  window = new BrowserWindow({width:1400,height:930,minWidth:1040,minHeight:720,backgroundColor:'#f7f6f2',title:'圣经讲义',webPreferences:{preload:path.join(__dirname,'preload.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true}});
  window.webContents.setWindowOpenHandler(({url})=>{if(/^https?:\/\//.test(url))shell.openExternal(url);return {action:'deny'};});
  window.webContents.on('will-navigate',(event,url)=>{event.preventDefault();if(/^https?:\/\//.test(url)&&!url.startsWith('http://127.0.0.1'))shell.openExternal(url);});
  if(app.isPackaged)await window.loadFile(path.join(root,'frontend','dist','index.html'));else await window.loadURL('http://127.0.0.1:5174');
  window.on('close',event=>{if(!closing){event.preventDefault();window.webContents.send('request-close');}});
});
ipcMain.on('confirm-close',event=>{if(senderAllowed(event)){closing=true;app.quit();}});
app.on('before-quit',event=>{if(!closing&&window&&!window.isDestroyed()){event.preventDefault();window.webContents.send('request-close');return;}closing=true;backend?.kill('SIGTERM');});
app.on('window-all-closed',()=>app.quit());
