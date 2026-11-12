import { test as base, expect } from '@playwright/test';
import { installMockedApiRoutes } from './api';

type MockHandles = Awaited<ReturnType<typeof installMockedApiRoutes>>;

type Fixtures = {
  mockApi: MockHandles;
};

/**
 * Mocked project: install Tier-1 stubs before each test.
 * Live project: no stubs (fixture still defined but unused).
 */
export const test = base.extend<Fixtures>({
  mockApi: async ({ page }, use, testInfo) => {
    if (testInfo.project.name === 'mocked') {
      const handles = await installMockedApiRoutes(page);
      await use(handles);
    } else {
      await use({
        wasCancelled: () => false,
        holdRunning: () => undefined,
        resetStatusPolls: () => undefined,
      });
    }
  },
});

export { expect };
