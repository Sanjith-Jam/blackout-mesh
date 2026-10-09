import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, AlertTriangle, ArrowDown, Check, CircleHelp, Cpu, Pause, Play, RotateCcw, Server, Shield, Timer, Zap } from 'lucide-react';
import { changeCapacity, changeFeeder, fetchModelStatus, getWebSocketUrl, setReplayAction } from '../api';
import { ActivityPrediction, ModelStatus, Snapshot } from '../types';
import './DemoDashboard.css';

const rooms = [
  { id: 'CR1', name: 'Classroom 01', serviceId: 'L3' },
  { id: 'CR2', name: 'Classroom 02', serviceId: 'L4' },
  { id: 'CR3', name: 'Classroom 03', serviceId: 'L5' },
] as const;

const evaluationFields: Record<string, string> = {
  macro_f1_all_rows_unknown_as_error: 'Macro F1 · unknown as error',
  occupancy_recall_all_rows_unknown_counts_as_miss: 'Occupancy recall · unknown as miss',
  false_inactive_rate_of_occupied: 'False inactive rate',
  coverage: 'Coverage',
  unknown_rate: 'UNKNOWN rate',
};

function modelEvaluation(value: Record<string, unknown> | undefined) {
  if (!value) return null;
  const split = value.test_exploratory ? 'test_exploratory' : value.test ? 'test' : value.validation ? 'validation' : null;
  const selected = split && typeof value[split] === 'object' && value[split] !== null ? value[split] as Record<string, unknown> : null;
  if (!selected) return null;
  return {
    label: split === 'test_exploratory' ? 'TIME-DISJOINT EXPLORATORY TEST' : split === 'test' ? 'TEST' : 'VALIDATION',
    sampleCount: typeof selected.n === 'number' ? selected.n : null,
    scope: typeof value.scope === 'string' ? value.scope : null,
    previouslyInspected: split === 'test_exploratory',
    metrics: Object.entries(evaluationFields).flatMap(([key, label]) => {
      const metric = selected[key];
      return typeof metric === 'number' && Number.isFinite(metric) ? [[label, metric] as [string, number]] : [];
    }),
  };
}

function prediction(snapshot: Snapshot, roomId: string): ActivityPrediction | undefined {
  return snapshot.activity?.[roomId];
}

function servedForMask(snapshot: Snapshot, mask: number) {
  return snapshot.services.filter((service) => {
    const bit = Number(service.id.replace(/^L/, ''));
    return Number.isInteger(bit) && Boolean(mask & (1 << bit));
  });
}

function FlowMap({ snapshot, hidden }: { snapshot: Snapshot; hidden: boolean }) {
  const servedOn = (feeder: 'A' | 'B') => snapshot.services.some((service) => service.feeder === feeder && service.modeled_served);
  const feederA = servedOn('A');
  const feederB = servedOn('B');
  return <div className="mesh-map" data-hidden={hidden} aria-label="Simulated power source connected to two feeders and six services">
    <div className="mesh-source"><span className="mesh-icon"><Zap size={18} /></span><span><b>SIMULATED SOURCE</b><small>{snapshot.source.capacity_w.toLocaleString()} W available</small></span><i /></div>
    <svg className="mesh-wires" viewBox="0 0 1000 180" preserveAspectRatio="none" aria-hidden="true">
      <path className={feederA ? 'wire-on' : 'wire-off'} d="M500 0 V38 Q500 52 485 52 H250 V100" />
      <path className={feederB ? 'wire-on' : 'wire-off'} d="M500 38 Q500 52 515 52 H750 V100" />
      <path className={feederA ? 'wire-on' : 'wire-off'} d="M250 100 V180" /><path className={feederB ? 'wire-on' : 'wire-off'} d="M750 100 V180" />
    </svg>
    <div className="mesh-feeders"><div><span>FEEDER A</span><b>{snapshot.feeder_limits_w.A.toLocaleString()} W limit</b></div><div><span>FEEDER B</span><b>{snapshot.feeder_limits_w.B.toLocaleString()} W limit</b></div></div>
    <div className="mesh-services">
      {snapshot.services.map((item) => {
        const bit = Number(item.id.replace(/^L/, ''));
        const restoring = Boolean(snapshot.proposed_mask & (1 << bit)) && !item.modeled_served;
        return <div className={`mesh-service ${item.modeled_served ? 'is-served' : restoring ? 'is-restoring' : 'is-shed'}`} key={item.id} title={item.model_reason}>
          <span className="service-state-icon">{item.modeled_served ? <Check size={13} /> : restoring ? <Timer size={13} /> : <AlertTriangle size={13} />}</span>
          <b>{item.id}</b><span>{item.name}</span><small>{item.watts.toLocaleString()} W · {item.modeled_served ? 'SERVED' : restoring ? 'RESTORING' : item.requested ? 'SHED' : 'IDLE'}</small>
        </div>;
      })}
    </div>
    <div className="mesh-legend"><span><i className="legend-dot served-dot" /> Simulated served</span><span><i className="legend-dot shed-dot" /> Shed or idle</span><span><i className="legend-dot unknown-dot" /> Unknown evidence</span></div>
  </div>;
}

