import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDistrictHistory } from '../api';
import type { DistrictHistoryPage, DistrictSnapshot } from '../types';

type Summary = { served_w?: number; unmet_w?: number; critical_shortfall_w?: number; faults?: string[]; applied_edge_ids?: string[]; candidate_edge_ids?: string[]; solver_status?: string | null; reason?: string | null };

export function AuditReplayList({ page }: { page: DistrictHistoryPage }) {
  const [index, setIndex] = useState<number | null>(null);
  if (!page.items.length) return <p>No committed revisions in this run yet.</p>;
  const current = page.items[index ?? page.items.length - 1];
  const summary = (current.payload.summary || {}) as Summary;
  const action = (current.payload.action || {}) as { action?: string; component_id?: string | null };
  return <>
    <label className="district-scenario-label">Committed revision (read-only)
      <input type="range" min={0} max={page.items.length - 1} value={index ?? page.items.length - 1}
        aria-valuetext={`revision ${current.revision}`} onChange={event => setIndex(Number(event.target.value))} /></label>
    <p role="status">Revision {current.revision} · {current.timestamp} · {action.action || 'unknown'}{action.component_id ? ` ${action.component_id}` : ''}.
      Served {summary.served_w ?? 'unknown'} W; unmet {summary.unmet_w ?? 'unknown'} W; critical shortfall {summary.critical_shortfall_w ?? 'unknown'} W.
      Faults: {summary.faults?.join(', ') || 'none'}. Applied ties: {summary.applied_edge_ids?.join(', ') || 'none'}.
      {summary.solver_status ? ` Proposal ${summary.solver_status}.` : ''} {summary.reason || ''}</p>
  </>;
}

export default function DistrictAuditReplay({ snapshot }: { snapshot: DistrictSnapshot }) {
  const runId = snapshot.identity.run_id;
  const history = useQuery({ queryKey: ['district-history', runId, snapshot.identity.revision], queryFn: ({ signal }) => getDistrictHistory(runId, signal), retry: 0 });
  return <section className="district-risk-card" aria-label="Audit replay">
    <h3>Audit replay</h3>
    <p>Journal: {snapshot.audit.journal}. Playback reads committed SQLite records and cannot issue commands.
      {snapshot.audit.rehydration ? ` Restart: ${snapshot.audit.rehydration.status} from run ${snapshot.audit.rehydration.from_run_id.slice(0, 8)} revision ${snapshot.audit.rehydration.from_revision}. ${snapshot.audit.rehydration.reason}` : ''}</p>
    {history.isError ? <p>History unavailable.</p> : history.data ? <AuditReplayList page={history.data} /> : <p>Loading history…</p>}
  </section>;
}
