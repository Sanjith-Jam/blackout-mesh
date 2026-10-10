import { useState } from 'react';
import { CapacityLaw, ContinuityLaw } from './ElectricalLaws';
import { EVIDENCE_LABEL, OVERALL_LABEL, w } from './model';
import type { PowerSystem } from './model';

export interface FaultActions {
  killFeeder: (id: string) => void;
  restoreFeeder: (id: string) => void;
  dropCapacity: () => void;
  restoreCapacity: () => void;
  injectDropout: () => void;
  clearHospitalFault: () => void;
}

type Incident = { id: string; title: string; kind: 'open' | 'capacity' | 'missing' | 'other'; rooms: string[] };

export function incidentsOf(data: PowerSystem): Incident[] {
  const out: Incident[] = [];
  for (const f of data.faults) {
    if (f.kind === 'FEEDER_OPEN') out.push({ id: f.id, title: `Feeder ${f.target} outage`, kind: 'open',
      rooms: data.rooms.filter(r => r.feeder === f.target).map(r => r.id) });
    else if (f.kind === 'CAPACITY_REDUCED' || f.kind === 'ZONE_BUDGET_REDUCED') out.push({ id: f.id, title: f.description, kind: 'capacity',
      rooms: [...new Set(data.appliances.filter(a => a.state === 'SHED').map(a => a.room_id))] });
    else if (f.kind === 'SENSOR_DROPOUT' || f.kind === 'STUCK_SENSOR') out.push({ id: f.id, title: f.description, kind: 'missing', rooms: [f.target] });
    else out.push({ id: f.id, title: f.description, kind: 'other', rooms: [f.target] });
  }
  return out;
}

