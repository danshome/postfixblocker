import { test, expect } from '@playwright/test';

test.beforeEach(async ({ request }) => {
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

  // Initially empty
  await expect(page.locator('ul li')).toHaveCount(0);

  // Add a literal address
  await page.getByPlaceholder('email or regex', { exact: true }).fill('e2e1@example.com');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.locator('ul li')).toContainText(['e2e1@example.com']);

  // Add a regex entry
  await page.getByPlaceholder('email or regex', { exact: true }).fill('.*@e2e.com');
  await page.getByRole('checkbox', { name: 'Regex' }).first().check();
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.locator('ul li')).toContainText(['(regex)']);

  // Bulk add two addresses (one per line)
  await page.getByPlaceholder('one email or regex per line').fill('bulk1@example.com\nbulk2@example.com');
  await page.getByRole('button', { name: 'Add List' }).click();
  await expect(page.locator('ul li')).toContainText(['bulk1@example.com', 'bulk2@example.com']);

  // Delete the first entry
  const first = page.locator('ul li', { hasText: 'e2e1@example.com' });
  await first.getByRole('button', { name: 'Delete' }).click();
  await expect(first).toHaveCount(0);
});
