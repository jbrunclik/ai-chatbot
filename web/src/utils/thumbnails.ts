import { files } from '../api/client';
import { getElementById, scrollToBottom } from './dom';
import { checkScrollButtonVisibility } from '../components/ScrollToBottom';

const MAX_CONCURRENT_FETCHES = 6;
const loadingQueue: Array<() => Promise<void>> = [];
let activeFetches = 0;

// Flag to indicate we should scroll to bottom after images load
// This is set when opening a conversation and cleared when switching away
let shouldScrollOnImageLoad = false;

// Track pending image loads for debounced scroll
let pendingImageLoads = 0;
let scrollTimeout: number | undefined;

/**
 * Enable scroll-to-bottom behavior when images load.
 * Called when opening a conversation.
 */
export function enableScrollOnImageLoad(): void {
  shouldScrollOnImageLoad = true;
  pendingImageLoads = 0;
  if (scrollTimeout) {
    cancelAnimationFrame(scrollTimeout);
    scrollTimeout = undefined;
  }
}

/**
 * Disable scroll-to-bottom behavior.
 * Called when switching conversations or creating new chat.
 */
export function disableScrollOnImageLoad(): void {
  shouldScrollOnImageLoad = false;
  pendingImageLoads = 0;
  if (scrollTimeout) {
    cancelAnimationFrame(scrollTimeout);
    scrollTimeout = undefined;
  }
}

/**
 * Check if scroll-on-image-load is currently enabled.
 * Used to determine if we should delay initial scroll in renderMessages.
 */
export function isScrollOnImageLoadEnabled(): boolean {
  return shouldScrollOnImageLoad;
}

/**
 * Schedule a scroll to bottom after all images have loaded.
 * Uses debouncing to wait for all concurrent image loads to complete.
 */
function scheduleScrollAfterImageLoad(): void {
  if (!shouldScrollOnImageLoad) return;

  // Clear any existing timeout
  if (scrollTimeout) {
    cancelAnimationFrame(scrollTimeout);
  }

  // Wait for a short period after the last image load to ensure all images have rendered
  // This handles the case where multiple images are loading concurrently
  // Use multiple RAFs to ensure layout has fully settled before starting smooth scroll
  scrollTimeout = requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const messagesContainer = getElementById<HTMLDivElement>('messages');
        if (messagesContainer && pendingImageLoads === 0) {
          // Use smooth scroll to avoid abrupt flashing
          scrollToBottom(messagesContainer, true);
          // Update button visibility after scrolling
          requestAnimationFrame(() => {
            checkScrollButtonVisibility();
          });
        }
        scrollTimeout = undefined;
      });
    });
  });
}

/**
 * Process the loading queue with concurrency limit
 */
function processQueue(): void {
  while (activeFetches < MAX_CONCURRENT_FETCHES && loadingQueue.length > 0) {
    const task = loadingQueue.shift();
    if (task) {
      activeFetches++;
      task().finally(() => {
        activeFetches--;
        processQueue();
      });
    }
  }
}

/**
 * Queue a thumbnail load with concurrency limiting
 */
function queueLoad(loadFn: () => Promise<void>): void {
  loadingQueue.push(loadFn);
  processQueue();
}

/**
 * Create an Intersection Observer for lazy loading images
 */
export function createThumbnailObserver(): IntersectionObserver {
  return new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const img = entry.target as HTMLImageElement;
          const messageId = img.dataset.messageId;
          const fileIndex = img.dataset.fileIndex;

          if (messageId && fileIndex) {
            // Track this image load if we're in scroll mode
            if (shouldScrollOnImageLoad) {
              pendingImageLoads++;
            }

            queueLoad(async () => {
              try {
                const blob = await files.fetchThumbnail(
                  messageId,
                  parseInt(fileIndex, 10)
                );
                const url = URL.createObjectURL(blob);
                img.src = url;

                // Wait for the image to actually load and render
                await new Promise<void>((resolve) => {
                  if (img.complete && img.naturalHeight !== 0) {
                    // Image already loaded
                    resolve();
                  } else {
                    img.addEventListener('load', () => resolve(), { once: true });
                    img.addEventListener('error', () => resolve(), { once: true });
                  }
                });

                // Remove loading state from wrapper (if exists) or image
                const wrapper = img.closest('.message-image-wrapper');
                if (wrapper) {
                  wrapper.classList.remove('loading');
                }
                img.classList.remove('loading');
                img.classList.add('loaded');

                // Decrement pending loads and schedule scroll
                if (shouldScrollOnImageLoad) {
                  pendingImageLoads = Math.max(0, pendingImageLoads - 1);
                  scheduleScrollAfterImageLoad();
                }

                // Clean up blob URL when image is removed from DOM
                const cleanup = () => {
                  URL.revokeObjectURL(url);
                };

                // Use MutationObserver to detect removal
                const parent = img.parentElement;
                if (parent) {
                  const mutationObserver = new MutationObserver((mutations) => {
                    for (const mutation of mutations) {
                      if (mutation.removedNodes.length > 0) {
                        for (const node of mutation.removedNodes) {
                          if (node === img || node.contains?.(img)) {
                            cleanup();
                            mutationObserver.disconnect();
                            return;
                          }
                        }
                      }
                    }
                  });
                  mutationObserver.observe(parent, { childList: true, subtree: true });
                }
              } catch (error) {
                console.error('Failed to load thumbnail:', error);
                // Remove loading state from wrapper (if exists) or image
                const wrapper = img.closest('.message-image-wrapper');
                if (wrapper) {
                  wrapper.classList.remove('loading');
                  wrapper.classList.add('error');
                }
                img.classList.remove('loading');
                img.classList.add('error');

                // Decrement pending loads even on error, and schedule scroll
                if (shouldScrollOnImageLoad) {
                  pendingImageLoads = Math.max(0, pendingImageLoads - 1);
                  scheduleScrollAfterImageLoad();
                }
              }
            });
          }

          // Stop observing this image
          thumbnailObserver?.unobserve(img);
        }
      });
    },
    {
      rootMargin: '50px',
      threshold: 0.1,
    }
  );
}

let thumbnailObserver: IntersectionObserver | null = null;

/**
 * Get or create the thumbnail observer
 */
export function getThumbnailObserver(): IntersectionObserver {
  if (!thumbnailObserver) {
    thumbnailObserver = createThumbnailObserver();
  }
  return thumbnailObserver;
}

/**
 * Observe an image element for lazy loading
 */
export function observeThumbnail(img: HTMLImageElement): void {
  getThumbnailObserver().observe(img);
}

/**
 * Clean up blob URLs when images are removed
 */
export function cleanupBlobUrl(url: string): void {
  if (url.startsWith('blob:')) {
    URL.revokeObjectURL(url);
  }
}