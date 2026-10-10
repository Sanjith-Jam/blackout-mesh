import { PowerEdge, PowerEdgeState } from '../types';

/** Short text for each edge state, so status never depends on colour alone (#23). */
export const EDGE_LABEL: Record<PowerEdgeState, string> = {
  ENERGIZED: 'ON',
  PENDING_RESTORATION: 'WAIT',
  SHED: 'OFF',
  OPEN: 'OPEN',
  UNKNOWN: '?',
};

const EDGE_TEXT: Record<PowerEdgeState, string> = {
  ENERGIZED: 'energized (modeled)',
  PENDING_RESTORATION: 'restoring: commanded, waiting for the restoration delay',
  SHED: 'shed by the allocator',
  OPEN: 'open: no path from the supply',
  UNKNOWN: 'unknown: evidence missing or diagnosis abstained',
};

export function edgeIndex(edges: PowerEdge[] | undefined): Record<string, PowerEdge> {
  return Object.fromEntries((edges ?? []).map(edge => [edge.id, edge]));
}

export function describeEdge(edge: PowerEdge | undefined): string {
  if (!edge) return 'No edge data for this path.';
  const watts = `${edge.served_w.toLocaleString()} of ${edge.requested_w.toLocaleString()} ${edge.unit} ${edge.provenance.toLowerCase()}`;
  const observed = edge.observed ? ` Observed ${edge.observed.output_voltage_v ?? '—'} V (${edge.observed.provenance.toLowerCase().replace(/_/g, ' ')}); ${edge.observed.note}` : '';
  return `${EDGE_TEXT[edge.state]}. ${edge.reason}. ${watts}. Hardware: ${edge.physical.toLowerCase().replace(/_/g, ' ')}.${observed}`;
}

type WireProps = { edge: PowerEdge | undefined; d: string; main?: boolean; live: boolean };

/** One drawn wire for one canonical edge. Only ENERGIZED edges animate, and only while the feed is live. */
export function PowerWire({ edge, d, main = false, live }: WireProps) {
  const state: PowerEdgeState = edge?.state ?? 'UNKNOWN';
  return <g data-edge-id={edge?.id ?? 'missing'} data-state={state}
            className={`power-map__circuit state-${state} ${main ? 'is-main' : ''}`}>
    <title>{describeEdge(edge)}</title>
    <path className="power-map__cable-bed" d={d} />
    <path className="power-map__cable" d={d} />
    {state === 'ENERGIZED' && live && <path className="power-map__current" d={d} />}
  </g>;
}

export function EdgeLegend({ stale }: { stale: boolean }) {
  return <div className="power-map__legend" aria-label="Path states">
    <span><i className="live" />Energized</span>
    <span><i className="pending" />Restoring</span>
    <span><i />Shed</span>
    <span><i className="open" />Open</span>
    <span><i className="unknown" />Unknown</span>
    {stale && <span className="power-map__stale-note">Connection lost: showing last known state, not live</span>}
  </div>;
}

export const EDGE_FOOTNOTE = 'Watts are modeled allocation values, not measured current. Moving pulses are decorative: their speed does not represent power.';
