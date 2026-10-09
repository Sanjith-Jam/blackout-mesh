import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { axe } from 'jest-axe';
import { describe, expect, it } from 'vitest';
import hospital from '../test/fixtures/hospital.json';
import missingSensor from '../test/fixtures/hospital_missing_sensor.json';
import { clone, mockFetch } from '../test/mockApi';
import HospitalDemo from './HospitalDemo';

describe('Hospital page (#16)', () => {
  it('shows a missing-sensor abstention instead of a healthy status', async () => {
    const snap = clone(hospital);
    const abstained = missingSensor.transformers.find(t => t.diagnosis.status === 'ABSTAINED')!;
    const tx = snap.transformers.find(t => t.id === abstained.id)!;
    tx.diagnosis = clone(abstained.diagnosis) as typeof tx.diagnosis;
    mockFetch({ 'GET /api/v1/visualizers/hospital': () => ({ json: snap }) });
    render(<MemoryRouter><HospitalDemo /></MemoryRouter>);
    expect(await screen.findByText(/Abstained:/)).toBeInTheDocument();
    expect(screen.getAllByText(/UNKNOWN/).length).toBeGreaterThan(0);
  });

  it('draws every hospital wire from a backend edge', async () => {
    mockFetch({ 'GET /api/v1/visualizers/hospital': () => ({ json: hospital }) });
    render(<MemoryRouter><HospitalDemo /></MemoryRouter>);
    await screen.findByRole('region', { name: 'Hospital floor plans' });
    expect(document.querySelectorAll('[data-edge-id]')).toHaveLength(hospital.edges.length);
    expect(document.querySelectorAll('[data-edge-id="missing"]')).toHaveLength(0);
  });

  it('has no automated accessibility violations in the live view', async () => {
    mockFetch({ 'GET /api/v1/visualizers/hospital': () => ({ json: hospital }) });
    const { container } = render(<MemoryRouter><HospitalDemo /></MemoryRouter>);
    await screen.findByRole('region', { name: 'Hospital power state' });
    expect((await axe(container)).violations).toEqual([]);
  });
});
