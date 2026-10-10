import { describe, expect, it } from 'vitest';
import { hourSummary } from './DistrictEnergyCharts';

describe('energy charts', () => {
  it('summarises an hour without calling scheduled import delivered energy', () => {
    const text = hourSummary({ hour: 20, demand_w: 6200, pv_w: 0, baseline_grid_w: 6200, dispatch_grid_w: 6200, battery_soc_wh: 120,
      pv_used_w: 0, battery_charge_w: 0, battery_discharge_w: 0, grid_import_w: 6200, loss_wh: 0 });
    expect(text).toContain('20:00 · demand 6,200 W');
    expect(text).toContain('scheduled import');
  });
});
