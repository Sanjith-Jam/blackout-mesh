import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, AlertTriangle, ArrowLeft, CheckCircle2, CircleHelp, RefreshCw, Thermometer, Zap } from 'lucide-react';
import { getHospitalDemo, postHospitalDemo } from '../api';
import { HospitalDemoScenario, HospitalDemoSnapshot, HospitalDemoTransformer } from '../types';
import HospitalBlueprint from './HospitalBlueprint';
import './HospitalDemo.css';

const scenarios: { id: HospitalDemoScenario; label: string; detail: string }[] = [
  { id: 'normal', label: 'Normal operation', detail: 'All transformers within demo ranges' },
  { id: 'overload', label: 'Overload', detail: 'TX2 current above its rated threshold' },
  { id: 'cooling_failure', label: 'Cooling failure', detail: 'TX2 is hot while cooling is reported failed' },
  { id: 'upstream_loss', label: 'Upstream loss', detail: 'Low input and output voltage readings' },
  { id: 'missing_sensor', label: 'Missing sensor', detail: 'TX2 current reading is unavailable' },
];

function scenarioFromEvidence(snapshot: HospitalDemoSnapshot): HospitalDemoScenario {
  const codes = snapshot.transformers.map((transformer) => transformer.diagnosis.code);
  if (codes.includes('UPSTREAM_LOSS')) return 'upstream_loss';
  if (codes.includes('OVERLOAD')) return 'overload';
  if (codes.includes('COOLING_FAILURE')) return 'cooling_failure';
  if (codes.includes('UNKNOWN')) return 'missing_sensor';
  return 'normal';
}

function number(value: number | null, unit: string, digits = 1) {
  return value == null ? 'Unavailable' : `${value.toFixed(digits)} ${unit}`;
}

function CauseSummary({ transformers }: { transformers: HospitalDemoTransformer[] }) {
  const evidence = useMemo(() => transformers.map((transformer) => {
    const explanations: Record<string, [string, string]> = {
      UNKNOWN: ['Insufficient evidence', 'Missing sensor readings prevent a supported diagnosis.'],
      UPSTREAM_LOSS: ['Upstream supply is a plausible cause', 'Incoming and outgoing voltage are low across the monitored zones.'],
      OVERLOAD: ['Excess load is a plausible cause', 'Current exceeds the configured rating threshold while supply and cooling remain available. These readings do not exclude an internal fault.'],
      COOLING_FAILURE: ['Cooling fault is a plausible cause', 'The transformer is hot at normal current, and cooling is reported failed.'],
      HIGH_TEMPERATURE: ['Elevated temperature', 'The available readings do not isolate the thermal fault.'],
      NORMAL: ['No configured demo fault found', 'The backend found no exceeded demonstration threshold.'],
    };
    const [title, detail] = explanations[transformer.diagnosis.code] ?? ['Unclassified condition', transformer.diagnosis.cause];
    return { transformer, title, detail };
  }), [transformers]);

  return (
    <section className="hospital-cause-panel" aria-labelledby="hospital-cause-heading">
      <div className="hospital-panel-heading">
        <span className="hospital-heading-icon"><Activity size={17} aria-hidden="true" /></span>
        <div><h2 id="hospital-cause-heading">Likely cause from sensor evidence</h2><p>Threshold-based demonstration diagnosis; not a protection system.</p></div>
      </div>
      <div className="hospital-cause-list">
        {evidence.map(({ transformer, title, detail }) => (
          <article className="hospital-cause-row" key={transformer.id}>
            <span className={`hospital-cause-dot is-${transformer.diagnosis.severity}`} aria-hidden="true" />
            <div><strong>{transformer.id} · {title}</strong><p>{detail}</p></div>
          </article>
        ))}
      </div>
    </section>
  );
}

