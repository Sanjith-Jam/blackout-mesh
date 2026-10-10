import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Component tests run in jsdom with a mocked fetch/WebSocket (src/test/setup.ts). Browser E2E lives in e2e/.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': `${import.meta.dirname}/src` } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
});
