import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: ['e2e/**/*.spec.ts', 'visual/**/*.visual.ts'],
  // E2E tests share a single server with mocked state, so we run tests serially
  // to ensure test isolation. Different projects (chromium/webkit) still run sequentially.
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [['html', { outputFolder: 'playwright-report' }], ['list']],
  use: {
    baseURL: 'http://localhost:8001',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  // Only run on chromium by default - mobile tests use viewport emulation
  // Use --project=webkit to also test Safari rendering
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],

  webServer: {
    command: 'cd .. && .venv/bin/python tests/e2e-server.py',
    url: 'http://localhost:8001',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