function TransformerReadings({ transformer }: { transformer: HospitalDemoTransformer }) {
  const { sensors } = transformer;
  const readings: [string, string, string][] = [
    ['Current', number(sensors.current_a, 'A'), 'current'],
    ['Temperature', number(sensors.temperature_c, '°C'), 'temperature'],
    ['Input voltage', number(sensors.input_voltage_v, 'V', 0), 'input-voltage'],
    ['Output voltage', number(sensors.output_voltage_v, 'V', 0), 'output-voltage'],
    ['Cooling', sensors.cooling_ok == null ? 'Unknown' : sensors.cooling_ok ? 'Operating' : 'Failed', 'cooling'],
  ];
  return <dl className="hospital-reading-grid">{readings.map(([label, value, key]) => <div className="hospital-reading" key={key}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}

export default function HospitalDemo() {
  const [snapshot, setSnapshot] = useState<HospitalDemoSnapshot | null>(null);
  const [selected, setSelected] = useState<HospitalDemoScenario | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const requestVersion = useRef(0);
  const actionBusy = useRef(false);
  const pollBusy = useRef(false);
  const mounted = useRef(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (actionBusy.current || pollBusy.current) return;
    pollBusy.current = true;
    const version = requestVersion.current;
    try {
      const next = await getHospitalDemo(signal);
      if (mounted.current && version === requestVersion.current && !signal?.aborted) {
        setSnapshot(next);
        setSelected(scenarioFromEvidence(next));
        setError(null);
        setStale(false);
      }
    } catch {
      if (mounted.current && version === requestVersion.current && !signal?.aborted) {
        setError('The hospital sensor demo is unavailable. Check the backend connection and retry.');
        setStale(true);
      }
    } finally { pollBusy.current = false; }
  }, []);

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    void refresh(controller.signal);
    const timer = window.setInterval(() => void refresh(controller.signal), 1000);
    return () => { mounted.current = false; controller.abort(); window.clearInterval(timer); };
  }, [refresh]);

  const selectScenario = async (scenario: HospitalDemoScenario) => {
    if (actionBusy.current) return;
    actionBusy.current = true;
    requestVersion.current += 1;
    setPending(true);
    setSelected(scenario);
    setError(null);
    try {
      const next = await postHospitalDemo(scenario);
      if (mounted.current) { setSnapshot(next); setSelected(scenarioFromEvidence(next)); setStale(false); }
    } catch {
      if (mounted.current) { setError('That scenario could not be applied. The displayed readings may be out of date.'); setStale(true); }
    } finally {
      actionBusy.current = false;
      if (mounted.current) setPending(false);
    }
  };

  const transformers = snapshot?.transformers ?? [];
  const faults = transformers.filter((transformer) => !['NORMAL', 'UNKNOWN'].includes(transformer.diagnosis.code)).length;
  const unknown = transformers.filter((transformer) => transformer.diagnosis.code === 'UNKNOWN').length;

  return (
    <main className="hospital-demo">
      <header className="hospital-header">
        <Link to="/" className="hospital-back"><ArrowLeft size={17} aria-hidden="true" /> Home</Link>
        <div className="hospital-brand"><span className="hospital-brand-mark"><Activity size={19} aria-hidden="true" /></span><span>PriorityGrid <small>Virtual hospital diagnostics</small></span></div>
        <div className="hospital-header-actions"><nav className="hospital-route-links" aria-label="Demo navigation"><Link to="/classrooms">Classroom demo</Link><Link to="/demo">Live dashboard</Link></nav><span className="hospital-mode"><span /> SIMULATED</span></div>
      </header>

      <div className="hospital-content">
        <section className="hospital-title-row">
          <div><p className="hospital-eyebrow">Electrical monitoring · three virtual transformers</p><h1>Hospital power overview</h1><p className="hospital-subtitle">Follow sensor readings from the upstream supply through each transformer to its hospital zone.</p></div>
          <div className="hospital-summary" aria-live="polite"><div className="hospital-summary-icon"><Zap size={18} aria-hidden="true" /></div><div><strong>{unknown ? `${unknown} diagnosis${unknown > 1 ? 'es' : ''} unknown` : faults ? `${faults} transformer alert${faults > 1 ? 's' : ''}` : 'Readings within demo limits'}</strong><span>{snapshot?.summary ?? 'Loading synthetic sensor readings…'}</span></div></div>
        </section>

        {error && <div className="hospital-error" role="alert"><AlertTriangle size={18} aria-hidden="true" />{error}<button type="button" onClick={() => void refresh()}><RefreshCw size={15} aria-hidden="true" /> Retry</button></div>}
        {snapshot && stale && <div className="hospital-stale" role="status"><CircleHelp size={16} aria-hidden="true" /> Showing the last sensor snapshot. Flow animation is paused until updates resume.</div>}

        <section className="hospital-scenario-panel" aria-labelledby="scenario-heading">
          <div className="hospital-panel-heading"><span className="hospital-heading-icon"><Thermometer size={17} aria-hidden="true" /></span><div><h2 id="scenario-heading">Choose a sensor scenario</h2><p>Each choice changes synthetic readings; the diagnosis is computed from those readings.</p></div></div>
          <div className="hospital-scenario-grid" role="group" aria-label="Sensor scenarios">
            {scenarios.map((scenario) => <button key={scenario.id} type="button" className={`hospital-scenario ${selected === scenario.id ? 'selected' : ''}`} aria-pressed={selected === scenario.id} disabled={pending} onClick={() => void selectScenario(scenario.id)}><strong>{scenario.label}</strong><span>{scenario.detail}</span></button>)}
          </div>
          {pending && <p className="hospital-pending" role="status">Applying virtual sensor readings…</p>}
        </section>

        {!snapshot ? <section className="hospital-loading" aria-live="polite"><CircleHelp size={22} aria-hidden="true" />Loading transformer evidence…</section> : <>
          <section className="hospital-blueprint-panel" aria-label="Hospital floor plans">
            <HospitalBlueprint snapshot={snapshot} connected={!stale} />
          </section>

          <div className="hospital-detail-grid">{transformers.map((transformer) => <article className={`hospital-transformer-detail severity-${transformer.diagnosis.severity}`} key={transformer.id}>
            <div className="hospital-transformer-heading"><div><p>{transformer.zone}</p><h2>{transformer.name}</h2></div><span className={`hospital-diagnosis-badge severity-${transformer.diagnosis.severity}`}>{transformer.diagnosis.code.replace(/_/g, ' ')}</span></div>
            <TransformerReadings transformer={transformer} />
            <div className="hospital-diagnosis-copy"><strong>{transformer.diagnosis.cause}</strong><ul>{transformer.diagnosis.evidence.map((item) => <li key={item}>{item}</li>)}</ul><p>{transformer.diagnosis.recommendation}</p></div>
          </article>)}</div>

          <CauseSummary transformers={transformers} />
          <aside className="hospital-threshold-note"><CheckCircle2 size={18} aria-hidden="true" /><div><strong>Demonstration thresholds only</strong><p>Overload: above 110% of rating. High temperature: 80 °C or more. Possible upstream loss: input below 180 V and output below 100 V. These heuristics are not certified protection settings.</p></div></aside>
        </>}
      </div>
    </main>
  );
}
