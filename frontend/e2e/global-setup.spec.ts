/*
 Global Playwright setup: ensure both API backends are ready and reset ONCE
 before the entire e2e suite. Do NOT reset before each test — this would hide
 ordering/leakage problems that we specifically want to detect.
*/
/* eslint sonarjs/no-empty-test-file: "off" -- This file is a Playwright global setup module, not a test file. It is named with .spec.ts so eslint-plugin-boundaries recognizes it as a known element type. Adding tests here would be incorrect because Playwright treats this as a special setup module executed once before tests, not a test suite. */

/**
 * Wait until an HTTP endpoint responds with a 2xx status.
 * @param {string} url - Absolute URL to poll for readiness.
 * @param {number} [timeoutMs] - Maximum time to wait in milliseconds.
 * @returns {Promise<void>} Resolves when the endpoint responds OK.
 */
async function waitForOk(url: string, timeoutMs = 600_000): Promise<void> {
  const start = Date.now();
  for (;;) {
    try {
      const r = await fetch(url, { method: 'GET' });
      if (r.ok) return;
    } catch {
      // Backend may not be up yet; ignore transient network errors.
      void 0;
    }
    if (Date.now() - start > timeoutMs) {
      throw new Error(`Timeout waiting for ${url} to be ready`);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

/**
 * POST a JSON payload and return whether the response is OK (2xx).
 * @param {string} url - Absolute URL to post to.
 * @param {unknown} body - Serializable JSON body; defaults to empty object.
 * @returns {Promise<boolean>} True if the response had an OK status.
 */
async function postJson(url: string, body: unknown): Promise<boolean> {
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    });
    return r.ok;
  } catch {
    return false;
  }
}

/**
 * Playwright global setup executed once before the e2e test suite.
 * Ensures the backend API is ready and attempts an optional baseline reset.
 * @returns {Promise<void>} Resolves when setup is complete.
 */
export default async function globalSetup(): Promise<void> {
  // Directly target API containers (not the dev servers) to avoid any coupling
  // with the webServer startup order.
  const bases = ['http://127.0.0.1:5002'];

  // Wait for the API to become responsive
  for (const base of bases) {
    await waitForOk(`${base}/addresses`).catch((error) => {
      // Let it throw — this will fail the suite early with a clear message
      throw error;
    });
  }

  // Reset both databases ONCE to a baseline state
  for (const base of bases) {
    const ok = await postJson(`${base}/test/reset`, { seeds: [] });
    if (!ok) {
      // Not fatal: older backends may not expose /test/reset. The tests still
      // create and clean up their own data, but we prefer this fast path.
      // Intentionally do not implement a fallback full wipe here to keep the
      // policy of "one reset at the start".

      console.warn(
        `[global-setup] /test/reset not available or failed for ${base}`,
      );
    }
  }
}
