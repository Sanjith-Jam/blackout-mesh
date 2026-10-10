import { AllocationHistory, CapacityBar, TrendChart } from './Charts';
import type { Sample } from './history';
import { OVERALL_LABEL, w } from './model';
import type { PowerSystem } from './model';

export default function Overview({ data, history, onOpenRoom }: { data: PowerSystem; history: Sample[]; onOpenRoom: (room: string) => void }) {
  const overall = (data.diagnosis as { overall: string }).overall;
  const unserved = data.source.requested_w - data.source.served_w;
  const tiles = [
    { label: 'System status', value: OVERALL_LABEL[overall] ?? overall, note: 'Telemetry diagnosis + derived constraint checks', cls: `ov-${overall}` },
    { label: 'Source capacity', value: w(data.source.capacity_w), note: `Configured normal ${w(data.source.normal_capacity_w)} · simulated` },
    { label: 'Requested demand', value: w(data.source.requested_w), note: 'Configured demand of appliances requested ON' },
    { label: 'Modeled supply', value: w(data.source.served_w), note: 'Applied optimizer decision · not a measurement' },
    { label: 'Unserved demand', value: w(unserved), note: unserved > 0 ? 'Shed, pending or unreachable' : 'Every request is served' },
    { label: 'Active faults', value: String(data.faults.length), note: data.faults.map(f => f.kind.replace(/_/g, ' ').toLowerCase()).join(', ') || 'None injected' },
  ];
  const appEvents = data.appliance_events.slice(-6).reverse();
  return <section className="ps-overview" aria-label="Overview">
    <div className="ps-tiles">{tiles.map(t => <div key={t.label} className={`ps-tile ${t.cls ?? ''}`}><span>{t.label}</span><strong>{t.value}</strong><small>{t.note}</small></div>)}</div>
    <div className="ps-grid-2">
      <TrendChart title="Requested demand vs available capacity vs modeled supply" provenance="CONFIGURED + MODELED · sampled 1/s from backend"
        samples={history} series={[
          { label: 'Capacity', className: 'line-capacity', values: history.map(s => s.capacity), dashed: true },
          { label: 'Requested', className: 'line-requested', values: history.map(s => s.requested) },
          { label: 'Modeled served', className: 'line-served', values: history.map(s => s.served) }]} />
      <TrendChart title="Per-feeder demand and limit" provenance="CONFIGURED + MODELED · limit is 0 W while a feeder is open"
        samples={history} series={[
          { label: 'Feeder A limit', className: 'line-a-limit', values: history.map(s => s.feeders.A?.limit ?? null), dashed: true },
          { label: 'Feeder A served', className: 'line-a', values: history.map(s => s.feeders.A?.served ?? null) },
          { label: 'Feeder B limit', className: 'line-b-limit', values: history.map(s => s.feeders.B?.limit ?? null), dashed: true },
          { label: 'Feeder B served', className: 'line-b', values: history.map(s => s.feeders.B?.served ?? null) }]} />
    </div>
    <div className="ps-grid-2">
      <AllocationHistory samples={history} />
      <div className="ps-card"><h3>Capacity margins</h3>{data.constraint_checks.filter(c => c.scope !== 'zone').map(c =>
        <CapacityBar key={c.id} label={c.label} requested={c.requested_w} limit={c.limit_w} served={c.served_w}
          open={c.scope === 'feeder' && !data.feeders.find(f => `feeder:${f.id}` === c.id)?.available} />)}</div>
    </div>
    <div className="ps-grid-2">
      <div className="ps-card"><h3>Rooms</h3>
        <div className="ps-table-scroll"><table className="ps-table"><thead><tr><th>Room</th><th>Feeder</th><th>Served / requested</th><th>Evidence</th></tr></thead>
          <tbody>{data.rooms.map(r => <tr key={r.id}><th><button className="ps-link" onClick={() => onOpenRoom(r.id)}>{r.name}</button></th><td>{r.feeder}</td>
            <td>{w(r.served_w)} / {w(r.requested_w)}</td><td>{r.zone === 'hospital' ? r.evidence_status : r.session ? `session · ${r.activity_state}` : 'no session'}</td></tr>)}</tbody></table></div></div>
      <div className="ps-card"><h3>Recent events</h3>
        <ol className="ps-timeline">{[...data.events].reverse().slice(0, 6).map((e, i) => <li key={`${String(e.timestamp)}-${i}`}><time>{new Date(String(e.timestamp)).toLocaleTimeString()}</time> <b>{String(e.type)}</b> {String(e.description)}</li>)}
          {appEvents.map(e => <li key={`${e.timestamp}-${e.appliance_id}-${e.to}`}><time>{new Date(e.timestamp).toLocaleTimeString()}</time> <b>{e.appliance_id}</b> {e.from_state ?? '—'} → {e.to}</li>)}</ol>
        {data.events.length === 0 && appEvents.length === 0 && <p className="ps-muted">No events yet in this run.</p>}</div>
    </div>
  </section>;
}
