import { useMemo } from 'react';
import ApplianceIcon from './ApplianceIcon';
import { APPLIANCE_STATE, EDGE_STATE, EVIDENCE_LABEL, w } from './model';
import type { Appliance, Edge, PowerSystem, Room } from './model';

/** Architectural floor plan: hospital wing above a corridor, classroom block below, plant room on the left.
 * Every wire is drawn from one configured edge (`data.edges`) and styled by that edge's modeled state;
 * there is no wire without an edge and no edge without a wire. */

export const VIEW = { width: 1240, height: 880 };
const WING_X = 210, ROOM_W = 336, HOSP_TOP = 20, ROOM_H = 320, CLASS_TOP = 540;
const FEEDER_Y: Record<string, number> = { A: 380, B: 490 };
const PLANT = { x: 18, y: 352, w: 172, h: 168 };
const SOURCE = { x: 62, y: 436 };
const BREAKER_X = 150;

type Pt = [number, number];
export interface Layout {
  rooms: { room: Room; x: number; y: number; top: boolean; cx: number; panel: Pt; circuit?: Pt }[];
  appliances: Map<string, { cx: number; cy: number; side: -1 | 1; laneX: number }>;
  wires: { edge: Edge; d: string }[];
}

const pathD = (pts: Pt[]) => pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x} ${y}`).join(' ');

export function floorPlanLayout(data: PowerSystem): Layout {
  const hospital = data.rooms.filter(r => r.zone === 'hospital');
  const classrooms = data.rooms.filter(r => r.zone === 'classroom');
  const rooms: Layout['rooms'] = [];
  const appliances: Layout['appliances'] = new Map();
  const place = (list: Room[], top: boolean) => list.forEach((room, i) => {
    const x = WING_X + i * ROOM_W, y = top ? HOSP_TOP : CLASS_TOP, cx = x + ROOM_W / 2;
    const panel: Pt = top ? [cx, y + ROOM_H - 16] : [cx, y + 18];
    rooms.push({ room, x, y, top, cx, panel, circuit: top ? undefined : [cx, CLASS_TOP - 18] });
    const items = data.appliances.filter(a => a.room_id === room.id);
    const rows = Math.ceil(items.length / 2);
    items.forEach((a, k) => {
      const row = Math.floor(k / 2), side: -1 | 1 = k % 2 === 0 ? -1 : 1;
      const rowY = top ? y + 92 + row * 84 : y + 108 + row * 84;
      // Cable-tray lanes: the appliance farthest from the panel takes the innermost lane, so no branch crosses another.
      const fromFar = top ? row : rows - 1 - row;
      appliances.set(a.id, { cx: cx + side * 100, cy: rowY, side, laneX: cx + side * (5 + 7 * fromFar) });
    });
  });
  place(hospital, true);
  place(classrooms, false);

  const roomOf = new Map(rooms.map(r => [r.room.id, r]));
  const byDistribution = new Map(rooms.map(r => [r.room.distribution_id, r]));
  const byService = new Map(rooms.filter(r => r.room.service_id).map(r => [r.room.service_id as string, r]));
  const lastTap = (feeder: string) => Math.max(...rooms.filter(r => r.room.feeder === feeder).map(r => r.cx));
  const wires: Layout['wires'] = [];
  for (const edge of data.edges) {
    let pts: Pt[] | null = null;
    if (edge.kind === 'feeder') {
      const y = FEEDER_Y[edge.to_node];
      pts = [[SOURCE.x + 18, SOURCE.y], [SOURCE.x + 34, SOURCE.y], [SOURCE.x + 34, y], [BREAKER_X + 18, y], [lastTap(edge.to_node), y]];
    } else if (edge.kind === 'distribution' && byDistribution.has(edge.to_node)) {
      const r = byDistribution.get(edge.to_node)!;
      if (r.top) pts = [[r.cx, FEEDER_Y[edge.from_node]], [r.cx, r.panel[1] + 10]];
      else pts = [[r.cx, (r.circuit as Pt)[1] + 8], [r.cx, r.panel[1] - 8]];  // circuit breaker -> classroom panel
    } else if (edge.kind === 'circuit' && byService.has(edge.to_node)) {
      const r = byService.get(edge.to_node)!;
      pts = [[r.cx, FEEDER_Y[edge.from_node]], [r.cx, (r.circuit as Pt)[1] - 8]];
    } else if (edge.kind === 'branch') {
      const a = data.appliances.find(x => x.id === edge.to_node);
      const spot = a && appliances.get(a.id);
      const r = a && roomOf.get(a.room_id);
      if (a && spot && r) {
        const laneX = spot.laneX;
        const start: Pt = r.top ? [r.cx, r.panel[1] - 10] : [r.cx, r.panel[1] + 10];
        const elbowY = r.top ? r.panel[1] - 22 : r.panel[1] + 22;
        const endX = spot.cx - spot.side * 66;
        pts = [start, [laneX, elbowY], [laneX, spot.cy], [endX, spot.cy]];
      }
    }
    if (pts) wires.push({ edge, d: pathD(pts) });
  }
  return { rooms, appliances, wires };
}

function Wire({ edge, d, dim }: { edge: Edge; d: string; dim: boolean }) {
  const style = EDGE_STATE[edge.state];
  return <g className={`ps-wire ${style.className}${dim ? ' is-dim' : ''}`} data-edge={edge.id} data-state={edge.state}>
    <title>{`${edge.from_node} → ${edge.to_node}: ${style.label}${edge.served_w ? `, ${w(edge.served_w)} modeled` : ''}`}</title>
    <path d={d} className="ps-wire-base" />
    {edge.state === 'ENERGIZED' && <path d={d} className="ps-wire-pulse" />}
  </g>;
}

function ApplianceGlyph({ a, x, y, selected, onSelect }: { a: Appliance; x: number; y: number; selected: boolean; onSelect: (id: string) => void }) {
  const st = APPLIANCE_STATE[a.state];
  const label = `${a.name} in ${a.room_id}, ${w(a.demand_w)}, priority ${a.priority_rank}${a.protected ? ' protected' : ''}, ${st.label}`;
  return <g className={`ps-appliance ${st.className}${selected ? ' is-selected' : ''}`} transform={`translate(${x} ${y})`}
    role="button" tabIndex={0} aria-label={label} aria-pressed={selected} data-appliance={a.id} data-state={a.state}
    onClick={() => onSelect(a.id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(a.id); } }}>
    <rect className="ps-appliance-card" x={-66} y={-36} width={132} height={78} rx={8} />
    <g className="ps-appliance-icon" transform="translate(-40 -12) scale(0.95)"><ApplianceIcon kind={a.key} /></g>
    <text className="ps-appliance-name" x={-16} y={-18}>{a.name.length > 15 ? `${a.name.slice(0, 14)}…` : a.name}</text>
    <text className="ps-appliance-meta" x={-16} y={-3}>{w(a.demand_w)}</text>
    <g transform="translate(-16 6)">
      <rect className={`ps-priority${a.protected ? ' is-protected' : ''}`} x={0} y={0} width={a.protected ? 42 : 24} height={14} rx={3} />
      <text className="ps-priority-text" x={4} y={10.5}>{a.protected ? `P${a.priority_rank} 🛡` : `P${a.priority_rank}`}</text>
    </g>
    <text className="ps-appliance-state" x={-60} y={34}>{`${st.glyph} ${st.short}`}</text>
  </g>;
}

export default function FloorPlan({ data, selected, onSelect, highlight }: {
  data: PowerSystem; selected: string | null; onSelect: (id: string) => void; highlight?: string[] }) {
  const layout = useMemo(() => floorPlanLayout(data), [data]);
  const byId = new Map(data.appliances.map(a => [a.id, a]));
  const feeders = new Map(data.feeders.map(f => [f.id, f]));
  const hl = new Set(highlight ?? []);
  const leds = new Map(data.indicators.map(i => [i.room_id, i]));
  return <div className="ps-floorplan-scroll">
    <svg className="ps-floorplan" viewBox={`0 0 ${VIEW.width} ${VIEW.height}`} role="group" aria-label="Floor plan with rooms, appliances and configured wiring">
      <defs>
        <pattern id="ps-grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" className="ps-grid-line" /></pattern>
        <pattern id="ps-grid-major" width="100" height="100" patternUnits="userSpaceOnUse"><rect width="100" height="100" fill="url(#ps-grid)" /><path d="M100 0H0V100" className="ps-grid-major" /></pattern>
        <pattern id="ps-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><path d="M0 0V8" className="ps-hatch-line" /></pattern>
      </defs>
      <rect width={VIEW.width} height={VIEW.height} fill="url(#ps-grid-major)" className="ps-paper" />

      {/* Corridor and wings */}
      <rect x={WING_X} y={HOSP_TOP + ROOM_H} width={ROOM_W * 3} height={CLASS_TOP - HOSP_TOP - ROOM_H} className="ps-corridor" />
      <text className="ps-zone-label" x={WING_X + 8} y={HOSP_TOP + ROOM_H + 22}>Corridor · feeder A runs above, feeder B below</text>
      <text className="ps-wing-label" x={WING_X} y={14}>HOSPITAL WING · FEEDER A</text>
      <text className="ps-wing-label" x={WING_X} y={VIEW.height - 6}>CLASSROOM BLOCK · FEEDER B</text>

      {/* Plant room with the source and feeder breakers */}
      <g className="ps-plant">
        <rect x={PLANT.x} y={PLANT.y} width={PLANT.w} height={PLANT.h} className="ps-room-wall" />
        <text className="ps-room-name" x={PLANT.x + 10} y={PLANT.y + 20}>Plant room</text>
        <circle cx={SOURCE.x} cy={SOURCE.y} r={18} className={`ps-source${data.source.capacity_w > 0 ? '' : ' is-dead'}`} />
        <path d={`M${SOURCE.x - 10} ${SOURCE.y} q5 -9 10 0 t10 0`} className="ps-source-wave" />
        <text className="ps-small" x={PLANT.x + 10} y={PLANT.y + PLANT.h - 28}>{data.source.name}</text>
        <text className="ps-small strong" x={PLANT.x + 10} y={PLANT.y + PLANT.h - 12}>{`${w(data.source.served_w)} of ${w(data.source.capacity_w)}`}</text>
        {['A', 'B'].map(id => {
          const f = feeders.get(id);
          const y = FEEDER_Y[id];
          return f && <g key={id} className={`ps-breaker${f.available ? '' : ' is-open'}`} data-feeder={id}>
            <rect x={BREAKER_X - 14} y={y - 10} width={28} height={20} rx={3} />
            {f.available ? <path d={`M${BREAKER_X - 8} ${y} H${BREAKER_X + 8}`} /> : <path d={`M${BREAKER_X - 8} ${y + 4} L${BREAKER_X + 7} ${y - 7}`} />}
            <text className="ps-small strong" x={BREAKER_X - 40} y={y - 14}>{`Feeder ${id}`}</text>
            <text className={`ps-small ${f.available ? '' : 'danger'}`} x={BREAKER_X - 40} y={y + 24}>{f.available ? `${w(f.served_w)} / ${w(f.limit_w)}` : '✕ OPEN'}</text>
          </g>;
        })}
      </g>

      {/* Rooms */}
      {layout.rooms.map(({ room, x, y, top, panel, circuit }) => {
        const led = leds.get(room.id);
        return <g key={room.id} className={`ps-room${hl.has(room.id) ? ' is-highlight' : ''}`} data-room={room.id}>
          <rect x={x} y={y} width={ROOM_W} height={ROOM_H} className="ps-room-floor" />
          <path className="ps-room-wall" d={top
            ? `M${x} ${y + ROOM_H} V${y} H${x + ROOM_W} V${y + ROOM_H} M${x} ${y + ROOM_H} H${x + 40} M${x + 92} ${y + ROOM_H} H${x + ROOM_W}`
            : `M${x} ${y} V${y + ROOM_H} H${x + ROOM_W} V${y} M${x} ${y} H${x + 40} M${x + 92} ${y} H${x + ROOM_W}`} />
          <path className="ps-door" d={top ? `M${x + 40} ${y + ROOM_H} A52 52 0 0 1 ${x + 92} ${y + ROOM_H - 52}` : `M${x + 40} ${y} A52 52 0 0 0 ${x + 92} ${y + 52}`} />
          <text className="ps-room-name" x={x + 12} y={y + 24}>{room.name}</text>
          <text className="ps-small" x={x + 12} y={y + 40}>{`${w(room.served_w)} of ${w(room.requested_w)} modeled`}</text>
          {room.zone === 'hospital'
            ? <text className={`ps-evidence ev-${room.evidence_status}`} x={x + ROOM_W - 12} y={y + 24} textAnchor="end">{`${room.evidence_status === 'NORMAL' ? '●' : room.evidence_status === 'FAULT_DETECTED' ? '▲' : '?'} ${EVIDENCE_LABEL[room.evidence_status] ?? room.evidence_status}`}</text>
            : <text className="ps-small" x={x + ROOM_W - 12} y={y + 24} textAnchor="end">{room.session ? `Session · ${room.activity_state ?? 'UNKNOWN'}` : 'No session'}</text>}
          {led && <g className={`ps-led${led.commanded ? ' is-on' : ''}`}>
            <circle cx={x + ROOM_W - 18} cy={y + 40} r={5} />
            <text className="ps-small" x={x + ROOM_W - 28} y={y + 44} textAnchor="end">{`Room LED ${led.commanded ? 'on' : 'off'}${led.confirmed == null ? ' (unconfirmed)' : led.confirmed ? ' (ACK)' : ' (no ACK)'}`}</text>
          </g>}
          <g className="ps-panel">
            {top ? <><circle cx={panel[0] - 5} cy={panel[1]} r={7} /><circle cx={panel[0] + 5} cy={panel[1]} r={7} /></>
              : <rect x={panel[0] - 12} y={panel[1] - 8} width={24} height={16} rx={2} />}
            <text className="ps-small" x={panel[0] + 16} y={panel[1] + (top ? 4 : 4)}>{room.distribution_name}</text>
          </g>
          {circuit && <g className="ps-circuit"><rect x={circuit[0] - 9} y={circuit[1] - 8} width={18} height={16} rx={2} />
            <text className="ps-small" x={circuit[0] + 14} y={circuit[1] + 4}>{`Circuit ${room.service_id}`}</text></g>}
        </g>;
      })}

      {/* Wires: one per configured edge */}
      <g className="ps-wires">{layout.wires.map(({ edge, d }) =>
        <Wire key={edge.id} edge={edge} d={d} dim={!!selected && edge.kind === 'branch' && edge.to_node !== selected} />)}</g>

      {/* Appliances */}
      {[...layout.appliances.entries()].map(([id, spot]) => {
        const a = byId.get(id)!;
        return <ApplianceGlyph key={id} a={a} x={spot.cx} y={spot.cy} selected={selected === id} onSelect={onSelect} />;
      })}
    </svg>
  </div>;
}
