import { useMemo } from 'react';
import { APPLIANCE_STATE, EDGE_STATE, w } from './model';
import type { PowerSystem } from './model';

/** Source → feeder → (circuit) → room distribution → appliance, laid out left to right from `data.edges`. */
const COL = { source: 24, feeder: 200, circuit: 380, room: 540, appliance: 760 };
const ROW = 24, GAP = 14, TOP = 30;

export function networkLayout(data: PowerSystem) {
  const nodes = new Map<string, { x: number; y: number; label: string; sub?: string }>();
  let y = TOP;
  const roomY = new Map<string, number>();
  for (const room of data.rooms) {
    const items = data.appliances.filter(a => a.room_id === room.id);
    const start = y;
    for (const a of items) { nodes.set(a.id, { x: COL.appliance, y, label: a.name, sub: `${room.name} · ${w(a.demand_w)}` }); y += ROW; }
    roomY.set(room.id, (start + y - ROW) / 2);
    y += GAP;
  }
  for (const room of data.rooms) {
    const ry = roomY.get(room.id)!;
    nodes.set(room.distribution_id, { x: COL.room, y: ry, label: room.distribution_name, sub: `${room.name} distribution` });
    if (room.service_id) nodes.set(room.service_id, { x: COL.circuit, y: ry, label: `Circuit ${room.service_id}`, sub: 'campus service' });
  }
  for (const f of data.feeders) {
    const ys = data.rooms.filter(r => r.feeder === f.id).map(r => roomY.get(r.id)!);
    nodes.set(f.id, { x: COL.feeder, y: ys.reduce((a, b) => a + b, 0) / ys.length, label: f.name, sub: `limit ${w(f.limit_w)}` });
  }
  const fy = data.feeders.map(f => nodes.get(f.id)!.y);
  nodes.set(data.source.id, { x: COL.source, y: fy.reduce((a, b) => a + b, 0) / fy.length, label: data.source.name, sub: `capacity ${w(data.source.capacity_w)}` });
  const links = data.edges.map(e => {
    const a = nodes.get(e.from_node), b = nodes.get(e.to_node);
    if (!a || !b) return null;
    const x1 = a.x + 130, x2 = b.x - 6, mx = (x1 + x2) / 2;
    return { edge: e, d: `M${x1} ${a.y} C${mx} ${a.y} ${mx} ${b.y} ${x2} ${b.y}` };
  }).filter((l): l is NonNullable<typeof l> => l !== null);
  return { nodes, links, height: y + 10 };
}

export default function NetworkView({ data, selected, onSelect, highlight }: {
  data: PowerSystem; selected: string | null; onSelect: (id: string) => void; highlight?: string[] }) {
  const layout = useMemo(() => networkLayout(data), [data]);
  const byId = new Map(data.appliances.map(a => [a.id, a]));
  const feeders = new Map(data.feeders.map(f => [f.id, f]));
  const hl = new Set(highlight ?? []);
  return <div className="ps-floorplan-scroll">
    <svg className="ps-network" viewBox={`0 0 1040 ${layout.height}`} role="group" aria-label="Electrical network topology from source to every appliance">
      <rect width={1040} height={layout.height} className="ps-paper" />
      {['Source', 'Feeders', 'Circuits', 'Room distribution', 'Appliances'].map((t, i) =>
        <text key={t} className="ps-wing-label" x={[COL.source, COL.feeder, COL.circuit, COL.room, COL.appliance][i]} y={16}>{t.toUpperCase()}</text>)}
      <g>{layout.links.map(({ edge, d }) => <g key={edge.id} className={`ps-wire ${EDGE_STATE[edge.state].className}`} data-edge={edge.id} data-state={edge.state}>
        <title>{`${edge.from_node} → ${edge.to_node}: ${EDGE_STATE[edge.state].label}`}</title>
        <path d={d} className="ps-wire-base" />{edge.state === 'ENERGIZED' && <path d={d} className="ps-wire-pulse" />}
      </g>)}</g>
      {[...layout.nodes.entries()].map(([id, n]) => {
        const a = byId.get(id);
        if (a) {
          const st = APPLIANCE_STATE[a.state];
          return <g key={id} className={`ps-net-leaf ${st.className}${selected === id ? ' is-selected' : ''}${hl.has(a.room_id) ? ' is-highlight' : ''}`}
            transform={`translate(${n.x} ${n.y})`} role="button" tabIndex={0} aria-pressed={selected === id}
            aria-label={`${a.name} in ${a.room_id}, ${st.label}`} data-appliance={id} data-state={a.state}
            onClick={() => onSelect(id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(id); } }}>
            <rect x={-4} y={-10} width={270} height={20} rx={4} className="ps-net-leaf-bg" />
            <text className="ps-net-state" x={4} y={4}>{`${st.glyph} ${st.short}`}</text>
            <text className="ps-net-label" x={78} y={4}>{`${a.room_id} · ${a.name}`}</text>
            <text className="ps-small" x={262} y={4} textAnchor="end">{w(a.demand_w)}</text>
          </g>;
        }
        const f = feeders.get(id);
        return <g key={id} transform={`translate(${n.x} ${n.y})`} className={`ps-net-node${f && !f.available ? ' is-open' : ''}`} data-node={id}>
          <rect x={-6} y={-18} width={140} height={36} rx={6} />
          <text className="ps-net-label strong" x={4} y={-3}>{n.label}{f && !f.available ? ' ✕ OPEN' : ''}</text>
          <text className="ps-small" x={4} y={11}>{n.sub}</text>
        </g>;
      })}
    </svg>
  </div>;
}
