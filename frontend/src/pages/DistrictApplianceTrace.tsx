import type { DistrictSnapshot } from '../types';

type Props = { snapshot: DistrictSnapshot; selected: string | null };

export default function DistrictApplianceTrace({ snapshot, selected }: Props) {
  if (!snapshot.profile.appliance_count) return null;
  const adjacentEdges = snapshot.topology.edges.filter(edge => edge.from === selected || edge.to === selected).map(edge => edge.id);
  const loads = snapshot.state.loads.filter(load => load.building_id === selected
    || `load:${load.building_id}` === selected
    || load.appliances.some(item => item.path_edge_ids.some(edge => adjacentEdges.includes(edge))));
  return <section aria-label="Mapped appliance decisions">
    <h3>Mapped appliances · revision {snapshot.identity.revision}</h3>
    <p>{snapshot.profile.id}: {snapshot.profile.appliance_count} appliances. {snapshot.profile.decision.status}; independent watt-budget validation {snapshot.profile.decision.validation}. Physical confirmation: unknown. No PV/storage placement is configured.</p>
    {!loads.length ? <p>Select a mapped building or transformer to trace appliance decisions.</p> : loads.map(load => <div key={load.building_id}>
      <h4>{load.building_id}: {load.served_w} / {load.requested_w} W served</h4>
      <p>{load.tier_rationale}</p>
      <div className="district-data-table"><table><caption>Appliances at {load.building_id}</caption>
        <thead><tr><th>Appliance / service</th><th>Rated maximum</th><th>Requested</th><th>Served</th><th>Evidence / priority</th></tr></thead>
        <tbody>{load.appliances.map(item => <tr key={item.id}><th>{item.id}<small>{item.service_id}</small></th><td>{item.rated_max_w} W</td><td>{item.requested_w} W</td><td>{item.served_w} W</td><td>{item.reachable ? 'Source reachable' : 'Source unreachable'} · {item.priority_class}</td></tr>)}</tbody>
      </table></div>
    </div>)}
  </section>;
}