function EvidenceCard({ room, evidence, service }: { room: typeof rooms[number]; evidence?: ActivityPrediction; service?: Snapshot['services'][number] }) {
  const state = evidence?.state ?? 'UNKNOWN';
  const inputs = evidence?.evidence;
  const observed = (value: number | null | undefined, suffix: string, digits = 1) => value == null ? '—' : `${value.toFixed(digits)}${suffix}`;
  return <article className={`evidence-card evidence-${state.toLowerCase()}`}>
    <div className="evidence-top"><span className="evidence-glyph">{state === 'UNKNOWN' ? <CircleHelp size={17} /> : <Activity size={17} />}</span><span className="eyebrow">{room.id} · VIRTUAL ROOM</span><span className={`state-tag tag-${state.toLowerCase()}`}>{state}</span></div>
    <h3>{room.name}</h3>
    <p className="evidence-reason">{evidence?.reason || 'No current model evidence is available for this room.'}</p>
    <div className="evidence-facts">
      <div><span>Priority</span><b>{evidence?.priority || 'Unassigned'}</b></div>
      <div><span>Model score</span><b>{evidence?.score == null ? '—' : evidence.score.toFixed(3)}</b></div>
      <div><span>Modeled service</span><b>{service?.modeled_served ? 'Served' : service?.requested ? 'Shed' : 'Idle'}</b></div>
    </div>
    <div className="sensor-readings" aria-label="Observed model input values">
      <div><span>Temperature</span><b>{observed(inputs?.temperature_c, '°C')}</b></div>
      <div><span>Humidity</span><b>{observed(inputs?.humidity_pct, '%')}</b></div>
      <div><span>CO₂</span><b>{observed(inputs?.co2_ppm, ' ppm', 0)}</b></div>
      <div><span>Humidity ratio</span><b>{observed(inputs?.humidity_ratio, '', 4)}</b></div>
    </div>
    <div className="evidence-foot"><span>{evidence?.source?.replace(/_/g, ' ') || 'WAITING FOR OBSERVATION'}</span><span>{evidence?.observed_at ? new Date(evidence.observed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'NO TIMESTAMP'}</span></div>
  </article>;
}

export default function DemoDashboard() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [capacityDraft, setCapacityDraft] = useState(14000);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [pageVisible, setPageVisible] = useState(!document.hidden);
  const wsRef = useRef<WebSocket | null>(null);
  const observedCapacity = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    const connect = () => {
      if (!active) return;
      const ws = new WebSocket(getWebSocketUrl());
      wsRef.current = ws;
      ws.onopen = () => { if (active) { setConnected(true); setError(null); } };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as Snapshot;
          if (active) {
            setSnapshot(data);
            setModelStatus(data.model);
            if (observedCapacity.current !== data.source.capacity_w) {
              observedCapacity.current = data.source.capacity_w;
              setCapacityDraft(data.source.capacity_w);
            }
          }
        } catch { if (active) setError('Received an unreadable update from the simulation.'); }
      };
      ws.onerror = () => { if (active) setError('Live connection interrupted. Reconnecting…'); };
      ws.onclose = () => {
        if (!active) return;
        setConnected(false);
        setError('Live connection interrupted. Reconnecting…');
        reconnect = setTimeout(connect, 2500);
      };
    };
    connect();
    const controller = new AbortController();
    fetchModelStatus(controller.signal).then((status) => { if (active) setModelStatus(status); }).catch(() => { if (active) setModelStatus(null); });
    return () => {
      active = false;
      if (reconnect) clearTimeout(reconnect);
      controller.abort();
      wsRef.current?.close();
    };
  }, []);

  useEffect(() => {
    const updateVisibility = () => setPageVisible(!document.hidden);
    document.addEventListener('visibilitychange', updateVisibility);
    return () => document.removeEventListener('visibilitychange', updateVisibility);
  }, []);

  const current = snapshot?.allocation ? servedForMask(snapshot, snapshot.modeled_mask) : [];
  const baseline = useMemo(() => snapshot?.allocation ? servedForMask(snapshot, snapshot.allocation.baseline_mask) : [], [snapshot]);
  const currentWatts = current.reduce((sum, item) => sum + item.watts, 0);
  const baselineWatts = baseline.reduce((sum, item) => sum + item.watts, 0);
  const currentClassrooms = current.filter((item) => ['L3', 'L4', 'L5'].includes(item.id));
  const baselineClassrooms = baseline.filter((item) => ['L3', 'L4', 'L5'].includes(item.id));
  const pendingRestorations = snapshot?.services.filter((service) => {
    const bit = Number(service.id.replace(/^L/, ''));
    return Boolean(snapshot.proposed_mask & (1 << bit)) && !Boolean(snapshot.modeled_mask & (1 << bit));
  }) || [];

  const runAction = async (task: () => Promise<unknown>, message: string) => {
    if (busy) return;
    setBusy(true); setFeedback(null);
    try { await task(); setFeedback(message); }
    catch (cause) { setFeedback(cause instanceof Error ? cause.message : 'Action failed.'); }
    finally { setBusy(false); }
  };

  if (!snapshot) return <main className="console-loading"><Activity size={28} /><h1>Connecting to Blackout Mesh</h1><p>{error || 'Waiting for the simulation snapshot…'}</p><Link to="/">Return to overview</Link></main>;

  const sourceLabel = modelStatus?.data_source?.replace(/_/g, ' ') || 'DATA SOURCE UNAVAILABLE';
  const evaluation = modelEvaluation(modelStatus?.evaluation);

  return <main className="command-center">
    <a className="skip-link" href="#main-content">Skip to command center</a>
    <header className="console-header">
      <Link to="/" className="console-brand" aria-label="Blackout Mesh home"><span className="brand-mark"><Activity size={20} /></span><span>BLACKOUT <b>MESH</b><small>RESILIENCE DECISION SYSTEM</small></span></Link>
      <div className="console-header-right"><span className={`connection-tag ${connected ? 'online' : 'offline'}`}><i />{connected ? 'SIMULATION CONNECTED' : 'RECONNECTING'}</span><span className="hardware-tag"><span>●</span> HARDWARE DISCONNECTED</span><Link className="exit-link" to="/">Overview</Link></div>
    </header>
    {error && <div className="connection-alert" role="status"><AlertTriangle size={16} />{error}</div>}
    <div id="main-content" className="console-main">
      <section className="console-intro"><div><div className="eyebrow intro-label">SOFTWARE SIMULATION <span>·</span> SESSION {String(snapshot.control_revision).padStart(3, '0')}</div><h1>Keep critical systems<br /><em>in the loop.</em></h1><p>Observe room activity, inspect the model’s reasoning, and see how the constrained policy responds when supply changes.</p></div><div className="intro-status"><span className="status-orb"><Activity size={21} /></span><div><b>{modelStatus?.ready ? 'MODEL READY' : 'MODEL FALLBACK'}</b><span>{modelStatus?.model_type || 'Status unavailable'}</span></div></div></section>
      <section className="stat-strip" aria-label="Current simulation metrics">
        <div><span>SIMULATED SUPPLY</span><b>{snapshot.source.capacity_w.toLocaleString()}<small> W</small></b><i>14 kW source model</i></div>
        <div><span>ALLOCATED SERVICES</span><b>{current.length}<small> / {snapshot.services.length}</small></b><i>{currentWatts.toLocaleString()} W modeled served</i></div>
        <div><span>CRITICAL SHORTFALL</span><b className={snapshot.allocation.critical_shortfall_w ? 'text-amber' : ''}>{snapshot.allocation.critical_shortfall_w.toLocaleString()}<small> W</small></b><i>{snapshot.allocation.critical_shortfall_w ? 'Essential demand unmet' : 'Protected demand met'}</i></div>
        <div><span>REPLAY POSITION</span><b>{snapshot.replay.index}<small> / {snapshot.replay.length}</small></b><i>{snapshot.replay.running ? 'Recorded stream advancing' : 'Replay paused'}</i></div>
      </section>

      <div className="console-grid">
        <section className="panel topology-panel"><div className="panel-heading"><div><span className="eyebrow">01 / SYSTEM VIEW</span><h2>Power topology</h2></div><span className="simulation-chip"><span /> VIRTUAL SYSTEM</span></div><FlowMap snapshot={snapshot} hidden={!pageVisible} /><p className="panel-caption">This view shows modeled allocation state. It does not confirm power delivery or physical device acknowledgements.</p><p className={`restoration-caption ${pendingRestorations.length ? "pending" : "clear"}`}><Timer size={14} /> {pendingRestorations.length ? <>{pendingRestorations.length} service{pendingRestorations.length === 1 ? " is" : "s are"} waiting for simulated restoration: {pendingRestorations.map((service) => `${service.name} — ${service.model_reason}`).join("; ")}</> : "Pending restoration: 0 services. No loads are waiting."}</p></section>
        <section className="panel control-panel"><div className="panel-heading"><div><span className="eyebrow">02 / EXPERIMENT</span><h2>Replay controls</h2></div><span className="replay-count">{snapshot.replay.index} / {snapshot.replay.length}</span></div><div className="replay-buttons"><button disabled={busy || snapshot.replay.running} onClick={() => runAction(() => setReplayAction('start'), 'Recorded replay started.')}><Play size={16} /> Start</button><button disabled={busy || !snapshot.replay.running} onClick={() => runAction(() => setReplayAction('pause'), 'Recorded replay paused.')}><Pause size={16} /> Pause</button><button disabled={busy} onClick={() => runAction(() => setReplayAction('reset'), 'Replay reset to the beginning.')}><RotateCcw size={16} /> Reset</button></div><div className="control-divider" /><label className="capacity-label" htmlFor="capacity-range"><span>Simulated source capacity</span><b>{capacityDraft.toLocaleString()} W</b></label><input id="capacity-range" type="range" min="0" max="20000" step="500" value={capacityDraft} onChange={(event) => setCapacityDraft(Number(event.target.value))} /><div className="range-ends"><span>0 W</span><span>20,000 W</span></div><button className="apply-capacity" disabled={busy || capacityDraft === snapshot.source.capacity_w} onClick={() => runAction(() => changeCapacity(capacityDraft), `Simulated source set to ${capacityDraft.toLocaleString()} W.`)}><Zap size={15} /> Apply capacity</button><div className="feeder-control"><b>Feeder faults</b><div>{(['A', 'B'] as const).map((feeder) => <div className="feeder-action-row" key={feeder}><span>Feeder {feeder}</span><button disabled={busy} onClick={() => runAction(() => changeFeeder(feeder, false), `Feeder ${feeder} marked unavailable.`)}>Trip</button><button disabled={busy} onClick={() => runAction(() => changeFeeder(feeder, true), `Feeder ${feeder} restored.`)}>Restore</button></div>)}</div></div>{feedback && <p className="action-feedback" role="status">{feedback}</p>}<p className="control-note">Capacity and feeder controls affect the software model only.</p></section>
      </div>

      <section className="evidence-section"><div className="section-heading"><div><span className="eyebrow">03 / MODEL EVIDENCE</span><h2>What the model sees</h2></div><span className="provenance-label"><span className="provenance-mark">R</span>{sourceLabel}</span></div><div className="evidence-grid">{rooms.map((room) => <EvidenceCard key={room.id} room={room} evidence={prediction(snapshot, room.id)} service={snapshot.services.find((item) => item.id === room.serviceId)} />)}</div></section>

      <div className="bottom-grid"><section className="panel decision-panel"><div className="panel-heading"><div><span className="eyebrow">04 / DECISION TRACE</span><h2>Why this allocation?</h2></div><Shield size={18} /></div><div className="decision-flow"><div><span className="flow-step">01</span><b>OBSERVATION</b><small>{sourceLabel}</small></div><ArrowDown size={15} /><div><span className="flow-step">02</span><b>ACTIVITY ESTIMATE</b><small>Model outputs per-room state and reason</small></div><ArrowDown size={15} /><div><span className="flow-step">03</span><b>PRIORITY POLICY</b><small>{snapshot.allocation.objective || 'Priority objective unavailable'}</small></div><ArrowDown size={15} /><div><span className="flow-step">04</span><b>FEASIBLE ALLOCATION</b><small>{current.length} services · {currentWatts.toLocaleString()} W modeled served</small></div></div><div className="decision-explain"><b>Constraint check</b><span>{snapshot.allocation.critical_shortfall_w ? `${snapshot.allocation.critical_shortfall_w.toLocaleString()} W critical demand could not be served within the current source and feeder limits.` : `Modeled served load is ${currentWatts.toLocaleString()} W against ${snapshot.source.capacity_w.toLocaleString()} W of source capacity.`}</span></div></section>
      <section className="panel compare-panel">
        <div className="panel-heading"><div><span className="eyebrow">05 / SAME SNAPSHOT</span><h2>Policy comparison</h2></div><Cpu size={18} /></div>
        <p className="compare-copy">Current activity-aware policy and fixed-priority baseline use the same observations and modeled limits.</p>
        <div className="compare-row">
          <div><span>FIXED-PRIORITY BASELINE</span><b>{baseline.length}<small> services</small></b><i>{baselineWatts.toLocaleString()} W served</i><i>{baselineClassrooms.length} classroom services · {baselineClassrooms.map((item) => `CR${Number(item.id.slice(1)) - 2}`).join(", ") || "none"}</i></div>
          <div className="compare-divider">VS</div>
          <div><span>ACTIVITY-AWARE MODEL</span><b>{current.length}<small> services</small></b><i>{currentWatts.toLocaleString()} W served</i><i>{currentClassrooms.length} classroom services · {currentClassrooms.map((item) => `CR${Number(item.id.slice(1)) - 2}`).join(", ") || "none"}</i></div>
        </div>
        <div className="compare-note">Classroom service identities are shown for each policy. Outcomes are measured from this same simulation snapshot.</div>
        <div className="measured-metrics">
          <span>MODEL EVALUATION · {evaluation?.label || "NO REPORTED SPLIT"}{evaluation?.sampleCount == null ? "" : ` · n=${evaluation.sampleCount.toLocaleString()}`}</span>
          <p>{evaluation?.scope || sourceLabel} Model metrics describe this office-data proxy; they are not campus-lab accuracy claims.</p>
          {evaluation?.previouslyInspected && <small>Exploratory test: these results were previously inspected and are not a pristine final evaluation.</small>}
          {!evaluation && <small>Evaluation measurements are unavailable.</small>}
          {evaluation?.metrics.map(([key, value]) => <div key={key}><span>{key}</span><b>{(value * 100).toFixed(1)}%</b></div>)}
        </div>
      </section></div>
      <footer className="console-footer"><span><Server size={14} /> Backend-authoritative simulated state</span><span>Recorded office observations replayed as virtual room evidence</span><span>Hardware link: {snapshot.hardware_link.replace(/_/g, ' ')}</span></footer>
    </div>
  </main>;
}
