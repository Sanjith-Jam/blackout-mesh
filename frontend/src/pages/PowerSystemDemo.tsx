import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { changeCapacity, changeFeeder, getPowerSystem, postHospitalDemo, requestAppliance } from '../api';
import ApplianceDetail from '../powerSystem/ApplianceDetail';
import ElectricalLaws from '../powerSystem/ElectricalLaws';
import FaultDetection from '../powerSystem/FaultDetection';
import FloorPlan from '../powerSystem/FloorPlan';
import NetworkView from '../powerSystem/NetworkView';
import Overview from '../powerSystem/Overview';
import { usePowerHistory } from '../powerSystem/history';
import { APPLIANCE_STATE, EDGE_STATE, OVERALL_LABEL } from '../powerSystem/model';
import '../powerSystem/PowerSystem.css';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'floor', label: 'Floor Plan' },
  { id: 'network', label: 'Electrical Network' },
  { id: 'faults', label: 'Fault Detection' },
  { id: 'laws', label: 'Electrical Laws' },
] as const;
type Tab = typeof TABS[number]['id'];
const DROP_CAPACITY_W = 6000;
const STALE_AFTER_MS = 5000;

function Legend() {
  return <div className="ps-legend-panel" aria-label="Drawing legend">
    <ul className="ps-legend">{Object.entries(APPLIANCE_STATE).map(([k, s]) => <li key={k}><span className={`ps-legend-chip ${s.className}`}>{s.glyph}</span>{s.label}</li>)}</ul>
    <ul className="ps-legend">{Object.entries(EDGE_STATE).map(([k, s]) => <li key={k}><svg width="34" height="10" aria-hidden="true" className={`ps-wire ${s.className}`}><path d="M2 5 H32" className="ps-wire-base" /></svg>{s.label}</li>)}</ul>
    <p className="ps-muted">P1–P7 is the optimizer's priority class (🛡 protected). Room LEDs are room-level summaries; no appliance has its own LED, and an LED never proves appliance power.</p>
  </div>;
}

