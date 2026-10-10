import { describe, expect, it } from 'vitest';
import type { DistrictSnapshot } from '../types';
import { inspect } from './DistrictAssetInspector';

const snapshot = {
  topology: { nodes: [{ id: 'load:b1', role: 'load', building_id: 'b1', lon: 0, lat: 0 }], edges: [{ id: 'e1', from: 'a', to: 'b', kind: 'branch', limit_w: 1000, voltage_v: 400, rating_a: 100 }] },
  state: { edges: [{ id: 'e1', closed: true, faulted: false, energized: false, flow_w: 0 }], restoration: {}, transformers: [], source_capacity_w: 6000,
    loads: [{ building_id: 'b1', requested_w: 500, served_w: 200, unmet_w: 300, grid_served_w: 200, grid_requested_w: 500, local_supply_w: 0, tier: 'critical', tier_rationale: 'synthetic', local_supply_semantics: 'DISABLED', appliances: [] }] },
} as unknown as DistrictSnapshot;

describe('asset inspector', () => {
  it('explains a dead line and a partially served load', () => {
    expect(inspect(snapshot, 'e1')!.lines[0]).toBe('Closed but de-energized.');
    expect(inspect(snapshot, 'load:b1')!.lines[0]).toBe('Partially served: 200 W of 500 W (300 W unmet).');
    expect(inspect(snapshot, null)).toBeNull();
  });
});
