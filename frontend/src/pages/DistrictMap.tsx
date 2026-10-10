import { useState } from 'react';

export type DistrictFeature = {
  id: string;
  kind: 'road' | 'building';
  name: string | null;
  geometry_type: string;
  paths: { coordinates: number[][] }[];
};
export type DistrictNode = { id: string; role: string; lon: number; lat: number; building_id?: string | null };
export type DistrictEdge = { id: string; from: string; to: string; kind: string };
export type DistrictEdgeState = { id: string; closed: boolean; faulted: boolean; energized: boolean; flow_w: number };

type Props = {
  features: DistrictFeature[];
  nodes: DistrictNode[];
  edges: DistrictEdge[];
  edgeStates: DistrictEdgeState[];
  selected: string | null;
  onSelect: (id: string) => void;
  mode: 'shift' | 'energy' | 'healing' | 'transformers';
};

const WIDTH = 1000;
const HEIGHT = 700;
const PAD = 38;

export default function DistrictMap({ features, nodes, edges, edgeStates, selected, onSelect, mode }: Props) {
  const [extent, setExtent] = useState<'network' | 'area'>('network');
  const points = extent === 'network' ? nodes.map(n => [n.lon, n.lat]) : features.flatMap(f => f.paths.flatMap(p => p.coordinates)).concat(nodes.map(n => [n.lon, n.lat]));
  const lons = points.map(p => p[0]);
  const lats = points.map(p => p[1]);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const cos = Math.cos(((minLat + maxLat) / 2) * Math.PI / 180);
  const mapW = Math.max((maxLon - minLon) * cos, 0.00001);
  const mapH = Math.max(maxLat - minLat, 0.00001);
  const scale = Math.min((WIDTH - 2 * PAD) / mapW, (HEIGHT - 2 * PAD) / mapH);
  const offsetX = (WIDTH - mapW * scale) / 2;
  const offsetY = (HEIGHT - mapH * scale) / 2;
  const project = (lon: number, lat: number) => [offsetX + (lon - minLon) * cos * scale, HEIGHT - offsetY - (lat - minLat) * scale];
  const line = (coords: number[][]) => coords.map(([lon, lat], i) => `${i ? 'L' : 'M'}${project(lon, lat).join(' ')}`).join(' ');
  const geometry = (feature: DistrictFeature) => feature.paths.map(part => line(part.coordinates) + (feature.kind === 'building' ? ' Z' : '')).join(' ');
  const nodesById = new Map(nodes.map(n => [n.id, n]));
  const statesById = new Map(edgeStates.map(e => [e.id, e]));
  const activate = (event: React.KeyboardEvent<SVGElement>, id: string) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(id); }
  };

  return <div className="district-map">
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="group" aria-label="GNITC map. Cached OpenStreetMap geography with a synthetic electrical network.">
      <title>GNITC district map and selectable synthetic electrical assets</title>
      <rect width={WIDTH} height={HEIGHT} fill="#e8eee2" pointerEvents="none" />
      {features.filter(f => f.kind === 'road').map(f => <path key={f.id} className="road" d={geometry(f)} />)}
      {features.filter(f => f.kind === 'building').map(f => <path key={f.id} d={geometry(f)} className={`building${selected === f.id ? ' is-selected' : ''}`}
        role="button" tabIndex={0} aria-pressed={selected === f.id} aria-label={`${f.name || 'Building'} · cached map feature`} onClick={() => onSelect(f.id)} onKeyDown={e => activate(e, f.id)} />)}
      {edges.map(e => {
        const a = nodesById.get(e.from), b = nodesById.get(e.to);
        if (!a || !b) return null;
        const state = statesById.get(e.id);
        const [x1, y1] = project(a.lon, a.lat), [x2, y2] = project(b.lon, b.lat);
        return <g key={e.id}>
          <path d={`M${x1} ${y1} L${x2} ${y2}`} className={`wire${e.kind === 'tie' ? ' is-tie' : ''}${state?.faulted ? ' is-faulted' : state?.closed === false ? ' is-open' : ''}${selected === e.id ? ' is-selected' : ''}`} />
        </g>;
      })}
      {edges.map(e => {
        const a = nodesById.get(e.from), b = nodesById.get(e.to);
        if (!a || !b) return null;
        const state = statesById.get(e.id);
        const [x1, y1] = project(a.lon, a.lat), [x2, y2] = project(b.lon, b.lat);
        return <g key={`hit-${e.id}`} className="edge-hit" role="button" tabIndex={0}
          aria-pressed={selected === e.id}
          aria-label={`${e.id} · ${e.kind} · ${state?.faulted ? 'faulted' : state?.closed === false ? 'open' : state?.energized ? 'energized' : 'unenergized'}`}
          onClick={() => onSelect(e.id)} onKeyDown={event => activate(event, e.id)}>
          <path d={`M${x1} ${y1} L${x2} ${y2}`} stroke="transparent" strokeWidth="18" fill="none" pointerEvents="stroke" />
        </g>;
      })}
      {nodes.map(n => {
        const [x, y] = project(n.lon, n.lat);
        const radius = n.role === 'junction' ? 2.5 : n.role === 'load' ? 5 : 9;
        return <g key={n.id} className="node-hit" role="button" tabIndex={0} aria-pressed={selected === n.id} aria-label={`${n.id} · synthetic ${n.role}`}
          onClick={() => onSelect(n.id)} onKeyDown={event => activate(event, n.id)}>
          <circle cx={x} cy={y} r={Math.max(radius + 15, 24)} fill="transparent" pointerEvents="all" />
          {n.role === 'source' ? <path d={`M${x} ${y - radius} L${x + radius} ${y} L${x} ${y + radius} L${x - radius} ${y} Z`} className={`node is-source${selected === n.id ? ' is-selected' : ''}`} />
            : n.role === 'transformer' ? <rect x={x - radius} y={y - radius} width={radius * 2} height={radius * 2} rx="2" className={`node is-transformer${selected === n.id ? ' is-selected' : ''}`} />
              : <circle cx={x} cy={y} r={radius} className={`node is-${n.role}${selected === n.id ? ' is-selected' : ''}`} />}
          {(n.role === 'source' || n.role === 'transformer' || selected === n.id) && <text x={x + 12} y={y - 9} className="map-label">{n.role === 'source' ? 'Source' : n.role === 'transformer' ? `TX ${nodes.filter(item => item.role === 'transformer').indexOf(n) + 1}` : n.role === 'load' ? `Load ${nodes.filter(item => item.role === 'load').indexOf(n) + 1}` : 'Junction'}</text>}
        </g>;
      })}
      <text x={WIDTH - 46} y={45} textAnchor="middle" className="map-label">N ↑</text>
    </svg>
    <p className="district-map-note">{mode === 'shift' ? 'Cached streets and buildings · SHIFT generated electrical topology' : mode === 'energy' ? 'Synthetic demand, PV and battery model on the same district' : mode === 'healing' ? 'Red = simulated fault · dashed = open or declared tie' : 'Select a transformer to inspect simulated observations'}</p>
    <div className="district-map-tools" role="group" aria-label="Map extent"><button type="button" aria-pressed={extent === 'network'} onClick={() => setExtent('network')}>Fit network</button><button type="button" aria-pressed={extent === 'area'} onClick={() => setExtent('area')}>Full area</button></div>
  </div>;
}