export default function FaultDetection({ data, actions, disabled, feedback, onShowOnPlan }: {
  data: PowerSystem; actions: FaultActions; disabled: boolean; feedback: { text: string; error: boolean } | null;
  onShowOnPlan: (rooms: string[]) => void }) {
  const feederA = data.feeders.find(f => f.id === 'A')!, feederB = data.feeders.find(f => f.id === 'B')!;
  const reduced = data.source.capacity_w < data.source.normal_capacity_w;
  const incidents = incidentsOf(data);
  const [chosen, setChosen] = useState<string | null>(null);
  const incident = incidents.find(i => i.id === chosen) ?? incidents[0] ?? null;
  const diag = data.diagnosis as { overall: string; campus: { status: string; detail: string; hypotheses: Array<Record<string, unknown>>; evaluated_at: string | null; inputs: string };
    transformers: Array<{ zone: string; status: string; diagnosis?: Record<string, unknown> }> };
  const opt = data.optimizer as { solver: string; status: string; stages: Array<{ stage: string; status: string }>; solve_ms: number; validated: boolean;
    proposed_violations: string[]; applied_violations: string[]; restoration: { stable_for_s: number | null; stable_required_s?: number } };
  const notServed = data.appliances.filter(a => a.state !== 'SERVED');
  const byReason = new Map<string, typeof notServed>();
  for (const a of notServed) byReason.set(a.reason_code, [...(byReason.get(a.reason_code) ?? []), a]);
  const pending = data.appliances.filter(a => a.state === 'PENDING_RESTORATION');
  const hyps = diag.campus.hypotheses;
  const exceeded = data.constraint_checks.filter(c => c.exceeded);

  const steps: { label: string; value: string; ok?: boolean }[] = [
    { label: 'Fault input', value: data.faults.length ? data.faults.map(f => f.description).join(' ') : 'No injected fault' },
    { label: 'State update', value: `Source ${w(data.source.capacity_w)} · feeder A ${feederA.available ? 'closed' : 'OPEN'} · feeder B ${feederB.available ? 'closed' : 'OPEN'} · revision ${data.site.revision}` },
    { label: 'Observation validation', value: diag.campus.evaluated_at ? `Bus/feeder telemetry window evaluated ${new Date(diag.campus.evaluated_at).toLocaleTimeString()}` : 'No telemetry evaluated', ok: !!diag.campus.evaluated_at },
    { label: 'Fault detection', value: hyps.length ? hyps.map(h => `${h.code} at ${h.asset_id} (${h.confirmation})`).join('; ') : `No hypothesis (${diag.campus.status})` },
    { label: 'Diagnosis', value: `${OVERALL_LABEL[diag.overall] ?? diag.overall}: ${diag.campus.detail}` },
    { label: 'Optimization', value: `${opt.solver}: ${opt.status}, ${opt.stages.length} lexicographic stages, ${opt.solve_ms} ms`, ok: opt.status === 'OPTIMAL' },
    { label: 'Constraint validation', value: opt.validated ? 'Proposed and applied plans pass every hard constraint' : [...opt.proposed_violations, ...opt.applied_violations].join('; '), ok: opt.validated },
    { label: 'Modeled state update', value: `${data.appliances.filter(a => a.state === 'SERVED').length} served, ${pending.length} pending, ${data.appliances.filter(a => a.state === 'SHED').length} shed, ${data.appliances.filter(a => a.state === 'UNREACHABLE').length} unreachable · ${w(data.source.served_w)} modeled` },
    { label: 'Event recording', value: data.events.length ? `${data.events[data.events.length - 1].type}: ${data.events[data.events.length - 1].description}` : 'No events yet' },
  ];

  return <section className="ps-faults" aria-label="Fault detection">
    <div className="ps-card" role="group" aria-label="Fault Lab controls">
      <h3>Fault Lab</h3>
      <p className="ps-muted">Every button sends one command to the backend. The page shows only what the backend returns.</p>
      <div className="ps-buttons">
        <button disabled={disabled || !feederA.available} onClick={() => actions.killFeeder('A')}>Kill Feeder A</button>
        <button disabled={disabled || feederA.available} onClick={() => actions.restoreFeeder('A')}>Restore Feeder A</button>
        <button disabled={disabled || reduced} onClick={actions.dropCapacity}>Drop Capacity · 6,000 W</button>
        <button disabled={disabled || !reduced} onClick={actions.restoreCapacity}>Restore Capacity · {w(data.source.normal_capacity_w)}</button>
        <button disabled={disabled || !feederB.available} onClick={() => actions.killFeeder('B')}>Kill Feeder B</button>
        <button disabled={disabled || feederB.available} onClick={() => actions.restoreFeeder('B')}>Restore Feeder B</button>
        <button disabled={disabled} onClick={actions.injectDropout}>ICU sensor dropout</button>
        <button disabled={disabled || !data.faults.some(f => f.id.startsWith('hospital:'))} onClick={actions.clearHospitalFault}>Clear hospital fault</button>
      </div>
      <p className={`ps-feedback${feedback?.error ? ' is-error' : ''}`} role={feedback?.error ? 'alert' : 'status'}>{feedback?.text ?? 'Inject a fault to see the pipeline respond.'}</p>
    </div>

    <div className="ps-grid-2">
      <div className="ps-card" aria-label="Injected simulation inputs" role="region">
        <h3>What was injected</h3>
        <p className="ps-muted">Simulation inputs (ground truth). The diagnosis cannot read these; it sees telemetry only.</p>
        {data.faults.length ? <ul className="ps-list">{data.faults.map(f => <li key={f.id}><b>{f.kind.replace(/_/g, ' ')}</b> · {f.description} <span className="ps-tag tag-example">{f.provenance}</span></li>)}</ul>
          : <p>No injected faults are active.</p>}
      </div>
      <div className="ps-card" aria-label="Backend diagnosis" role="region">
        <h3>Backend diagnosis</h3>
        <p className={`ps-overall ov-${diag.overall}`}>{OVERALL_LABEL[diag.overall] ?? diag.overall}</p>
        <p><b>Campus:</b> {diag.campus.status} · {diag.campus.detail}</p>
        {hyps.map(h => <div key={String(h.id)} className="ps-hypothesis">
          <p><b>{String(h.code)}</b> at {String(h.asset_id)} · {String(h.confirmation)} · {String(h.sufficiency)}</p>
          <p className="ps-muted">Evidence: {(h.supporting_evidence as string[] | undefined)?.join(' ') || 'none'}</p>
          <p className="ps-muted">Next check: {String(h.recommendation)}</p></div>)}
        <ul className="ps-list">{diag.transformers.map(t => <li key={t.zone}><b>{t.zone}</b> transformer: {EVIDENCE_LABEL[t.status] ?? t.status}
          {t.diagnosis && typeof t.diagnosis.cause === 'string' ? ` · ${t.diagnosis.cause}` : ''}</li>)}</ul>
        {exceeded.length > 0 && <p><b>Constraint checks:</b> {exceeded.map(c => `${c.label}: requested ${w(c.requested_w)} > limit ${w(c.limit_w)}`).join('; ')} <span className="ps-tag tag-derived">DERIVED</span></p>}
        <p className="ps-muted">{diag.campus.inputs}</p>
      </div>
    </div>

    <div className="ps-card" role="region" aria-label="Fault to UI pipeline">
      <h3>Fault → diagnosis → allocation pipeline (live)</h3>
      <ol className="ps-pipeline">{steps.map(s => <li key={s.label} className={s.ok === false ? 'is-bad' : ''}><b>{s.label}</b><span>{s.value}</span></li>)}</ol>
    </div>

    <div className="ps-grid-2">
      <div className="ps-card" role="region" aria-label="Affected loads">
        <h3>Affected loads</h3>
        {notServed.length === 0 ? <p>Every requested appliance is served in the model.</p> :
          [...byReason.entries()].map(([code, list]) => <details key={code} open={list.length <= 6}>
            <summary><b>{code.replace(/_/g, ' ')}</b> · {list.length} appliance{list.length === 1 ? '' : 's'} · {w(list.reduce((s, a) => s + a.demand_w, 0))}</summary>
            <ul className="ps-list">{list.map(a => <li key={a.id}>{a.room_id} · {a.name} ({w(a.demand_w)}, P{a.priority_rank}) <span className="ps-muted">{a.reason}</span></li>)}</ul>
          </details>)}
      </div>
      <div className="ps-card" role="region" aria-label="Allocation response and recovery">
        <h3>Allocation response and recovery</h3>
        <p>{w(data.source.served_w)} of {w(data.source.requested_w)} requested is served within {w(data.source.capacity_w)} capacity.</p>
        <p>Optimizer: <b>{opt.status}</b> · validated: <b>{opt.validated ? 'yes' : 'no'}</b></p>
        {pending.length > 0 ? <p>{pending.length} appliance{pending.length === 1 ? '' : 's'} wait for the restoration gate: constraints stable for {opt.restoration.stable_for_s ?? '—'} s of the {opt.restoration.stable_required_s ?? 5} s required, then one priority group per second.</p>
          : <p className="ps-muted">No appliance is waiting for restoration.</p>}
        <p className="ps-muted">Recovery changes the simulated state only. It does not claim a physical fault was repaired, and restoring one fault never clears another.</p>
      </div>
    </div>

    <div className="ps-card" role="region" aria-label="Relevant electrical principle">
      <h3>Relevant electrical principle</h3>
      {incidents.length > 1 && <div className="ps-segmented" role="radiogroup" aria-label="Choose an incident">{incidents.map(i =>
        <button key={i.id} role="radio" aria-checked={incident?.id === i.id} className={incident?.id === i.id ? 'is-active' : ''} onClick={() => setChosen(i.id)}>{i.title}</button>)}</div>}
      {incident ? <>
        <p><b>{incident.title}.</b> {incident.kind === 'open' ? 'Continuity: with the feeder open there is no closed path, so the downstream appliances are unreachable regardless of capacity.'
          : incident.kind === 'capacity' ? 'Capacity: requested demand is compared with the configured limit; the optimizer sheds the lowest-priority appliances until served power fits.'
          : incident.kind === 'missing' ? 'Missing telemetry: the sensor stopped reporting, so the diagnosis abstains. Lost data is not evidence of an electrical failure.'
          : 'See the electrical laws for the relationship behind this incident.'}</p>
        {incident.rooms.length > 0 && <button className="ps-link" onClick={() => onShowOnPlan(incident.rooms)}>Show {incident.rooms.join(', ')} on the floor plan</button>}
        {incident.kind === 'capacity' ? <CapacityLaw data={data} emphasis /> : <ContinuityLaw data={data} emphasis={incident.kind === 'missing' ? 'missing' : 'open'} />}
      </> : <><p>No incident is active. The capacity relationship below shows the live margins.</p><CapacityLaw data={data} /></>}
    </div>

    <div className="ps-card" role="region" aria-label="Fault and recovery timeline">
      <h3>Fault and recovery timeline</h3>
      <ol className="ps-timeline">{[...data.events].reverse().slice(0, 14).map((e, i) => <li key={`${String(e.timestamp)}-${i}`}>
        <time>{new Date(String(e.timestamp)).toLocaleTimeString()}</time> <b>{String(e.type)}</b> {String(e.description)}</li>)}</ol>
    </div>
  </section>;
}
