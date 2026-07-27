import { test, expect } from '../fixtures/test';
import { buttons, nav } from '../helpers/selectors';

test.describe('social publish', () => {
  test('social page loads postable jobs', async ({ page, mockApi }) => {
    void mockApi;
    await page.goto('/');
    await page.locator('.nav-btn', { hasText: nav.social }).click();
    await expect(page.getByRole('heading', { name: 'Post a Video' })).toBeVisible();
    await expect(page.locator('#socialJobSelect')).toContainText('E2E Test Widget', {
      timeout: 15_000,
    });
    await expect(page.getByRole('button', { name: buttons.postNow })).toBeEnabled();
  });

  test('schedule without datetime shows toast', async ({ page, mockApi }) => {
    void mockApi;
    await page.goto('/');
    await page.locator('.nav-btn', { hasText: nav.social }).click();
    await expect(page.getByRole('button', { name: buttons.schedulePost })).toBeEnabled({
      timeout: 15_000,
    });
    await page.getByRole('button', { name: buttons.schedulePost }).click();
    await expect(page.locator('.toast')).toContainText(/schedule date\/time|Post Now/i);
  });

  test('job dry run posts via publish/batch stub', async ({ page, mockApi }) => {
    void mockApi;
    await page.goto('/');
    await page.locator('.nav-btn', { hasText: nav.social }).click();
    await expect(page.getByRole('button', { name: buttons.dryRun })).toBeEnabled({
      timeout: 15_000,
    });
    await page.getByRole('button', { name: buttons.dryRun }).click();
    await expect(page.locator('.toast')).toContainText(/Dry run successful|Posted successfully/i, {
      timeout: 10_000,
    });
  });
});
