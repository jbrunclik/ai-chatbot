/**
 * Visual regression tests for popup components (info popups, lightbox)
 */
import { test, expect } from '../global-setup';
import type { Page } from '@playwright/test';

/**
 * Helper to dismiss any overlays that might interfere with tests
 */
async function dismissOverlays(page: Page): Promise<void> {
  await page.evaluate(() => {
    const banner = document.querySelector('.version-banner');
    if (banner) {
      (banner as HTMLElement).style.display = 'none';
    }
  });
}

/**
 * SVG icons used in popups
 */
const CLOSE_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
const COST_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`;
const SOURCES_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`;
const SPARKLES_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>`;

test.describe('Visual: Cost Popups', () => {
  test('message cost popup', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject message cost popup directly
    await page.evaluate(({ COST_ICON, CLOSE_ICON }) => {
      const popup = document.createElement('div');
      popup.id = 'message-cost-popup';
      popup.className = 'info-popup';
      popup.innerHTML = `
        <div class="info-popup-content">
          <div class="info-popup-header">
            <span class="info-popup-icon">${COST_ICON}</span>
            <h3>Message Cost</h3>
            <button class="info-popup-close" aria-label="Close">${CLOSE_ICON}</button>
          </div>
          <div class="info-popup-body message-cost-body">
            <div class="message-cost-content">
              <table class="message-cost-table">
                <tbody>
                  <tr>
                    <td class="message-cost-label">Cost:</td>
                    <td class="message-cost-value message-cost-amount">0.42 Kč</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Model:</td>
                    <td class="message-cost-value">gemini-3-flash-preview</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Input tokens:</td>
                    <td class="message-cost-value">1,234</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Output tokens:</td>
                    <td class="message-cost-value">567</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Total tokens:</td>
                    <td class="message-cost-value">1,801</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Cost (USD):</td>
                    <td class="message-cost-value">$0.001234</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById('message-cost-popup');
      if (existing) existing.remove();
      document.body.appendChild(popup);
    }, { COST_ICON, CLOSE_ICON });

    await page.waitForTimeout(300);

    await expect(page.locator('#message-cost-popup')).toHaveScreenshot('popup-message-cost.png');
  });

  test('cost history popup', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject cost history popup directly
    await page.evaluate(({ COST_ICON, CLOSE_ICON }) => {
      const popup = document.createElement('div');
      popup.id = 'cost-history-popup';
      popup.className = 'info-popup';
      popup.innerHTML = `
        <div class="info-popup-content">
          <div class="info-popup-header">
            <span class="info-popup-icon">${COST_ICON}</span>
            <h3>Cost History</h3>
            <button class="info-popup-close" aria-label="Close">${CLOSE_ICON}</button>
          </div>
          <div class="info-popup-body cost-history-body">
            <div class="cost-history-content">
              <table class="cost-history-table">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Cost</th>
                    <th>Messages</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>December 2025</td>
                    <td class="cost-amount">12.50 Kč</td>
                    <td class="cost-messages">42</td>
                  </tr>
                  <tr>
                    <td>November 2025</td>
                    <td class="cost-amount">8.75 Kč</td>
                    <td class="cost-messages">31</td>
                  </tr>
                  <tr>
                    <td>October 2025</td>
                    <td class="cost-amount">15.20 Kč</td>
                    <td class="cost-messages">58</td>
                  </tr>
                </tbody>
                <tfoot>
                  <tr class="cost-history-total">
                    <td><strong>Total</strong></td>
                    <td class="cost-amount"><strong>36.45 Kč</strong></td>
                    <td class="cost-messages"><strong>131</strong></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById('cost-history-popup');
      if (existing) existing.remove();
      document.body.appendChild(popup);
    }, { COST_ICON, CLOSE_ICON });

    await page.waitForTimeout(300);

    await expect(page.locator('#cost-history-popup')).toHaveScreenshot('popup-cost-history.png');
  });

  test('cost history empty state', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject cost history popup with empty state
    await page.evaluate(({ COST_ICON, CLOSE_ICON }) => {
      const popup = document.createElement('div');
      popup.id = 'cost-history-popup';
      popup.className = 'info-popup';
      popup.innerHTML = `
        <div class="info-popup-content">
          <div class="info-popup-header">
            <span class="info-popup-icon">${COST_ICON}</span>
            <h3>Cost History</h3>
            <button class="info-popup-close" aria-label="Close">${CLOSE_ICON}</button>
          </div>
          <div class="info-popup-body cost-history-body">
            <div class="cost-history-empty">
              <p>No cost history available yet.</p>
              <p class="text-muted">Costs will appear here as you use the chatbot.</p>
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById('cost-history-popup');
      if (existing) existing.remove();
      document.body.appendChild(popup);
    }, { COST_ICON, CLOSE_ICON });

    await page.waitForTimeout(300);

    await expect(page.locator('#cost-history-popup')).toHaveScreenshot('popup-cost-history-empty.png');
  });
});

