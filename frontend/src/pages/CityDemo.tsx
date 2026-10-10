import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Activity, ArrowRight, Radio, ShieldCheck, Zap } from 'lucide-react';
import { changeCapacity, changeClassroomLoad, changeFeeder, getCityDemo, getDemoEvidence } from '../api';
import { servedWatts, type DemandForecast, type Snapshot } from '../types';
import { BenchmarkCard } from '../components/ui/benchmark-card';
import HardwarePanel from './HardwarePanel';
import CityGrid, { feederState } from './CityGrid';
import DemandForecastPanel from './DemandForecastPanel';
import './CityDemo.css';

export function decisionReason(snapshot: Snapshot, serviceId: string) {
  const decisions = snapshot.allocation.explanation?.decisions;
  const decision = Array.isArray(decisions) && decisions.find(d => d.service_id === serviceId);
  return typeof decision?.reason === 'string' ? decision.reason : snapshot.services.find(s => s.id === serviceId)?.model_reason ?? 'Decision evidence unavailable.';
}

export default function CityDemo() {
  const queryClient = useQueryClient();
  const [source, setSource] = useState<DemandForecast['source']>('LIVE_REQUESTED_DEMAND');
  const [replayIndex, setReplayIndex] = useState(3);
  const [selected, setSelected] = useState('L3');
  const [pending, setPending] = useState(false);
  const actionInFlight = useRef(false);
  const [feedback, setFeedback] = useState('');
  const city = useQuery({ queryKey: ['city-demo', source, replayIndex], queryFn: ({ signal }) => getCityDemo(source, replayIndex, signal), refetchInterval: 1000, retry: 1, placeholderData: previous => previous });
  const evidence = useQuery({ queryKey: ['demo-evidence'], queryFn: ({ signal }) => getDemoEvidence(signal), staleTime: Infinity });
  const snapshot = city.data?.snapshot;
  const act = async (operation: () => Promise<unknown>, message: string) => {
    if (actionInFlight.current || city.isError) return;
    actionInFlight.current = true;
    setPending(true); setFeedback('Applying eventâ€¦');
    await queryClient.cancelQueries({ queryKey: ['city-demo'] });
    try {
      await operation();
      await queryClient.invalidateQueries({ queryKey: ['city-demo'] });
      setFeedback(message);
    } catch (error) { setFeedback(error instanceof Error ? error.message : 'Event failed.'); }
    finally { actionInFlight.current = false; setPending(false); }
  };
  if (!snapshot || !city.data) return <div className="city-demo city-loading"><Activity aria-hidden="true" /><h1>{city.isError ? 'City grid unavailable' : 'Connecting to the city gridâ€¦'}</h1>{city.isError && <><p role="alert">Start the local backend to load the simulated city.</p><button onClick={() => void city.refetch()}>Try again</button></>}</div>;
  const openFeeders = ['A', 'B'].filter(id => feederState(snapshot, id) === 'OPEN');
  const requested = snapshot.services.filter(s => s.requested);
  const shed = requested.filter(s => servedWatts(s) < (s.requested_w ?? s.watts));
  const servedW = snapshot.allocation.served_w;
  const requestedW = requested.reduce((sum, s) => sum + (s.requested_w ?? s.watts), 0);
  const selectedService = snapshot.services.find(s => s.id === selected);
  const recovering = snapshot.proposed_mask !== snapshot.modeled_mask;
  const disabled = pending || city.isError || city.isPlaceholderData;
  const outcomes = [
    { label: 'Simple fixed priority', mask: snapshot.allocation.baseline_mask },
    { label: 'Our exact policy Â· proposed', mask: snapshot.proposed_mask },
  ];
  return <div className="city-demo">
    <header className="city-heading"><div><span className="city-eyebrow">Blackout Mesh / city command center</span><h1>Navigate the outage.</h1><p>See what lost power, why it was cut, and what can safely recover next.</p></div><div className="city-live"><span className={`city-dot ${city.isError ? 'is-shed' : 'is-served'}`} />{city.isError ? 'Stale Â· last known state' : 'Live simulation'}<small>Run {snapshot.site?.run_id}</small></div></header>
    <p className="city-boundary">Illustrative city; electrical demand and outages are simulated at lab scale. USB / ESP-NOW status is physical only when a device reports it.</p>
    {city.isError && <p className="city-warning" role="alert">Connection lost. Controls are disabled; the grid shows the last known snapshot.</p>}
    <section className="city-events" aria-label="City event controls"><span><Zap size={18} aria-hidden="true" /> One event updates the whole grid</span>
      <button disabled={disabled} onClick={() => void act(async () => { for (const { id } of ((snapshot.zones?.classroom as any)?.classrooms || []) ?? []) await changeClassroomLoad(id, true, snapshot.contract.identity.run_id); }, 'All classroom sessions requested.')}>Request all rooms</button>
      <button disabled={disabled} onClick={() => void act(() => changeCapacity(Math.round((snapshot.source.max_capacity_w ?? 14000) * 0.43)), `${Math.round((snapshot.source.max_capacity_w ?? 14000) * 0.43).toLocaleString()} W shortage applied. Protected demand takes priority.`)}>6 kW shortage</button>
      {Object.keys(snapshot.feeder_limits_w).map(id => <button key={id} disabled={disabled} onClick={() => void act(() => changeFeeder(id, openFeeders.includes(id)), `Feeder ${id} ${openFeeders.includes(id) ? 'repaired' : 'tripped'} in simulation.`)}>{openFeeders.includes(id) ? 'Repair' : 'Trip'} feeder {id}</button>)}
      <button disabled={disabled} onClick={() => void act(() => changeCapacity(snapshot.source.max_capacity_w ?? 14000), `${(snapshot.source.max_capacity_w ?? 14000).toLocaleString()} W supply restored. Loads still wait for stable evidence.`)}>Restore supply</button>
    </section><p className="city-feedback" role="status">{feedback || 'Start with â€œRequest all roomsâ€, then trigger a shortage or feeder trip.'}</p>
    <div className="city-scope-grid">
      {[{ label: 'Source power state', title: 'City source', capacity: snapshot.source.capacity_w, watts: servedW }, ...Object.keys(snapshot.feeder_limits_w).map(id => ({ label: `Feeder ${id} power state`, title: `Feeder ${id}`, capacity: snapshot.feeder_limits_w[id], watts: snapshot.services.filter(s => s.feeder === id).reduce((sum, s) => sum + servedWatts(s), 0) }))].map(scope => <section className="city-scope" key={scope.title} aria-label={scope.label} data-revision={snapshot.site?.revision}>
        <span>{scope.title}</span><strong>{scope.watts.toLocaleString()} / {scope.capacity.toLocaleString()} W</strong><small>Served / configured limit Â· revision {snapshot.site?.revision}</small>
      </section>)}
    </div>
    <div className="city-main-grid"><CityGrid snapshot={snapshot} selected={selected} onSelect={setSelected} />
      <section className="city-panel city-recovery" aria-label="Outage recovery guidance"><ShieldCheck aria-hidden="true" /><h2>Recovery navigator</h2>
        <ol><li className={openFeeders.length ? 'is-attention' : ''}><strong>Locate the interruption</strong><p>{openFeeders.length ? `Feeder ${openFeeders.join(' and ')} is open. Downstream loads have no supply.` : ['A', 'B'].every(id => feederState(snapshot, id) === 'CLOSED') ? 'Both feeders are closed. Check source capacity and requested demand.' : 'Feeder evidence is incomplete; inspect status before recovery.'}</p></li>
          <li className={snapshot.allocation.critical_shortfall_w ? 'is-attention' : ''}><strong>Check protected demand</strong><p>{snapshot.allocation.critical_shortfall_w ? `${snapshot.allocation.critical_shortfall_w.toLocaleString()} W critical shortfall. Capacity or reachability is insufficient.` : 'Critical requested demand is served in the current model.'}</p></li>
          <li className={shed.length ? 'is-attention' : ''}><strong>Repair, then restore supply</strong><p>{servedW.toLocaleString()} / {requestedW.toLocaleString()} W served. {shed.length} requested service{shed.length === 1 ? '' : 's'} waiting or shed.</p>{openFeeders.map(id => <button key={id} disabled={disabled} onClick={() => void act(() => changeFeeder(id, true), `Feeder ${id} repaired; restoration remains gated.`)}>Repair feeder {id}</button>)}{snapshot.source.capacity_w < (snapshot.source.max_capacity_w ?? 14000) && <button disabled={disabled} onClick={() => void act(() => changeCapacity(snapshot.source.max_capacity_w ?? 14000), 'Supply restored; waiting for stable capacity.')}>Restore supply</button>}</li>
          <li><strong>{recovering ? 'Restoration in progress' : shed.length ? 'Keep constraints visible' : 'Requested services recovered'}</strong><p>{recovering ? 'The controller is waiting for stability or adding services in stages. Keep this screen open to follow recovery.' : shed.length ? 'Unmet demand remains visible. A forecast cannot bypass a capacity limit or an open feeder.' : 'Every requested service is served. No physical power-delivery claim is implied.'}</p></li></ol>
        <p className="city-small">Recovery uses the existing controllerâ€™s evidence, stability and dwell checks. No automatic feeder bypass or mesh routing.</p>
      </section></div>
    <section className="city-panel city-decisions" aria-label="Power decision explanations"><h2>Every cut has a reason</h2>
      {selectedService && <p className="city-selected"><strong>Selected: {selectedService.name}</strong> â€” {decisionReason(snapshot, selectedService.id)}</p>}
      {shed.length ? shed.map(service => <article key={service.id} className="city-shed-reason"><strong>{service.name} Â· {((service.requested_w ?? service.watts) - servedWatts(service)).toLocaleString()} W shed</strong><p>{decisionReason(snapshot, service.id)}</p><details><summary>More decision detail</summary><p>{service.model_reason} Â· {service.tier} Â· feeder {service.feeder}</p></details></article>) : <p>All requested services are served.</p>}
    </section>
    <div className="city-bottom-grid"><DemandForecastPanel forecast={city.data.forecast} evidence={evidence.data} source={source} onSource={setSource} replayIndex={replayIndex} onNext={() => setReplayIndex(index => index === 7 ? 3 : index + 1)} />
      <section className="city-panel" aria-label="Real-time hardware monitoring"><header className="city-panel-heading"><div><h2><Radio size={19} aria-hidden="true" /> Real-time hardware monitoring</h2><p>Board A USB bridge and board B LED acknowledgments</p></div></header>
        <HardwarePanel hardware={city.data.hardware} /><dl className="city-hardware-values"><div><dt>Commanded mask</dt><dd>{city.data.hardware.commanded_mask == null ? 'Unknown' : `0x${city.data.hardware.commanded_mask.toString(16)}`}</dd></div><div><dt>Confirmed mask</dt><dd>{city.data.hardware.confirmed_mask == null ? 'Unknown' : `0x${city.data.hardware.confirmed_mask.toString(16)}`}</dd></div><div><dt>Last radio result</dt><dd>{city.data.hardware.last_radio_result ?? 'No device report'}</dd></div></dl>
        <p className="city-small">Disconnected hardware stays unknown. Software simulation and gateway test fixtures do not confirm physical LEDs. Hardware acceptance and its backup video are deferred.</p>
      </section></div>
    <section className="city-panel" aria-label="Simple controller comparison"><h2>Simple controller vs ours</h2><p>Same revision, demand, capacity and feeder limits. Compare candidate plans; restoration dwell is shown separately in the applied state.</p><div className="city-comparison">{outcomes.map(outcome => {
      const selectedServices = snapshot.services.filter((_, i) => outcome.mask & (1 << i));
      const watts = selectedServices.reduce((sum, s) => sum + s.watts, 0);
      const unmet = requested.filter((s, i) => s.tier === 'T1' && !selectedServices.some(selectedService => selectedService.id === s.id)).reduce((sum, s) => sum + s.watts, 0);
      return <article key={outcome.label}><h3>{outcome.label}</h3><strong>{watts.toLocaleString()} W</strong><p>Critical unmet: {unmet.toLocaleString()} W</p><p>{selectedServices.map(s => s.name).join(', ') || 'No services selected'}</p></article>;
    })}</div><p>Currently applied: <b>{servedW.toLocaleString()} W</b>{recovering ? ' Â· restoration gated' : ''}.</p>
      <details><summary>6 kW shortage benchmark Â· include switching costs</summary><div className="city-table-scroll"><table><caption>Five seeds per policy Â· simulated 40-minute runs Â· oracle is offline only</caption><thead><tr><th>Policy</th><th>Occupied service</th><th>Switches</th><th>Essential unmet Wh</th><th>Critical unmet Wh</th></tr></thead><tbody>{evidence.data?.ablation.map(row => <tr key={row.policy}><th>{row.policy}</th><td>{row.occupied_service_pct.toFixed(1)}%</td><td>{row.switching_count.toFixed(1)}</td><td>{row.essential_unmet_wh.toFixed(1)}</td><td>{row.critical_unmet_wh.toFixed(1)}</td></tr>)}</tbody></table></div><p>More occupied service can come with more switching and unmet essential demand. ML is optional; this table does not establish a universal improvement.</p></details>
    </section>
    <BenchmarkCard />
    <nav className="city-drilldowns" aria-label="Grid drill-downs"><Link to="/hospital">Hospital detail <ArrowRight size={16} aria-hidden="true" /></Link><Link to="/classrooms">Classroom detail <ArrowRight size={16} aria-hidden="true" /></Link><Link to="/console">History and engineering console <ArrowRight size={16} aria-hidden="true" /></Link></nav>
  </div>;
}

