import type { DemandForecast, DemoEvidence } from '../types';

/** Compact top-of-page alert; advisory only, never changes allocation. */
export function ForecastAlert({ forecast }: { forecast: DemandForecast }) {
  if (forecast.status !== 'SHORTAGE_RISK') return null;
  const last = forecast.points[forecast.points.length - 1];
  const now = forecast.observations_w[forecast.observations_w.length - 1];
  return <p className="city-forecast-alert" role="alert">
    <strong>Early warning · possible shortfall within {forecast.first_shortage_s} s.</strong>{' '}
    Now {now?.toLocaleString() ?? 'unknown'} W → forecast {last?.demand_w.toLocaleString() ?? 'unknown'} W at +60 s vs {forecast.capacity_w.toLocaleString()} W capacity.{' '}
    <a href="#city-forecast">See forecast</a> · Advisory; trained on synthetic data.
  </p>;
}

export default function DemandForecastPanel({ forecast, evidence, source, onSource, onNext, replayIndex }: {
  forecast: DemandForecast; evidence?: DemoEvidence; source: DemandForecast['source'];
  onSource: (source: DemandForecast['source']) => void; onNext: () => void; replayIndex: number;
}) {
  const history = forecast.observations_w;
  const points = forecast.points;
  const x = (seconds: number) => 36 + (seconds + 110) / 170 * 528;
  const y = (watts: number) => 176 - watts / 14000 * 146;
  const observed = history.map((watts, i) => `${x((i - history.length + 1) * 10)},${y(watts)}`).join(' ');
  const predicted = points.map(p => `${x(p.ahead_s)},${y(p.demand_w)}`).join(' ');
  const band = [...points.map(p => `${x(p.ahead_s)},${y(p.upper_w)}`), ...[...points].reverse().map(p => `${x(p.ahead_s)},${y(p.lower_w)}`)].join(' ');
  const last = points[points.length - 1];
  return <section className="city-panel" id="city-forecast" aria-label="Predictive demand forecast">
    <header className="city-panel-heading"><div><h2>Predictive AI · next 60 seconds</h2><p>Ridge regression trained on synthetic demand sessions</p></div></header>
    <div className="city-forecast-controls"><label>Observation source<select value={source} onChange={event => onSource(event.target.value as DemandForecast['source'])}>
      <option value="LIVE_REQUESTED_DEMAND">Live simulated demand</option><option value="SYNTHETIC_REPLAY">Synthetic rising-demand rehearsal</option>
    </select></label>{source === 'SYNTHETIC_REPLAY' && <button onClick={onNext}>{replayIndex === 7 ? 'Restart rehearsal' : 'Next 10 s sample'}</button>}</div>
    <p className={`city-forecast-status ${forecast.status === 'SHORTAGE_RISK' ? 'is-warning' : ''}`} role="status">
      {forecast.status === 'UNKNOWN' ? forecast.reason : forecast.status === 'SHORTAGE_RISK' ? `Possible capacity shortfall within ${forecast.first_shortage_s} seconds.` : 'Forecast band stays within current source capacity.'}
    </p>
    <svg className="city-forecast-chart" viewBox="0 0 600 210" role="img" aria-label={`Observed demand and next-minute forecast against ${forecast.capacity_w} watts of capacity. ${last ? `60-second forecast ${last.demand_w} watts.` : 'Forecast unavailable.'}`}>
      {[0, 7000, 14000].map(w => <g key={w}><path className="city-chart-rule" d={`M36 ${y(w)}H565`} /><text x="2" y={y(w) - 4}>{w / 1000} kW</text></g>)}
      <path className="city-chart-capacity" d={`M36 ${y(forecast.capacity_w)}H565`} /><text x="570" y={Math.max(12, y(forecast.capacity_w) + 4)}>Limit</text>
      <path className="city-chart-now" d={`M${x(0)} 20V180`} /><text x={x(0) - 10} y="199">Now</text><text x={x(60) - 22} y="199">+60 s</text>
      <polygon className="city-chart-band" points={band} />
      <polyline className="city-chart-observed" points={observed} />
      <polyline className="city-chart-forecast" points={history.length && points.length ? `${x(0)},${y(history[history.length - 1])} ${predicted}` : ''} />
    </svg>
    <dl className="city-forecast-numbers"><div><dt>Last requested demand</dt><dd>{history[history.length - 1]?.toLocaleString() ?? '—'} W</dd></div><div><dt>Forecast at +60 s</dt><dd>{last?.demand_w.toLocaleString() ?? '—'} W</dd></div></dl>
    {last && <p className="city-small">Empirical error band at +60 s: {last.lower_w.toLocaleString()}–{last.upper_w.toLocaleString()} W. Green solid = observations; blue dashed = forecast; shading = error band.</p>}
    <p className="city-small">{forecast.source === 'SYNTHETIC_REPLAY' ? 'Rehearsal observations are synthetic and do not change the live grid. ' : 'Input is requested demand before shedding, sampled every 10 seconds. '}{forecast.reason}</p>
    <details><summary>Forecast evidence and limits</summary><p>Held-out synthetic sessions: {evidence?.forecast_test_sessions ?? '—'}. Mean absolute error at 60 s: {evidence?.forecast_mae_60s_w ?? '—'} W; last-value baseline: {evidence?.persistence_mae_60s_w ?? '—'} W. Abrupt trips cannot be forecast reliably. No campus validation. Forecasts never authorize switching or restoration.</p></details>
  </section>;
}
