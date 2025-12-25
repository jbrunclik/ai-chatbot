/**
 * E2E tests for conversation management
 */
import { test, expect } from '../global-setup';

test.describe('Conversations', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');

    // Disable streaming for reliable mock responses
    const streamBtn = page.locator('#stream-btn');
    const isPressed = await streamBtn.getAttribute('aria-pressed');
    if (isPressed === 'true') {
      await streamBtn.click();
    }
  });

  test('creates new conversation on new chat click', async ({ page }) => {
    await page.click('#new-chat-btn');

    // Should show messages area
    const messagesContainer = page.locator('#messages');
    await expect(messagesContainer).toBeVisible();

    // Welcome message should be shown for new conversation
    const welcomeMessage = page.locator('.welcome-message');
    await expect(welcomeMessage).toBeVisible();
  });

  test('conversation appears in sidebar after first message', async ({ page }) => {
    // Start a new conversation
    await page.click('#new-chat-btn');

    // Type and send a message
    await page.fill('#message-input', 'Hello, this is a test message');
    await page.click('#send-btn');

    // Wait for response
    await page.waitForSelector('.message.assistant', { timeout: 10000 });

    // Conversation should appear in sidebar
    const convItem = page.locator('.conversation-item-wrapper');
    await expect(convItem).toBeVisible();
  });

  test('can switch between conversations', async ({ page }) => {
    // Create first conversation
    await page.click('#new-chat-btn');
    await page.fill('#message-input', 'First conversation');
    await page.click('#send-btn');
    await page.waitForSelector('.message.assistant', { timeout: 10000 });

    // Create second conversation
    await page.click('#new-chat-btn');
    await page.fill('#message-input', 'Second conversation');
    await page.click('#send-btn');
    // Wait for the new assistant message (this is a fresh conversation view)
    await page.waitForSelector('.message.assistant', { timeout: 10000 });

    // Should have two conversations in sidebar
    const convItems = page.locator('.conversation-item-wrapper');
    await expect(convItems).toHaveCount(2);

    // Click on first conversation (the older one, which is at the bottom after ordering by updated_at)
    await convItems.last().click();

    // Messages should contain "First conversation"
    const userMessage = page.locator('.message.user');
    await expect(userMessage).toContainText('First conversation');
  });

  test('shows message after sending', async ({ page }) => {
    await page.click('#new-chat-btn');

    const testMessage = 'Test message for E2E';
    await page.fill('#message-input', testMessage);
    await page.click('#send-btn');

    // Human message should appear
    const userMessage = page.locator('.message.user');
    await expect(userMessage).toBeVisible();
    await expect(userMessage).toContainText(testMessage);

    // Assistant message should appear (from mock)
    const assistantMessage = page.locator('.message.assistant');
    await expect(assistantMessage).toBeVisible({ timeout: 10000 });
    await expect(assistantMessage).toContainText('mock response', { ignoreCase: true });
  });

  test('clears input after sending', async ({ page }) => {
    await page.click('#new-chat-btn');

    await page.fill('#message-input', 'Test message');
    await page.click('#send-btn');

    const input = page.locator('#message-input');
    await expect(input).toHaveValue('');
  });

  test('disables send button when input is empty', async ({ page }) => {
    await page.click('#new-chat-btn');

    const sendBtn = page.locator('#send-btn');
    await expect(sendBtn).toBeDisabled();

    await page.fill('#message-input', 'Some text');
    await expect(sendBtn).toBeEnabled();

    await page.fill('#message-input', '');
    await expect(sendBtn).toBeDisabled();
  });

  test('can send with Enter key', async ({ page }) => {
    await page.click('#new-chat-btn');

    await page.fill('#message-input', 'Test with Enter');
    await page.press('#message-input', 'Enter');

    // Message should be sent
    const userMessage = page.locator('.message.user');
    await expect(userMessage).toBeVisible();
    await expect(userMessage).toContainText('Test with Enter');
  });

  test('Shift+Enter creates new line instead of sending', async ({ page }) => {
    await page.click('#new-chat-btn');

    await page.fill('#message-input', 'Line 1');
    await page.press('#message-input', 'Shift+Enter');
    await page.type('#message-input', 'Line 2');

    const input = page.locator('#message-input');
    await expect(input).toHaveValue('Line 1\nLine 2');

    // Message should not be sent yet
    const messages = page.locator('.message');
    await expect(messages).toHaveCount(0);
  });
});

test.describe('Conversation deletion', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');

    // Disable streaming for reliable mock responses
    const streamBtn = page.locator('#stream-btn');
    const isPressed = await streamBtn.getAttribute('aria-pressed');
    if (isPressed === 'true') {
      await streamBtn.click();
    }

    // Create a conversation first
    await page.click('#new-chat-btn');
    await page.fill('#message-input', 'Test conversation');
    await page.click('#send-btn');
    await page.waitForSelector('.message.assistant', { timeout: 10000 });
  });

  test('delete button appears on hover', async ({ page }) => {
    const convItem = page.locator('.conversation-item-wrapper').first();
    const deleteBtn = convItem.locator('.conversation-delete');

    // Initially not visible (opacity: 0)
    await expect(deleteBtn).toHaveCSS('opacity', '0');

    // Hover on the conversation item to reveal delete button
    await convItem.hover();

    // Delete button should now be visible (opacity: 1)
    await expect(deleteBtn).toHaveCSS('opacity', '1');
  });

  test('clicking delete removes conversation', async ({ page }) => {
    // Hover to reveal delete button, then click
    const convItem = page.locator('.conversation-item-wrapper').first();
    await convItem.hover();

    const deleteBtn = convItem.locator('.conversation-delete');
    await deleteBtn.click();

    // Wait for custom modal to appear and click confirm (Delete button)
    const modal = page.locator('.modal-container:not(.modal-hidden)');
    await expect(modal).toBeVisible();
    await modal.locator('.modal-confirm').click();

    // Conversation should be removed
    const convItems = page.locator('.conversation-item-wrapper');
    await expect(convItems).toHaveCount(0);

    // Empty state should show
    const emptyState = page.locator('.conversations-empty');
    await expect(emptyState).toBeVisible();
  });

  test('can cancel deletion', async ({ page }) => {
    // Hover to reveal delete button, then click
    const convItem = page.locator('.conversation-item-wrapper').first();
    await convItem.hover();

    const deleteBtn = convItem.locator('.conversation-delete');
    await deleteBtn.click();

    // Wait for custom modal to appear and click cancel
    const modal = page.locator('.modal-container:not(.modal-hidden)');
    await expect(modal).toBeVisible();
    await modal.locator('.modal-cancel').click();

    // Conversation should still be there
    const convItems = page.locator('.conversation-item-wrapper');
    await expect(convItems).toHaveCount(1);
  });
});
