import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DistrictMap from './DistrictMap';

describe('DistrictMap', () => {
  it('keeps map assets keyboard-selectable with visible selection state', () => {
    const onSelect = vi.fn();
    render(<DistrictMap features={[]} nodes={[
      { id: 'source', role: 'source', lon: 78.65, lat: 17.16 },
      { id: 'tx-1', role: 'transformer', lon: 78.66, lat: 17.16 },
    ]} edges={[{ id: 'line-1', from: 'source', to: 'tx-1', kind: 'branch' }]}
    edgeStates={[{ id: 'line-1', closed: true, faulted: false, energized: true, flow_w: 300 }]}
    selected={null} onSelect={onSelect} mode="shift" />);

    const source = screen.getByRole('button', { name: 'source · synthetic source' });
    expect(screen.getByRole('group', { name: /Cached OpenStreetMap geography/ })).toBeInTheDocument();
    fireEvent.keyDown(source, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('source');

    const line = screen.getByRole('button', { name: /line-1 · branch · energized/ });
    fireEvent.click(line);
    expect(onSelect).toHaveBeenCalledWith('line-1');
  });
});
