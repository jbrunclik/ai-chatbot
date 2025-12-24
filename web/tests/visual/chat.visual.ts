/**
 * Visual regression tests for chat interface
 */
import { test, expect } from '../global-setup';

test.describe('Visual: Chat Interface', () => {
  test('empty conversation state', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');

    // Wait for welcome message to appear
    await page.waitForSelector('.welcome-message');

    // Wait for any animations to complete
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('empty-conversation.png', {
      fullPage: true,
    });
  });

  test('conversation with messages', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');

    // Send a message
    await page.fill('#message-input', 'Hello, this is a test message!');
    await page.click('#send-btn');

    // Wait for response
    await page.waitForSelector('.message.assistant', { timeout: 10000 });

    // Wait for animations
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('conversation-with-messages.png', {
      fullPage: true,
    });
  });

  test('sidebar with conversations', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');

    // Create multiple conversations
    for (let i = 0; i < 3; i++) {
      await page.click('#new-chat-btn');
      await page.fill('#message-input', `Test message ${i + 1}`);
      await page.click('#send-btn');
      await page.waitForSelector('.message.assistant', { timeout: 10000 });
    }

    // Wait for animations
    await page.waitForTimeout(500);

    await expect(page.locator('#sidebar')).toHaveScreenshot('sidebar-conversations.png');
  });

  test('message input focused', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');

    // Focus on input
    await page.focus('#message-input');

    // Type some text
    await page.fill('#message-input', 'Typing a message...');

    await expect(page.locator('.input-container')).toHaveScreenshot('input-focused.png');
  });

  test('model selector dropdown', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');

    // Open model selector dropdown
    const modelSelectorBtn = page.locator('#model-selector-btn');
    await modelSelectorBtn.click();

    // Wait for dropdown to be visible
    await expect(page.locator('#model-dropdown')).not.toHaveClass(/hidden/);

    await expect(page.locator('.input-toolbar')).toHaveScreenshot('model-selector.png');
  });
});

test.describe('Visual: Chat States', () => {
  // Note: Loading state test removed as it's inherently flaky - the mock responds too quickly
  // to reliably capture the loading state. Would require artificially slowing down the mock.

  test('stream button active', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');

    // Ensure streaming is enabled
    const streamBtn = page.locator('#stream-btn');
    const isPressed = await streamBtn.getAttribute('aria-pressed');
    if (isPressed !== 'true') {
      await streamBtn.click();
    }

    await expect(streamBtn).toHaveScreenshot('stream-btn-active.png');
  });

  test('search button active', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await page.click('#new-chat-btn');

    // Activate search
    const searchBtn = page.locator('#search-btn');
    await searchBtn.click();

    await expect(searchBtn).toHaveScreenshot('search-btn-active.png');
  });
});
