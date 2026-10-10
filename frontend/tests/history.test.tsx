import { afterEach, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HistoryRecord, ServerHistory, mergeRecords, useServerHistory } from '../src/history';
import HistoryControls from '../src/components/HistoryControls';

const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173' });
for (const [name, value] of Object.entries({ window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, IS_REACT_ACT_ENVIRONMENT: true })) {
  Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
}
let root: Root | undefined;
let client: QueryClient | undefined;
let latest: ServerHistory;
const now = new Date().toISOString();
function record(seq: number, kind: HistoryRecord['kind']): HistoryRecord {
  return { seq, record_id: 'id-' + seq, run_id: 'run', site_id: 'campus', kind, timestamp: now, revision: seq, provenance: 'SIMULATED',
    payload: kind === 'telemetry' ? { capacity: 14000, demand: 14000, servedCount: 6, shedCount: 0 } :
      kind === 'event' ? { event: { event_id: 'event-' + seq, run_id: 'run', timestamp: now, type: 'CAPACITY_CHANGE', description: 'Recorded event' } } :
      { event_ids: ['event-2'], inputs: { capacity_w: 14000 }, trail: { observation: null, command_identity: null, validated_ack: null } } };
}
function Widget() {
  latest = useServerHistory([]);
  return <HistoryControls history={latest} />;
}
async function waitFor(check: () => boolean) {
  for (let n = 0; n < 100; n++) {
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)); });
    if (check()) return;
  }
  throw new Error('History did not reach expected state');
}
async function mount() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const element = document.createElement('div');
  document.body.appendChild(element);
  root = createRoot(element);
  await act(async () => root!.render(<QueryClientProvider client={client!}><Widget /></QueryClientProvider>));
}
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined; client?.clear(); document.body.innerHTML = ''; localStorage.clear(); mock.restoreAll();
});
it('orders and deduplicates equal-timestamp records by stable sequence', () => {
  assert.deepEqual(mergeRecords([record(2, 'event'), record(1, 'telemetry'), record(2, 'event')]).map(r => r.seq), [1, 2]);
});
it('backfills pages and reconnect gaps; reload recovers range and records', async () => {
  const calls: number[] = [];
  const signals: AbortSignal[] = [];
  mock.method(globalThis, 'fetch', async (input: string, init: RequestInit) => {
    const url = new URL(String(input));
    if (url.pathname.endsWith('/runs')) return new Response(JSON.stringify({ current_run_id: 'run', runs: [{ run_id: 'run', started_at: now }] }));
    assert.notEqual(init?.method, 'POST');
    signals.push(init.signal as AbortSignal);
    const after = Number(url.searchParams.get('after'));
    calls.push(after);
    const items = after === 0 ? [record(1, 'telemetry'), record(2, 'event')] :
      after === 2 ? [record(3, 'decision'), record(4, 'telemetry')] :
      after === 4 ? [record(5, 'event'), record(6, 'decision')] : [];
    return new Response(JSON.stringify({ items, next_cursor: after === 0 ? 2 : null, retention_gap: false }));
  });
  await mount();
  await waitFor(() => latest.records.length === 6);
  assert.ok(calls.includes(2) && calls.includes(4));
  assert.equal(latest.events.length, 2);
  assert.equal(latest.telemetry[0].time, now);
  assert.ok(signals.every(signal => signal instanceof AbortSignal));
  const start = latest.selection.start;
  await act(async () => latest.setSelection(old => ({ ...old, mode: 'HISTORY', run: 'run', seq: 3 })));
  await act(async () => root!.unmount());
  client!.clear(); root = undefined;
  await mount();
  await waitFor(() => latest.records.length === 4);
  assert.equal(latest.selection.mode, 'HISTORY');
  assert.equal(latest.selection.start, start);
  assert.equal(latest.selected?.seq, 3);
});
it('read-only playback advances recorded decisions without control requests', async () => {
  localStorage.setItem('prioritygrid-history-v1', JSON.stringify({ mode: 'HISTORY', run: 'run', start: new Date(Date.now() - 3600000).toISOString(), end: '', seq: 3 }));
  const fetchMock = mock.method(globalThis, 'fetch', async (input: string, init: RequestInit) => {
    assert.notEqual(init?.method, 'POST');
    return new Response(JSON.stringify(String(input).endsWith('/runs') ?
      { current_run_id: 'run', runs: [{ run_id: 'run', started_at: now }] } :
      { items: [record(1, 'telemetry'), record(2, 'event'), record(3, 'decision'), record(4, 'decision')], next_cursor: null }));
  });
  await mount();
  await waitFor(() => latest.decisions.length === 2);
  const count = fetchMock.mock.calls.length;
  await act(async () => latest.selectIndex(1));
  assert.equal(latest.selected?.seq, 4);
  assert.equal(fetchMock.mock.calls.length, count);
  assert.ok(document.body.textContent?.includes('Unknown / hardware pending'));
});


it('cancels an obsolete history request when the recorded run changes', async () => {
  let obsolete: AbortSignal | undefined;
  mock.method(globalThis, 'fetch', async (input: string, init: RequestInit) => {
    const url = new URL(String(input));
    if (url.pathname.endsWith('/runs')) return new Response(JSON.stringify({ current_run_id: 'run', runs: [{ run_id: 'run', started_at: now }] }));
    if (url.searchParams.get('run_id') !== 'run') return new Response(JSON.stringify({ items: [], next_cursor: null }));
    obsolete = init.signal as AbortSignal;
    return new Promise<Response>((_, reject) => obsolete!.addEventListener('abort', () => reject(new DOMException('Cancelled', 'AbortError'))));
  });
  await mount();
  await waitFor(() => !!obsolete);
  await act(async () => latest.setSelection(old => ({ ...old, mode: 'HISTORY', run: 'other' })));
  await waitFor(() => !!obsolete?.aborted);
  assert.equal(obsolete?.aborted, true);
});
