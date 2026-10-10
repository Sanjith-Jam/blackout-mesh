import { expect, test } from '@playwright/test';

// Needs the optional AC engine in the backend interpreter (backend/requirements-electrical.txt).
test('one-click emergency → validated proposal → fresh evidence → modeled recovery', async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto('/grid');
  await page.getByRole('button', { name: 'Simulate emergency' }).click();
  const workflow = page.getByRole('list', { name: 'Modeled recovery workflow' });
  await expect(workflow).toContainText('AC PASSED', { timeout: 20_000 });
  await expect(page.getByRole('status', { name: 'Outage impact' })).toContainText(/Critical unmet [1-9]/);
  const apply = page.getByRole('button', { name: 'Apply validated proposal' });
  await expect(apply).toBeDisabled();
  await page.getByRole('button', { name: 'Record healthy observation' }).click();
  await expect(workflow).toContainText('1 / 2');
  await page.waitForTimeout(5_500);
  await page.getByRole('button', { name: 'Record healthy observation' }).click();
  await expect(apply).toBeEnabled();
  await apply.click();
  await expect(workflow).toContainText('Modeled: tie:declared-demo');
  await expect(page.getByRole('status', { name: 'Outage impact' })).toContainText('Critical unmet 0 W');
  await expect(page.getByRole('table', { name: /Incident impact comparison/ })).toContainText('After recovery');
});

test('a refused action shows the backend reason, not an HTTP code', async ({ page }) => {
  await page.goto('/grid');
  await page.getByRole('tab', { name: 'Self-healing' }).click();
  await page.getByRole('button', { name: 'Record healthy observation' }).click();
  await expect(page.getByText(/healthy observation #\d+ recorded/)).toBeVisible();
  // Replay a stale sequence number: the backend must refuse it with a specific reason.
  await page.route('**/api/v1/district/action', async route => {
    const body = route.request().postDataJSON();
    await route.continue({ postData: JSON.stringify({ ...body, observation: { ...body.observation, sequence: 1 } }) });
  });
  await page.getByRole('button', { name: 'Record healthy observation' }).click();
  await expect(page.getByText(/Refused: observation is duplicate, reordered, stale or malformed/)).toBeVisible();
  await expect(page.getByText(/HTTP error 422/)).toHaveCount(0);
});

test('a watt-feasible weak tie is refused by the AC check with its numbers', async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto('/grid');
  await page.getByRole('button', { name: 'Simulate emergency' }).click();
  const workflow = page.getByRole('list', { name: 'Modeled recovery workflow' });
  await expect(workflow).toContainText('AC PASSED', { timeout: 20_000 });
  await page.getByRole('button', { name: 'Rehearse weak tie (AC refusal)' }).click();
  await expect(workflow).toContainText('Stale; propose again');
  await page.getByRole('button', { name: 'Propose recovery' }).click();
  await expect(workflow).toContainText('Refused by AC check');
  await expect(page.getByRole('region', { name: 'Recovery proposal explanation' })).toContainText(/line_loading at tie:declared-demo: [2-9]\.\d+ vs 1/);
  await page.getByRole('button', { name: 'Restore tie rating' }).click();
});
