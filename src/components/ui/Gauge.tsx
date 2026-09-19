import { useEffect, useState } from 'react';

const palette = {
  red: '#dc2626',
  amber: '#f59e0b',
  green: '#16a34a',
};

export type GaugeTone = keyof typeof palette;

export function Gauge({
  percent,
  tone,
  size = 96,
  stroke = 9,
}: {
  percent: number;
  tone: GaugeTone;
  size?: number;
  stroke?: number;
}) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => setProgress(percent), 150);
    return () => window.clearTimeout(timer);
  }, [percent]);

  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const fontSize = size >= 90 ? 20 : 13;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        className="-rotate-90"
        role="img"
        aria-label={`${percent} percent`}
      >
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e5e7eb" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={palette[tone]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - progress / 100)}
          className="transition-[stroke-dashoffset] duration-1000 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-bold text-slate-800" style={{ fontSize }}>
          {percent}%
        </span>
      </div>
    </div>
  );
}
