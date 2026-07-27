import { test, expect } from '../fixtures/test';
import { buttons } from '../helpers/selectors';

test.describe('settings', () => {
  test('opens settings and tests LLM via stub', async ({ page, mockApi }) => {
    void mockApi;
    await page.goto('/');
    await page.getByRole('button', { name: buttons.settings }).click();
    await expect(page.getByRole('heading', { name: /LLM Settings/i })).toBeVisible();
    await expect(page.locator('#settingsProvider')).toBeVisible();

    await page.getByRole('button', { name: buttons.testLlm }).click();
    await expect(page.locator('.toast')).toContainText('LLM connection OK', {
      timeout: 10_000,
    });
  });
});
