export type User = {id:number;username:string;display_name:string;role:'admin'|'reader';active:boolean;must_change_password:boolean};
export type Ref = {ordinal:number;raw:string;status:string;message:string;book?:string;chapter?:number;start?:number;end?:number;part?:string};
export type Lecture = {id:number;title:string;category:string;tags:string[];published:boolean;deleted:boolean;revision:number;updated_at:string;markdown:string;html:string;references:Ref[];import_report:string[];has_original:boolean;original_extension:string};
export type Translation = {id:number;code:string;name:string;language:string;source:string;revision:number};
declare global {interface Window {desktop?:{connection:()=>Promise<{base:string;key:string;error?:string}>;saveFile:(name:string,bytes:Uint8Array)=>Promise<boolean>;onClose:(fn:()=>void)=>()=>void;confirmClose:()=>void;onBackendError:(fn:(message:string)=>void)=>()=>void}}}
let base='http://127.0.0.1:8765/api';
let key='';
let token='';
export function setToken(value:string){token=value;}
export async function configure(){
  if(window.desktop){const c=await window.desktop.connection();base=c.base;key=c.key;if(c.error)throw Error(c.error);}
  else {
    key=(import.meta as any).env.VITE_APP_KEY||'';
    if(!key){
      const response=await fetch('/web-config.json',{cache:'no-store'});
      if(!response.ok)throw Error('网页服务连接失败，请重新启动网页版。');
      const config=await response.json();base='/api';key=config.key;
    }
  }
}
export async function api<T=any>(path:string,method='GET',data?:unknown):Promise<T>{
  const response=await fetch(base+path,{method,headers:{'X-App-Key':key,...(token?{Authorization:`Bearer ${token}`} :{}),...(data instanceof FormData?{}:data!==undefined?{'Content-Type':'application/json'}:{})},body:data instanceof FormData?data:data!==undefined?JSON.stringify(data):undefined});
  if(!response.ok){const body=await response.json().catch(()=>({}));if(response.status===401)window.dispatchEvent(new Event('session-expired'));throw Error(typeof body.detail==='string'?body.detail:body.detail?.map((e:any)=>e.msg).join('；')||`请求失败 (${response.status})`);}
  return response.json();
}
export async function download(path:string,name:string){
  const response=await fetch(base+path,{headers:{'X-App-Key':key,Authorization:`Bearer ${token}`}});
  if(!response.ok){const body=await response.json();throw Error(body.detail||'导出失败');}
  const bytes=new Uint8Array(await response.arrayBuffer());
  if(window.desktop)return window.desktop.saveFile(name,bytes);
  const url=URL.createObjectURL(new Blob([bytes]));const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);return true;
}
