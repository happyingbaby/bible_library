import React, {useEffect, useRef, useState} from 'react';
import {Search, X} from 'lucide-react';
import {api, Lecture} from './api';
import './ScriptureSearch.css';

type VerseResult = {id:number; translation_name:string; book:string; book_name:string; chapter:number; verse:number; text:string};
type Results = {items:VerseResult[]; total:number};

function Highlight({text, keyword}:{text:string; keyword:string}) {
  const parts = text.split(new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
  return <>{parts.map((part, i) => i % 2 ? <mark key={i}>{part}</mark> : part)}</>;
}

export default function ScriptureSearch({renderContent}:{renderContent:(lecture:Lecture)=>React.ReactNode}) {
  const [input, setInput] = useState('');
  const [keyword, setKeyword] = useState('');
  const [results, setResults] = useState<Results>({items:[], total:0});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<VerseResult|null>(null);
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [lectureLoading, setLectureLoading] = useState(false);
  const [lectureError, setLectureError] = useState('');
  const request = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultButtons = useRef(new Map<number, HTMLButtonElement>());
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => () => {request.current++;}, []);

  async function search(more = false) {
    const q = more ? keyword : input.trim();
    if (!q) {setError('请输入检索关键词'); inputRef.current?.focus(); return;}
    const version = ++request.current;
    const offset = more ? results.items.length : 0;
    setLoading(true); setError('');
    if (!more) {setKeyword(q); setSelected(null); setResults({items:[], total:0});}
    try {
      const page = await api<Results>(`/verses/search?q=${encodeURIComponent(q)}&offset=${offset}`);
      if (version === request.current) setResults(old => ({total:page.total, items:more ? [...old.items, ...page.items] : page.items}));
    } catch (e) {if (version === request.current) setError((e as Error).message);}
    finally {if (version === request.current) setLoading(false);}
  }

  useEffect(() => {
    if (!selected) return;
    let canceled = false;
    closeRef.current?.focus();
    api<Lecture[]>(`/verses/lectures?book=${encodeURIComponent(selected.book)}&chapter=${selected.chapter}&verse=${selected.verse}`)
      .then(rows => {if (!canceled) setLectures(rows);})
      .catch(e => {if (!canceled) setLectureError(e.message);})
      .finally(() => {if (!canceled) setLectureLoading(false);});
    return () => {canceled = true;};
  }, [selected]);

  function closeDrawer() {
    if (selected) resultButtons.current.get(selected.id)?.focus();
    setSelected(null);
  }

  return <div className="scripture-search-workspace">
    <main className="scripture-search-main">
      <header><p className="eyebrow">SCRIPTURE SEARCH</p><h1>经文检索</h1><p className="muted">检索已录入的全部译本，点击经文查看引用它的讲义。</p></header>
      <form className="scripture-search-form" onSubmit={e => {e.preventDefault(); void search();}}>
        <input ref={inputRef} aria-label="经文关键词" placeholder="输入关键词，例如：创造" maxLength={200} value={input} onChange={e => setInput(e.target.value)}/>
        <button className="primary" disabled={loading || !input.trim()}><Search size={16}/>检索</button>
      </form>
      {error && <p className="callout" role="alert">{error}</p>}
      <p role="status" className="muted">{loading ? '正在检索…' : keyword ? `共 ${results.total} 条经文结果，已显示 ${results.items.length} 条` : '输入关键词开始检索'}</p>
      {!loading && !error && keyword && !results.total && <p className="callout neutral">没有找到匹配经文。可更换关键词；尚未录入经文时请联系管理员。</p>}
      <div className="scripture-search-results" aria-label="经文检索结果">
        {results.items.map(item => <button key={item.id} ref={node => {if(node) resultButtons.current.set(item.id, node); else resultButtons.current.delete(item.id);}}
          className={'scripture-result ' + (selected?.id === item.id ? 'chosen' : '')}
          aria-expanded={selected?.id === item.id} aria-controls={selected?.id === item.id ? 'related-lectures' : undefined}
          onClick={() => {if(selected?.id === item.id) return; setLectures([]); setLectureError(''); setLectureLoading(true); setSelected(item);}}>
          <strong>{item.book_name} · 第 {item.chapter} 章 · 第 {item.verse} 节</strong>
          <small>{item.translation_name}</small><p><Highlight text={item.text} keyword={keyword}/></p>
        </button>)}
      </div>
      {results.items.length < results.total && <button disabled={loading} onClick={() => void search(true)}>加载更多（剩余 {results.total - results.items.length} 条）</button>}
    </main>
    {selected && <aside id="related-lectures" className="related-lectures" aria-label="引用该经文的讲义" onKeyDown={e => {if(e.key === 'Escape') {e.stopPropagation(); closeDrawer();}}}>
      <header><div><h2>{selected.book_name} {selected.chapter}章{selected.verse}节</h2><p>引用该经文的讲义{!lectureLoading && !lectureError && ` · ${lectures.length} 篇`}</p></div><button ref={closeRef} className="icon" aria-label="关闭讲义抽屉" onClick={closeDrawer}><X size={20}/></button></header>
      <div className="related-lectures-body">
        <p className="selected-verse">{selected.text}</p>
        {lectureLoading && <p role="status">正在读取关联讲义…</p>}
        {lectureError && <p className="callout" role="alert">{lectureError}<button onClick={() => {setLectureError(''); setLectureLoading(true); setSelected({...selected});}}>重试</button></p>}
        {!lectureLoading && !lectureError && !lectures.length && <p className="callout neutral">暂无可查看的讲义引用该经文。</p>}
        {lectures.length > 0 && <nav aria-label="关联讲义目录"><ol>{lectures.map(l => <li key={l.id}><a href={`#related-lecture-${l.id}`}>{l.title}</a></li>)}</ol></nav>}
        {lectures.map(l => <article id={`related-lecture-${l.id}`} key={l.id} className="related-lecture"><h3>{l.title}</h3><p className="muted">{[l.author, l.sermon_date, l.published ? '已发布' : '未发布'].filter(Boolean).join(' · ')}</p>{renderContent(l)}</article>)}
      </div>
    </aside>}
  </div>;
}
