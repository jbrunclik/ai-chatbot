/**
 * Global setup that runs before each test file
 */
import { test as base, expect } from '@playwright/test';

/**
 * Extended test with automatic database reset before each test
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    // Reset database before each test for isolation
    const response = await page.request.post('http://localhost:8001/test/reset');
    expect(response.ok()).toBeTruthy();

    await use(page);
  },
});

export { expect } from '@playwright/test';
