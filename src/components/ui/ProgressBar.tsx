export function ProgressBar({
  value,
  className = '',
  barClassName = 'bg-emerald-500',
}: {
  value: number;
  className?: string;
  barClassName?: string;
}) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-slate-200 ${className}`}>
      <div
        className={`h-full rounded-full transition-[width] duration-700 ease-out ${barClassName}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
