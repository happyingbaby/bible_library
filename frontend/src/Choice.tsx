import React, {useEffect, useId, useRef, useState} from 'react';
import {ChevronDown, Check} from 'lucide-react';

type Props = {label:string;value:string;options:{value:string;label:string}[];disabled?:boolean;onChange:(value:string)=>void};
export default function Choice({label,value,options,disabled,onChange}:Props){
  const [open,setOpen]=useState(false),[active,setActive]=useState(0);
  const root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),id=useId();
  const selected=options.findIndex(option=>option.value===value);
  useEffect(()=>{if(disabled)setOpen(false);},[disabled]);
  useEffect(()=>{
    if(!open)return;
    const close=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener('pointerdown',close);
    return()=>document.removeEventListener('pointerdown',close);
  },[open]);
  useEffect(()=>{if(open)document.getElementById(`${id}-${active}`)?.scrollIntoView({block:'nearest'});},[open,active,id]);
  const choose=(index:number)=>{if(options[index])onChange(options[index].value);setOpen(false);trigger.current?.focus();};
  return <div className="choice" ref={root} onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget))setOpen(false);}}>
    <button type="button" ref={trigger} className="choice-trigger" role="combobox" aria-label={label} aria-expanded={open} aria-controls={id} aria-haspopup="listbox" aria-activedescendant={open?`${id}-${active}`:undefined} disabled={disabled} onClick={()=>{setActive(Math.max(0,selected));setOpen(!open);}} onKeyDown={e=>{
      if(e.key==='Escape'){e.preventDefault();setOpen(false);return;}
      if(e.key==='Tab'){setOpen(false);return;}
      if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();setOpen(true);setActive(open?Math.max(0,Math.min(options.length-1,active+(e.key==='ArrowDown'?1:-1))):Math.max(0,selected));}
      else if(e.key==='Home'||e.key==='End'){e.preventDefault();setOpen(true);setActive(e.key==='Home'?0:options.length-1);}
      else if((e.key==='Enter'||e.key===' ')&&open){e.preventDefault();choose(active);}
      else if(e.key.length===1&&e.key!==' '){const index=options.findIndex(option=>option.label.toLowerCase().startsWith(e.key.toLowerCase()));if(index>=0){e.preventDefault();setOpen(true);setActive(index);}}
    }}><span>{options[selected]?.label||'请选择'}</span><ChevronDown size={16}/></button>
    {open&&<div className="choice-options" id={id} role="listbox" aria-label={label}>{options.map((option,index)=><div id={`${id}-${index}`} key={option.value} role="option" aria-selected={option.value===value} className={index===active?'active':''} onPointerDown={e=>e.preventDefault()} onPointerMove={()=>setActive(index)} onClick={()=>choose(index)}><span>{option.label}</span>{option.value===value&&<Check size={15}/>}</div>)}</div>}
  </div>;
}
