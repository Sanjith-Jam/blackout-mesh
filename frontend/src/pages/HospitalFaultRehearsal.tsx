import { useEffect, useRef, useState } from 'react';
import { postHospitalScenario } from '../api';
import type { HospitalDemoScenario, HospitalFaultSnapshot } from '../types';

const FAULTS: [NonNullable<HospitalDemoScenario>, string][] = [
  ['normal', 'Clear example'], ['overload', 'Overload'], ['cooling_failure', 'Cooling failure'],
  ['overload_cooling', 'Overload + cooling'], ['upstream_loss', 'Upstream loss'],
  ['missing_sensor', 'Sensor dropout'], ['stuck_sensor', 'Stuck sensor'],
];

export default function HospitalFaultRehearsal() {
  const [result, setResult] = useState<HospitalFaultSnapshot | null>(null);
  const [selected, setSelected] = useState<HospitalDemoScenario>(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  const show = async (scenario: NonNullable<HospitalDemoScenario>) => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setPending(true); setError('');
    try {
      const response = await postHospitalScenario(scenario, controller.signal);
      if (!controller.signal.aborted) { setResult(response); setSelected(scenario); }
    } catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Diagnostic example failed.'); }
    finally { if (!controller.signal.aborted) setPending(false); }
  };
  return <section className="classroom-demo__panel hospital-rehearsal" aria-label="Hospital fault rehearsal" aria-busy={pending}>
    <h2>Faults, evidence, and uncertainty</h2>
    <p>Steady-state diagnostic examples using separate 100 A transformer fixtures. These buttons do not inject faults into the live city or change its allocation.</p>
    <div className="hospital-rehearsal__buttons">{FAULTS.map(([scenario, label]) => <button key={scenario} className="classroom-demo__button" disabled={pending} aria-pressed={selected === scenario} onClick={() => void show(scenario)}>{label}</button>)}</div>
    {error && <p role="alert">{error}</p>}
    <div className="hospital-rehearsal__results">{result?.transformers.map(tx => <article key={tx.id} className={tx.diagnosis.abstention ? 'is-untrusted' : ''} aria-label={`${tx.id} diagnostic evidence`}>
      <h3>{tx.id} · {tx.zone}</h3><strong>{tx.diagnosis.abstention ? 'Cannot determine cause · sensor evidence untrusted' : tx.diagnosis.code.replace(/_/g, ' ')}</strong>
      {tx.diagnosis.hypotheses?.map((hypothesis, index) => <div key={hypothesis.id}><h4>{index + 1}. {hypothesis.cause}</h4><p>Evidence score {hypothesis.evidence_score} · heuristic, uncalibrated</p><ul>{hypothesis.supporting_evidence.map(item => <li key={item}>{item}</li>)}</ul></div>)}
      {tx.diagnosis.abstention && <div role="status"><p>{tx.diagnosis.abstention.details}</p><p><strong>Next check:</strong> {tx.diagnosis.abstention.next_check_needed}</p></div>}
    </article>)}</div>
  </section>;
}
