import type { Source } from '../types/api';
import { escapeHtml } from '../utils/dom';
import { SOURCES_ICON } from '../utils/icons';
import { createPopup, type PopupInstance } from './InfoPopup';

/**
 * Render sources list HTML
 */
function renderSourcesList(sources: Source[]): string {
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

  return `
    <div class="sources-header-badge">
      <span class="sources-count">${sources.length}</span>
    </div>
    <div class="sources-list">
      ${sourcesHtml}
    </div>
  `;
}

// Create the sources popup instance
const sourcesPopup: PopupInstance<Source[]> = createPopup<Source[]>(
  {
    id: 'sources-popup',
    eventName: 'sources:open',
    icon: SOURCES_ICON,
    title: 'Sources',
    styleClass: 'sources',
  },
  renderSourcesList
);

/**
 * Initialize sources popup event handlers
 */
export function initSourcesPopup(): void {
  sourcesPopup.init();
}

/**
 * Open sources popup with the given sources
 */
export function openSourcesPopup(sources: Source[]): void {
  if (sources && sources.length > 0) {
    sourcesPopup.open(sources);
  }
}

/**
 * Close sources popup
 */
export function closeSourcesPopup(): void {
  sourcesPopup.close();
}