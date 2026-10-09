import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import campus from '../test/fixtures/campus.json';
import { FakeSocket, clone } from '../test/mockApi';
import DemoDashboard from './DemoDashboard';

// Charts and the flow graph are canvas/layout heavy and irrelevant to the socket lifecycle.
vi.mock('../components/TopologyGraph', () => ({ default: () => null }));
vi.mock('../components/SourceCapacityDemandChart', () => ({ default: () => null }));
vi.mock('../components/AllocationHistoryChart', () => ({ default: () => null }));

function frame(revision: number, capacity: number, runId = 'run-a') {
  const snap = clone(campus);
  snap.published_revision = revision;
  snap.control_revision = revision;
  snap.source.capacity_w = capacity;
  snap.site = { ...snap.site, run_id: runId, revision };
  return snap;
}

describe('Live console socket lifecycle (#16, #13)', () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => vi.useRealTimers());

  it('does not reconnect after the page unmounts', async () => {
    const view = render(<MemoryRouter><DemoDashboard /></MemoryRouter>);
    expect(FakeSocket.instances).toHaveLength(1);
    view.unmount();
    expect(FakeSocket.instances[0].closed).toBe(true);
    await act(async () => { vi.advanceTimersByTime(10_000); });
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it('reconnects after an unexpected drop while mounted, using the configured API host', async () => {
    render(<MemoryRouter><DemoDashboard /></MemoryRouter>);
    expect(FakeSocket.instances[0].url).toMatch(/^ws:\/\/127\.0\.0\.1:8000\/ws\/live/);
    act(() => FakeSocket.instances[0].drop());
    await act(async () => { vi.advanceTimersByTime(3_500); });
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it('ignores malformed and out-of-order frames', async () => {
    render(<MemoryRouter><DemoDashboard /></MemoryRouter>);
    const ws = FakeSocket.instances[0];
    act(() => { ws.open(); ws.message(frame(5, 9000)); });
    expect(await screen.findByText('9000')).toBeInTheDocument();
    act(() => ws.message('{not json'));
    act(() => ws.message(frame(3, 4000))); // older revision of the same run arrives late
    expect(screen.getByText('9000')).toBeInTheDocument();
    expect(screen.queryByText('4000')).not.toBeInTheDocument();
    act(() => ws.message(frame(1, 7000, 'run-b'))); // a new run (reset/restart) is accepted
    expect(await screen.findByText('7000')).toBeInTheDocument();
  });
});
