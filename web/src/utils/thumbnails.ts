import { files } from '../api/client';

const MAX_CONCURRENT_FETCHES = 6;
const loadingQueue: Array<() => Promise<void>> = [];
let activeFetches = 0;

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
            queueLoad(async () => {
              try {
                const blob = await files.fetchThumbnail(
                  messageId,
                  parseInt(fileIndex, 10)
                );
                const url = URL.createObjectURL(blob);
                img.src = url;
                // Remove loading state from wrapper (if exists) or image
                const wrapper = img.closest('.message-image-wrapper');
                if (wrapper) {
                  wrapper.classList.remove('loading');
                }
                img.classList.remove('loading');
                img.classList.add('loaded');

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