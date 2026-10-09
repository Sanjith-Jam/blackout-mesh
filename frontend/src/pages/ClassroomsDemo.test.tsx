import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import classrooms from '../test/fixtures/classrooms.json';
import { clone, mockFetch } from '../test/mockApi';
import ClassroomsDemo from './ClassroomsDemo';

const PATH = '/api/v1/visualizers/classrooms';

function renderPage() {
  return render(<MemoryRouter><ClassroomsDemo /></MemoryRouter>);
}

describe('Classrooms page (#16)', () => {
  beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
  afterEach(() => { vi.useRealTimers(); });

  it('shows loading, then the published state with every wire mapped to an edge', async () => {
    mockFetch({ [`GET ${PATH}`]: () => ({ json: classrooms }) });
    renderPage();
    expect(screen.getByText(/Connecting to classroom supply/)).toBeInTheDocument();
    await screen.findByText('Classroom power map');
    expect(screen.getByRole('button', { name: /CR1 scanned/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /Scan CR3/ })).toHaveAttribute('aria-pressed', 'false');
    const wires = document.querySelectorAll('[data-edge-id]');
    expect(wires).toHaveLength(classrooms.edges.length);
    expect(document.querySelectorAll('[data-edge-id="missing"]')).toHaveLength(0);
    const energized = classrooms.edges.filter(e => e.state === 'ENERGIZED').length;
    expect(document.querySelectorAll('[data-state="ENERGIZED"]')).toHaveLength(energized);
  });

  it('shows an error with retry when the backend is unavailable, and recovers', async () => {
    let up = false;
    mockFetch({ [`GET ${PATH}`]: () => (up ? { json: classrooms } : { status: 503, json: { detail: 'down' } }) });
    renderPage();
    await screen.findByText('Classroom demo unavailable');
    up = true;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByText('Classroom power map');
  });

  it('toggles a scanned room off with unscan (multi-scan)', async () => {
    const api = mockFetch({
      [`GET ${PATH}`]: () => ({ json: classrooms }),
      [`POST ${PATH}`]: () => {
        const next = clone(classrooms);
        next.scanned_classroom_ids = ['CR2'];
        return { json: next };
      },
    });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /CR1 scanned/ }));
    await waitFor(() => expect(api.posts()).toHaveLength(1));
    expect(api.posts()[0].body).toEqual({ action: 'unscan', classroom_id: 'CR1' });
    await screen.findByRole('button', { name: /Scan CR1/ });
  });

  it('debounces the supply slider into one validated command', async () => {
    const api = mockFetch({ [`GET ${PATH}`]: () => ({ json: classrooms }), [`POST ${PATH}`]: () => ({ json: classrooms }) });
    renderPage();
    const slider = await screen.findByLabelText(/Supply limit/);
    fireEvent.change(slider, { target: { value: '4000' } });
    fireEvent.change(slider, { target: { value: '4500' } });
    fireEvent.change(slider, { target: { value: '5000' } });
    expect(api.posts()).toHaveLength(0);
    await act(async () => { vi.advanceTimersByTime(350); });
    await waitFor(() => expect(api.posts()).toHaveLength(1));
    expect(api.posts()[0].body).toEqual({ action: 'set_capacity', capacity_w: 5000 });
  });

  it('keeps the last state and shows an alert when a command is rejected', async () => {
    mockFetch({ [`GET ${PATH}`]: () => ({ json: classrooms }), [`POST ${PATH}`]: () => ({ status: 422, json: { detail: 'bad' } }) });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /Scan CR3/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/HTTP error 422|failed/i);
    expect(screen.getByRole('button', { name: /CR1 scanned/ })).toBeInTheDocument();
  });

  it('shows the protected-essentials status in text', async () => {
    mockFetch({ [`GET ${PATH}`]: () => ({ json: classrooms }) });
    renderPage();
    expect(await screen.findByRole('status')).toHaveTextContent(/Protected essentials served/);
  });

  it('stops polling after unmount', async () => {
    const api = mockFetch({ [`GET ${PATH}`]: () => ({ json: classrooms }) });
    const view = renderPage();
    await screen.findByText('Classroom power map');
    view.unmount();
    const before = api.fn.mock.calls.length;
    await act(async () => { vi.advanceTimersByTime(5000); });
    expect(api.fn.mock.calls.length).toBe(before);
  });
});
