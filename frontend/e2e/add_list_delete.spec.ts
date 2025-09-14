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
  await expect(page.locator('table')).toContainText('No data');

  // Add a literal address via paste box
  await page.getByPlaceholder('paste emails or regex (one per line)').fill('e2e1@example.com');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.locator('table')).toContainText('e2e1@example.com');

  // Add a regex entry via paste box
  await page.getByPlaceholder('paste emails or regex (one per line)').fill('.*@e2e.com');
  await page.getByRole('checkbox', { name: 'Regex' }).check();
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  const regexRow = page.locator('tr.mat-row', { hasText: '.*@e2e.com' });
  await expect(regexRow).toContainText('Yes');

  // Bulk add two addresses (one per line) via paste box
  await page.getByPlaceholder('paste emails or regex (one per line)').fill('bulk1@example.com\nbulk2@example.com');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.locator('table')).toContainText(['bulk1@example.com', 'bulk2@example.com']);

  // Select two entries and delete selected
  await page.locator('tr.mat-row', { hasText: 'bulk1@example.com' }).getByRole('checkbox').check();
  await page.locator('tr.mat-row', { hasText: 'bulk2@example.com' }).getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Delete Selected' }).click();
  await expect(page.locator('table')).not.toContainText(['bulk1@example.com', 'bulk2@example.com']);

  // Delete all remaining
  await page.getByRole('button', { name: 'Delete All' }).click();
  await expect(page.locator('mat-list-item')).toHaveCount(0);
});
