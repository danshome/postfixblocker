import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // Run a single global reset before the entire suite starts; one-time cleanup after
  globalSetup: "./e2e/global-setup.spec.ts",
  // DB2 can take several minutes to become available; increase test timeout
  timeout: 600_000,
  expect: { timeout: 5000 },
  retries: 0,
  // Run E2E tests serially to avoid shared-state interference between specs
  workers: 1,
  webServer: {
    command: "npm run start:db2",
    url: "http://127.0.0.1:4200",
    timeout: 300_000,
    reuseExistingServer: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:4200" },
    },
  ],
});
