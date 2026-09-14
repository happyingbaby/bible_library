export type User = {id:number;username:string;display_name:string;role:'admin'|'reader';active:boolean;must_change_password:boolean};
export type Ref = {ordinal:number;raw:string;status:string;message:string;book?:string;book_name?:string;chapter?:number;start?:number;end?:number;part?:string};
export type Lecture = {id:number;title:string;author:string;sermon_date:string|null;category:string;tags:string[];published:boolean;deleted:boolean;revision:number;updated_at:string;markdown:string;html:string;references:Ref[];import_report:string[];has_original:boolean;original_extension:string};
export type Translation = {id:number;code:string;name:string;language:string;source:string;revision:number};
export type BibleBook = {code:string;name:string;chapters:number};
declare global {interface Window {desktop?:{saveFile:(name:string,bytes:Uint8Array)=>Promise<boolean>;onClose:(fn:()=>void)=>()=>void;confirmClose:()=>void}}}
const base='https://library.fdeline.com/api';
let token='';
export function setToken(value:string){token=value;}
export async function configure(){}
export async function api<T=any>(path:string,method='GET',data?:unknown):Promise<T>{
  const response=await fetch(base+path,{method,headers:{...(token?{Authorization:`Bearer ${token}`} :{}),...(data instanceof FormData?{}:data!==undefined?{'Content-Type':'application/json'}:{})},body:data instanceof FormData?data:data!==undefined?JSON.stringify(data):undefined});
  if(!response.ok){const body=await response.json().catch(()=>({}));if(response.status===401)window.dispatchEvent(new Event('session-expired'));throw Error(typeof body.detail==='string'?body.detail:body.detail?.map((e:any)=>e.msg).join('；')||`请求失败 (${response.status})`);}
  return response.json();
}
export async function download(path:string,name:string){
  const response=await fetch(base+path,{headers:{Authorization:`Bearer ${token}`}});
  if(!response.ok){const body=await response.json();throw Error(body.detail||'导出失败');}
  const bytes=new Uint8Array(await response.arrayBuffer());
  if(window.desktop)return window.desktop.saveFile(name,bytes);
  const url=URL.createObjectURL(new Blob([bytes]));const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);return true;
}
