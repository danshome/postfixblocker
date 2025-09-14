import { test, expect, request as pwRequest } from '@playwright/test';

const API_BASE = process.env.API_BASE || 'http://localhost:5001';

test.beforeEach(async ({ request }) => {
  // Reset backend state to ensure deterministic UI tests
  const resp = await request.get(`${API_BASE}/addresses`);
  if (resp.ok()) {
    const items = await resp.json();
    for (const it of items as any[]) {
      await request.delete(`${API_BASE}/addresses/${it.id}`);
    }
  }
});

test('add, list, and delete entries', async ({ page }) => {
  await page.goto('/');

  // Initially empty
  await expect(page.locator('ul li')).toHaveCount(0);

  // Add a literal address
  await page.getByPlaceholder('email or regex').fill('e2e1@example.com');
  await page.getByRole('button', { name: 'Add' }).click();
  await expect(page.locator('ul li')).toContainText(['e2e1@example.com']);

  // Add a regex entry
  await page.getByPlaceholder('email or regex').fill('.*@e2e.com');
  await page.getByLabel('Regex').check();
  await page.getByRole('button', { name: 'Add' }).click();
  await expect(page.locator('ul li')).toContainText(['(regex)']);

  // Delete the first entry
  const first = page.locator('ul li', { hasText: 'e2e1@example.com' });
  await first.getByRole('button', { name: 'Delete' }).click();
  await expect(first).toHaveCount(0);
});

