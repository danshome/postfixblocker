import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 5_000 },
  retries: 0,
  workers: 1,
  webServer: {
    command: 'npm run start:matrix',
    url: 'http://127.0.0.1:4201',
    timeout: 300_000,
    reuseExistingServer: true,
  },
  projects: [
    // Postgres-backed UI
    {
      name: 'pg-chromium',
      use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:4200' },
    },
    // DB2-backed UI on a different port to avoid collision
    {
      name: 'db2-chromium',
      use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:4201' },
    },
  ],
});
