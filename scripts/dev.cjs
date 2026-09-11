const {spawn} = require('node:child_process');
const path=require('node:path');
const root=path.join(__dirname,'..');
const vite=spawn(path.join(root,'node_modules','.bin','vite'),['--config','frontend/vite.config.ts'],{stdio:'inherit',cwd:root});
let electron;
const stop=()=>{electron?.kill();vite.kill();};
process.on('SIGINT',stop);process.on('SIGTERM',stop);
(async()=>{for(let i=0;i<100;i++){try{if((await fetch('http://127.0.0.1:5173')).ok)break;}catch{}await new Promise(r=>setTimeout(r,200));}
electron=spawn(require('electron'),['.'],{cwd:root,stdio:'inherit'});electron.on('exit',()=>{vite.kill();process.exit();});})();
