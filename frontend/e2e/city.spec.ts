import { expect, test } from '@playwright/test';

test.use({ video: 'on' });

test('city shortage, forecast warning and guided recovery use the real controller', async ({ page }, testInfo) => {
  // Same-origin browser requests forward to the isolated test backend, never the user's demo databases.
  await page.route('**/api/v1/**', async route => {
    const response = await route.fetch({ url: route.request().url().replace('http://127.0.0.1:5183', 'http://127.0.0.1:8183') });
    await route.fulfill({ response });
  });
  await page.routeWebSocket('**/ws/live', socket => socket.close());
  await page.goto('/demo');
  await expect(page.getByRole('region', { name: 'City electrical grid' })).toBeVisible();
  await page.getByRole('button', { name: 'Request all rooms', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'All three classroom sessions requested.' })).toBeVisible();
  const panels = ['Source power state', 'Hospital power state', 'Classroom power state'];
  const before = await page.getByRole('region', { name: panels[0], exact: true }).getAttribute('data-revision');
  await page.getByRole('button', { name: '6 kW shortage', exact: true }).click();
  await expect(page.locator('.city-shed-reason').first()).toContainText(/source_capacity|preference|restoration/);
  await expect.poll(async () => page.getByRole('region', { name: panels[0], exact: true }).getAttribute('data-revision')).not.toBe(before);
  const revisions = await Promise.all(panels.map(name => page.getByRole('region', { name, exact: true }).getAttribute('data-revision')));
  expect(new Set(revisions).size).toBe(1);
  await page.getByLabel('Observation source').selectOption('SYNTHETIC_REPLAY');
  await expect(page.getByRole('status').filter({ hasText: /Possible capacity shortfall within/ })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Predictive demand forecast' })).toContainText('Rehearsal observations are synthetic');
  await page.screenshot({ path: testInfo.outputPath('city-desktop.png'), fullPage: true });
  await page.getByRole('button', { name: 'Trip feeder A', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Outage recovery guidance' })).toContainText('Feeder A is open');
  await expect(page.getByRole('region', { name: 'Outage recovery guidance' })).toContainText('3,000 W critical shortfall');
  await page.getByRole('region', { name: 'Outage recovery guidance' }).getByRole('button', { name: 'Repair feeder A', exact: true }).click();
  await page.getByRole('button', { name: 'Restore supply', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Outage recovery guidance' })).toContainText('Requested services recovered', { timeout: 15000 });
  await expect(page.getByRole('region', { name: 'Power decision explanations' })).toContainText('All requested services are served');
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.screenshot({ path: testInfo.outputPath('city-mobile.png'), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
