import { ChildProcess, spawn } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { expect, Page, test } from '@playwright/test';

const PYTHON = process.env.PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3');
const BACKEND_DIR = resolve(import.meta.dirname, '../../backend');
const forwardHttp = (page: Page, backend: string) => page.route('**/api/v1/**', async route => {
  try {
    const response = await route.fetch({ url: route.request().url().replace('http://127.0.0.1:5183', backend) });
    await route.fulfill({ response });
  } catch {
    await route.abort('connectionrefused');  // backend is down: fail the request the way the browser would
  }
});
const capacity = (page: Page) => page.locator('.metric-box', { hasText: 'Live Capacity' }).locator('.metric-value');
const backendPill = (page: Page) => page.locator('.status-pill', { hasText: 'Backend' });

test('malformed, duplicate and out-of-order live frames never move the console backwards', async ({ page }) => {
  await forwardHttp(page, 'http://127.0.0.1:8183');
  const base = await (await page.request.get('http://127.0.0.1:8183/api/v1/snapshot')).json();
  const revision = base.published_revision as number;
  const frame = (published_revision: number, capacity_w: number) => JSON.stringify({
    type: 'snapshot', sent_at: new Date().toISOString(),
    payload: { ...base, published_revision, source: { ...base.source, capacity_w } },
  });
  let send: (message: string) => void = () => {};
  await page.routeWebSocket('**/ws/live', socket => { send = message => socket.send(message); });

  await page.goto('/console');
  await expect(capacity(page)).toContainText(String(base.source.capacity_w));

  send(frame(revision + 1, 7777));
  await expect(capacity(page)).toContainText('7777');

  for (const bad of [
    'not json {',                                             // malformed JSON
    JSON.stringify({ type: 'snapshot' }),                      // envelope missing everything
    JSON.stringify({ type: 'telemetry', payload: {} }),        // unknown frame type
    frame(revision + 1, 2222),                                 // duplicate revision
    frame(revision, 1111),                                     // older revision, arriving late
  ]) send(bad);
  send(frame(revision + 2, 6666));                             // the next real revision still applies
  await expect(capacity(page)).toContainText('6666');
  for (const value of ['2222', '1111']) await expect(capacity(page)).not.toContainText(value);
});

/** A backend this test owns, so it can be killed and started again mid-session. */
function startBackend(port: number, dataDir: string): Promise<ChildProcess> {
  const child = spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--app-dir', BACKEND_DIR, '--host', '127.0.0.1', '--port', String(port)], {
    env: { ...process.env, DATABASE_URL: 'sqlite://', PRIORITYGRID_HISTORY_DB: join(dataDir, 'history.sqlite3') },
    stdio: 'ignore',
  });
  return new Promise((ready, fail) => {
    const deadline = Date.now() + 60_000;
    const poll = async () => {
      try {
        if ((await fetch(`http://127.0.0.1:${port}/api/v1/health`)).ok) return ready(child);
      } catch { /* not up yet */ }
      if (child.exitCode !== null || Date.now() > deadline) return fail(new Error('test backend did not start'));
      setTimeout(poll, 250);
    };
    void poll();
  });
}
const stopBackend = (child: ChildProcess) => new Promise<void>(done => {
  if (child.exitCode !== null) return done();
  child.once('exit', () => done());
  child.kill();
});

test('the console notices a real backend restart, reconnects and resyncs to the new run', async ({ page }) => {
  test.setTimeout(120_000);
  const port = 8184;
  const backend = `http://127.0.0.1:${port}`;
  const dataDir = mkdtempSync(join(tmpdir(), 'blackout-restart-'));
  let server = await startBackend(port, dataDir);
  try {
    await forwardHttp(page, backend);
    // Bridge the page's live socket to whichever backend process is running now.
    await page.routeWebSocket('**/ws/live', socket => {
      const upstream = new WebSocket(`ws://127.0.0.1:${port}/ws/live`);
      upstream.onmessage = event => socket.send(String(event.data));
      upstream.onclose = () => socket.close();
      upstream.onerror = () => socket.close();
      socket.onClose(() => upstream.close());
    });
    const runId = async () => (await (await page.request.get(`${backend}/api/v1/snapshot`)).json()).contract.identity.run_id as string;

    const firstRun = await runId();
    await page.goto('/console');
    await expect(backendPill(page)).toContainText('Live');
    await expect(page.getByText(`run ${firstRun}`)).toBeVisible();

    await stopBackend(server);
    await expect(backendPill(page)).toContainText('Stale/Disconnected');
    await expect(page.getByText('Reconnecting to backend...')).toBeVisible();

    server = await startBackend(port, dataDir);
    const secondRun = await runId();
    expect(secondRun).not.toBe(firstRun);
    await expect(backendPill(page)).toContainText('Live', { timeout: 30_000 });
    await expect(page.getByText(`run ${secondRun}`)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('Reconnecting to backend...')).toHaveCount(0);
  } finally {
    await stopBackend(server);
  }
});
