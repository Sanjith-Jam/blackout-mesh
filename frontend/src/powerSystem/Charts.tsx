import type { Sample } from './history';
import { w } from './model';

/** Small step-line trend chart in SVG. Steps, not smooth curves: the backend publishes discrete states. */
export interface Series { label: string; className: string; values: (number | null)[]; dashed?: boolean }

export function TrendChart({ title, provenance, samples, series, height = 160 }: {
  title: string; provenance: string; samples: Sample[]; series: Series[]; height?: number }) {
  const W = 560, H = height, L = 56, R = 10, T = 10, B = 24;
  const all = series.flatMap(s => s.values.filter((v): v is number => v != null));
  const max = Math.max(1000, ...all) * 1.08;
  const n = samples.length;
  const x = (i: number) => L + (n <= 1 ? 0 : (i / (n - 1)) * (W - L - R));
  const y = (v: number) => T + (1 - v / max) * (H - T - B);
  const step = (vals: (number | null)[]) => {
    let d = '';
    vals.forEach((v, i) => {
      if (v == null) return;
      d += d ? ` H${x(i).toFixed(1)} V${y(v).toFixed(1)}` : `M${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
    });
    return d;
  };
  const span = n > 1 ? Math.round((samples[n - 1].t - samples[0].t) / 1000) : 0;
  const latest = series.map(s => s.values[s.values.length - 1]);
  return <figure className="ps-chart">
    <figcaption><strong>{title}</strong><span className="ps-provenance">{provenance}</span></figcaption>
    {n === 0 ? <p className="ps-muted">Waiting for the first backend sample…</p> :
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}. Latest: ${series.map((s, i) => `${s.label} ${latest[i] == null ? 'unknown' : w(latest[i] as number)}`).join(', ')}`}>
        {[0, 0.5, 1].map(f => <g key={f}><line x1={L} x2={W - R} y1={y(max * f / 1.08)} y2={y(max * f / 1.08)} className="ps-chart-grid" />
          <text x={L - 6} y={y(max * f / 1.08) + 4} textAnchor="end" className="ps-chart-tick">{w(max * f / 1.08)}</text></g>)}
        <text x={L} y={H - 6} className="ps-chart-tick">{`−${span} s`}</text>
        <text x={W - R} y={H - 6} textAnchor="end" className="ps-chart-tick">now</text>
        {series.map(s => <path key={s.label} d={step(s.values)} className={`ps-chart-line ${s.className}`} strokeDasharray={s.dashed ? '6 4' : undefined} />)}
      </svg>}
    <ul className="ps-legend">{series.map((s, i) => <li key={s.label}><span className={`ps-swatch ${s.className}${s.dashed ? ' is-dashed' : ''}`} />{s.label}: <b>{latest[i] == null ? '—' : w(latest[i] as number)}</b></li>)}</ul>
  </figure>;
}

/** Appliance count per modeled state over time, as stacked bands. */
export function AllocationHistory({ samples }: { samples: Sample[] }) {
  const order = ['SERVED', 'PENDING_RESTORATION', 'SHED', 'UNREACHABLE', 'NOT_REQUESTED'] as const;
  const labels: Record<string, string> = { SERVED: 'Served', PENDING_RESTORATION: 'Pending', SHED: 'Shed', UNREACHABLE: 'No path', NOT_REQUESTED: 'Off' };
  const W = 560, H = 120, L = 56, R = 10, T = 8, B = 20;
  const n = samples.length;
  const total = n ? order.reduce((s, k) => s + (samples[n - 1].states[k] ?? 0), 0) : 0;
  const colW = n ? (W - L - R) / n : 0;
  return <figure className="ps-chart">
    <figcaption><strong>Appliance allocation history</strong><span className="ps-provenance">MODELED · count of appliances per state</span></figcaption>
    {n === 0 ? <p className="ps-muted">Waiting for the first backend sample…</p> :
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Latest allocation: ${order.map(k => `${samples[n - 1].states[k] ?? 0} ${labels[k]}`).join(', ')}`}>
        <text x={L - 6} y={T + 8} textAnchor="end" className="ps-chart-tick">{total}</text>
        <text x={L - 6} y={H - B} textAnchor="end" className="ps-chart-tick">0</text>
        {samples.map((s, i) => {
          let acc = 0;
          return <g key={s.t}>{order.map(k => {
            const v = s.states[k] ?? 0;
            const h = total ? (v / total) * (H - T - B) : 0;
            const rect = <rect key={k} x={L + i * colW} y={H - B - acc - h} width={Math.max(colW, 0.6)} height={h} className={`ps-band band-${k}`} />;
            acc += h;
            return rect;
          })}</g>;
        })}
      </svg>}
    <ul className="ps-legend">{order.map(k => <li key={k}><span className={`ps-swatch band-${k}`} />{labels[k]}: <b>{n ? samples[n - 1].states[k] ?? 0 : '—'}</b></li>)}</ul>
  </figure>;
}

/** Requested vs limit vs served bars for one scope, used by Overview and the capacity law. */
export function CapacityBar({ label, requested, limit, served, open }: { label: string; requested: number; limit: number; served: number; open?: boolean }) {
  const max = Math.max(requested, limit, served, 1);
  const exceeded = requested > limit;
  return <div className={`ps-capbar${exceeded ? ' is-exceeded' : ''}`} data-scope={label}>
    <div className="ps-capbar-head"><strong>{label}</strong>
      <span>{open ? '✕ open: limit 0 W' : exceeded ? `▲ requested exceeds limit by ${w(requested - limit)}` : `${w(limit - served)} headroom`}</span></div>
    <div className="ps-capbar-track" aria-hidden="true">
      <div className="ps-capbar-req" style={{ width: `${(requested / max) * 100}%` }} />
      <div className="ps-capbar-served" style={{ width: `${(served / max) * 100}%` }} />
      <div className="ps-capbar-limit" style={{ left: `${(limit / max) * 100}%` }} />
    </div>
    <dl className="ps-capbar-values"><div><dt>Requested</dt><dd>{w(requested)}</dd></div><div><dt>Limit</dt><dd>{w(limit)}</dd></div>
      <div><dt>Modeled served</dt><dd>{w(served)}</dd></div><div><dt>Unserved</dt><dd>{w(Math.max(0, requested - served))}</dd></div></dl>
  </div>;
}
