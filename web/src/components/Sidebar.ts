import { escapeHtml, getElementById } from '../utils/dom';
import { renderUserAvatarHtml } from '../utils/avatar';
import { DELETE_ICON, LOGOUT_ICON } from '../utils/icons';
import { useStore } from '../state/store';
import type { Conversation } from '../types/api';

/**
 * Render the conversations list in the sidebar
 */
export function renderConversationsList(): void {
  const container = getElementById<HTMLDivElement>('conversations-list');
  if (!container) return;

  const { conversations, currentConversation, isLoading } = useStore.getState();

  if (isLoading && conversations.length === 0) {
    container.innerHTML = `
      <div class="conversations-loading">
        <div class="loading-spinner"></div>
      </div>
    `;
    return;
  }

  if (conversations.length === 0) {
    container.innerHTML = `
      <div class="conversations-empty">
        <p>No conversations yet</p>
        <p class="text-muted">Start a new chat to begin</p>
      </div>
    `;
    return;
  }

  container.innerHTML = conversations
    .map((conv) => renderConversationItem(conv, conv.id === currentConversation?.id))
    .join('');
}

/**
 * Render a single conversation item
 */
function renderConversationItem(conv: Conversation, isActive: boolean): string {
  const title = escapeHtml(conv.title || 'New Conversation');

  return `
    <div class="conversation-item-wrapper ${isActive ? 'active' : ''}" data-conv-id="${conv.id}">
      <div class="conversation-item">
        <div class="conversation-title">${title}</div>
        <button class="conversation-delete" data-delete-id="${conv.id}" aria-label="Delete">
          ${DELETE_ICON}
        </button>
      </div>
      <button class="conversation-delete-swipe" data-delete-id="${conv.id}" aria-label="Delete">
        ${DELETE_ICON}
      </button>
    </div>
  `;
}

/**
 * Render user info in sidebar footer
 */
export function renderUserInfo(): void {
  const container = getElementById<HTMLDivElement>('user-info');
  if (!container) return;

  const { user } = useStore.getState();

  if (!user) {
    container.innerHTML = '';
    return;
  }

  const name = user.name || user.email;
  const avatarHtml = renderUserAvatarHtml(user.picture || undefined, name);

  container.innerHTML = `
    <div class="user-profile">
      ${avatarHtml}
      <span class="user-name">${escapeHtml(name)}</span>
    </div>
    <button id="logout-btn" class="btn-logout" title="Logout">
      ${LOGOUT_ICON}
    </button>
  `;
}

/**
 * Update conversation title in sidebar
 */
export function updateConversationTitle(convId: string, title: string): void {
  const wrapper = document.querySelector<HTMLDivElement>(
    `.conversation-item-wrapper[data-conv-id="${convId}"]`
  );
  if (wrapper) {
    const titleEl = wrapper.querySelector<HTMLDivElement>('.conversation-title');
    if (titleEl) {
      titleEl.textContent = title;
    }
  }
}

/**
 * Set active conversation in sidebar
 */
export function setActiveConversation(convId: string | null): void {
  // Remove active from all
  document
    .querySelectorAll<HTMLDivElement>('.conversation-item-wrapper.active')
    .forEach((el) => el.classList.remove('active'));

  // Add active to current
  if (convId) {
    const wrapper = document.querySelector<HTMLDivElement>(
      `.conversation-item-wrapper[data-conv-id="${convId}"]`
    );
    wrapper?.classList.add('active');
  }
}

/**
 * Toggle sidebar visibility (mobile)
 */
export function toggleSidebar(): void {
  useStore.getState().toggleSidebar();
  updateSidebarVisibility();
}

/**
 * Close sidebar (mobile)
 */
export function closeSidebar(): void {
  useStore.getState().closeSidebar();
  updateSidebarVisibility();
}

/**
 * Update sidebar visibility based on state
 */
function updateSidebarVisibility(): void {
  const sidebar = getElementById<HTMLElement>('sidebar');
  const app = getElementById<HTMLDivElement>('app');
  if (!sidebar || !app) return;

  const { isSidebarOpen } = useStore.getState();

  if (isSidebarOpen) {
    sidebar.classList.add('open');
    // Create overlay for mobile
    let overlay = app.querySelector<HTMLDivElement>('.sidebar-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'sidebar-overlay';
      overlay.addEventListener('click', closeSidebar);
      app.appendChild(overlay);
    }
    overlay.classList.add('visible');
  } else {
    sidebar.classList.remove('open');
    const overlay = app.querySelector<HTMLDivElement>('.sidebar-overlay');
    overlay?.classList.remove('visible');
  }
}