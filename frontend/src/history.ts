import { useEffect, useState } from 'react';
import { useInfiniteQuery, useQuery, useQueryClient, InfiniteData } from '@tanstack/react-query';
import { Snapshot, SystemEvent } from './types';

export interface HistoryRecord {
  seq: number; record_id: string; run_id: string; site_id: string;
  kind: 'event' | 'decision' | 'telemetry'; timestamp: string; revision: number; provenance: string;
  payload: {
    snapshot?: Snapshot; event?: SystemEvent; event_ids?: string[];
    inputs?: unknown; policy?: unknown; model?: unknown;
    trail?: { observation: unknown; command_identity: unknown; validated_ack: unknown };
    capacity?: number; demand?: number; servedCount?: number; shedCount?: number;
  };
}
interface Page { items: HistoryRecord[]; next_cursor: number | null; retention_gap: boolean }
interface Selection { mode: 'LIVE' | 'HISTORY'; run: string; start: string; end: string; seq: number }
const STORAGE_KEY = 'prioritygrid-history-v1';
const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
export async function historyGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(API + '/api/v1/history/' + path, { signal });
  if (!response.ok) throw new Error('History request failed: HTTP ' + response.status);
  return response.json();
}
function initialSelection(): Selection {
  const fallback: Selection = { mode: 'LIVE', run: '', start: new Date(Date.now() - 3600000).toISOString(), end: '', seq: 0 };
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (saved && ['LIVE', 'HISTORY'].includes(saved.mode) && typeof saved.run === 'string' &&
        typeof saved.start === 'string' && Number.isFinite(Date.parse(saved.start)) &&
        typeof saved.end === 'string' && (!saved.end || Number.isFinite(Date.parse(saved.end)))) return { ...fallback, ...saved };
  } catch { /* Storage is optional; server records remain authoritative. */ }
  return fallback;
}
export function mergeRecords(records: HistoryRecord[]): HistoryRecord[] {
  return [...new Map(records.map(record => [record.seq, record])).values()].sort((a, b) => a.seq - b.seq);
}
export function useServerHistory(socketEvents: SystemEvent[]) {
  const client = useQueryClient();
  const [selection, setSelection] = useState(initialSelection);
  const [playing, setPlaying] = useState(false);
  const runs = useQuery({
    queryKey: ['history-runs', 'campus'],
    queryFn: ({ signal }) => historyGet<{ current_run_id: string; runs: { run_id: string; started_at: string }[] }>('runs', signal),
    refetchInterval: selection.mode === 'LIVE' ? 5000 : false,
  });
  const run = selection.mode === 'LIVE' ? runs.data?.current_run_id : selection.run || runs.data?.current_run_id;
  const key = ['history', 'campus', run, selection.start, selection.end];
  const request = (after: number, signal?: AbortSignal) => {
    const params = new URLSearchParams({ site_id: 'campus', run_id: run || '', after: String(after), limit: '200', start: selection.start });
    if (selection.end) params.set('end', selection.end);
    return historyGet<Page>('records?' + params, signal);
  };
  const pages = useInfiniteQuery({
    queryKey: key, enabled: !!run, initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => request(pageParam, signal),
    getNextPageParam: last => last.next_cursor ?? undefined,
  });
  const records = mergeRecords(pages.data?.pages.flatMap(page => page.items) || []);
  const cursor = records[records.length - 1]?.seq || 0;
  const tail = useQuery({
    queryKey: [...key, 'tail', cursor],
    enabled: !!run && selection.mode === 'LIVE' && !pages.hasNextPage && !pages.isFetching,
    queryFn: ({ signal }) => request(cursor, signal), refetchInterval: 2000,
  });
  useEffect(() => {
    if (pages.hasNextPage && !pages.isFetching) void pages.fetchNextPage();
  }, [pages.hasNextPage, pages.isFetching, pages.fetchNextPage]);
  useEffect(() => {
    if (!tail.data?.items.length) return;
    client.setQueryData<InfiniteData<Page, number>>(key, old => old ? {
      pages: [...old.pages, tail.data], pageParams: [...old.pageParams, cursor],
    } : old);
  }, [tail.data, client, run, selection.start, selection.end, cursor]);
  const socketIdentity = socketEvents.map(event => event.event_id).join(",");
  useEffect(() => {
    if (socketEvents.some(event => event.run_id === run && event.event_id)) {
      void client.invalidateQueries({ queryKey: [...key, 'tail'] });
    }
  }, [socketIdentity, run, client, selection.start, selection.end]);
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(selection)); } catch { /* Optional preferences only. */ }
  }, [selection]);
  const decisions = records.filter(record => record.kind === 'decision');
  const selected = decisions.find(record => record.seq === selection.seq) || decisions[0];
  const index = selected ? decisions.indexOf(selected) : 0;
  const selectIndex = (next: number) => setSelection(old => ({ ...old, seq: decisions[next]?.seq || 0 }));
  useEffect(() => {
    if (!playing || selection.mode !== 'HISTORY') return;
    if (index >= decisions.length - 1) { setPlaying(false); return; }
    const timer = window.setTimeout(() => selectIndex(index + 1), 1000);
    return () => window.clearTimeout(timer);
  }, [playing, selection.mode, index, decisions.length]);
  const cutoff = selection.mode === 'HISTORY' ? selected?.seq || 0 : Infinity;
  const events = records.filter(record => record.kind === 'event' && record.seq <= cutoff)
    .map(record => record.payload.event).filter((event): event is SystemEvent => !!event);
  if (selection.mode === 'LIVE') events.push(...socketEvents.filter(event => event.run_id === run && !!event.event_id && Date.parse(event.timestamp) >= Date.parse(selection.start) && (!selection.end || Date.parse(event.timestamp) <= Date.parse(selection.end))));
  const uniqueEvents = [...new Map(events.map(event => [event.event_id, event])).values()];
  const telemetry = records.filter(record => record.kind === 'telemetry' && (selection.mode === 'LIVE' || (!!selected && record.timestamp <= selected.timestamp))).map(record => ({
    time: record.timestamp, capacity: record.payload.capacity!, demand: record.payload.demand!,
    servedCount: record.payload.servedCount!, shedCount: record.payload.shedCount!,
  }));
  return {
    selection, setSelection, run, runs: runs.data?.runs || [], records, selected, decisions, index,
    playing, setPlaying, selectIndex, telemetry, events: uniqueEvents,
    snapshot: selected?.payload.snapshot,
    error: runs.error || pages.error || tail.error,
    pending: pages.isFetching,
    retentionGap: pages.data?.pages.some(page => page.retention_gap) || tail.data?.retention_gap,
  };
}
export type ServerHistory = ReturnType<typeof useServerHistory>;
