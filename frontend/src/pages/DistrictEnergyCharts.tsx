import { useState } from 'react';
import ReactECharts from 'echarts-for-react';
import type { DistrictSnapshot } from '../types';

type Row = DistrictSnapshot['energy']['profile'][number];

/** Read-only inspection of the 24-hour CityLearn profile; it never advances the backend hour. */
export function hourSummary(row: Row) {
  return `${row.hour}:00 · demand ${row.demand_w.toLocaleString()} W · PV ${row.pv_w.toLocaleString()} W (${row.pv_used_w.toLocaleString()} W used) · `
    + `scheduled import ${row.baseline_grid_w.toLocaleString()} W baseline vs ${row.dispatch_grid_w.toLocaleString()} W with battery · `
    + `battery ${row.battery_soc_wh.toLocaleString()} Wh`;
}

export default function DistrictEnergyCharts({ snapshot }: { snapshot: DistrictSnapshot }) {
  const profile = snapshot.energy.profile;
  const [inspect, setInspect] = useState<number | null>(null);
  const hour = inspect ?? snapshot.energy.hour;
  const hours = profile.map(row => `${row.hour}:00`);
  const marker = { symbol: 'none', silent: true, label: { formatter: inspect === null ? 'Model hour' : 'Inspecting' },
    lineStyle: { color: '#8a6534', type: 'dashed' as const }, data: [{ xAxis: `${hour}:00` }] };
  const grid = { left: 8, right: 16, top: 30, bottom: 40, containLabel: true };
  const power = {
    tooltip: { trigger: 'axis' }, legend: { bottom: 0 }, grid,
    xAxis: { type: 'category', data: hours, boundaryGap: false }, yAxis: { type: 'value', name: 'W' },
    series: [
      { name: 'Demand', type: 'line', data: profile.map(r => r.demand_w), itemStyle: { color: '#c0392b' }, markLine: marker },
      { name: 'PV generated', type: 'line', areaStyle: { opacity: .15 }, data: profile.map(r => r.pv_w), itemStyle: { color: '#e0a526' } },
      { name: 'Scheduled import · baseline', type: 'line', step: 'middle', data: profile.map(r => r.baseline_grid_w), itemStyle: { color: '#8a9387' }, lineStyle: { type: 'dashed' } },
      { name: 'Scheduled import · battery dispatch', type: 'line', step: 'middle', data: profile.map(r => r.dispatch_grid_w), itemStyle: { color: '#2f5d3a' } },
    ],
  };
  const battery = {
    tooltip: { trigger: 'axis' }, legend: { bottom: 0 }, grid,
    xAxis: { type: 'category', data: hours }, yAxis: [{ type: 'value', name: 'Wh' }, { type: 'value', name: 'W' }],
    series: [
      { name: 'Battery state', type: 'line', smooth: true, areaStyle: { opacity: .2 }, data: profile.map(r => r.battery_soc_wh), itemStyle: { color: '#2f5d3a' }, markLine: marker },
      { name: 'Charge', type: 'bar', yAxisIndex: 1, data: profile.map(r => r.battery_charge_w), itemStyle: { color: '#4d9a5c' } },
      { name: 'Discharge', type: 'bar', yAxisIndex: 1, data: profile.map(r => -r.battery_discharge_w), itemStyle: { color: '#c0392b' } },
    ],
  };
  return <section aria-label="24-hour energy charts">
    <h3>24-hour profile</h3>
    <ReactECharts option={power} style={{ height: 280, width: '100%' }} opts={{ renderer: 'svg' }} />
    <ReactECharts option={battery} style={{ height: 220, width: '100%' }} opts={{ renderer: 'svg' }} />
    <label className="district-scenario-label">Inspect an hour (read-only; does not change the model)
      <input type="range" min={0} max={profile.length - 1} value={hour} aria-valuetext={`${hour}:00`}
        onChange={event => setInspect(Number(event.target.value))} /></label>
    <p role="status">{profile[hour] ? hourSummary(profile[hour]) : 'No profile row.'}{inspect !== null && inspect !== snapshot.energy.hour
      ? <> · <button type="button" className="is-secondary" onClick={() => setInspect(null)}>Back to model hour {snapshot.energy.hour}</button></> : null}</p>
    <p className="district-action-help">Scheduled imports are profile requests, not delivered feeder flow or measured savings.</p>
  </section>;
}
