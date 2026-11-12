import { test, expect } from '../fixtures/test';
import { buttons, ids } from '../helpers/selectors';

test.describe('generate flow', () => {
  test('shows validation toast when required fields empty', async ({ page, mockApi }) => {
    void mockApi;
    await page.goto('/');
    await page.getByRole('button', { name: buttons.generate }).click();
    await expect(page.locator('.toast')).toContainText(/Product Name|Key Features|Affiliate Link/i);
  });

  test('mocked generate reaches results', async ({ page, mockApi }) => {
    mockApi.holdRunning(true);
    await page.goto('/');
    await page.locator(ids.productName).fill('E2E Test Widget');
    await page.locator(ids.keyFeatures).fill('fast, cheap, quiet');
    await page.locator(ids.affiliateLink).fill('https://amzn.to/e2e-test');
    await page.getByRole('button', { name: buttons.generate }).click();

    await expect(page.getByText(/Rendering video|Starting|Cancel Job|Writing script/i).first()).toBeVisible({
      timeout: 15_000,
    });
    mockApi.holdRunning(false);
    await expect(page.getByText(/Generation Complete/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('button', { name: buttons.publishNow })).toBeVisible();
  });

  test('cancel job hits cancel API while progress shown', async ({ page, mockApi }) => {
    mockApi.holdRunning(true);
    await page.goto('/');
    await page.locator(ids.productName).fill('Cancel Me Widget');
    await page.locator(ids.keyFeatures).fill('one, two');
    await page.locator(ids.affiliateLink).fill('https://amzn.to/cancel');
    await page.getByRole('button', { name: buttons.generate }).click();

    await expect(page.getByRole('button', { name: buttons.cancelJob })).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole('button', { name: buttons.cancelJob }).click();
    await expect(page.locator('.toast')).toContainText(/Cancel requested|Cancel/i, {
      timeout: 10_000,
    });
    expect(mockApi.wasCancelled()).toBeTruthy();
  });
});
