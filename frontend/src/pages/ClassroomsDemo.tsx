import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, AlertTriangle, Zap } from 'lucide-react';
import { getClassroomDemo, postClassroomDemo } from '../api';
import { ClassroomDemoRoom, ClassroomDemoSnapshot } from '../types';
import './ClassroomVisualizer.css';
import ClassroomBlueprint from './ClassroomBlueprint';

export default function ClassroomsDemo() {
  const [snapshot, setSnapshot] = useState<ClassroomDemoSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const pollInFlight = useRef(false);
  const actionInFlight = useRef(false);
  const requestVersion = useRef(0);
  const mounted = useRef(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (pollInFlight.current || actionInFlight.current) return;
    pollInFlight.current = true;
    const version = requestVersion.current;
    try {
      const data = await getClassroomDemo(signal);
      if (mounted.current && version === requestVersion.current) {
        setSnapshot(data);
        setError(null);
      }
    } catch (cause) {
      if (mounted.current && version === requestVersion.current && !signal?.aborted) {
        setError(cause instanceof Error ? cause.message : 'Could not load classroom state.');
      }
    } finally {
      pollInFlight.current = false;
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    void refresh(controller.signal);
    const timer = window.setInterval(() => void refresh(controller.signal), 1000);
    return () => {
      mounted.current = false;
      controller.abort();
      window.clearInterval(timer);
    };
  }, [refresh]);

  const runAction = async (action: 'scan' | 'normal' | 'overload' | 'reset', classroomId?: ClassroomDemoRoom['id']) => {
    if (actionInFlight.current) return;
    actionInFlight.current = true;
    requestVersion.current += 1;
    setPending(true);
    setError(null);
    setFeedback(null);
    try {
      const next = await postClassroomDemo(action, classroomId);
      if (mounted.current) {
        setSnapshot(next);
        setFeedback(action === 'scan' ? `Scanned ${classroomId}.` : `${action === 'normal' ? 'Normal 8,000 W' : action === 'overload' ? 'Overload 3,400 W' : 'Classroom demo reset'} applied.`);
      }
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : 'The classroom action failed.');
    } finally {
      actionInFlight.current = false;
      if (mounted.current) setPending(false);
    }
  };

  if (!snapshot) {
    return <main className="classroom-demo classroom-demo__loading" aria-busy={!error}>
      {error ? <AlertTriangle size={30} aria-hidden="true" /> : <Activity size={30} aria-hidden="true" />}
      <h1>{error ? 'Classroom demo unavailable' : 'Connecting to classroom supply…'}</h1>
      {error && <><p role="alert">{error}</p><button className="classroom-demo__button" onClick={() => void refresh()}>Try again</button></>}
    </main>;
  }

  return <main className="classroom-demo">
    <header className="classroom-demo__header">
      <div className="classroom-demo__brand"><span className="classroom-demo__brand-icon"><Zap size={22} aria-hidden="true" /></span><div><span className="classroom-demo__eyebrow">PriorityGrid · Simulated</span><h1 className="classroom-demo__title">Classroom electrical blueprint</h1></div></div>
      <nav className="classroom-demo__nav" aria-label="Visualizer navigation"><Link className="classroom-demo__back" to="/hospital">Hospital demo</Link><Link className="classroom-demo__back" to="/">Back to overview</Link></nav>
    </header>
    {error && <div className="classroom-demo__alert" role="alert">Connection lost — displaying last known simulated state. {error}</div>}
    <div className="classroom-demo__layout">
      <section className="classroom-demo__main" aria-label="Classroom power state">
        <div className="classroom-demo__metrics">
          <div className="classroom-demo__metric"><span className="classroom-demo__metric-label">Classroom-only supply</span><span className="classroom-demo__metric-value">{snapshot.capacity_w.toLocaleString()} W</span></div>
          <div className="classroom-demo__metric"><span className="classroom-demo__metric-label">Requested</span><span className="classroom-demo__metric-value">{snapshot.requested_w.toLocaleString()} W</span></div>
          <div className="classroom-demo__metric"><span className="classroom-demo__metric-label">Served</span><span className="classroom-demo__metric-value">{snapshot.served_w.toLocaleString()} W</span></div>
          <div className="classroom-demo__metric"><span className="classroom-demo__metric-label">Unmet</span><span className="classroom-demo__metric-value">{snapshot.shortfall_w.toLocaleString()} W</span></div>
        </div>
        <section aria-label="Classroom floor plans" aria-describedby="classroom-blueprint-key">
          <p id="classroom-blueprint-key" className="classroom-demo__blueprint-key">Room plans show equipment and routed conduit. Green moving dashes mark energized paths; gray dashed runs and dark fixtures are shed. {error ? 'Motion pauses while the connection is unavailable.' : ''}</p>
          {snapshot.rooms.map(room => <ClassroomBlueprint key={room.id} room={room} selected={snapshot.selected_classroom_id === room.id} energized={!error} />)}
        </section>
      </section>
      <aside className="classroom-demo__panel classroom-demo__controls" aria-labelledby="classroom-controls-title" aria-busy={pending}>
        <h2 id="classroom-controls-title">Demo controls</h2>
        <p>Scans and power presets update the simulated classroom allocator.</p>
        <div className="classroom-demo__button-stack" aria-label="Scan a classroom RFID card">
          {(['CR1', 'CR2', 'CR3'] as const).map(id => <button key={id} className={`classroom-demo__button ${snapshot.selected_classroom_id === id ? 'classroom-demo__button--primary' : ''}`} aria-pressed={snapshot.selected_classroom_id === id} disabled={pending} onClick={() => void runAction('scan', id)}>Scan {id}{snapshot.rooms.find(room => room.id === id)?.rfid_active ? ' · scanned' : ''}</button>)}
        </div>
        <div className="classroom-demo__control-divider" />
        <div className="classroom-demo__button-stack">
          <button className="classroom-demo__button" disabled={pending} onClick={() => void runAction('normal')}>Normal · 8,000 W</button>
          <button className="classroom-demo__button classroom-demo__button--warn" disabled={pending} onClick={() => void runAction('overload')}>Overload · 3,400 W</button>
          <button className="classroom-demo__button" disabled={pending} onClick={() => void runAction('reset')}>Reset demo</button>
        </div>
        <p className="classroom-demo__feedback" aria-live="polite">{pending ? 'Updating classroom state…' : feedback ?? ''}</p>
        <p><strong>Policy:</strong> {snapshot.policy}</p>
        <p>RFID scan state is shown as session evidence. The 8,000 W budget belongs to this classroom demo and is separate from the six-service campus model.</p>
      </aside>
    </div>
  </main>;
}
