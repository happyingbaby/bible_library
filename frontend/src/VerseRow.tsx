import React, {useLayoutEffect, useRef, useState} from 'react';

export default function VerseRow({children}:{children:React.ReactNode}){
  const ref=useRef<HTMLElement>(null),[multiline,setMultiline]=useState(false);
  useLayoutEffect(()=>{
    const paragraph=ref.current?.querySelector('p');
    if(!paragraph)return;
    const measure=()=>setMultiline(paragraph.getBoundingClientRect().height>parseFloat(getComputedStyle(paragraph).lineHeight)+1);
    measure();
    const observer=new ResizeObserver(measure);observer.observe(paragraph);
    return()=>observer.disconnect();
  },[children]);
  return <article ref={ref} className={multiline?'multiline':''}>{children}</article>;
}
