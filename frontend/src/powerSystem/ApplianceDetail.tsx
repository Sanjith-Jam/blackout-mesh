import { APPLIANCE_STATE, w } from './model';
import type { PowerSystem } from './model';

export default function ApplianceDetail({ data, id, onClose, onRequest, disabled }: {
  data: PowerSystem; id: string | null; onClose: () => void; onRequest: (id: string, requested: boolean) => void; disabled: boolean }) {
  const a = id ? data.appliances.find(x => x.id === id) : null;
  if (!a) return <aside className="ps-detail" aria-label="Appliance details"><h3>Appliance details</h3>
    <p className="ps-muted">Select an appliance on the drawing (click, or Tab then Enter) to see its configuration, modeled state, reason and events.</p></aside>;
  const st = APPLIANCE_STATE[a.state];
  return <aside className="ps-detail" aria-label={`Details for ${a.name}`}>
    <header><h3>{a.name}</h3><button className="ps-link" onClick={onClose}>Close</button></header>
    <p className={`ps-state-chip ${st.className}`}>{st.glyph} {st.label}</p>
    <p>{a.reason}</p>
    <dl className="ps-dl">
      <dt>Appliance ID</dt><dd><code>{a.id}</code></dd>
      <dt>Profile asset</dt><dd><code>{a.asset_id}</code></dd>
      <dt>Equipment type</dt><dd>{a.key.replace(/_/g, ' ')}</dd>
      <dt>Room / feeder</dt><dd>{a.room_id} · Feeder {a.feeder} · circuit {a.service_id}</dd>
      <dt>Configured demand</dt><dd>{w(a.demand_w)} <span className="ps-tag tag-example">configured simulated assumption</span></dd>
      <dt>Priority</dt><dd>P{a.priority_rank} · {a.priority_label}{a.protected ? ' · protected' : ''}</dd>
      <dt>Service tier / essential</dt><dd>{a.service_tier} · {a.essential ? 'essential' : 'non-essential'}</dd>
      <dt>Requested state</dt><dd>{a.requested ? 'ON' : 'OFF'}</dd>
      <dt>Optimizer command</dt><dd>{a.commanded ? 'serve' : 'do not serve'}</dd>
      <dt>Modeled state</dt><dd>{st.label} ({w(a.served_w)} modeled)</dd>
      <dt>Reachability</dt><dd>{a.reachable ? 'Path from source closed' : 'No path from source'}</dd>
      <dt>Reason code</dt><dd><code>{a.reason_code}</code></dd>
      <dt>Path</dt><dd>{a.path.join(' → ')}</dd>
      <dt>Dependencies</dt><dd>{a.requires.length ? a.requires.join(', ') : 'none configured'}{a.indivisible_group ? ` · group ${a.indivisible_group}` : ''}</dd>
      <dt>Provenance</dt><dd>Demand: configured · state: modeled · no physical measurement</dd>
    </dl>
    <button disabled={disabled} onClick={() => onRequest(a.id, !a.requested)}>{a.requested ? 'Request off' : 'Request on'}</button>
    <h4>Recent events</h4>
    {a.events.length ? <ul className="ps-changes">{[...a.events].reverse().map(e => <li key={`${e.timestamp}-${e.to}`}>
      <time>{new Date(e.timestamp).toLocaleTimeString()}</time> {e.from_state ?? '—'} → <b>{e.to}</b> <span className="ps-muted">{e.reason}{e.command ? ` · after ${e.command}` : ''}</span></li>)}</ul>
      : <p className="ps-muted">No state changes since this run started.</p>}
  </aside>;
}
