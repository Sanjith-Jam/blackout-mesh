import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PowerEdge } from '../types';
import { EDGE_LABEL, EdgeLegend, PowerWire, describeEdge } from './PowerEdges';

const base: PowerEdge = {
  id: 'classroom:CR1>ac', from: 'CR1', to: 'CR1.ac', state: 'ENERGIZED', connected: true, commanded: true, applied: true,
  requested_w: 1000, served_w: 1000, unit: 'W', provenance: 'MODELED', physical: 'NOT_CONNECTED', reason: 'Air conditioning: served',
};

function drawn(edge: PowerEdge | undefined, live = true) {
  const { container } = render(<svg><PowerWire edge={edge} d="M0 0H10" live={live} /></svg>);
  return container.querySelector('[data-edge-id]') as SVGGElement;
}

describe('PowerWire (#23)', () => {
  it('animates only an energized edge on a live feed', () => {
    expect(drawn(base).querySelector('.power-map__current')).not.toBeNull();
    expect(drawn(base, false).querySelector('.power-map__current')).toBeNull(); // stale feed: no motion
    for (const state of ['PENDING_RESTORATION', 'SHED', 'OPEN', 'UNKNOWN'] as const) {
      const g = drawn({ ...base, state, applied: false });
      expect(g.dataset.state).toBe(state);
      expect(g.querySelector('.power-map__current')).toBeNull();
    }
  });

  it('treats a missing edge as unknown, never as healthy', () => {
    const g = drawn(undefined);
    expect(g.dataset.edgeId).toBe('missing');
    expect(g.dataset.state).toBe('UNKNOWN');
    expect(g.querySelector('title')?.textContent).toMatch(/No edge data/);
  });

  it('explains evidence with units, provenance and hardware status', () => {
    const text = describeEdge({ ...base, observed: { output_voltage_v: 220, energized: true, provenance: 'SIMULATED_SENSOR', note: 'Voltage presence only; no measured branch current.' } });
    expect(text).toContain('1,000 of 1,000 W modeled');
    expect(text).toContain('Hardware: not connected');
    expect(text).toContain('simulated sensor');
    expect(text).toContain('no measured branch current');
  });

  it('labels every state in text, not colour alone', () => {
    render(<EdgeLegend stale />);
    for (const word of ['Energized', 'Restoring', 'Shed', 'Open', 'Unknown']) expect(screen.getByText(word)).toBeInTheDocument();
    expect(screen.getByText(/not live/)).toBeInTheDocument();
    expect(new Set(Object.values(EDGE_LABEL)).size).toBe(5);
  });
});
