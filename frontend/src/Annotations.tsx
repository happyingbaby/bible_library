import React, {useEffect, useRef, useState} from 'react';
import {api, Lecture, Ref} from './api';
import './Annotations.css';

type Note = {id:number; lecture_id:number; lecture_revision:number|null; lecture_title:string; content:string; quote:string; paragraph_index:number|null; available:boolean; revision:number};
type Props = {initialLecture:Lecture|null; onRef:(ref:Ref)=>void; onDirty:(dirty:boolean)=>void};

export default function Annotations({initialLecture,onRef,onDirty}:Props) {
  const [lecture,setLecture]=useState<Lecture|null>(initialLecture);
  const [notes,setNotes]=useState<Note[]>([]);
  const [scope,setScope]=useState(initialLecture?'lecture':'all');
  const [selected,setSelected]=useState<number|null>(null);
  const [edit,setEdit]=useState<Note|null>(null);
  const [text,setText]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [more,setMore]=useState(false);
  const root=useRef<HTMLDivElement>(null);
  const sequence=useRef(0);
  const dirty=text!==(edit?.content||'');
  useEffect(()=>{onDirty(dirty);return()=>onDirty(false);},[dirty,onDirty]);
  useEffect(()=>()=>{sequence.current++;},[]);
  const guard=()=>!dirty||window.confirm('批注尚未保存，放弃修改吗？');
  async function load(append=false) {
    const seq=++sequence.current;
    setBusy(true);setError('');
    try {
      const rows=await api<Note[]>(`/annotations?offset=${append?notes.length:0}${scope==='lecture'&&lecture?`&lecture_id=${lecture.id}`:''}`);
      if(seq===sequence.current){setNotes(old=>append?[...old,...rows]:rows);setMore(rows.length===100);}
    } catch(e){if(seq===sequence.current)setError((e as Error).message);}
    finally{if(seq===sequence.current)setBusy(false);}
  }
  useEffect(()=>{setNotes([]);void load();},[scope,lecture?.id]);
  useEffect(()=>{
    root.current?.querySelectorAll('[data-paragraph-index]').forEach(node=>{
      const index=Number(node.getAttribute('data-paragraph-index'));
      node.classList.toggle('annotation-selected',index===selected);
      node.classList.toggle('annotation-marked',notes.some(n=>n.lecture_id===lecture?.id&&n.paragraph_index===index));
    });
    if(selected!==null){const node=root.current?.querySelector<HTMLElement>(`[data-paragraph-index="${selected}"]`);node?.scrollIntoView({block:'center',behavior:'smooth'});node?.focus({preventScroll:true});}
  },[lecture,selected,notes]);
  async function jump(note:Note) {
    if(!guard())return;
    setBusy(true);setError('');
    try {
      const fresh=await api<Note>(`/annotations/${note.id}`);
      if(!fresh.available){throw Error('讲义暂不可访问；仍可管理自己的批注。');}
      const next=await api<Lecture>(`/lectures/${note.lecture_id}`);
      if(next.revision!==fresh.lecture_revision)throw Error('讲义刚刚更新，请重新点击跳转。');
      setLecture(next);setSelected(fresh.paragraph_index);setEdit(null);setText('');
      if(fresh.paragraph_index===null)setError('原段落已修改或无法唯一识别，批注已保留，请根据摘录查找。');
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function save() {
    setBusy(true);setError('');
    try {
      if(edit)await api(`/annotations/${edit.id}`,'PUT',{content:text,revision:edit.revision});
      else if(lecture&&selected!==null)await api('/annotations','POST',{lecture_id:lecture.id,lecture_revision:lecture.revision,paragraph_index:selected,content:text});
      else throw Error('请先选择段落');
      setEdit(null);setText('');await load();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  const selectParagraph=(target:HTMLElement)=>{
    if(busy)return;
    const ref=target.closest('[data-ref]');
    if(ref&&lecture){onRef(lecture.references[Number(ref.getAttribute('data-ref'))]);return;}
    if(target.closest('a'))return;
    const p=target.closest('[data-paragraph-index]');
    if(p&&guard()){setSelected(Number(p.getAttribute('data-paragraph-index')));setEdit(null);setText('');}
  };
  return <div className="annotations-workspace">
    <main className="annotation-reading"><header><h1>{lecture?.title||'我的批注'}</h1><p>点击段落，或用 Tab 选中段落后按回车，添加个人批注。</p></header>
      {lecture?<div ref={root} className="prose annotation-prose" onClick={e=>{const target=e.target as HTMLElement;const link=target.closest('a');if(link){e.preventDefault();const href=link.getAttribute('href');if(href&&/^https?:\/\//.test(href))window.open(href,'_blank','noopener');}else selectParagraph(target);}} onKeyDown={e=>{if(e.key==='Enter'&&(e.target as HTMLElement).matches('[data-paragraph-index]')){e.preventDefault();selectParagraph(e.target as HTMLElement);}}} dangerouslySetInnerHTML={{__html:lecture.html}}/>:<p>从右侧批注点击「跳转段落」，或返回资料库打开讲义后选择「段落批注」。</p>}
    </main>
    <aside className="annotation-panel" aria-label="个人批注"><h2>我的批注</h2><p className="muted">批注仅本人可查看和修改</p>
      <label>批注范围<select disabled={busy} value={scope} onChange={e=>setScope(e.target.value)}><option value="all">全部讲义</option>{lecture&&<option value="lecture">当前讲义</option>}</select></label>
      {error&&<p role="alert" className="callout">{error}</p>}
      {(edit||selected!==null)&&<form onSubmit={e=>{e.preventDefault();void save();}}><h3>{edit?'编辑批注':`段落 ${(selected??0)+1} · 添加批注`}</h3><textarea aria-label="批注内容" required maxLength={10000} value={text} onChange={e=>setText(e.target.value)} placeholder="写下你的思考…"/><div className="annotation-actions"><button className="primary" disabled={busy||!text.trim()||!dirty}>保存批注</button><button type="button" disabled={busy} onClick={()=>{if(guard()){setEdit(null);setSelected(null);setText('');}}}>取消</button></div></form>}
      <button disabled={busy} onClick={()=>void load()}>刷新批注</button>
      {busy&&<p role="status">正在读取或保存…</p>}
      {!busy&&!notes.length&&<p>暂无批注。选择左侧段落开始记录。</p>}
      {notes.map(note=><article className={'annotation-card '+(note.lecture_id===lecture?.id&&note.paragraph_index===selected?'active':'')} key={note.id}><h3>{note.lecture_title}</h3>{note.quote&&<blockquote>{note.quote}</blockquote>}<p className="annotation-content">{note.content}</p><div className="annotation-actions"><button disabled={busy||!note.available} onClick={()=>void jump(note)}>{note.paragraph_index===null?'查看讲义（定位失效）':'跳转段落'}</button><button disabled={busy} onClick={()=>{if(guard()){setEdit(note);setText(note.content);}}}>编辑</button><button disabled={busy} onClick={async()=>{if(!window.confirm('永久删除这条个人批注？'))return;setBusy(true);setError('');try{await api(`/annotations/${note.id}?revision=${note.revision}`,'DELETE');if(edit?.id===note.id){setEdit(null);setText('');}await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>删除</button></div></article>)}
      {more&&<button disabled={busy} onClick={()=>void load(true)}>加载更多批注</button>}
    </aside>
  </div>;
}
