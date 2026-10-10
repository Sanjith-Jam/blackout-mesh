/** Line illustrations of the configured equipment types, drawn in a 40 × 40 box centred on (0, 0).
 * Only keys that exist in the site catalog are drawn; anything else gets a neutral plug symbol. */
const S = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;

function Body({ children }: { children: React.ReactNode }) {
  return <g {...S}>{children}</g>;
}

const ICONS: Record<string, React.ReactNode> = {
  ventilator: <Body><rect x={-13} y={-14} width={20} height={24} rx={2} /><rect x={-10} y={-11} width={14} height={8} rx={1} />
    <path d="M-9 5 h4 M-1 5 h4" /><path d="M7 -2 C 14 -2 14 10 18 12" /><circle cx={-3} cy={14} r={3} /><path d="M-9 -7 l3 -2 l3 3 l3 -3 l3 2" /></Body>,
  monitor: <Body><rect x={-16} y={-13} width={32} height={22} rx={2} /><path d="M-12 -2 h6 l3 -6 l4 11 l3 -5 h8" /><path d="M-5 13 h10 M0 9 v4" /></Body>,
  infusion: <Body><path d="M0 -18 v6" /><path d="M-6 -12 h12 v10 a6 6 0 0 1 -12 0 z" /><path d="M-3 -6 h6" /><path d="M0 4 v6" />
    <path d="M0 10 C 0 16 8 14 8 18" /><rect x={-8} y={11} width={6} height={7} rx={1} /></Body>,
  lights: <Body><path d="M-14 -6 h28 v6 h-28 z" /><path d="M-10 4 l-3 6 M0 4 v7 M10 4 l3 6" /><path d="M-4 -12 l4 -5 l4 5" /></Body>,
  oxygen: <Body><rect x={-7} y={-12} width={14} height={28} rx={6} /><path d="M-3 -16 h6 v4 h-6 z" /><text x={0} y={6} textAnchor="middle" fontSize={8} stroke="none" fill="currentColor">O₂</text></Body>,
  surgical_light: <Body><path d="M0 -18 v6" /><ellipse cx={0} cy={-4} rx={15} ry={7} /><circle cx={-6} cy={-4} r={2} /><circle cx={0} cy={-4} r={2} /><circle cx={6} cy={-4} r={2} />
    <path d="M-10 6 l-4 10 M0 6 v11 M10 6 l4 10" strokeDasharray="2 2" /></Body>,
  anesthesia: <Body><rect x={-12} y={-16} width={24} height={30} rx={2} /><circle cx={-4} cy={-8} r={4} /><path d="M-4 -8 l2 -2" /><rect x={3} y={-11} width={6} height={6} rx={1} />
    <path d="M-8 2 h16 M-8 7 h16" /><path d="M12 -2 c6 0 6 10 0 12" /></Body>,
  esu: <Body><rect x={-15} y={-10} width={24} height={18} rx={2} /><circle cx={-8} cy={-1} r={3} /><path d="M-1 -4 h6 M-1 2 h6" /><path d="M9 -1 C 16 -1 13 12 18 16" /><path d="M15 13 l5 5" strokeWidth={2.4} /></Body>,
  ac: <Body><rect x={-17} y={-10} width={34} height={14} rx={3} /><path d="M-13 0 h26" /><path d="M-10 8 c2 3 -2 5 0 8 M0 8 c2 3 -2 5 0 8 M10 8 c2 3 -2 5 0 8" /></Body>,
  bed_lights: <Body><path d="M-17 8 v-10 M-17 2 h34 v6 M-17 8 h34" /><rect x={-15} y={-4} width={8} height={5} rx={2} /><path d="M6 -16 l-4 8 h8 z" /><path d="M2 -6 l-2 3 M10 -6 l2 3" /></Body>,
  nurse_call: <Body><rect x={-9} y={-15} width={18} height={26} rx={3} /><circle cx={0} cy={-3} r={5} /><path d="M0 -6 v6 M-3 -3 h6" /><path d="M-4 15 c4 4 8 -2 12 2" /></Body>,
  fans: <Body><circle cx={0} cy={-2} r={2.5} /><path d="M0 -4.5 C -3 -14 8 -16 4 -6 M2 0 C 11 3 6 13 -1 4 M-2.5 -1 C -12 -5 -10 -16 -1.5 -4" /><path d="M0 1 v15 M-6 16 h12" /></Body>,
  water_pump: <Body><circle cx={-3} cy={2} r={9} /><path d="M-3 -7 v-8 h14 v6" /><path d="M6 2 h10" /><path d="M-3 2 l5 -3" /><path d="M-12 14 h18" /><path d="M14 -9 c0 4 4 4 4 0 c0 -3 -2 -5 -2 -7 c0 2 -2 4 -2 7" /></Body>,
  lighting: <Body><path d="M-6 -2 a8 8 0 1 1 12 0 c-2 2 -2 4 -2 6 h-8 c0 -2 0 -4 -2 -6 z" /><path d="M-3 8 h6 M-2 12 h4" /><path d="M0 -18 v-2 M-12 -12 l-2 -2 M12 -12 l2 -2" /></Body>,
  computers: <Body><rect x={-16} y={-14} width={22} height={16} rx={1.5} /><path d="M-8 2 v4 h6 v-4 M-11 6 h12" /><rect x={9} y={-14} width={8} height={22} rx={1} /><path d="M11 -9 h4 M11 -5 h4" /><path d="M-16 13 h22" /></Body>,
  projector: <Body><rect x={-16} y={-6} width={26} height={14} rx={3} /><circle cx={4} cy={1} r={4} /><path d="M10 -2 l8 -6 M10 4 l8 6" strokeDasharray="2 2" /><path d="M-12 8 v4 M6 8 v4" /><circle cx={-9} cy={1} r={1} /></Body>,
  instruments: <Body><rect x={-16} y={-12} width={32} height={20} rx={2} /><path d="M-12 -2 q3 -8 6 0 t6 0 t6 0" /><circle cx={9} cy={-5} r={3} /><path d="M9 -5 l2 -2" /><path d="M-12 4 h8 M2 4 h10" /><path d="M-10 8 v6 M10 8 v6" /></Body>,
};

const FALLBACK = <Body><rect x={-10} y={-10} width={20} height={16} rx={3} /><path d="M-4 6 v6 M4 6 v6" /></Body>;

export default function ApplianceIcon({ kind }: { kind: string }) {
  return <>{ICONS[kind] ?? FALLBACK}</>;
}

export const KNOWN_ICON_KEYS = Object.keys(ICONS);
