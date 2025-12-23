import type { GeneratedImage } from '../types/api';
import { escapeHtml } from '../utils/dom';
import { SPARKLES_ICON } from '../utils/icons';
import { createPopup, type PopupInstance } from './InfoPopup';

/**
 * Render generated images info HTML
 */
function renderImageGenInfo(images: GeneratedImage[]): string {
  const imagesHtml = images
    .map(
      (img, index) => `
      <div class="imagegen-item">
        <div class="imagegen-number">${index + 1}</div>
        <div class="imagegen-details">
          <div class="imagegen-label">Prompt used:</div>
          <div class="imagegen-prompt">${escapeHtml(img.prompt)}</div>
        </div>
      </div>
    `
    )
    .join('');

  return `
    <div class="imagegen-header-badge">
      <span class="imagegen-count">${images.length}</span>
    </div>
    <div class="imagegen-list">
      ${imagesHtml}
    </div>
  `;
}

// Create the image generation popup instance
const imageGenPopup: PopupInstance<GeneratedImage[]> = createPopup<GeneratedImage[]>(
  {
    id: 'imagegen-popup',
    eventName: 'imagegen:open',
    icon: SPARKLES_ICON,
    title: 'Image Generation',
    styleClass: 'imagegen',
  },
  renderImageGenInfo
);

/**
 * Initialize image generation popup event handlers
 */
export function initImageGenPopup(): void {
  imageGenPopup.init();
}

/**
 * Open image generation popup with the given images
 */
export function openImageGenPopup(images: GeneratedImage[]): void {
  if (images && images.length > 0) {
    imageGenPopup.open(images);
  }
}

/**
 * Close image generation popup
 */
export function closeImageGenPopup(): void {
  imageGenPopup.close();
}