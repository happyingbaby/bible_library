// 本地"记住密码"凭据存储。
// 注意：浏览器 localStorage 为明文存储，这里仅做 base64 基础混淆（非加密），
// 目的是避免密码以明文直接可读；凭据仍可能被本机其他程序读取。
// 仅建议在个人可信设备上使用此功能。
const STORAGE_KEY='bible-login-remember';

interface StoredCredentials{username:string;password:string}

// 处理非 ASCII（如中文密码）：先 URI 编码再 base64
function encode(value:string):string{return btoa(encodeURIComponent(value));}
function decode(value:string):string{return decodeURIComponent(atob(value));}

export function saveCredentials(username:string,password:string):void{
  try{
    localStorage.setItem(STORAGE_KEY,JSON.stringify({u:encode(username),p:encode(password)}));
  }catch{
    // 忽略隐私模式或配额错误
  }
}

export function loadCredentials():StoredCredentials|null{
  try{
    const raw=localStorage.getItem(STORAGE_KEY);
    if(!raw)return null;
    const parsed=JSON.parse(raw) as {u:string;p:string};
    return {username:decode(parsed.u),password:decode(parsed.p)};
  }catch{
    return null;
  }
}

export function clearCredentials():void{
  try{
    localStorage.removeItem(STORAGE_KEY);
  }catch{
    // 忽略
  }
}
