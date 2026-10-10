import { useQuery } from '@tanstack/react-query';
import { getDemoEvidence } from '../../api';

export function BenchmarkCard() {
  const { data, isError } = useQuery({ queryKey: ['demo-evidence'], queryFn: ({ signal }) => getDemoEvidence(signal), staleTime: Infinity });
  const ms = (value: number | null | undefined) => value == null ? 'Unavailable' : `${value.toFixed(2)} ms`;
  const stats = [
    { label: 'Occupancy inference', value: ms(data?.inference_median_ms), detail: `Warm single reading · median of ${data?.inference_calls ?? '—'} calls` },
    { label: 'Exact allocation', value: ms(data?.allocation_median_ms), detail: `${data?.masks ?? '—'} plans · median of ${data?.allocation_calls ?? '—'} decisions` },
    { label: 'Constraint violations', value: data?.constraint_violations == null ? 'Unavailable' : `${data.constraint_violations} / ${data.allocation_runs} runs`, detail: 'Simulated benchmark outcomes; not a field safety guarantee' },
  ];
  return <section className="rounded-2xl border border-border bg-card p-6 text-card-foreground" aria-label="Measured software benchmarks">
    <h2 className="text-xl font-semibold">Measured software benchmarks</h2>
    <p className="mt-2 text-sm text-muted-foreground">Recorded on the benchmark machine. These measure different tasks, not competing controller speeds.</p>
    {isError && <p role="status">Benchmark evidence could not be loaded.</p>}
    <dl className="mt-5 grid gap-5 sm:grid-cols-3">{stats.map(stat => <div key={stat.label}>
      <dt className="text-sm font-medium">{stat.label}</dt>
      <dd className="mt-1 text-2xl font-bold">{stat.value}</dd>
      <dd className="mt-2 text-sm text-muted-foreground">{stat.detail}</dd>
    </div>)}</dl>
    <details className="mt-4 text-sm"><summary className="cursor-pointer">Measurement sources</summary>
      <p>backend/models/evaluation.json · backend/benchmarks/results/allocation_profile.json · allocation_report.json</p>
    </details>
  </section>;
}
