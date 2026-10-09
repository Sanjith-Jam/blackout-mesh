import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, CheckCircle2, CircleHelp } from 'lucide-react';
import { getHospitalDemo, postHospitalDemo } from '../api';
import { HospitalDemoScenario, HospitalDemoSnapshot, HospitalDemoTransformer } from '../types';
import HospitalBlueprint from './HospitalBlueprint';
import './HospitalDemo.css';
import './ClassroomVisualizer.css';

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
  const [scannedZone, setScannedZone] = useState<string | null>(null);
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
    <main className="classroom-demo">
      <header className="classroom-demo__header">
        <div className="classroom-demo__brand"><span className="classroom-demo__brand-icon"><Activity size={22} aria-hidden="true" /></span><div><span className="classroom-demo__eyebrow">PriorityGrid · Simulated</span><h1 className="classroom-demo__title">Hospital power map</h1></div></div>
        <nav className="classroom-demo__nav" aria-label="Visualizer navigation"><Link className="classroom-demo__back" to="/classrooms">Classroom demo</Link><Link className="classroom-demo__back" to="/">Back to overview</Link></nav>
      </header>

      {error && <div className="classroom-demo__alert" role="alert">Connection lost — displaying last known simulated state. {error}</div>}
      
      <div className="classroom-demo__layout">
        <section className="classroom-demo__main" aria-label="Hospital power state">
          
          <div className="classroom-demo__metrics">
            <div className="classroom-demo__metric"><span className="classroom-demo__metric-label">Hospital faults</span><span className="classroom-demo__metric-value">{faults}</span></div>
            <div className="classroom-demo__metric"><span className="classroom-demo__metric-label">Unknowns</span><span className="classroom-demo__metric-value">{unknown}</span></div>
            <div className="classroom-demo__metric" style={{ gridColumn: 'span 2' }}><span className="classroom-demo__metric-label">Diagnosis summary</span><span className="classroom-demo__metric-value" style={{ fontSize: '1rem', marginTop: '0.4rem', color: 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block' }}>{snapshot?.summary ?? 'Loading synthetic sensor readings…'}</span></div>
          </div>

          {!snapshot ? <section className="classroom-demo__loading" aria-live="polite"><CircleHelp size={22} aria-hidden="true" />Loading transformer evidence…</section> : <>
            <section aria-label="Hospital floor plans">
              <p className="classroom-demo__blueprint-key">A shared supply feeds three hospital zones. Animated lines show voltage readings and energized outputs. A fault diagnosis does not trip a circuit in this demo.</p>
              <HospitalBlueprint snapshot={snapshot} connected={!stale} />
            </section>

            <div className="hospital-detail-grid">{transformers.map((transformer) => <article className={`hospital-transformer-detail severity-${transformer.diagnosis.severity}`} key={transformer.id}>
              <div className="hospital-transformer-heading"><div><p>{transformer.zone}</p><h2>{transformer.name}</h2></div><span className={`hospital-diagnosis-badge severity-${transformer.diagnosis.severity}`}>{transformer.diagnosis.code.replace(/_/g, ' ')}</span></div>
              <TransformerReadings transformer={transformer} />
              <div className="hospital-diagnosis-copy"><strong>{transformer.diagnosis.cause}</strong><ul>{transformer.diagnosis.evidence.map((item) => <li key={item}>{item}</li>)}</ul><p>{transformer.diagnosis.recommendation}</p></div>
            </article>)}</div>

            <CauseSummary transformers={transformers} />
            <aside className="hospital-threshold-note"><CheckCircle2 size={18} aria-hidden="true" /><div><strong>Demonstration thresholds only</strong><p>Overload: above 110% of rating. High temp: 80°C or more. Upstream loss: input &lt; 180V and output &lt; 100V. These heuristics are not certified protection settings.</p></div></aside>
          </>}
        </section>

        <aside className="classroom-demo__panel classroom-demo__controls" aria-labelledby="hospital-controls-title" aria-busy={pending}>
          <h2 id="hospital-controls-title">Demo controls</h2>
          <p>Scenarios inject synthetic sensor evidence to trigger different hospital diagnoses.</p>
          
          <div className="classroom-demo__button-stack" aria-label="Scan a hospital zone">
            {(['ICU', 'Theatre', 'Wards'] as const).map(zone => (
              <button 
                key={zone} 
                className={`classroom-demo__button ${scannedZone === zone ? 'classroom-demo__button--primary' : ''}`} 
                disabled={pending} 
                onClick={() => setScannedZone(zone)}
              >
                Scan {zone}{scannedZone === zone ? ' · scanned' : ''}
              </button>
            ))}
          </div>

          <div className="classroom-demo__control-divider" />
          
          <div className="classroom-demo__button-stack" aria-label="Apply hospital scenario">
            <button className={`classroom-demo__button ${selected === 'normal' ? 'classroom-demo__button--primary' : ''}`} disabled={pending} onClick={() => void selectScenario('normal')}>Normal operation</button>
          </div>
          
          <div className="classroom-demo__control-divider" />
          
          <div className="classroom-demo__button-stack">
            <button className={`classroom-demo__button ${selected === 'overload' ? 'classroom-demo__button--primary' : 'classroom-demo__button--warn'}`} disabled={pending} onClick={() => void selectScenario('overload')}>Overload</button>
            <button className={`classroom-demo__button ${selected === 'cooling_failure' ? 'classroom-demo__button--primary' : 'classroom-demo__button--warn'}`} disabled={pending} onClick={() => void selectScenario('cooling_failure')}>Cooling failure</button>
            <button className={`classroom-demo__button ${selected === 'upstream_loss' ? 'classroom-demo__button--primary' : 'classroom-demo__button--warn'}`} disabled={pending} onClick={() => void selectScenario('upstream_loss')}>Upstream loss</button>
            <button className={`classroom-demo__button ${selected === 'missing_sensor' ? 'classroom-demo__button--primary' : 'classroom-demo__button--warn'}`} disabled={pending} onClick={() => void selectScenario('missing_sensor')}>Missing sensor</button>
          </div>

          <div className="classroom-demo__control-divider" />
          
          <div className="classroom-demo__button-stack">
            <button className="classroom-demo__button" disabled={pending} onClick={() => { setScannedZone(null); void selectScenario('normal'); }}>Reset demo</button>
          </div>

          <p className="classroom-demo__feedback" aria-live="polite">{pending ? 'Applying virtual sensor readings…' : ''}</p>
          <p><strong>Note:</strong> Each choice changes synthetic readings. The backend recalculates its diagnosis based purely on these updated sensor values.</p>
        </aside>
      </div>
    </main>
  );
}
