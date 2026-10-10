import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { DistrictSnapshot } from '../types';
import { clearFaultGate, generationTransitionFeedback, TransformerCutaway } from './DistrictDemo';

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

  it('keeps fault clearing disabled until the current fault has two stable evidence intervals', () => {
    expect(clearFaultGate('edge-1', ['edge-1'], 0)).toMatchObject({
      enabled: false,
      reason: expect.stringContaining('0 of 2'),
    });
    expect(clearFaultGate('edge-1', ['edge-1'], 1).enabled).toBe(false);
    expect(clearFaultGate('edge-1', ['edge-1'], 2).enabled).toBe(true);
    expect(clearFaultGate('edge-2', ['edge-1'], 2).enabled).toBe(false);
  });

  it('shows an accessible synthetic transformer schematic and highlights only the diagnosed part', () => {
    const { container } = render(<TransformerCutaway componentId="TX-1" suspectedPart="winding" />);
    expect(screen.getByRole('img', { name: 'Illustrative synthetic transformer cutaway for TX-1' })).toBeVisible();
    expect(container.querySelectorAll('.cutaway-part.is-suspected')).toHaveLength(1);
    expect(container.querySelector('.cutaway-part.is-suspected')).toHaveTextContent('Winding');
  });
});
