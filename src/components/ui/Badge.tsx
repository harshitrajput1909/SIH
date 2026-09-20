import type { ReactNode } from 'react';
import type { RiskLevel } from '../../types';

export type ChipTone = 'green' | 'amber' | 'red' | 'sky' | 'slate';

const toneClasses: Record<ChipTone, string> = {
  green: 'bg-emerald-100 text-emerald-700',
  amber: 'bg-amber-100 text-amber-700',
  red: 'bg-red-100 text-red-600',
  sky: 'bg-sky-100 text-sky-700',
  slate: 'bg-slate-100 text-slate-600',
};

export function Chip({
  tone,
  children,
  className = '',
}: {
  tone: ChipTone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium ${toneClasses[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export const riskTone: Record<RiskLevel, ChipTone> = {
  low: 'green',
  medium: 'amber',
  high: 'red',
  critical: 'red',
};
