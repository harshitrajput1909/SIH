import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Bell, ChevronDown, Menu, Search } from 'lucide-react';

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/assurance/datasets': 'Dataset Assurance',
  '/assurance/models': 'Model Assurance',
  '/assurance/inference': 'Inference Assurance',
  '/audit/reports': 'Audit & Reports',
};

export function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  const { pathname } = useLocation();

  useEffect(() => {
    document.title = `${pageTitles[pathname] ?? 'TRUSTVISION'} · TRUSTVISION`;
  }, [pathname]);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 sm:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        aria-label="Open navigation"
        className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-100 lg:hidden"
      >
        <Menu size={19} />
      </button>

      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
        <span className="text-sm text-slate-600">System Online</span>
      </div>

      <div className="hidden flex-1 justify-center px-6 md:flex">
        <div className="relative w-full max-w-md">
          <Search
            size={15}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            placeholder="Search datasets, models, reports..."
            className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-navy-500 focus:bg-white focus:outline-none"
          />
        </div>
      </div>

      <div className="ml-auto flex items-center gap-1.5 md:ml-0">
        <button
          type="button"
          aria-label="Notifications"
          className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-100"
        >
          <Bell size={18} />
        </button>
        <button type="button" className="flex items-center gap-2.5 rounded-lg p-1.5 hover:bg-slate-100">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-ink-800 text-xs font-semibold text-white">
            HR
          </span>
          <span className="hidden text-left leading-tight sm:block">
            <span className="block text-sm font-medium text-slate-800">Harshit</span>
            <span className="block text-[11px] text-slate-500">Analyst</span>
          </span>
          <ChevronDown size={14} className="hidden text-slate-400 sm:block" />
        </button>
      </div>
    </header>
  );
}
