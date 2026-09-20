import type { EvidenceScene } from '../types';

function Scene({ scene }: { scene: EvidenceScene }) {
  switch (scene) {
    case 'tank':
      return (
        <>
          <rect width="160" height="120" fill="#adb69c" />
          <rect y="86" width="160" height="34" fill="#9aa785" />
          <rect x="34" y="74" width="96" height="17" rx="8.5" fill="#363d2b" />
          <path d="M44 74 L118 74 L109 58 L53 58 Z" fill="#444d36" />
          <rect x="62" y="42" width="38" height="17" rx="3" fill="#313824" />
          <rect x="100" y="48" width="40" height="4.5" rx="2.25" fill="#313824" />
          <circle cx="52" cy="82.5" r="3.5" fill="#232819" />
          <circle cx="68" cy="82.5" r="3.5" fill="#232819" />
          <circle cx="84" cy="82.5" r="3.5" fill="#232819" />
          <circle cx="100" cy="82.5" r="3.5" fill="#232819" />
        </>
      );
    case 'truck':
      return (
        <>
          <rect width="160" height="120" fill="#b2b9c1" />
          <rect y="88" width="160" height="32" fill="#9aa2ab" />
          <rect x="26" y="40" width="64" height="44" rx="3" fill="#414b58" />
          <rect x="90" y="54" width="32" height="30" rx="4" fill="#2f3743" />
          <rect x="95" y="59" width="13" height="10" rx="1.5" fill="#9fb3c8" />
          <circle cx="46" cy="88" r="9" fill="#171e26" />
          <circle cx="46" cy="88" r="3.5" fill="#6b7280" />
          <circle cx="102" cy="88" r="9" fill="#171e26" />
          <circle cx="102" cy="88" r="3.5" fill="#6b7280" />
          <circle cx="118" cy="88" r="9" fill="#171e26" />
          <circle cx="118" cy="88" r="3.5" fill="#6b7280" />
        </>
      );
    case 'plane':
      return (
        <>
          <rect width="160" height="120" fill="#9cb8cd" />
          <ellipse cx="36" cy="28" rx="24" ry="8" fill="#ffffff" opacity="0.35" />
          <ellipse cx="130" cy="94" rx="28" ry="9" fill="#ffffff" opacity="0.3" />
          <ellipse cx="82" cy="62" rx="56" ry="8.5" fill="#3c4c5e" />
          <path d="M74 62 L112 30 L125 32 L90 66 Z" fill="#29394b" />
          <path d="M118 58 L138 42 L144 46 L127 62 Z" fill="#29394b" />
        </>
      );
    case 'snow':
      return (
        <>
          <rect width="160" height="120" fill="#e2e7ec" />
          <ellipse cx="40" cy="38" rx="26" ry="10" fill="#cdd6de" />
          <ellipse cx="122" cy="30" rx="20" ry="8" fill="#cdd6de" />
          <ellipse cx="92" cy="98" rx="42" ry="12" fill="#cdd6de" />
          <circle cx="30" cy="78" r="4" fill="#a7b2bd" />
          <circle cx="142" cy="72" r="3" fill="#a7b2bd" />
          <line x1="40" y1="80" x2="68" y2="80" stroke="#b4bfc9" strokeWidth="2" strokeDasharray="4 4" />
          <rect x="70" y="62" width="28" height="13" rx="2.5" fill="#374151" />
          <rect x="74" y="56" width="12" height="7" rx="1.5" fill="#1f2937" />
        </>
      );
  }
}

export function EvidenceThumb({
  scene,
  className = '',
}: {
  scene: EvidenceScene;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 160 120"
      className={`block ${className}`}
      role="img"
      aria-label={`${scene} imagery sample`}
      preserveAspectRatio="xMidYMid slice"
    >
      <Scene scene={scene} />
      <g stroke="#0f172a" strokeOpacity="0.06" strokeWidth="0.5">
        {[32, 64, 96, 128].map((x) => (
          <line key={`x-${x}`} x1={x} y1="0" x2={x} y2="120" />
        ))}
        {[30, 60, 90].map((y) => (
          <line key={`y-${y}`} x1="0" y1={y} x2="160" y2={y} />
        ))}
      </g>
    </svg>
  );
}
