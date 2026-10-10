import { expect, Page, test } from '@playwright/test';

// Same-origin API calls go to the isolated test backend, never the user's demo databases.
const BACKEND = 'http://127.0.0.1:8183';
type Appliance = { id: string; state: string; zone: string; feeder: string };
type PowerSystem = { appliances: Appliance[]; edges: { id: string; state: string }[]; diagnosis: { overall: string }; site: { revision: number } };

const forward = async (page: Page) => {
  await page.route('**/api/v1/**', async route => {
    const response = await route.fetch({ url: route.request().url().replace('http://127.0.0.1:5183', BACKEND) });
    await route.fulfill({ response });
  });
  await page.routeWebSocket('**/ws/live', socket => socket.close());
};
const backendState = async (page: Page) => (await (await page.request.get(`${BACKEND}/api/v1/power-system`)).json()) as PowerSystem;

/** Every appliance and wire drawn on the current view carries the backend's state for that id. */
async function drawingMatchesBackend(page: Page, view: string) {
  await expect.poll(async () => {
    const data = await backendState(page);
    const drawn = await page.locator(`${view} [data-appliance]`).evaluateAll(els => els.map(e => [e.getAttribute('data-appliance'), e.getAttribute('data-state')]));
    const wires = view === '.ps-floorplan'
      ? await page.locator(`${view} [data-edge]`).evaluateAll(els => els.map(e => [e.getAttribute('data-edge'), e.getAttribute('data-state')]))
      : data.edges.map(e => [e.id, e.state]);
    const expected = Object.fromEntries(data.appliances.map(a => [a.id, a.state]));
    const expectedWires = Object.fromEntries(data.edges.map(e => [e.id, e.state]));
    return drawn.length === data.appliances.length && drawn.every(([id, s]) => expected[id!] === s)
      && wires.length === data.edges.length && wires.every(([id, s]) => expectedWires[id!] === s);
  }, { timeout: 8000 }).toBe(true);
}

test.beforeEach(async ({ page }) => {
  await forward(page);
  await page.request.post(`${BACKEND}/api/v1/site/scenario`, { data: { scenario: 'normal' } });
});
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.request.post(`${BACKEND}/api/v1/site/scenario`, { data: { scenario: 'normal' } });
});

test('feeder A outage and capacity drop flow from the Fault Lab through the backend to every view', async ({ page }, testInfo) => {
  await page.goto('/demo');
  await expect(page.getByRole('group', { name: /Floor plan with rooms/ })).toBeVisible();
  await drawingMatchesBackend(page, '.ps-floorplan');

  // Kill feeder A from the Fault Lab. The tab switch keeps the same backend run.
  await page.getByRole('tab', { name: /Fault Detection/ }).click();
  await page.getByRole('button', { name: 'Kill Feeder A', exact: true }).click();
  await expect.poll(async () => (await backendState(page)).appliances.filter(a => a.feeder === 'A').every(a => a.state === 'UNREACHABLE')).toBe(true);
  const outage = await backendState(page);
  expect(outage.appliances.filter(a => a.feeder === 'B' && a.state === 'UNREACHABLE')).toEqual([]);
  await expect(page.getByRole('region', { name: 'Injected simulation inputs' })).toContainText('FEEDER OPEN');
  await expect(page.getByRole('region', { name: 'Backend diagnosis' })).not.toContainText('Nominal');
  await page.screenshot({ path: testInfo.outputPath('demo-feeder-a-faults.png'), fullPage: true });

  await page.getByRole('tab', { name: 'Floor Plan' }).click();
  await drawingMatchesBackend(page, '.ps-floorplan');
  await page.screenshot({ path: testInfo.outputPath('demo-feeder-a-floor.png'), fullPage: true });
  await page.getByRole('radio', { name: 'Electrical network' }).click();
  await drawingMatchesBackend(page, '.ps-network');

  // Clicking an appliance shows its backend reason.
  const icu = outage.appliances.find(a => a.feeder === 'A')!;
  await page.locator(`.ps-network [data-appliance="${icu.id}"]`).click();
  await expect(page.getByRole('complementary')).toContainText('No path from source');

  // Restore feeder A, then drop capacity: loads shed individually, nothing becomes unreachable.
  await page.getByRole('tab', { name: /Fault Detection/ }).click();
  await page.getByRole('button', { name: 'Restore Feeder A', exact: true }).click();
  await page.getByRole('button', { name: 'Drop Capacity · 6,000 W', exact: true }).click();
  await expect.poll(async () => (await backendState(page)).diagnosis.overall).toBe('CONSTRAINT_ACTIVE');
  await expect(page.getByRole('region', { name: 'Backend diagnosis' })).toContainText('Capacity constraint active');
  const overload = await backendState(page);
  expect(overload.appliances.filter(a => a.state === 'UNREACHABLE')).toEqual([]);
  expect(overload.appliances.some(a => a.state === 'SHED')).toBe(true);
  await page.getByRole('tab', { name: 'Floor Plan' }).click();
  await drawingMatchesBackend(page, '.ps-floorplan');
  await page.screenshot({ path: testInfo.outputPath('demo-capacity-floor.png'), fullPage: true });

  // Restore capacity: staged restoration brings every requested appliance back.
  await page.getByRole('tab', { name: /Fault Detection/ }).click();
  await page.getByRole('button', { name: /Restore Capacity/ }).click();
  await expect.poll(async () => (await backendState(page)).appliances.every(a => a.state === 'SERVED' || a.state === 'NOT_REQUESTED'), { timeout: 30000 }).toBe(true);
});

test('hospital Full supply closes an open feeder A and Overload sheds per policy', async ({ page }, testInfo) => {
  // Feeder A left open (for example from the /demo Fault Lab) used to leave /hospital stuck at 0 W.
  await page.request.post(`${BACKEND}/api/v1/simulation/feeder`, { data: { feeder: 'A', available: false } });
  await page.goto('/hospital');
  const state = page.getByRole('region', { name: 'Hospital power state' });
  await expect(state).toContainText('Limited by campus feeder A (0 W)');
  await page.getByRole('button', { name: 'Full supply · 6,000 W' }).click();
  await expect.poll(async () => (await backendState(page)).appliances.filter(a => a.zone === 'hospital').every(a => a.state === 'SERVED'),
    { timeout: 20000 }).toBe(true);
  await expect(state.locator('.classroom-demo__metric').filter({ hasText: 'Served' })).toContainText('6,000 W');
  await expect(state).not.toContainText('UPSTREAM LOSS');
  await page.screenshot({ path: testInfo.outputPath('hospital-full-supply.png'), fullPage: true });

  await page.getByRole('button', { name: 'Overload preset' }).click();
  await expect.poll(async () => (await backendState(page)).appliances.some(a => a.zone === 'hospital' && a.state === 'SHED')).toBe(true);
  await expect(state.locator('.classroom-demo__metric').filter({ hasText: 'Unmet' })).not.toContainText(/^Unmet0 W$/);
  await page.screenshot({ path: testInfo.outputPath('hospital-overload.png'), fullPage: true });
});
