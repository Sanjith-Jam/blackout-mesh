import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { DistrictProposal } from '../types';
import DistrictRecoveryProposal from './DistrictRecoveryProposal';

const objective = (critical: number, served: number, switches: number) => ({ critical_served_w: critical, served_w: served, switching_actions: switches });
const proposal: DistrictProposal = {
  proposal_id: 'p', proposed_revision: 4, digest: 'abcdef0123456789', solver_status: 'FEASIBLE',
  objective_definition: 'lexicographic objective', load_semantics: 'divisible aggregate loads',
  configs_total: 4, configs_evaluated: 4, truncated: false,
  refused_configs: [{ edge_ids: ['tie:c'], reason: 'closing creates a loop' }],
  evaluations: [{ rank: 0, edge_ids: ['tie:a', 'tie:b'], objective: objective(800, 1000, 2), ac_status: 'REJECTED', ac_reason: 'Failed declared limit(s): voltage.',
    violations: [{ limit: 'voltage', component_id: 'L2', value: 0.91, limit_value: 0.94, unit: 'pu' }] },
    { rank: 1, edge_ids: ['tie:b'], objective: objective(800, 800, 1), ac_status: 'PASSED', ac_reason: 'ok', violations: [] }],
  baseline_objective: objective(0, 0, 0), bound_objective: objective(800, 1000, 2), candidate_edge_ids: ['tie:b'],
  switching_sequence: [{ operation: 'close', edge_id: 'tie:b' }], objective: objective(800, 800, 1),
  ac: { status: 'PASSED', engine: 'power-grid-model', engine_version: '1.13.193', model: 'unbalanced_three_phase', violations: [],
    min_voltage_pu: 0.98, max_voltage_pu: 1, max_line_loading: 0.2, max_transformer_loading: null, source_p_w: 802.5, loss_w: 2.5,
    balance_residual_w: 0.0001, reason: 'ok', unmodeled_checks: ['protection coordination'], safety_claim: 'NONE' },
};

describe('recovery proposal explanation', () => {
  it('shows objective, bound, the electrical refusal and the non-safety boundary', () => {
    render(<DistrictRecoveryProposal proposal={proposal} stale={false} />);
    expect(screen.getByRole('heading', { name: 'Proposal · FEASIBLE' })).toBeVisible();
    expect(screen.getByText(/Rejected rank 0 \(tie:a, tie:b/)).toHaveTextContent('voltage at L2: 0.91 vs 0.94 pu');
    expect(screen.getByText(/Watt-relaxation bound/)).toBeVisible();
    expect(screen.getByText(/close tie:b/)).toBeVisible();
    expect(screen.getByText(/Not permitted \(tie:c\)/)).toBeVisible();
    expect(screen.getByText(/not an operational safety approval/)).toBeVisible();
  });

  it('marks stale proposals', () => {
    render(<DistrictRecoveryProposal proposal={proposal} stale />);
    expect(screen.getByRole('heading', { name: 'Proposal · FEASIBLE · stale' })).toBeVisible();
  });
});
