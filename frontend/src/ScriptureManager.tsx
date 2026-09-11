import React, {useEffect, useState} from 'react';
import {api, Translation} from './api';

type Book = {code:string;name:string;chapters:number};
type Testament = {code:string;name:string;books:Book[]};
type Chapter = {number:number;stored_count:number;reference_verse_count:number|null};
type Content = {revision:number;verses:{verse:number;text:string}[]};
type Props = {translations:Translation[];onRefresh:()=>Promise<void>;onDirty:(dirty:boolean)=>void;onBusy:(busy:boolean)=>void};

export default function ScriptureManager({translations,onRefresh,onDirty,onBusy}:Props){
  const [catalog,setCatalog]=useState<Testament[]>([]),[testament,setTestament]=useState('OT'),[book,setBook]=useState('Gen'),[chapter,setChapter]=useState(1);
  const [translation,setTranslation]=useState(String(translations[0]?.id||'')),[chapters,setChapters]=useState<Chapter[]>([]),[content,setContent]=useState<Content|null>(null);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
  const [edit,setEdit]=useState<{verse:number;text:string;original:string;revision:number}|null>(null);
  const [creating,setCreating]=useState(false),[metadata,setMetadata]=useState({code:'',name:'',language:'zh',source:''});
  const dirty=!!edit&&edit.text!==edit.original || creating&&!!(metadata.code||metadata.name||metadata.source);
  useEffect(()=>{onDirty(dirty);return()=>onDirty(false);},[dirty,onDirty]);
  useEffect(()=>{onBusy(busy);return()=>onBusy(false);},[busy,onBusy]);
  useEffect(()=>{let active=true;api<Testament[]>('/bible/catalog').then(data=>{if(active)setCatalog(data);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[]);
  useEffect(()=>{
    let active=true;setLoading(true);setError('');setContent(null);setChapters([]);
    Promise.all([api<Chapter[]>(`/bible/books/${book}/chapters${translation?'?translation_id='+translation:''}`),translation?api<Content>(`/bible/translations/${translation}/${book}/${chapter}`):Promise.resolve(null)])
      .then(([cs,body])=>{if(active){setChapters(cs);setContent(body);}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[book,chapter,translation,refresh]);
  const guard=()=>!dirty||window.confirm('经文管理有未保存的内容，确定放弃吗？');
  const navigate=(fn:()=>void)=>{if(busy||!guard())return;setEdit(null);setCreating(false);setMetadata({code:'',name:'',language:'zh',source:''});setNotice('');fn();};
  const run=async(fn:()=>Promise<void>)=>{setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const selected=catalog.find(t=>t.code===testament),current=selected?.books.find(b=>b.code===book),chapterInfo=chapters.find(c=>c.number===chapter);
  const selectedTranslation=translations.find(t=>String(t.id)===translation);
  const numbers=Array.from({length:Math.max(chapterInfo?.reference_verse_count||0,...(content?.verses.map(v=>v.verse)||[]))},(_,i)=>i+1);
  const save=()=>run(async()=>{
    if(!edit)return;
    await api(`/bible/translations/${translation}/${book}/${chapter}/${edit.verse}`,'PUT',{text:edit.text,revision:edit.revision});
    setEdit(null);setRefresh(n=>n+1);setNotice('经文已保存');await onRefresh();
  });
  return <div className="bible-manager">
    <p className="muted">旧约 39 卷 · 新约 27 卷。按书卷、章、节维护各译本正文。</p>
    {error&&<p className="callout" role="alert">{error}</p>}{notice&&<p className="callout neutral" role="status">{notice}</p>}
    <div className="bible-toolbar"><label className="field"><span>当前译本</span><select aria-label="当前译本" disabled={busy} value={translation} onChange={e=>navigate(()=>setTranslation(e.target.value))}><option value="">请选择译本</option>{translations.map(t=><option key={t.id} value={t.id}>{t.name} · {t.language}</option>)}</select></label><button disabled={busy} onClick={()=>navigate(()=>setCreating(true))}>新建译本</button></div>
    {selectedTranslation&&<p className="small muted">{selectedTranslation.code} · 版本 {selectedTranslation.revision} · {selectedTranslation.source||'尚未填写来源'}</p>}
    {creating&&<form className="inset" onSubmit={e=>{e.preventDefault();run(async()=>{const result=await api<{id:number}>('/translations','POST',metadata);setCreating(false);setMetadata({code:'',name:'',language:'zh',source:''});await onRefresh();setTranslation(String(result.id));setNotice('译本已创建，可以开始录入经文');});}}>
      <h3>新建译本</h3><div className="row"><label className="field"><span>代码（英文、数字、下划线、短横线）</span><input required pattern="[A-Za-z0-9_-]{1,80}" maxLength={80} value={metadata.code} onChange={e=>setMetadata({...metadata,code:e.target.value})}/></label><label className="field"><span>译本名称</span><input required maxLength={150} value={metadata.name} onChange={e=>setMetadata({...metadata,name:e.target.value})}/></label></div>
      <div className="row"><label className="field"><span>语言（如 zh / en）</span><input required maxLength={30} value={metadata.language} onChange={e=>setMetadata({...metadata,language:e.target.value})}/></label><label className="field"><span>内容来源</span><input maxLength={2000} value={metadata.source} onChange={e=>setMetadata({...metadata,source:e.target.value})}/></label></div><button className="primary" disabled={busy||!metadata.name.trim()||!metadata.language.trim()}>创建译本</button><button type="button" disabled={busy} onClick={()=>navigate(()=>setCreating(false))}>取消</button>
    </form>}
    <div className="bible-testaments">{catalog.map(t=><button key={t.code} className={testament===t.code?'primary':''} disabled={busy} onClick={()=>navigate(()=>{setTestament(t.code);setBook(t.books[0].code);setChapter(1);})}>{t.name} · {t.books.length} 卷</button>)}</div>
    <div className="bible-layout"><nav className="bible-books" aria-label="书卷目录">{selected?.books.map(b=><button key={b.code} aria-current={book===b.code?'true':undefined} className={book===b.code?'primary':''} disabled={busy} onClick={()=>navigate(()=>{setBook(b.code);setChapter(1);})}><span>{b.name}</span><small>{b.chapters} 章</small></button>)}</nav>
    <section className="bible-content"><h3>{current?.name||book} <span className="muted">/ {current?.chapters||'—'} 章</span></h3>
      <div className="bible-chapters" aria-label="章节目录">{chapters.map(c=><button key={c.number} disabled={busy} title={`第 ${c.number} 章，已录入 ${c.stored_count} 节`} aria-label={`第 ${c.number} 章`} className={chapter===c.number?'primary':''} onClick={()=>navigate(()=>setChapter(c.number))}>{c.number}{c.stored_count>0&&<span className="chapter-dot"/>}</button>)}</div>
      <div className="bible-section-heading"><h3>第 {chapter} 章</h3><button disabled={busy||loading||!content} onClick={()=>navigate(()=>{if(content)setEdit({verse:(content.verses.at(-1)?.verse||0)+1,text:'',original:'',revision:content.revision});})}>新增经节</button></div>
      {loading?<p className="muted">正在读取章节…</p>:<><p className="muted">已录入 {content?.verses.length||0} 节{chapterInfo?.reference_verse_count!=null?` · 参考目录 ${chapterInfo.reference_verse_count} 节`:' · 参考节数尚未收录'}</p>{!translation&&<p className="callout neutral">请选择或新建译本，再维护经文正文。</p>}{chapterInfo?.reference_verse_count!=null&&<p className="small muted">参考节数来自所提供的网站信息，仅供核对；各译本分节可能不同。</p>}</>}
      {edit&&<form className="inset bible-edit" onSubmit={e=>{e.preventDefault();save();}}><h3>编辑经文</h3><label className="field"><span>节号</span><input type="number" required min={1} max={176} value={edit.verse} disabled={busy||!!edit.original} onChange={e=>{const verse=Number(e.target.value);if(content?.verses.some(v=>v.verse===verse)){setError('该节已有正文，请在下方选择编辑');return;}setEdit({...edit,verse});}}/></label><label className="field"><span>正文</span><textarea autoFocus required maxLength={10000} rows={5} value={edit.text} disabled={busy} onChange={e=>setEdit({...edit,text:e.target.value})}/></label><div className="bible-edit-actions"><button className="primary" disabled={busy||!edit.text.trim()}>保存经文</button><button type="button" disabled={busy} onClick={()=>navigate(()=>setEdit(null))}>取消</button><button type="button" disabled={busy} onClick={()=>setRefresh(n=>n+1)}>刷新章节</button></div><p className="small muted">若发生版本冲突，刷新后取消编辑，再重新打开该节核对修改。</p></form>}
      {!loading&&translation&&content&&<div className="bible-verses">{numbers.map(n=>{const row=content.verses.find(v=>v.verse===n);return <article key={n}><span className="verse-number">{n}</span><p className={row?'':'muted'}>{row?.text||'尚未录入'}</p><div><button disabled={busy} onClick={()=>navigate(()=>setEdit({verse:n,text:row?.text||'',original:row?.text||'',revision:content.revision}))}>{row?'编辑':'录入'}</button>{row&&<button className="danger" disabled={busy} onClick={()=>{if(!guard()||!window.confirm(`确定删除${current?.name} ${chapter}:${n} 的正文吗？`))return;run(async()=>{await api(`/bible/translations/${translation}/${book}/${chapter}/${n}?revision=${content.revision}`,'DELETE');setEdit(null);setRefresh(v=>v+1);setNotice('经文已删除');await onRefresh();});}}>删除</button>}</div></article>;})}{!numbers.length&&<p className="callout neutral">本章尚无经文。可新增经节，后续也可由采集程序写入。</p>}</div>}
    </section></div>
  </div>;
}
