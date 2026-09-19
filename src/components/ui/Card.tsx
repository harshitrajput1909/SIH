import type { ReactNode } from 'react';

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {children}
    </section>
  );
}

export function CardTitle({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <h3 className={`text-sm font-semibold text-slate-800 ${className}`}>{children}</h3>;
}
