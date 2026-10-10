import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { districtAction, generateDistrictTopology, getDistrictSnapshot, ApiError } from '../api';
import type { DistrictActionName, DistrictSnapshot } from '../types';
import DistrictMap, { type DistrictEdge, type DistrictEdgeState, type DistrictFeature, type DistrictNode } from './DistrictMap';
import './DistrictDemo.css';

const TABS = [
  { id: 'shift', label: 'SHIFT network' }, { id: 'energy', label: 'Energy' },
  { id: 'healing', label: 'Self-healing' }, { id: 'transformers', label: 'Transformers' },
] as const;
type Tab = typeof TABS[number]['id'];
const QUERY_KEY = ['district-study'];

function Kpi({ label, value }: { label: string; value: string }) {
  return <div className="district-kpi"><span>{label}</span><strong>{value}</strong></div>;
}

function number(value: unknown, unit: string) {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toLocaleString()} ${unit}` : 'Unknown';
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 409) return 'State changed before this action was applied. The latest snapshot has been refreshed.';
  return error instanceof Error ? error.message : 'District action failed.';
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

  const submit = async (operation: (current: DistrictSnapshot) => Promise<DistrictSnapshot>, success: string | ((updated: DistrictSnapshot) => string)) => {
    if (!snapshot || pending || district.isError || district.isPlaceholderData) return;
    setPending(true);
    setFeedback('Applying simulated action…');
    await client.cancelQueries({ queryKey: QUERY_KEY });
    try {
      const updated = await operation(snapshot);
      client.setQueryData(QUERY_KEY, updated);
      setFeedback(typeof success === 'function' ? success(updated) : success);
    } catch (error) {
      setFeedback(errorMessage(error));
      void client.invalidateQueries({ queryKey: QUERY_KEY });
    } finally {
      setPending(false);
    }
  };
  const action = (current: DistrictSnapshot, name: DistrictActionName, component_id?: string, fault_kind?: string) => districtAction({
    run_id: current.identity.run_id, expected_revision: current.identity.revision, action: name, component_id, fault_kind,
  });

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
    <p className="district-cue">Cached OpenStreetMap geography · synthetic electrical topology, loads and device observations</p>
    {district.isError && <p className="district-alert" role="alert">The connection failed. Controls are disabled and the last received snapshot remains visible. <button onClick={() => void district.refetch()}>Retry</button></p>}
    <div className="district-tabs" role="tablist" aria-label="District study views" onKeyDown={tabsKeyDown}>{TABS.map(item => <button key={item.id} id={`district-tab-${item.id}`} role="tab" tabIndex={tab === item.id ? 0 : -1}
      aria-selected={tab === item.id} aria-controls={`district-panel-${item.id}`} onClick={() => setTab(item.id)}>{item.label}</button>)}</div>
    <div className="district-workspace" id={`district-panel-${tab}`} role="tabpanel" aria-labelledby={`district-tab-${tab}`}>
      <section className="district-card" aria-label="District map"><div className="district-card-header"><h2>{snapshot.site.name} · {snapshot.site.radius_m} m study area</h2><p>{buildings.length} cached building footprints · {features.filter(feature => feature.kind === 'road').length} road features</p></div>
        <DistrictMap features={features} nodes={nodes} edges={edges} edgeStates={edgeStates} selected={selected} onSelect={setSelected} mode={tab} />
        <div className="district-legend" aria-label="Map legend"><span className="district-key is-source">Synthetic source</span><span className="district-key is-transformer">Synthetic transformer</span><span className="district-key is-load">Synthetic load endpoint</span><span className="district-key is-junction">Synthetic junction</span><span className="district-key is-fault">Simulated fault</span><span className="district-key is-open">Open line</span><span className="district-key is-tie">Declared tie</span><span className="district-key is-road">Cached road</span><span>Sand shapes: cached building footprints</span></div>
        <p className="district-attribution">{snapshot.map.attribution} · {snapshot.map.license} · <a href={snapshot.map.source_url} target="_blank" rel="noreferrer">map source</a>. Source snapshot {snapshot.map.source_sha256.slice(0, 12)}. Synthetic wires do not represent real feeders.</p>
      </section>
      <section className="district-card district-detail" aria-label={`${TABS.find(item => item.id === tab)?.label} details`}>
        {tab === 'shift' && <><h2>SHIFT distribution network</h2><p>{snapshot.topology.engine} · {snapshot.topology.engine_version.slice(0, 12)} · {snapshot.topology.engine_license}. {snapshot.topology.provenance}</p>
          <div className="district-form-row"><label>Transformer clusters<input type="number" min="2" max="6" value={clusterCount} onChange={event => setClusterCount(Math.min(6, Math.max(2, Number(event.target.value) || 2)))} /></label>
            <label>Secondary strategy<select value={secondaryStrategy} onChange={event => setSecondaryStrategy(event.target.value)}><option value="RadialStrategy">Radial</option><option value="MeshSteinerStrategy">Mesh / Steiner</option></select></label></div>
          <div className="district-actions"><button disabled={disabled || !snapshot.generation.available || snapshot.generation.status === 'GENERATING'} onClick={() => void submit(current => generateDistrictTopology({ run_id: current.identity.run_id, expected_revision: current.identity.revision, cluster_count: clusterCount, secondary_strategy: secondaryStrategy }), 'Topology generation started; waiting for the backend result.')}>Generate topology</button></div>
          <p className="district-generation-status">{snapshot.generation.available ? `Topology generation: ${snapshot.generation.status}.` : `Topology generation: UNAVAILABLE. ${snapshot.generation.reason || 'Optional generation runtime is not installed.'} Cached topology remains active.`} {snapshot.generation.available && snapshot.generation.reason}</p>
          {feedback && <p className="district-feedback" role="status">{feedback}</p>}
          <ol className="district-stages"><li>Map parcels</li><li>Cluster loads</li><li>Place transformers</li><li>Build synthetic lines</li><li>Validate topology</li></ol>
          <div className="district-kpis"><Kpi label="Mapped buildings" value={String(buildings.length)} /><Kpi label="Synthetic nodes" value={String(nodes.length)} /><Kpi label="Synthetic edges" value={String(edges.length)} /><Kpi label="Source limit" value={number(snapshot.state.source_capacity_w, 'W')} /></div>
          <h3>{selected ? `Selected · ${selected}` : 'Select a map asset'}</h3><p>{selectedNode ? `Synthetic ${selectedNode.role}${selectedNode.role === 'load' && selectedLoad ? ` · ${number(selectedLoad.requested_w, 'W')} requested / ${number(selectedLoad.served_w, 'W')} served` : ''}.` : selectedEdge ? `${selectedEdge.kind} · ${selectedState?.faulted ? 'faulted' : selectedState?.closed === false ? 'open' : selectedState?.energized ? 'energized' : 'not energized'} · ${number(selectedState?.flow_w, 'W')} modeled flow.` : selectedFeature ? 'Cached geography feature. This footprint has no verified electrical connection.' : 'Selection carries across all four views.'}</p>
          {selectedNode?.role === 'transformer' && <div className="district-actions"><button className="is-secondary" onClick={() => setTab('transformers')}>Inspect selected transformer</button></div>}
          <p>Load reachability and ratings are properties of this simulated topology.</p></>}
        {tab === 'energy' && <><h2>Battery dispatch · hour {snapshot.energy.hour}</h2><p>{snapshot.energy.engine}. Baseline and dispatch use the same 24-hour synthetic profile. {snapshot.energy.provenance}</p>
          <div className="district-kpis"><Kpi label="Battery state" value={number(snapshot.energy.battery_soc_wh, 'Wh')} /><Kpi label="PV used" value={number(snapshot.energy.pv_used_w, 'W')} /><Kpi label="Battery charge" value={number(snapshot.energy.battery_charge_w, 'W')} /></div>
          <h3>Scheduled import and modeled network service · hour {snapshot.energy.hour}</h3><p>CityLearn scheduled grid import: {number(snapshot.energy.grid_import_w, 'W')}. The district model routed {number(snapshot.state.grid_served_w, 'W')} of {number(snapshot.state.grid_requested_w, 'W')} requested grid service; total unmet district demand is {number(snapshot.state.unmet_w, 'W')}. Scheduled import is a request, not delivered feeder flow.</p>
          <div className="district-kpis"><Kpi label="CityLearn scheduled import" value={number(snapshot.energy.grid_import_w, 'W')} /><Kpi label="District grid requested" value={number(snapshot.state.grid_requested_w, 'W')} /><Kpi label="Modeled grid served" value={number(snapshot.state.grid_served_w, 'W')} /><Kpi label="Unmet district demand" value={number(snapshot.state.unmet_w, 'W')} /></div>
          <div className="district-data-table"><table><caption>CityLearn energy profile · grid imports are scheduled requests; watts except battery state and losses (Wh)</caption><thead><tr><th>Hour</th><th>Demand (W)</th><th>PV (W)</th><th>Baseline scheduled import (W)</th><th>Dispatch scheduled import (W)</th><th>Battery state (Wh)</th></tr></thead><tbody>{snapshot.energy.profile.map(row => <tr key={row.hour} aria-current={row.hour === snapshot.energy.hour ? 'time' : undefined}><th>{row.hour}:00</th><td>{number(row.demand_w, 'W')}</td><td>{number(row.pv_w, 'W')}</td><td>{number(row.baseline_grid_w, 'W')}</td><td>{number(row.dispatch_grid_w, 'W')}</td><td>{number(row.battery_soc_wh, 'Wh')}</td></tr>)}</tbody></table></div>
          <p>Import values are model output; a profile comparison is not a real-world savings claim.</p><div className="district-actions"><button disabled={disabled} onClick={() => void submit(current => action(current, 'advance_hour'), 'Advanced the simulated energy interval.')}>Advance one hour</button><button className="is-secondary" disabled={disabled} onClick={() => void submit(current => action(current, 'reset'), 'District simulation reset.')}>Reset simulation</button></div></>}
        {tab === 'healing' && <><h2>Fault isolation and recovery</h2><p>Inject a line-open fault, propose a declared tie, and apply only after stable modeled evidence. Simulated state stays separate from physical confirmation.</p>
          <div className="district-kpis"><Kpi label="Critical shortfall" value={number(snapshot.state.critical_shortfall_w, 'W')} /><Kpi label="Open faults" value={String(snapshot.state.faults.length)} /><Kpi label="Recovery proposal" value={String(restoration.candidate_edge_id || 'None')} /><Kpi label="Applied modeled tie" value={String(restoration.applied_edge_id || 'None')} /></div>
          <p>Source capacity: {number(snapshot.state.source_capacity_w, 'W')} · {snapshot.state.source_capacity_provenance} · {snapshot.state.source_capacity_note}. {snapshot.state.source_available ? 'Available in model.' : 'Unavailable in model.'} Stable evidence: {String(restoration.stable_evidence_count ?? 0)}. {restoration.reason || ''}</p>
          <div className="district-actions"><button className="is-danger" disabled={disabled || !selectedEdge || selectedEdge.kind === 'tie' || !!selectedState?.faulted} onClick={() => selectedEdge && void submit(current => action(current, 'inject_fault', selectedEdge.id, 'line_open'), 'Simulated line fault injected; state recalculated.')}>Inject selected line fault</button>
            <button className="is-secondary" disabled={disabled || !selectedEdge || !faultedEdges.includes(selectedEdge.id)} onClick={() => selectedEdge && void submit(current => action(current, 'clear_fault', selectedEdge.id, 'line_open'), 'Simulated line fault cleared.')}>Clear selected fault</button>
            <button className="is-secondary" disabled={disabled || !snapshot.state.faults.length || !!restoration.candidate_edge_id} onClick={() => void submit(current => action(current, 'propose_recovery'), updated => updated.state.restoration.candidate_edge_id ? `Recovery candidate ${updated.state.restoration.candidate_edge_id} proposed by the backend.` : `No recovery candidate: ${updated.state.restoration.reason || 'the backend found no feasible modeled tie.'}`)}>Propose recovery</button>
            <button className="is-secondary" disabled={disabled || !snapshot.state.faults.length} onClick={() => void submit(current => action(current, 'advance_hour'), updated => updated.state.restoration.candidate_edge_id ? 'One simulated hour advanced; fresh evidence was recorded for the recovery candidate.' : 'One simulated hour advanced; fault evidence was refreshed. You can propose recovery again.')}>{restoration.candidate_edge_id ? 'Advance evidence interval' : 'Advance fault evidence'}</button>
            <button disabled={disabled || !restoration.candidate_edge_id || Number(restoration.stable_evidence_count || 0) < 2} onClick={() => void submit(current => action(current, 'apply_recovery'), 'Recovery applied to modeled topology after stable evidence.')}>Apply safe proposal</button></div>
          <p className="district-feedback" role="status">{feedback || (restoration.candidate_edge_id ? `Candidate ${restoration.candidate_edge_id}; ${restoration.stable_evidence_count} stable evidence intervals recorded.` : 'Select a synthetic line on the map to inject a fault.')}</p>
          {snapshot.state.loads.map(load => <p className="district-load-row" key={load.building_id}>{load.building_id}: {number(load.served_w, 'W')} served of {number(load.requested_w, 'W')} gross demand · {load.tier}. Local supply {number(load.local_supply_w, 'W')}; routed grid service {number(load.grid_served_w, 'W')} of {number(load.grid_requested_w, 'W')} allocated; {number(load.unmet_w, 'W')} unmet. Demand: {load.demand_provenance}; local supply: {load.local_supply_provenance}; grid service: {load.grid_service_provenance}; unmet: {load.unmet_provenance}.</p>)}</>}
        {tab === 'transformers' && <><h2>Transformer inspection</h2><p>{selectedTransformer ? `Selected synthetic transformer ${selectedTransformer.component_id}.` : 'Select a synthetic transformer on the map.'} Measurements are shown only when the snapshot includes evidence.</p>
          {selectedTransformer ? <><div className="district-cutaway" aria-label="Transformer cutaway"><div className={selectedTransformer.diagnosis.suspected_part?.startsWith('cooling') ? 'is-suspected' : ''}>Cooling</div><div className={selectedTransformer.diagnosis.suspected_part === 'winding' ? 'is-suspected' : ''}>Winding</div><div className={selectedTransformer.diagnosis.suspected_part === 'core' ? 'is-suspected' : ''}>Core</div><div className={selectedTransformer.diagnosis.suspected_part === 'insulation' ? 'is-suspected' : ''}>Insulation</div></div>
            <p className={selectedTransformer.diagnosis.suspected_part ? 'district-alert' : ''}>{selectedTransformer.diagnosis.status === 'UNKNOWN' || !selectedTransformer.diagnosis.suspected_part ? 'Unknown: no fresh evidence supports a suspected area.' : `Simulated observation indicates ${selectedTransformer.diagnosis.suspected_part}. This is not a physical diagnosis.`}</p>
            <div className="district-data-table"><table><caption>Transformer telemetry · source: {String(selectedTransformer.sensor.provenance || 'unknown')}</caption><tbody><tr><th>Oil temperature</th><td>{number(selectedTransformer.sensor.oil_temperature_c, '°C')}</td><th>Voltage</th><td>{number(selectedTransformer.sensor.voltage_v, 'V')}</td></tr><tr><th>Current</th><td>{number(selectedTransformer.sensor.current_a, 'A')}</td><th>Cooling</th><td>{selectedTransformer.sensor.cooling_ok == null ? 'Unknown' : selectedTransformer.sensor.cooling_ok ? 'OK' : 'Not OK'}</td></tr></tbody></table></div>
            <ul className="district-list">{selectedTransformer.diagnosis.evidence.map((item, index) => <li key={index}>{item}</li>)}</ul>
            <label className="district-scenario-label">Simulated observation scenario<select value={transformerScenario} onChange={event => setTransformerScenario(event.target.value)}><option value="overload">Overload</option><option value="cooling_failure">Cooling failure</option><option value="missing_sensor">Missing sensor</option></select></label>
            <div className="district-actions"><button disabled={disabled} onClick={() => void submit(current => action(current, 'transformer_scenario', selectedTransformer.component_id, transformerScenario), 'Simulated transformer observations updated.')}>Apply scenario</button><button className="is-secondary" disabled={disabled} onClick={() => void submit(current => action(current, 'transformer_scenario', selectedTransformer.component_id, 'clear'), 'Simulated transformer scenario cleared.')}>Clear scenario</button></div>
          </> : <div className="district-empty"><p>No transformer selected.</p><button onClick={selectTransformer}>Select first transformer</button></div>}</>}
      </section>
    </div>
    <details className="district-boundary"><summary>Data and model boundaries</summary><p>Map: {snapshot.map.source} cached geography, {snapshot.map.license}. Network and ratings: {snapshot.topology.engine} synthetic topology. Loads, demand, PV, battery, faults, restorations and transformer scenarios are modeled. A modeled transition does not confirm physical power delivery or device state.</p></details>
  </div>;
}
