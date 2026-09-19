import type { ReactNode } from 'react';

export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-stretch gap-3">
        <span className="w-1 shrink-0 rounded-full bg-navy-800" aria-hidden="true" />
        <div>
          <h1 className="text-[22px] font-bold leading-tight tracking-tight text-navy-900">
            {title}
          </h1>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
        </div>
      </div>
      {children && <div className="shrink-0">{children}</div>}
    </div>
  );
}
