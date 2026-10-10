import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const historyDirectory = mkdtempSync(join(tmpdir(), 'blackout-browser-'));

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://127.0.0.1:5183', ...devices['Desktop Chrome'] },
  webServer: [{
    command: 'npm run dev -- --host 127.0.0.1 --port 5183',
    url: 'http://127.0.0.1:5183',
    reuseExistingServer: !process.env.CI,
    env: { VITE_API_BASE_URL: 'http://127.0.0.1:5183' },
  }, {
    command: `${process.env.PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3')} -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8183`,
    url: 'http://127.0.0.1:8183/api/v1/health',
    env: { DATABASE_URL: 'sqlite://', PRIORITYGRID_HISTORY_DB: join(historyDirectory, 'history.sqlite3') },
  }],
});
