import AxeBuilder from '@axe-core/playwright';
import { expect, Page, test } from '@playwright/test';

// Same-origin API calls go to the isolated test backend, never the user's demo databases.
const BACKEND = 'http://127.0.0.1:8183';
const forward = async (page: Page) => {
  await page.route('**/api/v1/**', async route => {
    const response = await route.fetch({ url: route.request().url().replace('http://127.0.0.1:5183', BACKEND) });
    await route.fulfill({ response });
  });
  await page.routeWebSocket('**/ws/live', socket => socket.close());
};
const resetClassrooms = (page: Page) => page.request.post(`${BACKEND}/api/v1/visualizers/classrooms`, { data: { action: 'reset' } });

/** Tab forward until the focused element matches, the way a keyboard-only user would reach it. */
async function tabTo(page: Page, matches: (el: Element) => boolean, limit = 80) {
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab');
    if (await page.evaluate(`(${matches.toString()})(document.activeElement)`)) return;
  }
  throw new Error('Control not reachable with Tab');
}
const byText = (text: string) => new Function('el', `return !!el && el.textContent.trim() === ${JSON.stringify(text)}`) as (el: Element) => boolean;

test.beforeEach(async ({ page }) => {
  await forward(page);
  await resetClassrooms(page);
});
// Polling pages keep requests in flight; drop the forwarding route before the page closes so a late
// fetch never fails the test that just finished.
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('keyboard-only classroom journey survives a backend outage and a page reload', async ({ page }) => {
  await page.goto('/classrooms');
  const controls = page.getByRole('group', { name: 'Scan classroom RFID cards' });
  await expect(controls).toBeVisible();

  await tabTo(page, byText('Scan CR1'));
  expect(await page.evaluate(() => document.activeElement?.matches(':focus-visible'))).toBe(true);
  await page.keyboard.press('Enter');
  await expect(controls.getByRole('button', { name: /CR1 scanned/ })).toHaveAttribute('aria-pressed', 'true');

  await tabTo(page, byText('Overload preset'));
  await page.keyboard.press('Space');
  const slider = page.getByRole('slider');
  await expect(slider).toHaveAttribute('aria-valuenow', '3400');
  await slider.focus();
  await page.keyboard.press('ArrowRight');
  await expect(slider).toHaveAttribute('aria-valuenow', '3500');

  // Backend goes away: the page keeps the last known state and says so in text, not only colour.
  await page.unroute('**/api/v1/**');
  await page.route('**/api/v1/**', route => route.abort('connectionrefused'));
  await page.getByRole('button', { name: 'Full supply · 8,000 W' }).click();
  await expect(page.getByRole('alert')).toContainText('Connection lost');
  await expect(controls.getByRole('button', { name: /CR1 scanned/ })).toBeVisible();

  // Backend returns: the next action recovers and the alert clears.
  await page.unroute('**/api/v1/**');
  await forward(page);
  await page.getByRole('button', { name: 'Full supply · 8,000 W' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(slider).toHaveAttribute('aria-valuenow', '8000');

  // Server state, not browser state, is what a reload shows.
  await page.reload();
  await expect(page.getByRole('group', { name: 'Scan classroom RFID cards' }).getByRole('button', { name: /CR1 scanned/ })).toBeVisible();
});

test('backend unavailable on first load shows a retry that recovers', async ({ page }) => {
  await page.unroute('**/api/v1/**');
  await page.route('**/api/v1/**', route => route.abort('connectionrefused'));
  await page.goto('/classrooms');
  await expect(page.getByRole('heading', { name: 'Classroom demo unavailable' })).toBeVisible();
  await page.unroute('**/api/v1/**');
  await forward(page);
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('group', { name: 'Scan classroom RFID cards' })).toBeVisible();
});

/** Wait for one-shot entrance fades to finish; axe misreads contrast on half-faded text. Looping effects are ignored. */
const settled = (page: Page) => page.waitForFunction(() => document.getAnimations()
  .every(a => a.playState !== 'running' || a.effect?.getComputedTiming().iterations === Infinity));

const ROUTES = ['/', '/demo', '/city', '/classrooms', '/hospital', '/console'];
const WIDTHS = [375, 1280];

for (const route of ROUTES) {
  for (const width of WIDTHS) {
    test(`${route} at ${width}px: no page overflow and no serious axe violations`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      await settled(page);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, 'horizontal page overflow in px').toBeLessThanOrEqual(0);
      const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      const serious = violations.filter(v => v.impact === 'serious' || v.impact === 'critical');
      expect(serious.map(v => `${v.id}: ${v.nodes.map(n => n.target.join(' ')).slice(0, 3).join(', ')}`)).toEqual([]);
    });
  }
}

test('reduced motion stops looping and moving animations on every visualizer', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.request.post(`${BACKEND}/api/v1/visualizers/classrooms`, { data: { action: 'scan', classroom_id: 'CR1' } });
  for (const route of ['/demo', '/city', '/classrooms', '/hospital']) {
    await page.goto(route);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    // Opacity fades are allowed; anything that loops forever or moves (transform, translate, offset, dash) is not.
    const moving = await page.evaluate(() => document.getAnimations()
      .filter(a => a.playState === 'running')
      .filter(a => {
        const effect = a.effect as KeyframeEffect | null;
        const loops = effect?.getComputedTiming().iterations === Infinity;
        const moves = (effect?.getKeyframes() ?? []).some(k => ['transform', 'translate', 'offsetDistance', 'strokeDashoffset'].some(p => p in k));
        return loops || moves;
      })
      .map(a => {
        const target = (a.effect as KeyframeEffect | null)?.target;
        return target instanceof Element ? `${target.tagName.toLowerCase()}.${[...target.classList].join('.')}` : 'unknown';
      }));
    expect(moving, `${route} keeps animating with reduced motion`).toEqual([]);
  }
});
