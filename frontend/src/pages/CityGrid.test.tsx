import { render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import campus from '../test/fixtures/campus.json';
import type { Snapshot } from '../types';
import CityGrid, { feederState } from './CityGrid';

test('unknown feeder evidence stays unknown and service buttons expose their state', () => {
  const snapshot = campus as unknown as Snapshot;
  expect(feederState({ ...snapshot, allocation: { ...snapshot.allocation, explanation: {} } }, 'A')).toBe('UNKNOWN');
  expect(feederState(snapshot, 'A')).toBe('CLOSED');
  render(<CityGrid snapshot={snapshot} selected="L0" onSelect={vi.fn()} />);
  expect(screen.getByRole('button', { name: 'Hospital Essential Circuit: Served' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getAllByRole('button')).toHaveLength(6);
});
