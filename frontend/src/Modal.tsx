import React from 'react';
import {X} from 'lucide-react';

export default function Modal({title,onClose,children,wide=false}:{title:string;onClose:()=>void;children:React.ReactNode;wide?:boolean}){return <div className="overlay" onClick={e=>{if(e.target===e.currentTarget)onClose();}}><section className={'modal '+(wide?'wide':'')} role="dialog" aria-modal="true" aria-label={title}><header><h2>{title}</h2><button className="icon" onClick={onClose} aria-label="关闭"><X size={20}/></button></header><div className="modal-body">{children}</div></section></div>}
