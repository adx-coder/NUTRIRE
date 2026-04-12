/** Botanical SVG accent illustrations — fern, wheat, leaf */

export function FernAccent() {
  return (
    <svg viewBox="0 0 200 200" fill="none" className="w-full h-full">
      <g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none">
        <path d="M30 180 Q60 100 110 50 Q130 30 160 10" />
        {Array.from({ length: 14 }).map((_, i) => {
          const t = i / 14;
          const x = 30 + t * 130;
          const y = 180 - t * 170;
          const len = 30 - t * 15;
          const angle = -30 - t * 25;
          const rad = (angle * Math.PI) / 180;
          const x2 = x + Math.cos(rad) * len;
          const y2 = y + Math.sin(rad) * len;
          const x3 = x - Math.cos(rad) * len * 0.7;
          const y3 = y - Math.sin(rad) * len * 0.7;
          return (
            <g key={i}>
              <path d={`M${x} ${y} Q${(x + x2) / 2} ${y2 - 5} ${x2} ${y2}`} />
              <path d={`M${x} ${y} Q${(x + x3) / 2} ${y3 - 5} ${x3} ${y3}`} />
            </g>
          );
        })}
      </g>
    </svg>
  );
}

export function WheatAccent() {
  return (
    <svg viewBox="0 0 200 200" fill="none" className="w-full h-full">
      <g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none">
        <path d="M100 190 L100 50" />
        {Array.from({ length: 8 }).map((_, i) => {
          const y = 50 + i * 16;
          return (
            <g key={i}>
              <ellipse cx={88} cy={y} rx={10} ry={5} transform={`rotate(-30 88 ${y})`} />
              <ellipse cx={112} cy={y} rx={10} ry={5} transform={`rotate(30 112 ${y})`} />
            </g>
          );
        })}
      </g>
    </svg>
  );
}

export function LeafAccent() {
  return (
    <svg viewBox="0 0 200 200" fill="none" className="w-full h-full">
      <g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none">
        <path d="M40 160 Q80 40 180 30 Q160 130 40 160 Z" />
        <path d="M40 160 Q100 100 180 30" />
        {Array.from({ length: 6 }).map((_, i) => {
          const t = (i + 1) / 7;
          const x1 = 40 + t * 140;
          const y1 = 160 - t * 130;
          return <path key={i} d={`M${x1} ${y1} Q${x1 - 20} ${y1 - 25} ${x1 - 35} ${y1 - 40}`} />;
        })}
      </g>
    </svg>
  );
}
