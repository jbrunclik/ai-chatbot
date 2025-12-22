import type { Source } from '../types/api';
import { getElementById, escapeHtml } from '../utils/dom';
import { CLOSE_ICON, SOURCES_ICON } from '../utils/icons';

/**
 * Initialize sources popup event handlers
 */
export function initSourcesPopup(): void {
  const popup = getElementById<HTMLDivElement>('sources-popup');
  const closeBtn = popup?.querySelector('.sources-popup-close');

  // Close on button click
  closeBtn?.addEventListener('click', closeSourcesPopup);

  // Close on backdrop click
  popup?.addEventListener('click', (e) => {
    if (e.target === popup) {
      closeSourcesPopup();
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !popup?.classList.contains('hidden')) {
      closeSourcesPopup();
    }
  });

  // Listen for custom sources:open events
  window.addEventListener('sources:open', ((e: CustomEvent) => {
    const { sources } = e.detail;
    if (sources && sources.length > 0) {
      openSourcesPopup(sources);
    }
  }) as EventListener);
}

/**
 * Open sources popup with the given sources
 */
export function openSourcesPopup(sources: Source[]): void {
  const popup = getElementById<HTMLDivElement>('sources-popup');
  const content = popup?.querySelector('.sources-popup-content');

  if (!popup || !content) return;

  // Render sources list
  const sourcesHtml = sources
    .map(
      (source, index) => `
      <a href="${escapeHtml(source.url)}"
         target="_blank"
         rel="noopener noreferrer"
         class="source-item">
        <span class="source-number">${index + 1}</span>
        <span class="source-title">${escapeHtml(source.title)}</span>
        <span class="source-url">${escapeHtml(new URL(source.url).hostname)}</span>
      </a>
    `
    )
    .join('');

  content.innerHTML = `
    <div class="sources-popup-header">
      <span class="sources-popup-icon">${SOURCES_ICON}</span>
      <h3>Sources <span class="sources-count">${sources.length}</span></h3>
      <button class="sources-popup-close" aria-label="Close">${CLOSE_ICON}</button>
    </div>
    <div class="sources-list">
      ${sourcesHtml}
    </div>
  `;

  // Re-attach close handler to new button
  content.querySelector('.sources-popup-close')?.addEventListener('click', closeSourcesPopup);

  // Show popup
  popup.classList.remove('hidden');
}

/**
 * Close sources popup
 */
export function closeSourcesPopup(): void {
  const popup = getElementById<HTMLDivElement>('sources-popup');
  if (popup) {
    popup.classList.add('hidden');
  }
}