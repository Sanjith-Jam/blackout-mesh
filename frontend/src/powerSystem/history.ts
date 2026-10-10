import { useEffect, useRef, useState } from 'react';
import type { PowerSystem } from './model';

/** Bounded client-side trend buffer sampled from the authoritative backend projection.
 * Values are copied from the backend as-is; nothing is interpolated or synthesised. */
export const HISTORY_LIMIT = 240;

export interface Sample {
  t: number;
  revision: number;
  capacity: number;
  requested: number;
  served: number;
  feeders: Record<string, { limit: number; requested: number; served: number; available: boolean }>;
  states: Record<string, number>;
}

export function sampleOf(data: PowerSystem): Sample {
  const states: Record<string, number> = {};
  for (const a of data.appliances) states[a.state] = (states[a.state] ?? 0) + 1;
  return {
    t: Date.parse(data.generated_at), revision: data.site.revision, capacity: data.source.capacity_w,
    requested: data.source.requested_w, served: data.source.served_w, states,
    feeders: Object.fromEntries(data.feeders.map(f => [f.id, { limit: f.available ? f.limit_w : 0, requested: f.requested_w, served: f.served_w, available: f.available }])),
  };
}

export function appendSample(history: Sample[], sample: Sample, limit = HISTORY_LIMIT): Sample[] {
  if (!Number.isFinite(sample.t)) return history;
  const last = history[history.length - 1];
  if (last && sample.t <= last.t) return history;  // out-of-order or duplicate frames never rewrite the past
  const next = [...history, sample];
  return next.length > limit ? next.slice(next.length - limit) : next;
}

export function usePowerHistory(data: PowerSystem | undefined) {
  const [history, setHistory] = useState<Sample[]>([]);
  const runId = useRef<string | null>(null);
  useEffect(() => {
    if (!data) return;
    if (runId.current && runId.current !== data.site.run_id) setHistory([]);  // a new run starts a new trend
    runId.current = data.site.run_id;
    setHistory(h => appendSample(h, sampleOf(data)));
  }, [data]);
  return history;
}
