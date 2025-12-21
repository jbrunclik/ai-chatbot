import { escapeHtml, getElementById, scrollToBottom, isScrolledToBottom } from '../utils/dom';
import { renderMarkdown, highlightAllCodeBlocks } from '../utils/markdown';
import { observeThumbnail } from '../utils/thumbnails';
import { createUserAvatarElement } from '../utils/avatar';
import { AI_AVATAR_SVG, getFileIcon, DOWNLOAD_ICON } from '../utils/icons';
import { useStore } from '../state/store';
import type { Message, FileMetadata } from '../types/api';

/**
 * Render all messages in the container
 */
export function renderMessages(messages: Message[]): void {
  const container = getElementById<HTMLDivElement>('messages');
  if (!container) return;

  if (messages.length === 0) {
    container.innerHTML = `
      <div class="welcome-message">
        <h2>Welcome to AI Chatbot</h2>
        <p>Start a conversation with Gemini AI</p>
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  messages.forEach((msg) => {
    addMessageToUI(msg, container);
  });

  scrollToBottom(container);
}

/**
 * Add a single message to the UI
 */
export function addMessageToUI(
  message: Message,
  container: HTMLElement = getElementById('messages')!
): void {
  const messageEl = document.createElement('div');
  messageEl.className = `message ${message.role}`;
  messageEl.dataset.messageId = message.id;

  // Avatar
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  if (message.role === 'assistant') {
    avatar.innerHTML = AI_AVATAR_SVG;
  } else {
    // User avatar - show picture or initials
    const user = useStore.getState().user;
    const name = user?.name || user?.email || 'User';
    const avatarContent = createUserAvatarElement(user?.picture || undefined, name, '');
    // For message avatars, we add content to the existing div instead of replacing it
    if (avatarContent instanceof HTMLImageElement) {
      avatar.appendChild(avatarContent);
    } else {
      avatar.textContent = avatarContent.textContent;
    }
  }
  messageEl.appendChild(avatar);

  // Content wrapper
  const contentWrapper = document.createElement('div');
  contentWrapper.className = 'message-content-wrapper';

  // Render text content
  const content = document.createElement('div');
  content.className = 'message-content';

  if (message.role === 'assistant') {
    // Assistant: files outside bubble, then text
    if (message.files && message.files.length > 0) {
      const filesContainer = renderMessageFiles(message.files, message.id);
      contentWrapper.appendChild(filesContainer);
    }
    content.innerHTML = renderMarkdown(message.content);
    highlightAllCodeBlocks(content);
    contentWrapper.appendChild(content);
  } else {
    // User: text first, then files inside the bubble
    if (message.content) {
      content.innerHTML = `<p>${escapeHtml(message.content).replace(/\n/g, '<br>')}</p>`;
    }
    if (message.files && message.files.length > 0) {
      const filesContainer = renderMessageFiles(message.files, message.id);
      content.appendChild(filesContainer);
    }
    contentWrapper.appendChild(content);
  }

  messageEl.appendChild(contentWrapper);
  container.appendChild(messageEl);
}

/**
 * Render files attached to a message
 */
function renderMessageFiles(files: FileMetadata[], messageId: string): HTMLElement {
  const container = document.createElement('div');
  container.className = 'message-files';

  // Separate images from other files
  const images = files.filter((f) => f.type.startsWith('image/'));
  const documents = files.filter((f) => !f.type.startsWith('image/'));

  // Render images in horizontal gallery
  if (images.length > 0) {
    const gallery = document.createElement('div');
    gallery.className = 'message-images';

    images.forEach((file) => {
      const fileIndex = files.indexOf(file);
      const imgWrapper = document.createElement('div');
      imgWrapper.className = 'message-image-wrapper';

      const img = document.createElement('img');
      img.className = 'message-image';
      img.alt = file.name;
      img.dataset.messageId = file.messageId || messageId;
      img.dataset.fileIndex = String(file.fileIndex ?? fileIndex);

      // If we have a local preview URL (just-uploaded file), use it directly
      // Otherwise, use lazy loading to fetch thumbnail from server
      if (file.previewUrl) {
        img.src = file.previewUrl;
      } else {
        // Add loading state for server-fetched images
        imgWrapper.classList.add('loading');

        // Add placeholder with filename
        const placeholder = document.createElement('span');
        placeholder.className = 'image-placeholder';
        placeholder.textContent = file.name;
        imgWrapper.appendChild(placeholder);

        img.loading = 'lazy';

        // Set up lazy loading - remove loading class from wrapper when loaded
        img.addEventListener('load', () => {
          imgWrapper.classList.remove('loading');
        });
        observeThumbnail(img);
      }

      // Click to open lightbox
      img.addEventListener('click', () => {
        window.dispatchEvent(
          new CustomEvent('lightbox:open', {
            detail: {
              messageId: img.dataset.messageId,
              fileIndex: img.dataset.fileIndex,
            },
          })
        );
      });

      imgWrapper.appendChild(img);
      gallery.appendChild(imgWrapper);
    });

    container.appendChild(gallery);
  }

  // Render documents as list
  if (documents.length > 0) {
    const list = document.createElement('div');
    list.className = 'message-documents';

    documents.forEach((file) => {
      const fileIndex = files.indexOf(file);
      const doc = document.createElement('div');
      doc.className = 'message-document';
      doc.innerHTML = `
        <span class="document-icon">${getFileIcon(file.type)}</span>
        <span class="document-name">${escapeHtml(file.name)}</span>
        <button class="document-download"
                data-message-id="${file.messageId || messageId}"
                data-file-index="${file.fileIndex ?? fileIndex}"
                title="Download">
          ${DOWNLOAD_ICON}
        </button>
      `;
      list.appendChild(doc);
    });

    container.appendChild(list);
  }

  return container;
}

/**
 * Add a streaming message placeholder
 */
export function addStreamingMessage(): HTMLElement {
  const container = getElementById<HTMLDivElement>('messages');
  if (!container) throw new Error('Messages container not found');

  const messageEl = document.createElement('div');
  messageEl.className = 'message assistant streaming';
  messageEl.innerHTML = `
    <div class="message-avatar">${AI_AVATAR_SVG}</div>
    <div class="message-content-wrapper">
      <div class="message-content">
        <span class="streaming-cursor"></span>
      </div>
    </div>
  `;

  container.appendChild(messageEl);
  scrollToBottom(container);

  return messageEl;
}

/**
 * Update streaming message content
 */
export function updateStreamingMessage(
  messageEl: HTMLElement,
  content: string
): void {
  const contentEl = messageEl.querySelector('.message-content');
  if (!contentEl) return;

  const wasAtBottom = isScrolledToBottom(
    getElementById('messages')!
  );

  // Render markdown for the accumulated content
  contentEl.innerHTML = renderMarkdown(content) + '<span class="streaming-cursor"></span>';

  if (wasAtBottom) {
    scrollToBottom(getElementById('messages')!);
  }
}

/**
 * Finalize streaming message
 */
export function finalizeStreamingMessage(
  messageEl: HTMLElement,
  messageId: string
): void {
  messageEl.classList.remove('streaming');
  messageEl.dataset.messageId = messageId;

  // Remove cursor
  const cursor = messageEl.querySelector('.streaming-cursor');
  cursor?.remove();

  // Apply syntax highlighting to code blocks
  const content = messageEl.querySelector('.message-content');
  if (content) {
    highlightAllCodeBlocks(content as HTMLElement);
  }
}

/**
 * Show loading indicator in messages
 */
export function showLoadingIndicator(): void {
  const container = getElementById<HTMLDivElement>('messages');
  if (!container) return;

  // Remove existing loading indicator
  hideLoadingIndicator();

  const loading = document.createElement('div');
  loading.className = 'message-loading';
  loading.innerHTML = `
    <div class="loading-dots">
      <span></span>
      <span></span>
      <span></span>
    </div>
  `;
  container.appendChild(loading);
  scrollToBottom(container);
}

/**
 * Hide loading indicator
 */
export function hideLoadingIndicator(): void {
  const loading = document.querySelector('.message-loading');
  loading?.remove();
}

/**
 * Show conversation loading overlay
 */
export function showConversationLoader(): void {
  const container = getElementById<HTMLDivElement>('messages');
  if (!container) return;

  // Remove existing loader
  hideConversationLoader();

  const loader = document.createElement('div');
  loader.className = 'conversation-loader';
  loader.innerHTML = `
    <div class="conversation-loader-content">
      <div class="loading-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
      <p>Loading conversation...</p>
    </div>
  `;
  container.appendChild(loader);
}

/**
 * Hide conversation loading overlay
 */
export function hideConversationLoader(): void {
  const loader = document.querySelector('.conversation-loader');
  loader?.remove();
}

/**
 * Update chat title in mobile header
 */
export function updateChatTitle(title: string): void {
  const titleEl = getElementById<HTMLSpanElement>('current-chat-title');
  if (titleEl) {
    titleEl.textContent = title;
  }
}