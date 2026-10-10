import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { DistrictHistoryPage } from '../types';
import { AuditReplayList } from './DistrictAuditReplay';

const record = (revision: number, action: string, served: number) => ({ seq: revision, record_id: `r${revision}`, site_id: 'gnitc-demo', run_id: 'run',
  kind: 'district_action', timestamp: `t${revision}`, revision, provenance: 'SIMULATED',
  payload: { action: { action }, summary: { served_w: served, unmet_w: 0, critical_shortfall_w: 0, faults: [], applied_edge_ids: [] } } });

describe('district audit replay', () => {
  it('scrubs committed revisions without any command controls', () => {
    const page: DistrictHistoryPage = { items: [record(2, 'inject_fault', 4000), record(3, 'apply_recovery', 5900)], next_cursor: null, retention_gap: false, pruned_through: 0 };
    render(<AuditReplayList page={page} />);
    expect(screen.getByRole('status')).toHaveTextContent('Revision 3');
    fireEvent.change(screen.getByRole('slider'), { target: { value: '0' } });
    expect(screen.getByRole('status')).toHaveTextContent('Revision 2 · t2 · inject_fault');
    expect(screen.queryByRole('button')).toBeNull();
  });
});
