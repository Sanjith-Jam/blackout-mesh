export function formatMetric(value: number | null | undefined, unit: string, fallback: string = '—'): string {
  if (value == null || !Number.isFinite(value)) {
    return fallback;
  }
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`;
}
