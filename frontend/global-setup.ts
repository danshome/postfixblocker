/*
 Global Playwright setup: ensure both API backends are ready and reset ONCE
 before the entire e2e suite. Do NOT reset before each test — this would hide
 ordering/leakage problems that we specifically want to detect.
*/

async function waitForOk(url: string, timeoutMs = 600_000): Promise<void> {
  const start = Date.now();
  for (;;) {
    try {
      const r = await fetch(url, { method: 'GET' });
      if (r.ok) return;
    } catch {}
    if (Date.now() - start > timeoutMs) {
      throw new Error(`Timeout waiting for ${url} to be ready`);
    }
    await new Promise(r => setTimeout(r, 1000));
  }
}

async function postJson(url: string, body: any): Promise<boolean> {
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

export default async function globalSetup() {
  // Directly target API containers (not the dev servers) to avoid any coupling
  // with the webServer startup order.
  const bases = ['http://127.0.0.1:5001', 'http://127.0.0.1:5002'];

  // Wait for both APIs to become responsive
  for (const base of bases) {
    await waitForOk(`${base}/addresses`).catch((e) => {
      // Let it throw — this will fail the suite early with a clear message
      throw e;
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
      // eslint-disable-next-line no-console
      console.warn(`[global-setup] /test/reset not available or failed for ${base}`);
    }
  }
}
