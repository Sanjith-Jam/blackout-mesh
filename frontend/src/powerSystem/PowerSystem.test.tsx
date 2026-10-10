import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import normal from '../test/fixtures/power_system.json';
import fault from '../test/fixtures/power_system_fault.json';
import ApplianceDetail from './ApplianceDetail';
import { KNOWN_ICON_KEYS } from './ApplianceIcon';
import ElectricalLaws from './ElectricalLaws';
import FaultDetection, { incidentsOf } from './FaultDetection';
import FloorPlan, { floorPlanLayout, VIEW } from './FloorPlan';
import { appendSample, HISTORY_LIMIT, sampleOf } from './history';
import type { PowerSystem } from './model';
import NetworkView from './NetworkView';

const base = normal as unknown as PowerSystem;
const faulted = fault as unknown as PowerSystem;
const noop = { killFeeder: vi.fn(), restoreFeeder: vi.fn(), dropCapacity: vi.fn(), restoreCapacity: vi.fn(), injectDropout: vi.fn(), clearHospitalFault: vi.fn() };

test('the floor plan draws every configured appliance once, with its backend state', () => {
  const { container } = render(<FloorPlan data={faulted} selected={null} onSelect={vi.fn()} highlight={[]} />);
  const drawn = [...container.querySelectorAll('[data-appliance]')];
  expect(drawn.map(e => e.getAttribute('data-appliance')).sort()).toEqual(faulted.appliances.map(a => a.id).sort());
  for (const a of faulted.appliances) expect(container.querySelector(`[data-appliance="${a.id}"]`)).toHaveAttribute('data-state', a.state);
  expect(faulted.appliances.every(a => KNOWN_ICON_KEYS.includes(a.key))).toBe(true);
  expect(container.querySelectorAll('[data-room]')).toHaveLength(6);
});

test('wires are exactly the configured topology edges and only energized wires pulse', () => {
  const { container } = render(<FloorPlan data={faulted} selected={null} onSelect={vi.fn()} highlight={[]} />);
  const wires = [...container.querySelectorAll('[data-edge]')];
  expect(wires.map(e => e.getAttribute('data-edge')).sort()).toEqual(faulted.edges.map(e => e.id).sort());
  for (const wire of wires) {
    const state = faulted.edges.find(e => e.id === wire.getAttribute('data-edge'))!.state;
    expect(wire).toHaveAttribute('data-state', state);
    expect(wire.querySelector('.ps-wire-pulse') !== null).toBe(state === 'ENERGIZED');
  }
});

test('every appliance sits inside its room and inside the drawing', () => {
  const layout = floorPlanLayout(faulted);
  // Appliance cards are 132 x 78 around their centre; rooms are 336 x 320.
  for (const a of faulted.appliances) {
    const p = layout.appliances.get(a.id)!;
    const r = layout.rooms.find(x => x.room.id === a.room_id)!;
    expect(p.cx - 66).toBeGreaterThanOrEqual(r.x); expect(p.cx + 66).toBeLessThanOrEqual(r.x + 336);
    expect(p.cy - 36).toBeGreaterThanOrEqual(r.y); expect(p.cy + 42).toBeLessThanOrEqual(r.y + 320);
    expect(p.cx).toBeLessThan(VIEW.width); expect(p.cy).toBeLessThan(VIEW.height);
  }
});

test('an open feeder shows its appliances as unreachable in text, not colour alone', () => {
  render(<FloorPlan data={faulted} selected={null} onSelect={vi.fn()} highlight={[]} />);
  const onFeederA = faulted.appliances.filter(a => a.feeder === 'A');
  expect(onFeederA.every(a => a.state === 'UNREACHABLE')).toBe(true);
  expect(screen.getAllByRole('button', { name: /Unreachable \(no path\)/ })).toHaveLength(onFeederA.length);
});

