import { test, expect } from '../fixtures/test';
import { nav } from '../helpers/selectors';

test.describe('smoke', () => {
  test('loads SPA and navigates primary pages', async ({ page, mockApi }) => {
    void mockApi;
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('Shadow');
    await expect(page.locator('.nav-btn', { hasText: nav.generate })).toBeVisible();
    await expect(page.getByText('Honest Review')).toBeVisible();
    await expect(page.getByText(/Curiosity/i).first()).toBeVisible();

    await page.locator('.nav-btn', { hasText: nav.analytics }).click();
    await expect(page.getByRole('heading', { name: /Analytics Dashboard/i })).toBeVisible();

    await page.locator('.nav-btn', { hasText: nav.social }).click();
    await expect(page.getByRole('heading', { name: 'Post a Video' })).toBeVisible();

    await page.locator('.nav-btn', { hasText: nav.generate }).click();
    await expect(page.getByRole('button', { name: /Generate Videos/i })).toBeVisible();
  });
});
