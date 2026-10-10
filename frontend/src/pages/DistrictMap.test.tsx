import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DistrictMap from './DistrictMap';

describe('DistrictMap', () => {
  it('lets a tree edge win pointer hits at crossings while leaving ties selectable', () => {
    const onSelect = vi.fn();
    render(<DistrictMap features={[]} nodes={[
      { id: 'nw', role: 'junction', lon: 0, lat: 10 },
      { id: 'se', role: 'junction', lon: 10, lat: 0 },
      { id: 'sw', role: 'junction', lon: 0, lat: 0 },
      { id: 'ne', role: 'junction', lon: 10, lat: 10 },
    ]} edges={[
      { id: 'tree-edge', from: 'nw', to: 'se', kind: 'line' },
      { id: 'tie:declared-demo', from: 'sw', to: 'ne', kind: 'tie' },
    ]} edgeStates={[]} selected={null} onSelect={onSelect} mode="shift" />);

    const tree = screen.getByRole('button', { name: 'tree-edge · line · unenergized' });
    const tie = screen.getByRole('button', { name: 'tie:declared-demo · tie · unenergized' });
    expect(tie.compareDocumentPosition(tree) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(tree);
    expect(onSelect).toHaveBeenLastCalledWith('tree-edge');
    fireEvent.click(tie);
    expect(onSelect).toHaveBeenLastCalledWith('tie:declared-demo');
    fireEvent.keyDown(tie, { key: 'Enter' });
    expect(onSelect).toHaveBeenLastCalledWith('tie:declared-demo');
  });

  it('keeps map assets keyboard-selectable with visible selection state', () => {
    const onSelect = vi.fn();
    render(<DistrictMap features={[]} nodes={[
      { id: 'source', role: 'source', lon: 78.65, lat: 17.16 },
      { id: 'tx-1', role: 'transformer', lon: 78.66, lat: 17.16 },
    ]} edges={[{ id: 'tie:declared-demo', from: 'source', to: 'tx-1', kind: 'tie' }]}
    edgeStates={[{ id: 'tie:declared-demo', closed: true, faulted: false, energized: true, flow_w: 300 }]}
    selected={null} onSelect={onSelect} mode="shift" />);

    const source = screen.getByRole('button', { name: 'source · synthetic source' });
    expect(screen.getByRole('group', { name: /Cached OpenStreetMap geography/ })).toBeInTheDocument();
    fireEvent.keyDown(source, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('source');

    const line = screen.getByRole('button', { name: /tie:declared-demo · tie · energized/ });
    const transformer = screen.getByRole('button', { name: 'tx-1 · synthetic transformer' });
    expect(line).toHaveClass('edge-hit');
    expect(line).toHaveAttribute('tabindex', '0');
    expect(line.compareDocumentPosition(transformer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(line);
    expect(onSelect).toHaveBeenCalledWith('tie:declared-demo');
    fireEvent.keyDown(line, { key: 'Enter' });
    expect(onSelect).toHaveBeenLastCalledWith('tie:declared-demo');
    fireEvent.click(transformer);
    expect(onSelect).toHaveBeenLastCalledWith('tx-1');
  });
});
