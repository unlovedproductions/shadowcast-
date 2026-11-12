import { test, expect } from '../fixtures/test';
import { buttons, ids, nav } from '../helpers/selectors';

test.describe('catalogs', () => {
  test('content style shows recommended background', async ({ page, mockApi }) => {
    void mockApi;
    await page.goto('/');
    await expect(page.getByText(/Recommended background for this style/i)).toBeVisible({
      timeout: 15_000,
    });
    await page.getByText('VS Battle', { exact: true }).click();
    await expect(page.getByText(/Recommended background for this style/i)).toBeVisible();
    await expect(page.locator('a', { hasText: 'Preview' })).toBeVisible();
  });

  test('analytics build tracking link', async ({ page, mockApi }) => {
    void mockApi;
    await page.goto('/');
    await page.locator('.nav-btn', { hasText: nav.analytics }).click();
    await expect(page.getByRole('heading', { name: /Track a Video/i })).toBeVisible();
    // Wait for auto dashboard load re-render so filled inputs are not wiped.
    await expect(page.getByRole('button', { name: buttons.loadDashboard })).toBeEnabled({
      timeout: 15_000,
    });
    await page.locator(ids.trackAffiliateUrl).fill('https://amzn.to/track-e2e');
    await page.locator(ids.trackVideoId).fill('vid-e2e-1');
    await page.getByRole('button', { name: buttons.buildTrackingLink }).click();
    await expect(page.getByRole('heading', { name: 'Tracking URL' })).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator('.result-block .content')).toContainText(/utm_campaign|shadowcast_|amzn\.to/i);
  });
});
