import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 5_000 },
  retries: 0,
  use: {
    baseURL: 'http://localhost:4200',
    headless: true,
  },
  webServer: {
    command: 'npm run start -- --proxy-config proxy.conf.json',
    port: 4200,
    timeout: 120_000,
    reuseExistingServer: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});

