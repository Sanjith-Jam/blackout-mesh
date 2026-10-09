import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://127.0.0.1:5183', ...devices['Desktop Chrome'] },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5183',
    url: 'http://127.0.0.1:5183',
    reuseExistingServer: !process.env.CI,
  },
});
