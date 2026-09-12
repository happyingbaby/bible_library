import React, {useEffect, useRef, useState} from 'react';
import {api, Translation} from './api';
import Choice from './Choice';

type Book = {code:string;name:string;chapters:number};
type Testament = {code:string;name:string;books:Book[]};
type Chapter = {number:number;stored_count:number;reference_verse_count:number|null};
type Content = {revision:number;verses:{verse:number;text:string}[]};
type Props = {translations:Translation[];onRefresh:()=>Promise<void>;onDirty:(dirty:boolean)=>void;onBusy:(busy:boolean)=>void};

export default function ScriptureManager({translations,onRefresh,onDirty,onBusy}:Props){
  const [catalog,setCatalog]=useState<Testament[]>([]),[testament,setTestament]=useState('OT'),[book,setBook]=useState('Gen'),[chapter,setChapter]=useState(1);
  const [translation,setTranslation]=useState(String(translations[0]?.id||'')),[chapters,setChapters]=useState<Chapter[]>([]),[content,setContent]=useState<Content|null>(null);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
  const [edit,setEdit]=useState<{verse:number;text:string;original:string;existing:boolean;revision:number|null}|null>(null);
  const [creating,setCreating]=useState(false),[metadata,setMetadata]=useState({code:'',name:'',language:'zh',source:''});
  const [range,setRange]=useState<{start:number;end:number}|null>({start:1,end:1}),[anchor,setAnchor]=useState<number|null>(null);
  const previousRange=useRef({start:1,end:1});
  const createRef=useRef<HTMLFormElement>(null),editRef=useRef<HTMLFormElement>(null);
  useEffect(()=>{setRange({start:1,end:1});setAnchor(null);},[book,chapter,translation]);
  useEffect(()=>{(creating?createRef.current:edit?editRef.current:null)?.scrollIntoView({block:'nearest',behavior:'smooth'});},[edit?.verse,creating]);
  const dirty=!!edit&&edit.text!==edit.original || creating&&!!(metadata.code||metadata.name||metadata.source);
  useEffect(()=>{onDirty(dirty);return()=>onDirty(false);},[dirty,onDirty]);
  useEffect(()=>{onBusy(busy);return()=>onBusy(false);},[busy,onBusy]);
  useEffect(()=>{let active=true;api<Testament[]>('/bible/catalog').then(data=>{if(active)setCatalog(data);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[]);
  useEffect(()=>{
    let active=true;setLoading(true);setError('');setContent(null);setChapters([]);
    Promise.all([api<Chapter[]>(`/bible/books/${book}/chapters${translation?'?translation_id='+translation:''}`),translation?api<Content>(`/bible/translations/${translation}/${book}/${chapter}`):Promise.resolve(null)])
      .then(([cs,body])=>{if(active){setChapters(cs);setContent(body);if(body)setEdit(previous=>previous&&previous.revision===null?{...previous,revision:body.revision}:previous);}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[book,chapter,translation,refresh]);
  const guard=()=>!dirty||window.confirm('经文管理有未保存的内容，确定放弃吗？');
  const navigate=(fn:()=>void)=>{if(busy||!guard())return;setEdit(null);setCreating(false);setMetadata({code:'',name:'',language:'zh',source:''});setNotice('');fn();};
  const run=async(fn:()=>Promise<void>)=>{setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const selected=catalog.find(t=>t.code===testament),current=selected?.books.find(b=>b.code===book),chapterInfo=chapters.find(c=>c.number===chapter);
  const selectedTranslation=translations.find(t=>String(t.id)===translation);
  const numbers=Array.from({length:Math.max(chapterInfo?.reference_verse_count||0,...(content?.verses.map(v=>v.verse)||[]))},(_,i)=>i+1);
  const openVerse=(number?:number)=>navigate(()=>{
    const verse=number??Array.from({length:176},(_,i)=>i+1).find(n=>!content?.verses.some(v=>v.verse===n));
    if(!verse){setError('本章 1～176 节均已录入，请选择已有经节编辑');return;}
    const row=content?.verses.find(v=>v.verse===verse);
    setRange({start:verse,end:verse});setAnchor(null);
    setEdit({verse,text:row?.text||'',original:row?.text||'',existing:!!row,revision:content?.revision??null});
  });
  const selectVerse=(number:number)=>navigate(()=>{
    if(anchor===null){setRange({start:number,end:number});setAnchor(number);}
    else{setRange({start:Math.min(anchor,number),end:Math.max(anchor,number)});setAnchor(null);}
  });
  const visibleNumbers=range?numbers.filter(n=>n>=range.start&&n<=range.end):numbers;
  const rangeTitle=range?(range.start===range.end?`第 ${range.start} 节`:`第 ${range.start}～${range.end} 节`):'全部经节';
  const save=()=>run(async()=>{
    if(!edit)return;
    if(!translation||!content||loading||edit.revision===null)throw Error('请选择经文所属译本并等待章节读取完成');
    if(!edit.existing&&content.verses.some(v=>v.verse===edit.verse))throw Error('所选译本的该节已有正文，请取消后使用该节的编辑按钮核对修改');
    await api(`/bible/translations/${translation}/${book}/${chapter}/${edit.verse}`,'PUT',{text:edit.text,revision:edit.revision});
    setRange({start:edit.verse,end:edit.verse});setAnchor(null);setEdit(null);setRefresh(n=>n+1);setNotice('经文已保存');await onRefresh();
  });
  return <div className="bible-manager">
    <p className="muted">旧约 39 卷 · 新约 27 卷。按书卷、章、节维护各译本正文。</p>
    {error&&<p className="callout" role="alert">{error}</p>}{notice&&<p className="callout neutral" role="status">{notice}</p>}
    <div className="bible-toolbar"><label className="field"><span>当前译本</span><Choice label="当前译本" disabled={busy} value={translation} onChange={value=>navigate(()=>setTranslation(value))} options={[{value:'',label:'请选择译本'},...translations.map(t=>({value:String(t.id),label:`${t.name} · ${t.language}`}))]}/></label><button disabled={busy} onClick={()=>{if(edit&&!edit.existing)setCreating(true);else navigate(()=>setCreating(true));}}>新建译本</button></div>
    {selectedTranslation&&<p className="small muted">{selectedTranslation.code} · 版本 {selectedTranslation.revision} · {selectedTranslation.source||'尚未填写来源'}</p>}
    {creating&&<form ref={createRef} className="inset" onSubmit={e=>{e.preventDefault();run(async()=>{const result=await api<{id:number}>('/translations','POST',metadata);setCreating(false);setMetadata({code:'',name:'',language:'zh',source:''});await onRefresh();setEdit(previous=>previous?{...previous,revision:null}:previous);setTranslation(String(result.id));setNotice('译本已创建，可以开始录入经文');});}}>
      <h3>新建译本</h3><div className="row"><label className="field"><span>代码（英文、数字、下划线、短横线）</span><input required pattern="[A-Za-z0-9_-]{1,80}" maxLength={80} value={metadata.code} onChange={e=>setMetadata({...metadata,code:e.target.value})}/></label><label className="field"><span>译本名称</span><input required maxLength={150} value={metadata.name} onChange={e=>setMetadata({...metadata,name:e.target.value})}/></label></div>
      <div className="row"><label className="field"><span>语言（如 zh / en）</span><input required maxLength={30} value={metadata.language} onChange={e=>setMetadata({...metadata,language:e.target.value})}/></label><label className="field"><span>内容来源</span><input maxLength={2000} value={metadata.source} onChange={e=>setMetadata({...metadata,source:e.target.value})}/></label></div><button className="primary" disabled={busy||!metadata.name.trim()||!metadata.language.trim()}>创建译本</button><button type="button" disabled={busy} onClick={()=>{setCreating(false);setMetadata({code:'',name:'',language:'zh',source:''});}}>取消</button>
    </form>}
    <div className="bible-testaments">{catalog.map(t=><button key={t.code} className={testament===t.code?'primary':''} disabled={busy} onClick={()=>navigate(()=>{setTestament(t.code);setBook(t.books[0].code);setChapter(1);})}>{t.name} · {t.books.length} 卷</button>)}</div>
    <div className="bible-layout"><nav className="bible-books" aria-label="书卷目录">{selected?.books.map(b=><button key={b.code} aria-current={book===b.code?'true':undefined} className={book===b.code?'primary':''} disabled={busy} onClick={()=>navigate(()=>{setBook(b.code);setChapter(1);})}><span>{b.name}</span><small>{b.chapters} 章</small></button>)}</nav>
    <section className="bible-content"><h3>{current?.name||book} <span className="muted">/ {current?.chapters||'—'} 章</span></h3>
      <nav className="chapter-navigation" aria-label="章节导航"><button disabled={busy||loading||chapter<=1} onClick={()=>navigate(()=>setChapter(chapter-1))}>上一章</button><Choice label="选择章" disabled={busy||loading} value={String(chapter)} onChange={value=>navigate(()=>setChapter(Number(value)))} options={Array.from({length:current?.chapters||chapter},(_,i)=>({value:String(i+1),label:`第 ${i+1} 章`}))}/><button disabled={busy||loading||chapter>=(current?.chapters||1)} onClick={()=>navigate(()=>setChapter(chapter+1))}>下一章</button></nav>
      <div className="bible-section-heading"><h3>选择经节</h3><button disabled={busy||loading} aria-expanded={range===null} onClick={()=>navigate(()=>{if(range){previousRange.current=range;setRange(null);}else setRange(previousRange.current);setAnchor(null);})}>{range===null?'隐藏全章':'显示全章'}</button></div>
      <p className="small muted" role="status">{anchor===null?'先点击起始节，再点击结束节，可连续显示一段经文。':'已选起始节 '+anchor+'，再点击一个节号选择范围；再次点击同一节只选该节。'}</p>
      <div className="bible-chapters" aria-label="经节目录">{numbers.map(n=><button key={n} disabled={busy||loading} title={`第 ${n} 节`} aria-label={`第 ${n} 节`} aria-pressed={!range||(n>=range.start&&n<=range.end)} className={!range||(n>=range.start&&n<=range.end)?'primary':''} onClick={()=>selectVerse(n)}>{n}{content?.verses.some(v=>v.verse===n)&&<span className="chapter-dot"/>}</button>)}</div>
      <div className="bible-section-heading"><h3>{rangeTitle}</h3><button disabled={busy||loading} onClick={()=>openVerse()}>新增经文</button></div>
      {translation&&!loading&&!content&&<button onClick={()=>setRefresh(n=>n+1)}>重新读取章节</button>}
      {loading?<p className="muted">正在读取章节…</p>:<><p className="muted">已录入 {content?.verses.length||0} 节{chapterInfo?.reference_verse_count!=null?` · 参考目录 ${chapterInfo.reference_verse_count} 节`:' · 参考节数尚未收录'}</p>{!translation&&<p className="callout neutral">可先录入正文，保存时需要指定所属译本。</p>}{chapterInfo?.reference_verse_count!=null&&<p className="small muted">参考节数来自所提供的网站信息，仅供核对；各译本分节可能不同。</p>}</>}
      {edit&&<form ref={editRef} className="inset bible-edit" onSubmit={e=>{e.preventDefault();save();}}><h3>{edit.existing?'编辑经文':'录入经文'} · {current?.name} {chapter}:{edit.verse}</h3><label className="field"><span>所属译本</span><Choice label="经文所属译本" disabled={busy||edit.existing} value={translation} onChange={value=>{setContent(null);setLoading(true);setEdit({...edit,revision:null});setTranslation(value);}} options={[{value:'',label:'请选择所属译本'},...translations.map(t=>({value:String(t.id),label:`${t.name} · ${t.language}`}))]}/></label>{!translation&&<p className="callout neutral">{translations.length?'可先输入正文，再选择译本保存。':'当前尚无译本。可以先填写正文，再点击上方「新建译本」；正文草稿会保留。'}</p>}{!edit.existing&&content?.verses.some(v=>v.verse===edit.verse)&&<p className="callout">该译本的此节已有正文，请通过该节的「编辑」按钮核对修改。</p>}<label className="field"><span>节号</span>{edit.existing?<p className="fixed-verse-number" aria-label="节号">第 {edit.verse} 节（不可修改）</p>:<input type="number" required min={1} max={176} value={edit.verse} disabled={busy||edit.existing} onChange={e=>{if(edit.existing)return;const verse=Number(e.target.value);if(content?.verses.some(v=>v.verse===verse)){setError('该节已有正文，请在下方选择编辑');return;}setEdit({...edit,verse});}}/>}</label><label className="field"><span>正文</span><textarea autoFocus required maxLength={10000} rows={5} value={edit.text} disabled={busy} onChange={e=>setEdit({...edit,text:e.target.value})}/></label><div className="bible-edit-actions"><button className="primary" disabled={busy||loading||!translation||edit.revision===null||!edit.text.trim()||(!edit.existing&&!!content?.verses.some(v=>v.verse===edit.verse))}>保存经文</button><button type="button" disabled={busy} onClick={()=>navigate(()=>setEdit(null))}>取消</button><button type="button" disabled={busy} onClick={()=>setRefresh(n=>n+1)}>刷新章节</button></div><p className="small muted">若发生版本冲突，刷新后取消编辑，再重新打开该节核对修改。</p></form>}
      {!loading&&<div className="bible-verses">{visibleNumbers.map(n=>{const row=content?.verses.find(v=>v.verse===n);return <article key={n}><span className="verse-number">{n}</span><p className={row?'':'muted'}>{row?.text||(translation?'尚未录入':'尚未选择译本，可先录入此节正文')}</p><div><button disabled={busy} onClick={()=>openVerse(n)}>{row?'编辑':'录入'}</button>{row&&content&&<button className="danger" disabled={busy} onClick={()=>{if(!guard()||!window.confirm(`确定删除${current?.name} ${chapter}:${n} 的正文吗？`))return;run(async()=>{await api(`/bible/translations/${translation}/${book}/${chapter}/${n}?revision=${content.revision}`,'DELETE');setEdit(null);setRefresh(v=>v+1);setNotice('经文已删除');await onRefresh();});}}>删除</button>}</div></article>;})}{!numbers.length&&<p className="callout neutral">本章尚无经文。可新增经节，后续也可由采集程序写入。</p>}</div>}
    </section></div>
  </div>;
}