test.describe('Visual: Sources Popup', () => {
  test('sources popup with multiple sources', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject sources popup directly
    await page.evaluate(({ SOURCES_ICON, CLOSE_ICON }) => {
      const popup = document.createElement('div');
      popup.id = 'sources-popup';
      popup.className = 'info-popup';
      popup.innerHTML = `
        <div class="info-popup-content">
          <div class="info-popup-header">
            <span class="info-popup-icon">${SOURCES_ICON}</span>
            <h3>Sources</h3>
            <button class="info-popup-close" aria-label="Close">${CLOSE_ICON}</button>
          </div>
          <div class="info-popup-body sources-body">
            <div class="sources-header-badge">
              <span class="sources-count">3</span>
            </div>
            <div class="sources-list">
              <a href="https://example.com/article1" target="_blank" rel="noopener noreferrer" class="source-item">
                <span class="source-number">1</span>
                <span class="source-title">Understanding TypeScript Generics</span>
                <span class="source-url">example.com</span>
              </a>
              <a href="https://docs.typescript.org/handbook" target="_blank" rel="noopener noreferrer" class="source-item">
                <span class="source-number">2</span>
                <span class="source-title">TypeScript Handbook - Official Documentation</span>
                <span class="source-url">docs.typescript.org</span>
              </a>
              <a href="https://blog.devtools.io/ts-tips" target="_blank" rel="noopener noreferrer" class="source-item">
                <span class="source-number">3</span>
                <span class="source-title">10 TypeScript Tips for Better Code Quality</span>
                <span class="source-url">blog.devtools.io</span>
              </a>
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById('sources-popup');
      if (existing) existing.remove();
      document.body.appendChild(popup);
    }, { SOURCES_ICON, CLOSE_ICON });

    await page.waitForTimeout(300);

    await expect(page.locator('#sources-popup')).toHaveScreenshot('popup-sources.png');
  });
});

test.describe('Visual: Image Generation Popup', () => {
  test('image generation popup', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject image generation popup directly
    await page.evaluate(({ SPARKLES_ICON, CLOSE_ICON }) => {
      const popup = document.createElement('div');
      popup.id = 'imagegen-popup';
      popup.className = 'info-popup';
      popup.innerHTML = `
        <div class="info-popup-content">
          <div class="info-popup-header">
            <span class="info-popup-icon">${SPARKLES_ICON}</span>
            <h3>Image Generation</h3>
            <button class="info-popup-close" aria-label="Close">${CLOSE_ICON}</button>
          </div>
          <div class="info-popup-body imagegen-body">
            <div class="imagegen-list">
              <a href="#" class="imagegen-item" onclick="return false;">
                <span class="imagegen-number">1</span>
                <span class="imagegen-prompt">A serene mountain landscape at sunset with vibrant orange and purple clouds</span>
              </a>
            </div>
            <div class="imagegen-cost">
              <div class="imagegen-label">Image generation cost:</div>
              <div class="imagegen-cost-value">2.50 Kč</div>
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById('imagegen-popup');
      if (existing) existing.remove();
      document.body.appendChild(popup);
    }, { SPARKLES_ICON, CLOSE_ICON });

    await page.waitForTimeout(300);

    await expect(page.locator('#imagegen-popup')).toHaveScreenshot('popup-imagegen.png');
  });

  test('image generation popup with multiple images', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject image generation popup with multiple images
    await page.evaluate(({ SPARKLES_ICON, CLOSE_ICON }) => {
      const popup = document.createElement('div');
      popup.id = 'imagegen-popup';
      popup.className = 'info-popup';
      popup.innerHTML = `
        <div class="info-popup-content">
          <div class="info-popup-header">
            <span class="info-popup-icon">${SPARKLES_ICON}</span>
            <h3>Image Generation</h3>
            <button class="info-popup-close" aria-label="Close">${CLOSE_ICON}</button>
          </div>
          <div class="info-popup-body imagegen-body">
            <div class="imagegen-list">
              <a href="#" class="imagegen-item" onclick="return false;">
                <span class="imagegen-number">1</span>
                <span class="imagegen-prompt">A futuristic cityscape with flying cars and neon lights</span>
              </a>
              <a href="#" class="imagegen-item" onclick="return false;">
                <span class="imagegen-number">2</span>
                <span class="imagegen-prompt">The same city from a different angle showing the main tower</span>
              </a>
            </div>
            <div class="imagegen-cost">
              <div class="imagegen-label">Image generation cost:</div>
              <div class="imagegen-cost-value">5.00 Kč</div>
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById('imagegen-popup');
      if (existing) existing.remove();
      document.body.appendChild(popup);
    }, { SPARKLES_ICON, CLOSE_ICON });

    await page.waitForTimeout(300);

    await expect(page.locator('#imagegen-popup')).toHaveScreenshot('popup-imagegen-multiple.png');
  });
});

test.describe('Visual: Lightbox', () => {
  test('lightbox with image', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject a visible lightbox with a test image
    await page.evaluate(() => {
      const lightbox = document.getElementById('lightbox');
      const img = document.getElementById('lightbox-img') as HTMLImageElement;

      if (lightbox && img) {
        // Use a simple colored rectangle as test image (data URL)
        img.src = 'data:image/svg+xml,' + encodeURIComponent(`
          <svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
            <defs>
              <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#667eea;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#764ba2;stop-opacity:1" />
              </linearGradient>
            </defs>
            <rect width="800" height="600" fill="url(#grad)"/>
            <text x="400" y="300" font-family="Arial, sans-serif" font-size="48" fill="white" text-anchor="middle" dominant-baseline="middle">Test Image</text>
          </svg>
        `);
        lightbox.classList.remove('hidden');
        lightbox.classList.remove('loading');
      }
    });

    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('lightbox-with-image.png', {
      fullPage: true,
    });
  });

  test('lightbox loading state', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Show lightbox in loading state
    await page.evaluate(() => {
      const lightbox = document.getElementById('lightbox');
      const img = document.getElementById('lightbox-img') as HTMLImageElement;

      if (lightbox && img) {
        img.src = '';
        lightbox.classList.remove('hidden');
        lightbox.classList.add('loading');
      }
    });

    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('lightbox-loading.png', {
      fullPage: true,
    });
  });
});

test.describe('Visual: Mobile Popups', () => {
  test.use({ viewport: { width: 375, height: 812 } }); // iPhone X

  test('mobile message cost popup', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject message cost popup directly
    await page.evaluate(({ COST_ICON, CLOSE_ICON }) => {
      const popup = document.createElement('div');
      popup.id = 'message-cost-popup';
      popup.className = 'info-popup';
      popup.innerHTML = `
        <div class="info-popup-content">
          <div class="info-popup-header">
            <span class="info-popup-icon">${COST_ICON}</span>
            <h3>Message Cost</h3>
            <button class="info-popup-close" aria-label="Close">${CLOSE_ICON}</button>
          </div>
          <div class="info-popup-body message-cost-body">
            <div class="message-cost-content">
              <table class="message-cost-table">
                <tbody>
                  <tr>
                    <td class="message-cost-label">Cost:</td>
                    <td class="message-cost-value message-cost-amount">0.42 Kč</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Model:</td>
                    <td class="message-cost-value">gemini-3-flash-preview</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Input tokens:</td>
                    <td class="message-cost-value">1,234</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Output tokens:</td>
                    <td class="message-cost-value">567</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Total tokens:</td>
                    <td class="message-cost-value">1,801</td>
                  </tr>
                  <tr>
                    <td class="message-cost-label">Cost (USD):</td>
                    <td class="message-cost-value">$0.001234</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById('message-cost-popup');
      if (existing) existing.remove();
      document.body.appendChild(popup);
    }, { COST_ICON, CLOSE_ICON });

    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('mobile-popup-message-cost.png');
  });

  test('mobile sources popup', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject sources popup directly
    await page.evaluate(({ SOURCES_ICON, CLOSE_ICON }) => {
      const popup = document.createElement('div');
      popup.id = 'sources-popup';
      popup.className = 'info-popup';
      popup.innerHTML = `
        <div class="info-popup-content">
          <div class="info-popup-header">
            <span class="info-popup-icon">${SOURCES_ICON}</span>
            <h3>Sources</h3>
            <button class="info-popup-close" aria-label="Close">${CLOSE_ICON}</button>
          </div>
          <div class="info-popup-body sources-body">
            <div class="sources-header-badge">
              <span class="sources-count">2</span>
            </div>
            <div class="sources-list">
              <a href="https://example.com/article" target="_blank" rel="noopener noreferrer" class="source-item">
                <span class="source-number">1</span>
                <span class="source-title">Getting Started with TypeScript</span>
                <span class="source-url">example.com</span>
              </a>
              <a href="https://docs.example.org" target="_blank" rel="noopener noreferrer" class="source-item">
                <span class="source-number">2</span>
                <span class="source-title">Official Documentation</span>
                <span class="source-url">docs.example.org</span>
              </a>
            </div>
          </div>
        </div>
      `;
      const existing = document.getElementById('sources-popup');
      if (existing) existing.remove();
      document.body.appendChild(popup);
    }, { SOURCES_ICON, CLOSE_ICON });

    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('mobile-popup-sources.png');
  });

  test('mobile lightbox with image', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#new-chat-btn');
    await dismissOverlays(page);

    // Inject a visible lightbox with a test image
    await page.evaluate(() => {
      const lightbox = document.getElementById('lightbox');
      const img = document.getElementById('lightbox-img') as HTMLImageElement;

      if (lightbox && img) {
        // Use a simple colored rectangle as test image (data URL)
        img.src = 'data:image/svg+xml,' + encodeURIComponent(`
          <svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">
            <defs>
              <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#f093fb;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#f5576c;stop-opacity:1" />
              </linearGradient>
            </defs>
            <rect width="400" height="300" fill="url(#grad)"/>
            <text x="200" y="150" font-family="Arial, sans-serif" font-size="32" fill="white" text-anchor="middle" dominant-baseline="middle">Mobile Image</text>
          </svg>
        `);
        lightbox.classList.remove('hidden');
        lightbox.classList.remove('loading');
      }
    });

    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('mobile-lightbox.png', {
      fullPage: true,
    });
  });
});
