import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { DistrictSnapshot } from '../types';
import DistrictApplianceTrace from './DistrictApplianceTrace';

const snapshot = {
  identity: { revision: 8 },
  profile: { id: 'mapped-study', appliance_count: 31, decision: { status: 'OPTIMAL', validation: 'PASSED' } },
  topology: { edges: [{ id: 'tx-to-room', from: 'transformer-1', to: 'load:building-1' }] },
  state: { loads: [{ building_id: 'building-1', served_w: 0, requested_w: 500,
    tier_rationale: 'Virtual teaching placement', appliances: [{ id: 'room.computers', service_id: 'L4',
      rated_max_w: 500, requested_w: 500, served_w: 0, reachable: false, priority_class: 'classroom_unknown',
      path_edge_ids: ['tx-to-room'] }] }] },
} as unknown as DistrictSnapshot;

describe('district appliance trace', () => {
  it('traces a transformer selection to the same-revision leaf decision and distinct rated/requested/served watts', () => {
    render(<DistrictApplianceTrace snapshot={snapshot} selected="transformer-1" />);
    expect(screen.getByRole('heading', { name: 'Mapped appliances · revision 8' })).toBeVisible();
    expect(screen.getByRole('table', { name: 'Appliances at building-1' })).toBeVisible();
    expect(screen.getByText('room.computers')).toBeVisible();
    expect(screen.getByText(/Source unreachable/)).toBeVisible();
    expect(screen.getByRole('columnheader', { name: 'Rated maximum' })).toBeVisible();
    expect(screen.getByText(/Physical confirmation: unknown/)).toBeVisible();
  });

  it('keeps the aggregate study outside the appliance claim', () => {
    const aggregate = { ...snapshot, profile: { ...snapshot.profile, appliance_count: 0 } };
    const { container } = render(<DistrictApplianceTrace snapshot={aggregate} selected="transformer-1" />);
    expect(container).toBeEmptyDOMElement();
  });
});
