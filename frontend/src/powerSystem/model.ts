import type { components } from '../schema';

export type PowerSystem = components['schemas']['PowerSystemResponse'];
export type Appliance = components['schemas']['Appliance'];
export type Room = components['schemas']['Room'];
export type Edge = components['schemas']['Edge'];
export type ApplianceState = Appliance['state'];
export type EdgeState = Edge['state'];

/** One visual language for every view: colour, line pattern, icon glyph and a text label together. */
export const APPLIANCE_STATE: Record<ApplianceState, { label: string; short: string; glyph: string; className: string }> = {
  SERVED: { label: 'Served', short: 'SERVED', glyph: '✓', className: 'is-served' },
  PENDING_RESTORATION: { label: 'Pending restoration', short: 'PENDING', glyph: '◷', className: 'is-pending' },
  SHED: { label: 'Shed', short: 'SHED', glyph: '⊘', className: 'is-shed' },
  UNREACHABLE: { label: 'Unreachable (no path)', short: 'NO PATH', glyph: '✕', className: 'is-unreachable' },
  NOT_REQUESTED: { label: 'Off by request', short: 'OFF', glyph: '○', className: 'is-off' },
};

export const EDGE_STATE: Record<EdgeState, { label: string; className: string }> = {
  ENERGIZED: { label: 'Modeled supply', className: 'wire-energized' },
  PENDING_RESTORATION: { label: 'Commanded, awaiting restoration', className: 'wire-pending' },
  SHED: { label: 'Connected, load shed', className: 'wire-shed' },
  OPEN: { label: 'Interrupted / feeder unavailable', className: 'wire-open' },
  UNKNOWN: { label: 'Stale or unknown evidence', className: 'wire-unknown' },
};

export const EVIDENCE_LABEL: Record<string, string> = {
  NORMAL: 'Telemetry normal',
  FAULT_DETECTED: 'Confirmed simulated fault',
  SUSPECTED: 'Suspected fault (awaiting confirmation)',
  INCONCLUSIVE: 'Inconclusive: insufficient telemetry',
  UNKNOWN: 'Unknown: no diagnosis',
  NOT_INSTRUMENTED: 'No room sensors configured',
};

export const OVERALL_LABEL: Record<string, string> = {
  NORMAL: 'Nominal (telemetry-backed)',
  FAULT_DETECTED: 'Fault detected',
  SUSPECTED: 'Fault suspected',
  INCONCLUSIVE: 'Inconclusive',
  CONSTRAINT_ACTIVE: 'Capacity constraint active',
  UNKNOWN: 'Unknown',
};

export const w = (watts: number) => `${Math.round(watts).toLocaleString('en-US')} W`;

export function edgeById(data: PowerSystem) {
  return new Map(data.edges.map(e => [e.id, e]));
}
