import { defineConfig, devices } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const root = __dirname;
const venvUvicorn = path.join(root, '.venv', 'bin', 'uvicorn');
const uvicornBin = fs.existsSync(venvUvicorn) ? venvUvicorn : 'python -m uvicorn';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list'], ['html', { open: 'on-failure' }]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'mocked',
      testMatch: /mocked\/.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'live',
      testMatch: /live\/.*\.spec\.ts/,
      timeout: 15 * 60_000,
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `${uvicornBin} app:app --host 127.0.0.1 --port 8000`,
    cwd: path.join(root, 'backend'),
    url: 'http://127.0.0.1:8000/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      ...process.env,
      INTERNAL_SERVICE_SECRET: '',
      HOST: '127.0.0.1',
      PORT: '8000',
    },
  },
});
