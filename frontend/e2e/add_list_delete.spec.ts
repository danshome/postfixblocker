import { test, expect } from 'playwright/test';

async function waitForApiReady(request: any, timeoutMs = 600_000): Promise<void> {
  const start = Date.now();
  // Poll until API is ready (200 OK) or timeout
  // Playwright's request fixture shares baseURL with each project so '/addresses' proxies correctly
  for (;;) {
    const resp = await request.get('/addresses');
    if (resp.ok()) return;
    if (Date.now() - start > timeoutMs) {
      throw new Error(`API not ready after ${timeoutMs}ms (last status=${resp.status()})`);
    }
    await new Promise(r => setTimeout(r, 1000));
  }
}

test.beforeEach(async ({ request }) => {
  // Ensure backend is up (DB ready) before proceeding
  await waitForApiReady(request);
  // Reset backend state via the dev-server proxy for the current project
  const resp = await request.get('/addresses');
  if (resp.ok()) {
    const items = await resp.json();
    for (const it of items as any[]) {
      await request.delete(`/addresses/${it.id}`);
    }
  }
});

test('add, list, and delete entries', async ({ page }) => {
  await page.goto('/');

  // Table body handle for scoping queries
  const body = page.locator('table tbody').first();

  // Add a literal address via paste box
  await page.getByPlaceholder('paste emails or regex (one per line)').fill('e2e1@example.com');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(body.locator('tr', { hasText: /e2e1@example\.com/ })).toBeVisible();

  // Add a regex entry via paste box
  await page.getByPlaceholder('paste emails or regex (one per line)').fill('.*@e2e.com');
  await page.getByRole('checkbox', { name: 'Regex' }).check();
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  // Locate the newly added regex row by name within tbody
  const rowByPattern = body.locator('tr', { hasText: /\.*@e2e\.com/ });
  await expect(rowByPattern).toBeVisible({ timeout: 30000 });
  await expect(rowByPattern.locator('td').nth(2)).toHaveText('Yes', { timeout: 30000 });

  // Bulk add two addresses (one per line) via paste box
  await page.getByPlaceholder('paste emails or regex (one per line)').fill('bulk1@example.com\nbulk2@example.com');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  // Wait for both bulk rows to appear in the table body
  await expect(body.locator('tr', { hasText: /bulk1@example\.com/ })).toBeVisible({ timeout: 15000 });
  await expect(body.locator('tr', { hasText: /bulk2@example\.com/ })).toBeVisible({ timeout: 15000 });

  // Select two entries (click rows from tbody) and delete selected
  await body.locator('tr', { hasText: /bulk1@example\.com/ }).click();
  await body.locator('tr', { hasText: /bulk2@example\.com/ }).click();
  await page.getByRole('button', { name: 'Delete Selected' }).click();
  await expect(page.locator('table')).not.toContainText(['bulk1@example.com', 'bulk2@example.com']);

  // Delete all remaining
  await page.getByRole('button', { name: 'Delete All' }).click();
  // Empty state again: ensure previously added entries are gone
  await expect(page.locator('table')).not.toContainText(['e2e1@example.com', '.*@e2e.com']);
});
