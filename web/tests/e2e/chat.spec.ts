/**
 * E2E tests for chat functionality
 */
import { test, expect } from '../global-setup';

test.describe('Chat - Batch Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');

    // Disable streaming for batch tests
    const streamBtn = page.locator('#stream-btn');
    const isPressed = await streamBtn.getAttribute('aria-pressed');
    if (isPressed === 'true') {
      await streamBtn.click();
    }
  });

  test('sends message and receives batch response', async ({ page }) => {
    await page.fill('#message-input', 'What is 2+2?');
    await page.click('#send-btn');

    // Wait for response (loading indicator may appear briefly but mock is fast)
    const assistantMessage = page.locator('.message.assistant');
    await expect(assistantMessage).toBeVisible({ timeout: 10000 });

    // Response should contain mock text
    await expect(assistantMessage).toContainText('mock response', { ignoreCase: true });
  });

  test('shows both user and assistant messages', async ({ page }) => {
    await page.fill('#message-input', 'Hello!');
    await page.click('#send-btn');

    await page.waitForSelector('.message.assistant', { timeout: 10000 });

    const userMessage = page.locator('.message.user');
    const assistantMessage = page.locator('.message.assistant');

    await expect(userMessage).toBeVisible();
    await expect(assistantMessage).toBeVisible();
    await expect(userMessage).toContainText('Hello!');
  });
});

test.describe('Chat - Streaming Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');

    // Enable streaming
    const streamBtn = page.locator('#stream-btn');
    const isPressed = await streamBtn.getAttribute('aria-pressed');
    if (isPressed !== 'true') {
      await streamBtn.click();
    }
  });

  test('streaming button toggles state', async ({ page }) => {
    const streamBtn = page.locator('#stream-btn');

    // Should be enabled (pressed)
    await expect(streamBtn).toHaveAttribute('aria-pressed', 'true');

    // Toggle off
    await streamBtn.click();
    await expect(streamBtn).toHaveAttribute('aria-pressed', 'false');

    // Toggle on
    await streamBtn.click();
    await expect(streamBtn).toHaveAttribute('aria-pressed', 'true');
  });

  test('streams response tokens progressively via SSE', async ({ page }) => {
    await page.fill('#message-input', 'Hello streaming');
    await page.click('#send-btn');

    // Wait for assistant message to appear (streaming creates element immediately)
    const assistantMessage = page.locator('.message.assistant');
    await expect(assistantMessage).toBeVisible({ timeout: 10000 });

    // Wait for streaming to complete - content should contain mock response
    // The mock streams "This is a mock response to: Hello streaming" word by word
    await expect(assistantMessage).toContainText('mock response', { timeout: 10000 });
    await expect(assistantMessage).toContainText('Hello streaming', { timeout: 10000 });
  });

  test('shows both user and assistant messages after streaming', async ({ page }) => {
    await page.fill('#message-input', 'Stream test');
    await page.click('#send-btn');

    // Wait for streaming to complete
    const assistantMessage = page.locator('.message.assistant');
    await expect(assistantMessage).toContainText('mock response', { timeout: 10000 });

    // Both messages should be visible
    const userMessage = page.locator('.message.user');
    await expect(userMessage).toBeVisible();
    await expect(userMessage).toContainText('Stream test');
    await expect(assistantMessage).toBeVisible();
  });
});

test.describe('Chat - Model Selection', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');
  });

  test('model selector button is visible', async ({ page }) => {
    const modelSelectorBtn = page.locator('#model-selector-btn');
    await expect(modelSelectorBtn).toBeVisible();
  });

  test('can open model dropdown', async ({ page }) => {
    const modelSelectorBtn = page.locator('#model-selector-btn');
    const modelDropdown = page.locator('#model-dropdown');

    // Dropdown should be hidden initially
    await expect(modelDropdown).toHaveClass(/hidden/);

    // Click to open dropdown
    await modelSelectorBtn.click();

    // Dropdown should be visible
    await expect(modelDropdown).not.toHaveClass(/hidden/);

    // Should show model options
    const modelOptions = modelDropdown.locator('.model-option');
    await expect(modelOptions.first()).toBeVisible();
  });
});

test.describe('Chat - Force Tools', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');
  });

  test('search button is visible', async ({ page }) => {
    const searchBtn = page.locator('#search-btn');
    await expect(searchBtn).toBeVisible();
  });

  test('search button toggles active state', async ({ page }) => {
    const searchBtn = page.locator('#search-btn');

    // Initially not active
    await expect(searchBtn).not.toHaveClass(/active/);

    // Click to activate
    await searchBtn.click();
    await expect(searchBtn).toHaveClass(/active/);

    // Click to deactivate
    await searchBtn.click();
    await expect(searchBtn).not.toHaveClass(/active/);
  });

  test('search button deactivates after sending message', async ({ page }) => {
    const searchBtn = page.locator('#search-btn');

    // Activate search
    await searchBtn.click();
    await expect(searchBtn).toHaveClass(/active/);

    // Send message
    await page.fill('#message-input', 'Search for something');
    await page.click('#send-btn');

    // Wait for response
    await page.waitForSelector('.message.assistant', { timeout: 10000 });

    // Search button should be deactivated (one-shot)
    await expect(searchBtn).not.toHaveClass(/active/);
  });
});

test.describe('Chat - Message Actions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');

    // Send a message first
    await page.fill('#message-input', 'Test message');
    await page.click('#send-btn');
    await page.waitForSelector('.message.assistant', { timeout: 10000 });
  });

  test('copy button is visible on messages', async ({ page }) => {
    const copyBtn = page.locator('.message-copy-btn').first();
    await expect(copyBtn).toBeVisible();
  });

  test('messages have proper structure', async ({ page }) => {
    // User message
    const userMessage = page.locator('.message.user');
    await expect(userMessage).toBeVisible();
    await expect(userMessage.locator('.message-content')).toBeVisible();

    // Assistant message
    const assistantMessage = page.locator('.message.assistant');
    await expect(assistantMessage).toBeVisible();
    await expect(assistantMessage.locator('.message-content')).toBeVisible();
  });
});
