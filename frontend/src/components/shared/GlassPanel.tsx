import type { ReactNode } from 'react';
export default function GlassPanel({children,className=''}:{children:ReactNode;className?:string}) { return <section className={`glass panel ${className}`}>{children}</section>; }