test('selecting an appliance with the keyboard opens its backend reason and request control', () => {
  const onSelect = vi.fn();
  const a = faulted.appliances.find(x => x.state === 'SHED')!;
  render(<NetworkView data={faulted} selected={null} onSelect={onSelect} highlight={[]} />);
  fireEvent.keyDown(screen.getByRole('button', { name: new RegExp(`^${a.name} in ${a.room_id}`) }), { key: 'Enter' });
  expect(onSelect).toHaveBeenCalledWith(a.id);
  const onRequest = vi.fn();
  render(<ApplianceDetail data={faulted} id={a.id} onClose={vi.fn()} onRequest={onRequest} disabled={false} />);
  const panel = screen.getByRole('complementary', { name: `Details for ${a.name}` });
  expect(panel).toHaveTextContent(a.reason);
  expect(panel).toHaveTextContent(a.reason_code);
  fireEvent.click(within(panel).getByRole('button', { name: 'Request off' }));
  expect(onRequest).toHaveBeenCalledWith(a.id, false);
});

test('the network view draws the same appliances as the floor plan', () => {
  const { container } = render(<NetworkView data={faulted} selected={null} onSelect={vi.fn()} highlight={[]} />);
  expect([...container.querySelectorAll('[data-appliance]')].map(e => `${e.getAttribute('data-appliance')}:${e.getAttribute('data-state')}`).sort())
    .toEqual(faulted.appliances.map(a => `${a.id}:${a.state}`).sort());
});

test('fault detection shows the injected inputs and the backend diagnosis separately', () => {
  expect(incidentsOf(faulted).length).toBeGreaterThan(0);
  render(<FaultDetection data={faulted} actions={noop} disabled={false} feedback={null} onShowOnPlan={vi.fn()} />);
  expect(screen.getByRole('region', { name: 'Injected simulation inputs' })).toHaveTextContent('FEEDER OPEN');
  expect(screen.getByRole('region', { name: 'Backend diagnosis' })).toHaveTextContent('Fault detected');
  expect(screen.getByRole('button', { name: 'Kill Feeder A' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Restore Feeder A' }));
  expect(noop.restoreFeeder).toHaveBeenCalledWith('A');
});

test('a missing diagnosis reads as unknown, never nominal', () => {
  const missing = { ...base, diagnosis: { ...(base.diagnosis as object), overall: 'INCONCLUSIVE' } } as PowerSystem;
  render(<FaultDetection data={missing} actions={noop} disabled={false} feedback={null} onShowOnPlan={vi.fn()} />);
  expect(screen.getByRole('region', { name: 'Backend diagnosis' })).toHaveTextContent('Inconclusive');
  expect(screen.getByRole('region', { name: 'Backend diagnosis' })).not.toHaveTextContent('Nominal');
});

test('electrical laws label their values and recompute from inputs', () => {
  render(<ElectricalLaws data={faulted} />);
  for (const law of [/Ohm/, /power/i, /Kirchhoff.*current/i, /Kirchhoff.*voltage/i, /energy/i, /capacity/i, /continuity/i])
    expect(screen.getAllByRole('heading', { name: law }).length).toBeGreaterThan(0);
  expect(screen.getAllByText('EDUCATIONAL EXAMPLE').length).toBeGreaterThan(0);
  expect(screen.getAllByText('LIVE MODEL VALUES').length).toBeGreaterThan(0);
});

test('history stays bounded and never rewrites the past', () => {
  let history = [] as ReturnType<typeof sampleOf>[];
  // Fixtures mask generated_at, so give samples their own clock.
  const s = { ...sampleOf(base), t: 1_000 };
  for (let i = 0; i < HISTORY_LIMIT + 50; i++) history = appendSample(history, { ...s, t: s.t + i * 1000 });
  expect(history).toHaveLength(HISTORY_LIMIT);
  expect(appendSample(history, { ...s, t: s.t })).toBe(history);
  expect(appendSample(history, { ...s, t: Number.NaN })).toBe(history);
  expect(s.served).toBe(base.source.served_w);
});
