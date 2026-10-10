import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, test } from 'vitest';
import stuck from '../test/fixtures/hospital_stuck_sensor.json';
import { mockFetch } from '../test/mockApi';
import HospitalFaultRehearsal from './HospitalFaultRehearsal';

test('stuck sensor example shows untrusted evidence and an inspection step', async () => {
  const api = mockFetch({ 'POST /api/v1/visualizers/hospital': () => ({ json: stuck }) });
  render(<HospitalFaultRehearsal />);
  fireEvent.click(screen.getByRole('button', { name: 'Stuck sensor', exact: true }));
  const card = await screen.findByRole('article', { name: 'TX2 diagnostic evidence' });
  expect(within(card).getByText('Cannot determine cause · sensor evidence untrusted')).toBeVisible();
  expect(within(card).getByText(/clamp meter/)).toBeVisible();
  expect(api.posts()[0].body).toEqual({ rehearsal: 'stuck_sensor' });
  expect(screen.getByText(/do not inject faults into the live city/)).toBeVisible();
});
