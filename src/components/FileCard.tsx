import type { ReactNode } from 'react';
import { Upload } from 'lucide-react';
import { Button } from './ui/Button';
import { Chip } from './ui/Badge';

export function FileCard({
  icon,
  name,
  meta,
  status,
  timestamp,
  onUploadClick,
  disabled,
}: {
  icon: ReactNode;
  name: string;
  meta: string;
  status: string;
  timestamp: string;
  onUploadClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-slate-100 text-slate-500">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-slate-800">{name}</p>
        <p className="text-xs text-slate-500">{meta}</p>
      </div>
      <div className="flex flex-col items-start gap-1 xl:items-end">
        <Chip tone="green">{status}</Chip>
        <span className="text-[11px] text-slate-400">{timestamp}</span>
      </div>
      <Button onClick={onUploadClick} disabled={disabled}>
        <Upload size={15} />
        Upload New
      </Button>
    </div>
  );
}
