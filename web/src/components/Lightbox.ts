import { getElementById } from '../utils/dom';
import { CLOSE_ICON } from '../utils/icons';
import { files } from '../api/client';

let currentBlobUrl: string | null = null;

/**
 * Initialize lightbox event handlers
 */
export function initLightbox(): void {
  const lightbox = getElementById<HTMLDivElement>('lightbox');
  const closeBtn = lightbox?.querySelector('.lightbox-close');

  // Close on button click
  closeBtn?.addEventListener('click', closeLightbox);

  // Close on backdrop click
  lightbox?.addEventListener('click', (e) => {
    if (e.target === lightbox) {
      closeLightbox();
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !lightbox?.classList.contains('hidden')) {
      closeLightbox();
    }
  });

  // Listen for custom lightbox:open events
  window.addEventListener('lightbox:open', ((e: CustomEvent) => {
    const { messageId, fileIndex } = e.detail;
    if (messageId && fileIndex !== undefined) {
      openLightbox(messageId, parseInt(fileIndex, 10));
    }
  }) as EventListener);
}

/**
 * Open lightbox with image from API
 */
export async function openLightbox(
  messageId: string,
  fileIndex: number
): Promise<void> {
  const lightbox = getElementById<HTMLDivElement>('lightbox');
  const img = getElementById<HTMLImageElement>('lightbox-img');

  if (!lightbox || !img) return;

  // Show lightbox with loading state
  lightbox.classList.remove('hidden');
  img.classList.add('loading');
  img.src = '';

  try {
    // Fetch full image
    const blob = await files.fetchFile(messageId, fileIndex);

    // Clean up previous blob URL
    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl);
    }

    currentBlobUrl = URL.createObjectURL(blob);
    img.src = currentBlobUrl;
    img.classList.remove('loading');
  } catch (error) {
    console.error('Failed to load image:', error);
    closeLightbox();
  }
}

/**
 * Close lightbox
 */
export function closeLightbox(): void {
  const lightbox = getElementById<HTMLDivElement>('lightbox');
  const img = getElementById<HTMLImageElement>('lightbox-img');

  if (lightbox) {
    lightbox.classList.add('hidden');
  }

  if (img) {
    img.src = '';
    img.classList.remove('loading');
  }

  // Clean up blob URL
  if (currentBlobUrl) {
    URL.revokeObjectURL(currentBlobUrl);
    currentBlobUrl = null;
  }
}

/**
 * Render lightbox HTML (called once during app init)
 */
export function renderLightbox(): string {
  return `
    <div id="lightbox" class="lightbox hidden">
      <div class="lightbox-container">
        <button class="lightbox-close" aria-label="Close">
          ${CLOSE_ICON}
        </button>
        <img id="lightbox-img" src="" alt="Full size image">
      </div>
    </div>
  `;
}