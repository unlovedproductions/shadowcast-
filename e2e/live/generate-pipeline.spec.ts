import { test, expect } from '@playwright/test';
import { buttons, ids } from '../helpers/selectors';

const liveEnabled = process.env.SHADOWCAST_E2E_LIVE === '1';

test.describe('live generate pipeline', () => {
  test.beforeEach(async ({ request }) => {
    test.skip(!liveEnabled, 'Set SHADOWCAST_E2E_LIVE=1 to run live pipeline');
    const res = await request.get('/api/readiness');
    const data = await res.json();
    test.skip(!data.ready, `Readiness blocked: ${(data.blockers || []).join('; ') || 'not ready'}`);
  });

  test('generates one short-form video end-to-end', async ({ page }) => {
    test.setTimeout(15 * 60_000);

    await page.goto('/');
    await page.locator(ids.productName).fill('Live E2E Widget');
    await page.locator(ids.keyFeatures).fill('durable, lightweight, quiet');
    await page.locator(ids.affiliateLink).fill('https://amzn.to/live-e2e');

    // Prefer a single hook if multi-selected — curiosity is default
    await page.getByRole('button', { name: buttons.generate }).click();

    // Progress or immediate blocker toast
    const toast = page.locator('.toast');
    await Promise.race([
      page.getByRole('button', { name: buttons.cancelJob }).waitFor({ state: 'visible', timeout: 30_000 }),
      toast.waitFor({ state: 'visible', timeout: 30_000 }),
    ]).catch(() => undefined);

    if (await toast.isVisible()) {
      const msg = await toast.textContent();
      if (/preflight|blocker|Enable voiceover/i.test(msg || '')) {
        throw new Error(`Live generate blocked before start: ${msg}`);
      }
    }

    await expect(page.getByRole('button', { name: buttons.cancelJob })).toBeVisible({
      timeout: 60_000,
    });

    // Wait for terminal UI
    await expect
      .poll(
        async () => {
          if (await page.getByText(/Generation Complete/i).isVisible().catch(() => false)) {
            return 'complete';
          }
          if (await page.getByText(/Generation Stopped/i).isVisible().catch(() => false)) {
            return 'error';
          }
          return 'running';
        },
        { timeout: 14 * 60_000, intervals: [5_000, 10_000, 15_000] },
      )
      .not.toBe('running');

    const stopped = await page.getByText(/Generation Stopped/i).isVisible().catch(() => false);
    if (stopped) {
      const step = await page.locator('text=Current step:').first().textContent().catch(() => '');
      throw new Error(`Live generate failed. ${step}`);
    }

    await expect(page.getByText(/Generation Complete/i)).toBeVisible();
  });
});
