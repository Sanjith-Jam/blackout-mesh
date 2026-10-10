import type { DistrictSnapshot } from '../types';
import type { DistrictEdge, DistrictEdgeState, DistrictNode } from './DistrictMap';

const w = (value: number | null | undefined) => typeof value === 'number' ? `${value.toLocaleString()} W` : 'Unknown';

/** One compact, read-only answer to "what is this and what does the model say about it?" */
export function inspect(snapshot: DistrictSnapshot, selected: string | null): { title: string; lines: string[] } | null {
  if (!selected) return null;
  const nodes = snapshot.topology.nodes as DistrictNode[];
  const edges = snapshot.topology.edges as (DistrictEdge & { limit_w?: number; rating_a?: number; voltage_v?: number | null })[];
  const node = nodes.find(item => item.id === selected);
  const edge = edges.find(item => item.id === selected);
  if (edge) {
    const state = (snapshot.state.edges as DistrictEdgeState[]).find(item => item.id === edge.id);
    const limit = edge.limit_w;
    const status = state?.faulted ? 'Simulated fault (open)' : state?.closed === false ? 'Open' : state?.energized ? 'Energized' : 'Closed but de-energized';
    const applied = snapshot.state.restoration.applied_edge_ids?.includes(edge.id);
    return { title: `${edge.kind === 'tie' ? 'Declared tie' : 'Synthetic line'} · ${edge.id}`, lines: [
      `${status}${applied ? ' · closed by applied modeled recovery' : ''}.`,
      `Modeled flow ${w(state?.flow_w)} of ${w(limit)} limit${limit && state ? ` (${Math.round(state.flow_w / limit * 100)}%)` : ''}.`,
      `${edge.voltage_v ? `${edge.voltage_v.toLocaleString()} V` : 'Voltage not declared'}${edge.rating_a ? ` · ${edge.rating_a} A rating` : ''} · synthetic rating, not a surveyed cable.`,
    ] };
  }
  if (!node) return { title: selected, lines: ['Cached geography feature. No verified electrical connection.'] };
  if (node.role === 'load') {
    const load = snapshot.state.loads.find(item => item.building_id === node.building_id);
    if (!load) return { title: `Load · ${node.id}`, lines: ['No configured demand.'] };
    const status = load.requested_w <= 0 ? 'Not requesting power' : load.served_w >= load.requested_w ? 'Fully served' : load.served_w > 0 ? 'Partially served' : 'Unserved';
    return { title: `Load · ${load.building_id}`, lines: [
      `${status}: ${w(load.served_w)} of ${w(load.requested_w)} (${w(load.unmet_w)} unmet).`,
      `Tier ${load.tier} · ${load.tier_rationale}`,
      `Grid service ${w(load.grid_served_w)} of ${w(load.grid_requested_w)}; local supply ${w(load.local_supply_w)} (${load.local_supply_semantics}).`,
      ...(load.appliances.length ? [`${load.appliances.filter(item => item.served_w > 0).length} of ${load.appliances.length} mapped appliances served.`] : []),
    ] };
  }
  if (node.role === 'transformer') {
    const transformer = snapshot.state.transformers.find(item => item.component_id === node.id);
    const diagnosis = transformer?.diagnosis;
    return { title: `Synthetic transformer · ${node.id}`, lines: [
      diagnosis?.status === 'SUSPECTED' ? `Suspected ${diagnosis.suspected_part} from simulated observations (not a physical diagnosis).` : 'No fresh evidence supports a suspected area.',
      `Sensor status ${String(transformer?.sensor.status ?? 'unknown')}.`,
    ] };
  }
  return { title: `Synthetic ${node.role} · ${node.id}`, lines: [node.role === 'source' ? `Dispatch limit ${w(snapshot.state.source_capacity_w)} (configured assumption).` : 'Junction in the synthetic topology.'] };
}

export default function DistrictAssetInspector({ snapshot, selected }: { snapshot: DistrictSnapshot; selected: string | null }) {
  const result = inspect(snapshot, selected);
  return <section className="district-risk-card" aria-label="Asset inspector" aria-live="polite">
    {result ? <><h3>{result.title}</h3>{result.lines.map(line => <p key={line}>{line}</p>)}</> : <p>Click a building, line or transformer on the map to inspect it.</p>}
  </section>;
}
