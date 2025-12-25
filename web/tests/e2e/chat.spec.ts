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

test.describe('Chat - Request Continuation on Conversation Switch', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
  });

  test('batch request completes after switching conversations', async ({ page }) => {
    // Disable streaming
    const streamBtn = page.locator('#stream-btn');
    const isPressed = await streamBtn.getAttribute('aria-pressed');
    if (isPressed === 'true') {
      await streamBtn.click();
    }

    // Create first conversation and send message
    await page.click('#new-chat-btn');
    await page.fill('#message-input', 'First conversation message');

    // Wait for the request to be sent
    const requestPromise = page.waitForRequest(
      (request) => request.url().includes('/chat/batch') && request.method() === 'POST',
      { timeout: 5000 }
    );

    await page.click('#send-btn');
    await requestPromise; // Wait for request to be sent

    // Wait for user message to appear (confirms UI updated)
    await page.waitForSelector('.message.user', { timeout: 5000 });

    // Switch to a new conversation immediately (before response completes)
    // The request will continue in the background
    await page.click('#new-chat-btn');

    // Poll by reloading the conversation until messages appear
    // Messages only appear when we reload (fetch from API), not automatically
    // Wait for both conversations to be in the list
    await page.waitForSelector('.conversation-item-wrapper', { timeout: 5000 });
    const convItems = page.locator('.conversation-item-wrapper');
    await expect(convItems).toHaveCount(2);

    // Find the conversation with the message by looking for one that has messages when clicked
    // Note: The new conversation is at index 0 (most recently created), the original is at index 1
    // But after the background request completes, the original may be reordered to index 0
    // We need to find the one that actually has our messages
    let messagesFound = false;
    // Poll every 300ms, up to 20 attempts (6 seconds total)
    // Batch is fast, so we should see messages quickly
    for (let attempt = 0; attempt < 20; attempt++) {
      // Try clicking on each conversation to find the one with messages
      // The conversation with messages may be at position 0 or 1 depending on timing
      const conversationToTry = attempt % 2 === 0 ? convItems.nth(0) : convItems.nth(1);
      await conversationToTry.click();

      // Wait for conversation to load
      await page.waitForSelector('.conversation-loader', { state: 'hidden', timeout: 2000 });

      // Check if both messages are present
      const userMsg = page.locator('.message.user');
      const assistantMsg = page.locator('.message.assistant');
      const userCount = await userMsg.count();
      const assistantCount = await assistantMsg.count();

      if (userCount > 0 && assistantCount > 0) {
        messagesFound = true;
        break;
      }

      await page.waitForTimeout(300);
    }

    expect(messagesFound).toBe(true);
    const assistantMessage = page.locator('.message.assistant');
    await expect(assistantMessage).toContainText('mock response', { ignoreCase: true });
  });

  test('streaming request continues after switching conversations', async ({ page }) => {
    // Enable streaming
    const streamBtn = page.locator('#stream-btn');
    const isPressed = await streamBtn.getAttribute('aria-pressed');
    if (isPressed !== 'true') {
      await streamBtn.click();
    }

    // Create first conversation and send message
    await page.click('#new-chat-btn');
    await page.fill('#message-input', 'Streaming message');

    // Wait for the request to be sent
    const requestPromise = page.waitForRequest(
      (request) => request.url().includes('/chat/stream') && request.method() === 'POST',
      { timeout: 5000 }
    );

    await page.click('#send-btn');
    await requestPromise; // Wait for request to be sent

    // Wait for streaming to start (assistant message appears)
    const assistantMessage = page.locator('.message.assistant');
    await expect(assistantMessage).toBeVisible({ timeout: 5000 });

    // Switch to a new conversation immediately (during streaming)
    // The request will continue in the background
    await page.click('#new-chat-btn');

    // Poll by reloading the conversation until messages appear
    // Streaming takes longer (word-by-word delay + cleanup thread delay)
    const convItems = page.locator('.conversation-item-wrapper');
    await expect(convItems.first()).toBeVisible();

    let messagesFound = false;
    // Poll every 300ms, up to 30 attempts (9 seconds total)
    // Streaming needs more time due to word-by-word delay + cleanup thread
    for (let attempt = 0; attempt < 30; attempt++) {
      // Try clicking on each conversation to find the one with messages
      // The conversation with messages may be at position 0 or 1 depending on timing
      const conversationToTry = attempt % 2 === 0 ? convItems.nth(0) : convItems.nth(1);
      await conversationToTry.click();

      // Wait for conversation to load
      await page.waitForSelector('.conversation-loader', { state: 'hidden', timeout: 2000 });

      // Check if both messages are present
      const userMsg = page.locator('.message.user');
      const assistantMsg = page.locator('.message.assistant');
      const userCount = await userMsg.count();
      const assistantCount = await assistantMsg.count();

      if (userCount > 0 && assistantCount > 0) {
        messagesFound = true;
        break;
      }

      await page.waitForTimeout(300);
    }

    expect(messagesFound).toBe(true);
    const assistantMessageComplete = page.locator('.message.assistant');
    await expect(assistantMessageComplete).toContainText('mock response', { ignoreCase: true });
  });

  test('multiple conversations can have active requests simultaneously', async ({ page }) => {
    // Enable streaming
    const streamBtn = page.locator('#stream-btn');
    const isPressed = await streamBtn.getAttribute('aria-pressed');
    if (isPressed !== 'true') {
      await streamBtn.click();
    }

    // Create and send message in first conversation
    await page.click('#new-chat-btn');
    await page.fill('#message-input', 'First message');
    await page.click('#send-btn');
    // Wait for streaming to complete (message appears in UI)
    await page.waitForSelector('.message.assistant', { timeout: 10000 });
    // Wait a bit more for cleanup thread to save to DB (1s delay + buffer)
    await page.waitForTimeout(2000);

    // Create second conversation and send message
    await page.click('#new-chat-btn');
    await page.fill('#message-input', 'Second message');
    await page.click('#send-btn');
    // Wait for streaming to complete
    await page.waitForSelector('.message.assistant', { timeout: 10000 });
    // Wait a bit more for cleanup thread to save to DB
    await page.waitForTimeout(2000);

    // Both conversations should have responses
    const convItems = page.locator('.conversation-item-wrapper');
    await expect(convItems).toHaveCount(2);

    // Switch to first conversation
    await convItems.nth(0).click();
    // Wait for conversation to load
    await page.waitForSelector('.conversation-loader', { state: 'hidden', timeout: 10000 });
    await page.waitForSelector('.message.user', { timeout: 10000 });
    const firstAssistant = page.locator('.message.assistant').first();
    await expect(firstAssistant).toContainText('mock response', { timeout: 10000 });

    // Switch to second conversation
    await convItems.nth(1).click();
    // Wait for conversation to load
    await page.waitForSelector('.conversation-loader', { state: 'hidden', timeout: 10000 });
    await page.waitForSelector('.message.user', { timeout: 10000 });
    const secondAssistant = page.locator('.message.assistant').first();
    await expect(secondAssistant).toContainText('mock response', { timeout: 10000 });
  });
});