export default function PowerSystemDemo() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.some(t => t.id === params.get('view')) ? params.get('view') : 'floor') as Tab;
  const setTab = (id: Tab) => setParams(p => { const n = new URLSearchParams(p); n.set('view', id); return n; }, { replace: true });
  const [selected, setSelected] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<{ text: string; error: boolean } | null>(null);
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);
  const query = useQuery({ queryKey: ['power-system'], queryFn: ({ signal }) => getPowerSystem(signal), refetchInterval: 1000, retry: 1,
    placeholderData: previous => previous });
  const data = query.data;
  const history = usePowerHistory(data);

  const act = async (operation: () => Promise<unknown>, message: string) => {
    if (inFlight.current) return;
    inFlight.current = true; setPending(true); setFeedback({ text: 'Sending command to the backend…', error: false });
    try {
      await operation();
      await queryClient.invalidateQueries({ queryKey: ['power-system'] });
      setFeedback({ text: message, error: false });
    } catch (error) {
      await queryClient.invalidateQueries({ queryKey: ['power-system'] });
      setFeedback({ text: `Command failed: ${error instanceof Error ? error.message : 'unknown error'}. The view shows the backend's actual state.`, error: true });
    } finally { inFlight.current = false; setPending(false); }
  };

  if (!data) return <div className="ps-page ps-loading"><Activity aria-hidden="true" />
    <h1>{query.isError ? 'Power system unavailable' : 'Connecting to the PriorityGrid backend…'}</h1>
    {query.isError && <><p role="alert">The backend at port 8000 did not answer. Start it to load the simulated site.</p><button onClick={() => void query.refetch()}>Try again</button></>}</div>;

  const stale = query.isError || Date.now() - Date.parse(data.generated_at) > STALE_AFTER_MS;
  const disabled = pending || stale;
  const overall = (data.diagnosis as { overall: string }).overall;
  const actions = {
    killFeeder: (id: string) => void act(() => changeFeeder(id, false), `Feeder ${id} opened in the simulation.`),
    restoreFeeder: (id: string) => void act(() => changeFeeder(id, true), `Feeder ${id} closed in the simulation; restoration is gated.`),
    dropCapacity: () => void act(() => changeCapacity(DROP_CAPACITY_W), `Source capacity dropped to ${DROP_CAPACITY_W.toLocaleString('en-US')} W.`),
    restoreCapacity: () => void act(() => changeCapacity(data.source.normal_capacity_w), 'Source capacity restored; restoration is gated.'),
    injectDropout: () => void act(() => postHospitalDemo('inject_fault', 'ICU', undefined, 'sensor_dropout'), 'ICU transformer sensors stop reporting (injected).'),
    clearHospitalFault: () => void act(() => postHospitalDemo('clear_fault'), 'Injected hospital fault cleared.'),
  };
  const showOnPlan = (rooms: string[]) => { setHighlight(rooms); setTab('floor'); };
  const onRequest = (id: string, requested: boolean) => void act(() => requestAppliance(id, requested), `${id} requested ${requested ? 'on' : 'off'}.`);

  return <div className="ps-page">
    <header className="ps-header">
      <div><span className="ps-eyebrow">PriorityGrid · appliance-level power management</span>
        <h1>Six rooms, {data.appliances.length} appliances, one decision.</h1>
        <p>Every appliance is its own optimizer decision. Watch faults change individual allocations and read why.</p></div>
      <div className={`ps-live${stale ? ' is-stale' : ''}`} role="status" aria-label="Backend connection">
        <span className="ps-dot" aria-hidden="true" />{stale ? 'Stale · last known backend state' : 'Live backend simulation'}
        <small>Run {data.site.run_id.slice(0, 8)} · revision {data.site.revision} · {OVERALL_LABEL[overall] ?? overall}</small></div>
    </header>
    <p className="ps-boundary">{data.boundary}</p>
    {stale && <p className="ps-warning" role="alert">Connection lost or data is older than {STALE_AFTER_MS / 1000} s. Controls are disabled and the drawing shows the last known backend state.</p>}
    <div className="ps-tabs" role="tablist" aria-label="Demo sections">
      {TABS.map(t => <button key={t.id} id={`tab-${t.id}`} role="tab" aria-selected={tab === t.id} aria-controls={`panel-${t.id}`}
        className={tab === t.id ? 'is-active' : ''} onClick={() => setTab(t.id)}>{t.label}{t.id === 'faults' && data.faults.length ? ` (${data.faults.length})` : ''}</button>)}
    </div>
    <div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="ps-panel-body">
      {tab === 'overview' && <Overview data={data} history={history} onOpenRoom={room => showOnPlan([room])} />}
      {(tab === 'floor' || tab === 'network') && <>
        <div className="ps-view-switch" role="radiogroup" aria-label="Power system view">
          <button role="radio" aria-checked={tab === 'floor'} className={tab === 'floor' ? 'is-active' : ''} onClick={() => setTab('floor')}>Floor plan</button>
          <button role="radio" aria-checked={tab === 'network'} className={tab === 'network' ? 'is-active' : ''} onClick={() => setTab('network')}>Electrical network</button>
          {highlight.length > 0 && <button className="ps-link" onClick={() => setHighlight([])}>Clear highlight ({highlight.join(', ')})</button>}
        </div>
        <div className="ps-plan-layout">
          {tab === 'floor' ? <FloorPlan data={data} selected={selected} onSelect={setSelected} highlight={highlight} />
            : <NetworkView data={data} selected={selected} onSelect={setSelected} highlight={highlight} />}
          <ApplianceDetail data={data} id={selected} onClose={() => setSelected(null)} onRequest={onRequest} disabled={disabled} />
        </div>
        <Legend />
      </>}
      {tab === 'faults' && <FaultDetection data={data} actions={actions} disabled={disabled} feedback={feedback} onShowOnPlan={showOnPlan} />}
      {tab === 'laws' && <ElectricalLaws data={data} />}
    </div>
    {tab !== 'faults' && feedback && <p className={`ps-feedback${feedback.error ? ' is-error' : ''}`} role={feedback.error ? 'alert' : 'status'}>{feedback.text}</p>}
  </div>;
}
