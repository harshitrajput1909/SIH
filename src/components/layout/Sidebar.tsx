import { NavLink } from 'react-router-dom';
import {
  Activity,
  Box,
  Database,
  FileText,
  LayoutDashboard,
  X,
} from 'lucide-react';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/assurance/datasets', label: 'Dataset Assurance', icon: Database, end: false },
  { to: '/assurance/models', label: 'Model Assurance', icon: Box, end: false },
  { to: '/assurance/inference', label: 'Inference Assurance', icon: Activity, end: false },
  { to: '/audit/reports', label: 'Audit & Reports', icon: FileText, end: false },
];

function Emblem({ className = '' }: { className?: string }) {
  const spokes = Array.from({ length: 12 }, (_, i) => {
    const angle = (i * Math.PI) / 6;
    return (
      <line
        key={i}
        x1={12 + 2.4 * Math.cos(angle)}
        y1={12 + 2.4 * Math.sin(angle)}
        x2={12 + 9 * Math.cos(angle)}
        y2={12 + 9 * Math.sin(angle)}
      />
    );
  });
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      className={className}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="2.4" />
      {spokes}
    </svg>
  );
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-slate-950/50 transition-opacity duration-300 lg:hidden ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-60 flex-col bg-ink-900 transition-transform duration-300 ease-out lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand */}
        <div className="flex items-center gap-3 px-5 pb-4 pt-6">
          <Emblem className="h-9 w-9 shrink-0 text-slate-300" />
          <div className="min-w-0">
            <p className="text-[15px] font-bold tracking-wide text-white">TRUSTVISION</p>
            <p className="text-[11px] text-slate-400">AI Integrity Assurance</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="ml-auto rounded p-1 text-slate-400 hover:bg-white/10 hover:text-white lg:hidden"
          >
            <X size={16} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-white/10 font-medium text-white'
                    : 'text-slate-300 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <item.icon size={17} strokeWidth={1.8} className="shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="border-t border-white/10 px-5 py-4">
          <p className="text-[11px] leading-relaxed text-slate-500">
            Secure AI
            <br />
            Stronger Nation
          </p>
          <div className="mt-4 flex items-center gap-2.5">
            <Emblem className="h-7 w-7 shrink-0 text-slate-400" />
            <div className="leading-tight">
              <p className="text-[11px] font-medium text-slate-200">Government of India</p>
              <p className="text-[10px] text-slate-400">Ministry of Defence</p>
            </div>
          </div>
          <div className="mt-3 flex h-1 overflow-hidden rounded-full">
            <span className="flex-1 bg-[#FF9933]" />
            <span className="flex-1 bg-white" />
            <span className="flex-1 bg-[#138808]" />
          </div>
        </div>
      </aside>
    </>
  );
}
