import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { DistrictSnapshot } from '../types';
import { clearFaultGate, generationTransitionFeedback, observationRequest, TransformerCutaway, transformerReading } from './DistrictDemo';

const generationSnapshot = (status: string): DistrictSnapshot => ({
  generation: { status, reason: 'test result' },
  topology: { nodes: [{}, {}], edges: [{}] },
} as unknown as DistrictSnapshot);

describe('district study evidence views', () => {
  it('reports terminal topology results only after a generation was running', () => {
    expect(generationTransitionFeedback(undefined, generationSnapshot('CACHED'))).toBeNull();
    expect(generationTransitionFeedback('CACHED', generationSnapshot('GENERATED'))).toBeNull();
    expect(generationTransitionFeedback('GENERATING', generationSnapshot('GENERATED')))
      .toBe('Topology generated: 2 nodes and 1 edge.');
    expect(generationTransitionFeedback('GENERATING', generationSnapshot('FAILED')))
      .toBe('Topology generation failed: test result');
  });

  it('keeps fault clearing disabled until the backend evidence gate is satisfied', () => {
    expect(clearFaultGate('edge-1', ['edge-1'], false, 0, '2 samples over 5 s')).toMatchObject({
      enabled: false,
      reason: expect.stringContaining('2 samples over 5 s; 0 healthy samples'),
    });
    // Sample count alone never opens the gate; only the backend's dwell/freshness verdict does.
    expect(clearFaultGate('edge-1', ['edge-1'], false, 5).enabled).toBe(false);
    expect(clearFaultGate('edge-1', ['edge-1'], true, 2).enabled).toBe(true);
    expect(clearFaultGate('edge-2', ['edge-1'], true, 2).enabled).toBe(false);
  });

  it('builds sequenced, timestamped simulated observations', () => {
    const now = new Date('2026-10-10T12:00:00.000Z');
    expect(observationRequest(null, true, now)).toEqual({ sequence: 1, observed_at: '2026-10-10T12:00:00.000Z',
      healthy: true, source: 'SIMULATED_OBSERVATION_ADAPTER' });
    expect(observationRequest(7, false, now).sequence).toBe(8);
  });

  it('shows an accessible synthetic transformer schematic and highlights only the diagnosed part', () => {
    const { container } = render(<TransformerCutaway componentId="TX-1" suspectedPart="winding" />);
    expect(screen.getByRole('img', { name: 'Illustrative synthetic transformer cutaway for TX-1' })).toBeVisible();
    expect(container.querySelectorAll('.cutaway-part.is-suspected')).toHaveLength(1);
    expect(container.querySelector('.cutaway-part.is-suspected')).toHaveTextContent('Winding');
  });

  it('labels populated stale transformer values as old readings', () => {
    const { rerender } = render(<div>{transformerReading({ status: 'STALE', oil_temperature_c: 105 }, 'oil_temperature_c', '°C')}</div>);
    expect(screen.getByText('Unknown')).toBeVisible();
    expect(screen.getByText('Stale last reading: 105 °C')).toBeVisible();
    rerender(<div>{transformerReading({ status: 'SIMULATED', oil_temperature_c: 105 }, 'oil_temperature_c', '°C')}</div>);
    expect(transformerReading({ status: 'SIMULATED', oil_temperature_c: 105 }, 'oil_temperature_c', '°C'))
      .toBe('105 °C');
  });
});
