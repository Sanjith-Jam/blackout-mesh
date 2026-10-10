import { FormEvent, useState } from 'react';
import { ServerHistory } from '../history';

export default function HistoryControls({ history }: { history: ServerHistory }) {
  const { selection, setSelection, selected } = history;
  const [start, setStart] = useState(selection.start);
  const [end, setEnd] = useState(selection.end);
  const [rangeError, setRangeError] = useState('');
  function applyRange(event: FormEvent) {
    event.preventDefault();
    if (!Number.isFinite(Date.parse(start)) || (end && (!Number.isFinite(Date.parse(end)) || Date.parse(end) < Date.parse(start)))) {
      setRangeError('Enter valid timestamps; end must be after start.'); return;
    }
    setRangeError('');
    setSelection(old => ({ ...old, start: new Date(start).toISOString(), end: end ? new Date(end).toISOString() : '', seq: 0 }));
    history.setPlaying(false);
  }
  return <section className="history-controls" aria-label="Recorded history and read-only playback">
    <div className="history-toolbar">
      <strong>{selection.mode === 'LIVE' ? 'LIVE · server-recorded history' : 'HISTORY · read-only playback'}</strong>
      <button className="btn-secondary" aria-pressed={selection.mode === 'LIVE'} onClick={() => {
        history.setPlaying(false); setSelection(old => ({ ...old, mode: 'LIVE' }));
      }}>Live</button>
      <button className="btn-secondary" aria-pressed={selection.mode === 'HISTORY'} onClick={() => {
        setSelection(old => ({ ...old, mode: 'HISTORY', run: history.run || '', seq: 0 }));
      }}>History</button>
      <label>Recorded run <select value={history.run || ''} disabled={selection.mode === 'LIVE'} onChange={event => {
        history.setPlaying(false); setSelection(old => ({ ...old, run: event.target.value, seq: 0 }));
      }}>{history.runs.map(run => <option key={run.run_id} value={run.run_id}>{new Date(run.started_at).toLocaleString()} · {run.run_id.slice(0, 8)}</option>)}</select></label>
    </div>
    <form className="history-toolbar" onSubmit={applyRange}>
      <label>From (UTC ISO) <input value={start} onChange={event => setStart(event.target.value)} /></label>
      <label>To (UTC ISO, blank = latest) <input value={end} onChange={event => setEnd(event.target.value)} /></label>
      <button className="btn-secondary" type="submit">Apply range</button>
    </form>
    {rangeError && <p role="alert">{rangeError}</p>}
    {history.error && <p role="alert">History unavailable: {history.error.message}. Live state is separate.</p>}
    {history.retentionGap && <p role="alert">This run has pruned records; earlier evidence may be unavailable.</p>}
    {history.pending && <p role="status">Loading recorded history…</p>}
    {selection.mode === 'HISTORY' && <>
      <div className="history-toolbar">
        <button className="btn-secondary" disabled={!history.index} onClick={() => { history.setPlaying(false); history.selectIndex(history.index - 1); }}>Previous decision</button>
        <button className="btn-secondary" disabled={!history.decisions.length} onClick={() => history.setPlaying(!history.playing)}>{history.playing ? 'Pause playback' : 'Play recorded decisions'}</button>
        <button className="btn-secondary" disabled={history.index >= history.decisions.length - 1} onClick={() => { history.setPlaying(false); history.selectIndex(history.index + 1); }}>Next decision</button>
        <span>{selected ? new Date(selected.timestamp).toLocaleString() + ' · revision ' + selected.revision + ' · ' + selected.provenance : 'No decisions in this range.'}</span>
      </div>
      {selected && <details>
        <summary>Incident → evidence → decision → applied state → ACK trail</summary>
        <p>Linked incidents: {selected.payload.event_ids?.join(', ') || 'None recorded'}</p>
        <p>Decision: {selected.record_id} · proposed mask {history.snapshot?.proposed_mask} · applied mask {history.snapshot?.modeled_mask}</p>
        <p>Command identity: {selected.payload.trail?.command_identity == null ? 'Unknown / hardware pending' : JSON.stringify(selected.payload.trail.command_identity)}</p>
        <p>Validated ACK: {selected.payload.trail?.validated_ack == null ? 'Unknown / hardware pending' : JSON.stringify(selected.payload.trail.validated_ack)}</p>
        <pre>{JSON.stringify({ inputs: selected.payload.inputs, policy: selected.payload.policy, model: selected.payload.model }, null, 2)}</pre>
      </details>}
      <p>Playback reads stored evidence. Live controls are disabled; no commands or controller ticks are issued by playback.</p>
    </>}
  </section>;
}
