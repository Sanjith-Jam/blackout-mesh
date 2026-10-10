import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { districtAction, generateDistrictTopology, getDistrictSnapshot, ApiError } from '../api';
import type { DistrictActionName, DistrictSnapshot } from '../types';
import DistrictMap, { type LoadStatus, type DistrictEdge, type DistrictEdgeState, type DistrictFeature, type DistrictNode } from './DistrictMap';
import './DistrictDemo.css';
import DistrictApplianceTrace from './DistrictApplianceTrace';
import DistrictRecoveryProposal from './DistrictRecoveryProposal';
import DistrictAuditReplay from './DistrictAuditReplay';

const TABS = [
  { id: 'shift', label: 'SHIFT network' }, { id: 'energy', label: 'Energy' },
  { id: 'healing', label: 'Self-healing' }, { id: 'transformers', label: 'Transformers' },
] as const;
type Tab = typeof TABS[number]['id'];
const QUERY_KEY = ['district-study'];
const EMERGENCY_EDGE = 'edge:junction:78.6583934:17.1624340:junction:78.6584455:17.1615332';

function Kpi({ label, value }: { label: string; value: string }) {
  return <div className="district-kpi"><span>{label}</span><strong>{value}</strong></div>;
}

function number(value: unknown, unit: string) {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toLocaleString()} ${unit}` : 'Unknown';
}

export function transformerReading(sensor: DistrictSnapshot['state']['transformers'][number]['sensor'], field: string, unit: string) {
  const reading = number(sensor[field], unit);
  return sensor.status === 'STALE' && reading !== 'Unknown'
    ? <><span>Unknown</span><small>Stale last reading: {reading}</small></> : reading;
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 409) return 'State changed before this action was applied. The latest snapshot has been refreshed.';
  if (error instanceof ApiError) return `Refused: ${error.message}`;
  return error instanceof Error ? error.message : 'District action failed.';
}

function generationMessage(snapshot: DistrictSnapshot) {
  const { generation, topology } = snapshot;
  if (generation.status === 'GENERATING') return 'Topology generation started; waiting for the backend result.';
  if (generation.status === 'GENERATED') return `Topology generated: ${topology.nodes.length} nodes and ${topology.edges.length} edge${topology.edges.length === 1 ? '' : 's'}.`;
  if (generation.status === 'FAILED') return `Topology generation failed: ${generation.reason || 'the backend could not generate a topology.'}`;
  if (generation.status === 'UNAVAILABLE') return `Topology generation unavailable: ${generation.reason || 'the optional runtime is unavailable.'}`;
  return `Topology status: ${generation.status}.`;
}

export function generationTransitionFeedback(previousStatus: string | undefined, snapshot: DistrictSnapshot) {
  return previousStatus === 'GENERATING' && snapshot.generation.status !== 'GENERATING'
    ? generationMessage(snapshot) : null;
}

export function clearFaultGate(selectedEdgeId: string | null, faultedEdgeIds: string[], evidenceReady: boolean, evidenceCount: number, rule = 'fresh healthy observations') {
  const isCurrentFault = selectedEdgeId !== null && faultedEdgeIds.includes(selectedEdgeId);
  const count = Number.isFinite(evidenceCount) ? Math.max(0, evidenceCount) : 0;
  return {
    enabled: isCurrentFault && evidenceReady,
    reason: !selectedEdgeId ? 'Select a currently faulted line to clear it.'
      : !isCurrentFault ? 'The selected line is not currently listed as faulted.'
        : !evidenceReady ? `Clear fault requires ${rule}; ${count} healthy sample${count === 1 ? '' : 's'} recorded. Record simulated observations to continue.`
          : 'The evidence gate is satisfied; this fault can be cleared in the modeled state.',
  };
}

export function observationRequest(lastSequence: number | null | undefined, healthy: boolean, now = new Date()) {
  return { sequence: (lastSequence ?? 0) + 1, observed_at: now.toISOString(), healthy, source: 'SIMULATED_OBSERVATION_ADAPTER' as const };
}

export function loadStatuses(nodes: DistrictNode[], loads: DistrictSnapshot['state']['loads']) {
  const byBuilding = new Map(loads.map(load => [load.building_id, load]));
  const result: Record<string, LoadStatus> = {};
  for (const node of nodes) {
    const load = node.building_id ? byBuilding.get(node.building_id) : undefined;
    if (!load) continue;
    result[node.id] = load.requested_w <= 0 ? 'idle' : load.served_w >= load.requested_w ? 'served' : load.served_w > 0 ? 'partial' : 'unserved';
  }
  return result;
}

type Impact = { served_w: number; unmet_w: number; critical_unmet_w: number; affected: number };
export function impactOf(snapshot: DistrictSnapshot): Impact {
  const loads = snapshot.state.loads;
  return { served_w: loads.reduce((sum, load) => sum + load.served_w, 0), unmet_w: snapshot.state.unmet_w,
    critical_unmet_w: snapshot.state.critical_shortfall_w, affected: loads.filter(load => load.unmet_w > 0).length };
}

export function recoverySteps(snapshot: DistrictSnapshot) {
  const r = snapshot.state.restoration;
  const faulted = snapshot.state.faults.length > 0;
  const applied = (r.applied_edge_ids?.length ?? 0) > 0;
  const proposal = r.proposal;
  const proposed = !!r.candidate_edge_id && !r.proposal_stale;
  const blocked = !!proposal && !proposal.candidate_edge_ids;
  return [
    { label: 'Fault', state: faulted ? 'done' : 'todo', detail: faulted ? `${snapshot.state.faults.length} open` : 'None injected' },
    { label: 'Proposal', state: applied || proposed ? 'done' : blocked || r.proposal_stale ? 'blocked' : 'todo',
      detail: applied ? 'Applied' : proposed ? `${proposal?.solver_status} · AC ${proposal?.ac?.status ?? 'unknown'}` : r.proposal_stale ? 'Stale; propose again' : blocked ? (proposal?.solver_status ?? 'Refused') : 'Not proposed' },
    { label: 'Evidence', state: applied || r.evidence_ready ? 'done' : 'todo', detail: applied ? 'Satisfied' : `${r.stable_evidence_count ?? 0} / 2 fresh samples` },
    { label: 'Apply', state: applied ? 'done' : proposed && r.evidence_ready ? 'todo' : 'blocked', detail: applied ? `Modeled: ${r.applied_edge_ids?.join(', ')}` : proposed && r.evidence_ready ? 'Permitted' : 'Locked' },
  ] as const;
}

export function TransformerCutaway({ componentId, suspectedPart }: { componentId: string; suspectedPart: string | null }) {
  const partClass = (part: string) => suspectedPart === part ? 'is-suspected' : '';
  return <svg className="district-cutaway" viewBox="0 0 520 290" role="img"
    aria-label={`Illustrative synthetic transformer cutaway for ${componentId}`}>
    <title>Illustrative transformer cutaway</title>
    <desc>Oil tank with core and winding, cooling radiator, and insulated bushings. Red indicates an observation-supported suspected area.</desc>
    <g className={`cutaway-part ${partClass('cooling_system')}`}>
      <path d="M145 103H105V216H145M105 119H85M105 143H85M105 167H85M105 191H85" />
      <text x="24" y="238">Cooling radiator</text>
    </g>
    <rect x="145" y="92" width="258" height="142" rx="8" className="cutaway-tank" />
    <path d="M153 133H395V225H153Z" className="cutaway-oil" />
    <g className={`cutaway-part ${partClass('core')}`}>
      <path d="M221 151V205H254V172H291V205H324V151H291V184H254V151Z" />
      <text x="256" y="220">Core</text>
    </g>
    <g className={`cutaway-part ${partClass('winding')}`}>
      <ellipse cx="272" cy="166" rx="12" ry="24" />
      <ellipse cx="272" cy="166" rx="18" ry="28" />
      <text x="339" y="177">Winding</text>
    </g>
    <g className={`cutaway-part ${partClass('insulation')}`}>
      <path d="M222 92V66M272 92V58M322 92V66" />
      <path d="M213 66H231M263 58H281M313 66H331" />
      <text x="194" y="39">Insulated bushings</text>
    </g>
    <text x="157" y="119" className="cutaway-label">Oil tank</text>
    <text x="420" y="155">Illustrative</text><text x="420" y="174">schematic</text>
  </svg>;
}

export default function DistrictDemo() {
  const client = useQueryClient();
  const district = useQuery({
    queryKey: QUERY_KEY,
    queryFn: ({ signal }) => getDistrictSnapshot(signal),
    refetchInterval: snapshot => snapshot.state.data?.generation.status === 'GENERATING' ? 1000 : 5000,
    retry: 1,
    placeholderData: previous => previous,
  });
  const snapshot = district.data;
  const [tab, setTab] = useState<Tab>('shift');
  const [selected, setSelected] = useState<string | null>(null);
  const [clusterCount, setClusterCount] = useState(4);
  const [secondaryStrategy, setSecondaryStrategy] = useState('RadialStrategy');
  const [transformerScenario, setTransformerScenario] = useState('overload');
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [incident, setIncident] = useState<{ before?: Impact; fault?: Impact; recovered?: Impact }>({});
  const previousGenerationStatus = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!snapshot) return;
    const message = generationTransitionFeedback(previousGenerationStatus.current, snapshot);
    if (message) setFeedback(message);
    previousGenerationStatus.current = snapshot.generation.status;
  }, [snapshot?.generation.status, snapshot?.identity.revision]);

  const submit = async (operation: (current: DistrictSnapshot) => Promise<DistrictSnapshot>, success: string | ((updated: DistrictSnapshot) => string)) => {
    if (!snapshot || pending || district.isError || district.isPlaceholderData) return;
    setPending(true);
    setFeedback('Applying simulated action…');
    await client.cancelQueries({ queryKey: QUERY_KEY });
    try {
      const before = impactOf(snapshot);
      const updated = await operation(snapshot);
      client.setQueryData(QUERY_KEY, updated);
      if (updated.state.faults.length > snapshot.state.faults.length && !snapshot.state.faults.length) setIncident({ before, fault: impactOf(updated) });
      else if ((updated.state.restoration.applied_edge_ids?.length ?? 0) > (snapshot.state.restoration.applied_edge_ids?.length ?? 0)) setIncident(current => ({ ...current, recovered: impactOf(updated) }));
      else if (updated.identity.run_id !== snapshot.identity.run_id) setIncident({});
      setFeedback(typeof success === 'function' ? success(updated) : success);
    } catch (error) {
      setFeedback(errorMessage(error));
      void client.invalidateQueries({ queryKey: QUERY_KEY });
    } finally {
      setPending(false);
    }
  };
  const action = (current: DistrictSnapshot, name: DistrictActionName, component_id?: string, fault_kind?: string, healthy?: boolean) => districtAction({
    action_id: crypto.randomUUID(), run_id: current.identity.run_id, expected_revision: current.identity.revision, action: name, component_id, fault_kind,
    observation: healthy === undefined ? undefined : observationRequest(current.state.restoration.last_observation_sequence, healthy),
  });

  // One-click rehearsal: acknowledged, sequential backend actions (peak hour → fault → proposal).
  const simulateEmergency = () => void submit(async current => {
    let latest = await action(current, 'reset');
    while (latest.energy.hour !== 20) latest = await action(latest, 'advance_hour');
    const tie = (latest.topology.edges as DistrictEdge[]).find(edge => edge.kind === 'tie');
    const candidates = (latest.topology.edges as DistrictEdge[]).filter(edge => edge.kind !== 'tie');
    const preferred = candidates.find(edge => edge.id === EMERGENCY_EDGE) ?? candidates[0];
    latest = await action(latest, 'inject_fault', preferred.id, 'line_open');
    setIncident({ before: impactOf(current), fault: impactOf(latest) });
    if (tie) latest = await action(latest, 'propose_recovery');
    setSelected(preferred.id);
    setTab('healing');
    return latest;
  }, updated => `Simulated emergency: peak hour, line fault, ${updated.state.critical_shortfall_w.toLocaleString()} W critical unmet; backend proposal ${updated.state.restoration.proposal?.solver_status ?? 'pending'}. Record fresh observations, then apply.`);

  if (!snapshot) return <div className="district-page district-empty"><h1>{district.isError ? 'District study unavailable' : 'Loading GNITC district…'}</h1>
    {district.isError && <><p role="alert">The local district API did not respond. Start the backend, then reload this snapshot.</p><button onClick={() => void district.refetch()}>Retry</button></>}</div>;

  const features = snapshot.map.features as DistrictFeature[];
  const nodes = snapshot.topology.nodes as DistrictNode[];
  const edges = snapshot.topology.edges as DistrictEdge[];
  const edgeStates = snapshot.state.edges as DistrictEdgeState[];
  const buildings = features.filter(feature => feature.kind === 'building');
  const selectedNode = nodes.find(node => node.id === selected);
  const selectedEdge = edges.find(edge => edge.id === selected);
  const selectedFeature = features.find(feature => feature.id === selected);
  const selectedState = edgeStates.find(edge => edge.id === selected);
  const selectedLoad = snapshot.state.loads.find(load => load.building_id === selectedNode?.building_id);
  const selectedTransformer = snapshot.state.transformers.find(item => item.component_id === selectedNode?.id);
  const faultedEdges = snapshot.state.faults.map(fault => fault.component_id);
  const restoration = snapshot.state.restoration;
  const clearFault = clearFaultGate(selectedEdge?.id || null, faultedEdges, !!restoration.evidence_ready, Number(restoration.stable_evidence_count || 0), restoration.evidence_rule);
  const proposalOpen = !!restoration.candidate_edge_id && !restoration.proposal_stale;
  const statusText = district.isError || district.isPlaceholderData ? 'Stale snapshot' : 'Backend snapshot';
  const disabled = pending || district.isError || district.isPlaceholderData;
  const tabsKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const current = TABS.findIndex(item => item.id === tab);
    const next = event.key === 'ArrowRight' ? (current + 1) % TABS.length : event.key === 'ArrowLeft' ? (current - 1 + TABS.length) % TABS.length : event.key === 'Home' ? 0 : event.key === 'End' ? TABS.length - 1 : -1;
    if (next >= 0) { event.preventDefault(); setTab(TABS[next].id); document.getElementById(`district-tab-${TABS[next].id}`)?.focus(); }
  };
  const selectTransformer = () => {
    const first = nodes.find(node => node.role === 'transformer');
    if (first) { setSelected(first.id); setTab('transformers'); }
  };

  return <div className="district-page">
    <header className="district-heading"><div><span className="district-eyebrow">Blackout Mesh / GNITC district</span>
      <h1>See the district as one system.</h1>
      <p>Explore one district map through network, energy, recovery and transformer views.</p></div>
      <div className={`district-status${district.isError || district.isPlaceholderData ? ' is-stale' : ''}`} role="status"><span className="district-status-dot" />{statusText}<small>Run {snapshot.identity.run_id.slice(0, 8)} · revision {snapshot.identity.revision}</small></div>
    </header>
    <div className="district-actions"><button className="is-danger" disabled={disabled} onClick={simulateEmergency}>Simulate emergency</button><button className="is-secondary" disabled={disabled} onClick={() => { setIncident({}); void submit(current => action(current, 'reset'), 'Scenario reset.'); }}>Reset scenario</button><span className="district-action-help">Simulated steps only; no hardware command or physical confirmation.</span></div>
    <p className="district-cue">Real geography; synthetic electrical assets and demand · {snapshot.profile.id} · profile {snapshot.profile.config_hash.slice(0, 12)}</p>
    {snapshot.audit.rehydration?.status === 'RESTORED' && <p className="district-alert" role="status">Restored revision {snapshot.audit.rehydration.from_revision} after a backend restart. Earlier observations are stale; fresh evidence is required before recovery.</p>}
    {district.isError && <p className="district-alert" role="alert">The connection failed. Controls are disabled and the last received snapshot remains visible. <button onClick={() => void district.refetch()}>Retry</button></p>}
    <div className="district-tabs" role="tablist" aria-label="District study views" onKeyDown={tabsKeyDown}>{TABS.map(item => <button key={item.id} id={`district-tab-${item.id}`} role="tab" tabIndex={tab === item.id ? 0 : -1}
      aria-selected={tab === item.id} aria-controls={`district-panel-${item.id}`} onClick={() => setTab(item.id)}>{item.label}</button>)}</div>
    <div className="district-workspace" id={`district-panel-${tab}`} role="tabpanel" aria-labelledby={`district-tab-${tab}`}>
      <section className="district-card" aria-label="District map"><div className="district-card-header"><h2>{snapshot.site.name} · {snapshot.map.radius_m.toLocaleString()} m OSM context</h2><p>{buildings.length} cached building footprints · {features.filter(feature => feature.kind === 'road').length} road features. Synthetic network generation still uses the preserved 500 m cache.</p></div>
        <p className="district-impact" role="status" aria-label="Outage impact"><span className={snapshot.state.loads.some(load => load.unmet_w > 0) ? 'is-bad' : ''}>{snapshot.state.loads.filter(load => load.unmet_w > 0).length} of {snapshot.state.loads.length} loads affected</span><span className={snapshot.state.critical_shortfall_w > 0 ? 'is-bad' : ''}>Critical unmet {number(snapshot.state.critical_shortfall_w, 'W')}</span><span>Total unmet {number(snapshot.state.unmet_w, 'W')}</span><span>{snapshot.state.faults.length} simulated fault{snapshot.state.faults.length === 1 ? '' : 's'}</span></p>
        <DistrictMap features={features} nodes={nodes} edges={edges} edgeStates={edgeStates} selected={selected} onSelect={setSelected} mode={tab} loadStatus={loadStatuses(nodes, snapshot.state.loads)} />
        <div className="district-legend" aria-label="Map legend"><span className="district-key is-source">Synthetic source</span><span className="district-key is-transformer">Synthetic transformer</span><span className="district-key is-load">Synthetic load endpoint</span><span className="district-key is-junction">Synthetic junction</span><span className="district-key is-fault">Simulated fault</span><span className="district-key is-open">Open line</span><span className="district-key is-tie">Declared tie</span><span className="district-key is-road">Cached road</span><span>Sand shapes: cached building footprints</span></div>
        <p className="district-attribution">{snapshot.map.attribution} · {snapshot.map.license} · <a href={snapshot.map.source_url} target="_blank" rel="noreferrer">map source</a>, retrieved {snapshot.map.retrieved}. Source snapshot {snapshot.map.source_sha256.slice(0, 12)}. Synthetic wires do not represent real feeders.</p>
      </section>
      <section className="district-card district-detail" aria-label={`${TABS.find(item => item.id === tab)?.label} details`}>
        {tab === 'shift' && <><h2>SHIFT distribution network</h2><p>{snapshot.topology.engine} · {snapshot.topology.engine_version.slice(0, 12)} · {snapshot.topology.engine_license}. {snapshot.topology.provenance}</p>
          <div className="district-form-row"><label>Transformer clusters<input type="number" min="2" max="6" value={clusterCount} onChange={event => setClusterCount(Math.min(6, Math.max(2, Number(event.target.value) || 2)))} /></label>
            <label>Secondary strategy<select value={secondaryStrategy} onChange={event => setSecondaryStrategy(event.target.value)}><option value="RadialStrategy">Radial</option><option value="MeshSteinerStrategy">Mesh / Steiner</option></select></label></div>
          <div className="district-actions"><button disabled={disabled || !snapshot.generation.available || snapshot.generation.status === 'GENERATING'} onClick={() => void submit(current => generateDistrictTopology({ run_id: current.identity.run_id, expected_revision: current.identity.revision, cluster_count: clusterCount, secondary_strategy: secondaryStrategy }), generationMessage)}>Generate topology</button></div>
          <p className="district-generation-status">{snapshot.generation.available ? `Topology generation: ${snapshot.generation.status}.` : `Topology generation: UNAVAILABLE. ${snapshot.generation.reason || 'Optional generation runtime is not installed.'} Cached topology remains active.`} {snapshot.generation.available && snapshot.generation.reason}</p>
          {feedback && <p className="district-feedback" role="status">{feedback}</p>}
          <ol className="district-stages"><li>Map parcels</li><li>Cluster loads</li><li>Place transformers</li><li>Build synthetic lines</li><li>Validate topology</li></ol>
          <div className="district-kpis"><Kpi label="Mapped buildings" value={String(buildings.length)} /><Kpi label="Synthetic nodes" value={String(nodes.length)} /><Kpi label="Synthetic edges" value={String(edges.length)} /><Kpi label="Source limit" value={number(snapshot.state.source_capacity_w, 'W')} /></div>
          <h3>{selected ? `Selected · ${selected}` : 'Select a map asset'}</h3><p>{selectedNode ? `Synthetic ${selectedNode.role}${selectedNode.role === 'load' && selectedLoad ? ` · ${number(selectedLoad.requested_w, 'W')} requested / ${number(selectedLoad.served_w, 'W')} served` : ''}.` : selectedEdge ? `${selectedEdge.kind} · ${selectedState?.faulted ? 'faulted' : selectedState?.closed === false ? 'open' : selectedState?.energized ? 'energized' : 'not energized'} · ${number(selectedState?.flow_w, 'W')} modeled flow.` : selectedFeature ? 'Cached geography feature. This footprint has no verified electrical connection.' : 'Selection carries across all four views.'}</p>
          {selectedNode?.role === 'transformer' && <div className="district-actions"><button className="is-secondary" onClick={() => setTab('transformers')}>Inspect selected transformer</button></div>}
          <DistrictApplianceTrace snapshot={snapshot} selected={selected} />
          <p>Load reachability and ratings are properties of this simulated topology.</p></>}
        {tab === 'energy' && <><h2>Battery dispatch · hour {snapshot.energy.hour}</h2><p>{snapshot.energy.engine}. Baseline and dispatch use the same 24-hour synthetic profile. {snapshot.energy.provenance}</p>
          <div className="district-kpis"><Kpi label="Battery state" value={number(snapshot.energy.battery_soc_wh, 'Wh')} /><Kpi label="PV used" value={number(snapshot.energy.pv_used_w, 'W')} /><Kpi label="Battery charge" value={number(snapshot.energy.battery_charge_w, 'W')} /></div>
          <h3>Scheduled import and modeled network service · hour {snapshot.energy.hour}</h3><p>Profile scheduled grid import: {number(snapshot.energy.grid_import_w, 'W')}. The district model routed {number(snapshot.state.grid_served_w, 'W')} of {number(snapshot.state.grid_requested_w, 'W')} requested grid service; total unmet district demand is {number(snapshot.state.unmet_w, 'W')}. Scheduled import is a request, not delivered feeder flow.</p>
          <div className="district-kpis"><Kpi label="Profile scheduled import" value={number(snapshot.energy.grid_import_w, 'W')} /><Kpi label="District grid requested" value={number(snapshot.state.grid_requested_w, 'W')} /><Kpi label="Modeled grid served" value={number(snapshot.state.grid_served_w, 'W')} /><Kpi label="Unmet district demand" value={number(snapshot.state.unmet_w, 'W')} /></div>
          <div className="district-data-table"><table><caption>Profile energy totals · 24 one-hour samples; power values integrated as Wh</caption><thead><tr><th>Demand</th><th>PV generated / used / curtailed</th><th>Baseline / dispatch import scheduled</th><th>Grid export</th><th>Battery charge / discharge / loss</th><th>Configured round-trip efficiency</th></tr></thead><tbody><tr><td>{number(snapshot.energy.totals.demand_wh, 'Wh')}</td><td>{number(snapshot.energy.totals.pv_generated_wh, 'Wh')} / {number(snapshot.energy.totals.pv_used_wh, 'Wh')} / {number(snapshot.energy.totals.pv_curtailed_wh, 'Wh')}</td><td>{number(snapshot.energy.totals.baseline_import_scheduled_wh, 'Wh')} / {number(snapshot.energy.totals.dispatch_import_scheduled_wh, 'Wh')}</td><td>{number(snapshot.energy.totals.grid_export_wh, 'Wh')}</td><td>{number(snapshot.energy.totals.battery_charge_wh, 'Wh')} / {number(snapshot.energy.totals.battery_discharge_wh, 'Wh')} / {number(snapshot.energy.totals.battery_loss_wh, 'Wh')}</td><td>{number(snapshot.energy.totals.battery_round_trip_efficiency * 100, '%')}</td></tr></tbody></table></div>
          <p>One-hour modeled network interval: {number(snapshot.energy.network_interval.served_wh, 'Wh')} served from {number(snapshot.energy.network_interval.requested_wh, 'Wh')} requested; {number(snapshot.energy.network_interval.grid_served_wh, 'Wh')} grid-routed, {number(snapshot.energy.network_interval.local_supply_wh, 'Wh')} allocated behind the meter, and {number(snapshot.energy.network_interval.unmet_wh, 'Wh')} unmet ({number(snapshot.energy.network_interval.unmet_fraction_of_requested * 100, '%')} of requested energy). Scheduled imports above are profile requests; only this interval's grid-served value is routed through the synthetic feeder model.</p>
          <div className="district-data-table"><table><caption>Profile hourly energy profile · imports are scheduled requests; W over each one-hour interval equals Wh</caption><thead><tr><th>Hour</th><th>Demand (W)</th><th>PV (W)</th><th>Baseline scheduled import (W)</th><th>Dispatch scheduled import (W)</th><th>Battery state (Wh)</th><th>Loss (Wh)</th></tr></thead><tbody>{snapshot.energy.profile.map(row => <tr key={row.hour} aria-current={row.hour === snapshot.energy.hour ? 'time' : undefined}><th>{row.hour}:00</th><td>{number(row.demand_w, 'W')}</td><td>{number(row.pv_w, 'W')}</td><td>{number(row.baseline_grid_w, 'W')}</td><td>{number(row.dispatch_grid_w, 'W')}</td><td>{number(row.battery_soc_wh, 'Wh')}</td><td>{number(row.loss_wh, 'Wh')}</td></tr>)}</tbody></table></div>
          <p>Import values are model output; a profile comparison is not a real-world savings claim.</p><div className="district-actions"><button disabled={disabled} onClick={() => void submit(current => action(current, 'advance_hour'), 'Advanced the simulated energy interval.')}>Advance one hour</button><button className="is-secondary" disabled={disabled} onClick={() => void submit(current => action(current, 'reset'), 'District simulation reset.')}>Reset simulation</button></div></>}
        {tab === 'healing' && <><h2>Fault isolation and recovery</h2><p>Inject a line-open fault, propose the best permitted tie configuration, and apply only after fresh sequenced observations and AC revalidation. Simulated state stays separate from physical confirmation.</p><p className="district-action-help">Priority tiers · {snapshot.state.loads[0]?.tier_provenance || 'provenance unavailable'}: {snapshot.state.loads[0]?.tier_rationale || 'Priority policy rationale unavailable.'}</p>
          <ol className="district-steps" aria-label="Modeled recovery workflow">{recoverySteps(snapshot).map((step, index) => <li key={step.label} className={step.state === 'done' ? 'is-done' : step.state === 'blocked' ? 'is-blocked' : ''}><strong>{index + 1}. {step.label}</strong>{step.detail}</li>)}</ol>
          {incident.before && <div className="district-data-table"><table><caption>Incident impact comparison · captured backend snapshots from this session</caption><thead><tr><th>Stage</th><th>Served</th><th>Critical unmet</th><th>Total unmet</th><th>Affected loads</th></tr></thead><tbody>{([['Before fault', incident.before], ['After fault', incident.fault], ['After recovery', incident.recovered]] as const).filter(([, row]) => row).map(([label, row]) => <tr key={label}><th>{label}</th><td>{number(row!.served_w, 'W')}</td><td>{number(row!.critical_unmet_w, 'W')}</td><td>{number(row!.unmet_w, 'W')}</td><td>{row!.affected}</td></tr>)}</tbody></table></div>}
          <div className="district-kpis"><Kpi label="Synthetic critical shortfall" value={number(snapshot.state.critical_shortfall_w, 'W')} /><Kpi label="Open faults" value={String(snapshot.state.faults.length)} /><Kpi label="Recovery proposal" value={String(restoration.candidate_edge_id || 'None')} /><Kpi label="Applied modeled ties" value={restoration.applied_edge_ids?.join(', ') || 'None'} /></div>
          <p>Source capacity: {number(snapshot.state.source_capacity_w, 'W')} · {snapshot.state.source_capacity_provenance} · {snapshot.state.source_capacity_note}. {snapshot.state.source_available ? 'Available in model.' : 'Unavailable in model.'} Evidence: {String(restoration.stable_evidence_count ?? 0)} healthy sample(s); rule: {restoration.evidence_rule || 'unknown'}; {restoration.evidence_ready ? 'satisfied' : 'not satisfied'}. {restoration.reason || ''}</p>
          <div className="district-actions"><button className="is-danger" disabled={disabled || !selectedEdge || selectedEdge.kind === 'tie' || !!selectedState?.faulted} onClick={() => selectedEdge && void submit(current => action(current, 'inject_fault', selectedEdge.id, 'line_open'), 'Simulated line fault injected; state recalculated.')}>Inject selected line fault</button>
            <button className="is-secondary" aria-describedby="clear-fault-help" disabled={disabled || !clearFault.enabled} onClick={() => selectedEdge && void submit(current => action(current, 'clear_fault', selectedEdge.id, 'line_open'), 'Simulated line fault cleared.')}>Clear selected fault</button>
            <button className="is-secondary" disabled={disabled || !snapshot.state.faults.length || proposalOpen} onClick={() => void submit(current => action(current, 'propose_recovery'), updated => updated.state.restoration.candidate_edge_id ? `Recovery candidate ${updated.state.restoration.candidate_edge_ids?.join(', ')} proposed (${updated.state.restoration.proposal?.solver_status}).` : `No recovery candidate: ${updated.state.restoration.reason || 'the backend found no validated configuration.'}`)}>Propose recovery</button>
            <button className="is-secondary" disabled={disabled} onClick={() => void submit(current => action(current, 'record_observation', undefined, undefined, true), updated => `Simulated healthy observation #${updated.state.restoration.last_observation_sequence} recorded; ${updated.state.restoration.stable_evidence_count} counted.`)}>Record healthy observation</button>
            <button className="is-secondary" disabled={disabled} onClick={() => void submit(current => action(current, 'record_observation', undefined, undefined, false), 'Simulated unhealthy observation recorded; the evidence gate was reset.')}>Record unhealthy observation</button>
            <button disabled={disabled || !proposalOpen || !restoration.evidence_ready} onClick={() => void submit(current => action(current, 'apply_recovery'), 'Recovery applied to modeled topology after fresh evidence and AC revalidation.')}>Apply validated proposal</button></div>
          <p className="district-action-help">Observations come from a labeled simulated adapter (timestamped, sequence-numbered). Advancing the hour is not evidence.</p>
          <p id="clear-fault-help" className="district-action-help" aria-live="polite">{clearFault.reason}</p>
          <DistrictRecoveryProposal proposal={restoration.proposal} stale={!!restoration.proposal_stale} />
          <DistrictAuditReplay snapshot={snapshot} />
          <p className="district-feedback" role="status">{feedback || (restoration.candidate_edge_id ? `Candidate ${restoration.candidate_edge_ids?.join(', ')}; ${restoration.stable_evidence_count} healthy observation(s) counted.` : 'Select a synthetic line on the map to inject a fault.')}</p>
          {snapshot.state.loads.map(load => <p className="district-load-row" key={load.building_id}>{load.building_id}: {number(load.served_w, 'W')} served of {number(load.requested_w, 'W')} gross demand · {load.tier}. Local supply {number(load.local_supply_w, 'W')}; routed grid service {number(load.grid_served_w, 'W')} of {number(load.grid_requested_w, 'W')} allocated; {number(load.unmet_w, 'W')} unmet. Demand: {load.demand_provenance}; local supply: {load.local_supply_provenance}, {load.local_supply_basis}, {load.local_supply_semantics}; grid service: {load.grid_service_provenance}; unmet: {load.unmet_provenance}.</p>)}</>}
        {tab === 'transformers' && <><h2>Transformer inspection</h2><p>{selectedTransformer ? `Selected synthetic transformer ${selectedTransformer.component_id}.` : 'Select a synthetic transformer on the map.'} Measurements are shown only when the snapshot includes evidence.</p>
          {selectedTransformer ? <><TransformerCutaway componentId={selectedTransformer.component_id} suspectedPart={selectedTransformer.diagnosis.status === 'SUSPECTED' ? selectedTransformer.diagnosis.suspected_part : null} />
            <p className={selectedTransformer.diagnosis.suspected_part ? 'district-alert' : ''}>{selectedTransformer.diagnosis.status === 'UNKNOWN' || !selectedTransformer.diagnosis.suspected_part ? 'Unknown: no fresh evidence supports a suspected area.' : `Simulated observation indicates ${selectedTransformer.diagnosis.suspected_part}. This is not a physical diagnosis.`}</p>
            <div className="district-data-table"><table><caption>Transformer telemetry · source: {String(selectedTransformer.sensor.provenance || 'unknown')}</caption><tbody><tr><th>Oil temperature</th><td>{transformerReading(selectedTransformer.sensor, 'oil_temperature_c', '°C')}</td><th>Voltage</th><td>{transformerReading(selectedTransformer.sensor, 'voltage_v', 'V')}</td></tr><tr><th>Current</th><td>{transformerReading(selectedTransformer.sensor, 'current_a', 'A')}</td><th>Cooling</th><td>{selectedTransformer.sensor.status === 'STALE' ? <><span>Unknown</span><small>Stale last reading: {selectedTransformer.sensor.cooling_ok ? 'OK' : 'Not OK'}</small></> : selectedTransformer.sensor.cooling_ok == null ? 'Unknown' : selectedTransformer.sensor.cooling_ok ? 'OK' : 'Not OK'}</td></tr></tbody></table></div>
            <ul className="district-list">{selectedTransformer.diagnosis.evidence.map((item, index) => <li key={index}>{item}</li>)}</ul>
            <label className="district-scenario-label">Simulated observation scenario<select value={transformerScenario} onChange={event => setTransformerScenario(event.target.value)}><option value="overload">Overload</option><option value="cooling_failure">Cooling failure</option><option value="missing_sensor">Missing sensor</option><option value="stale_sensor">Stale sensor readings</option></select></label>
            <div className="district-actions"><button disabled={disabled} onClick={() => void submit(current => action(current, 'transformer_scenario', selectedTransformer.component_id, transformerScenario), 'Simulated transformer observations updated.')}>Apply scenario</button><button className="is-secondary" disabled={disabled} onClick={() => void submit(current => action(current, 'transformer_scenario', selectedTransformer.component_id, 'clear'), 'Simulated transformer scenario cleared.')}>Clear scenario</button></div>
          </> : <div className="district-empty"><p>No transformer selected.</p><button onClick={selectTransformer}>Select first transformer</button></div>}</>}
      </section>
    </div>
    <details className="district-boundary"><summary>Data and model boundaries</summary><p>Map: {snapshot.map.source} cached geography, {snapshot.map.license}. Network and ratings: {snapshot.topology.engine} synthetic topology. Loads, demand, PV, battery, faults, restorations and transformer scenarios are modeled. A modeled transition does not confirm physical power delivery or device state.</p></details>
  </div>;
}
