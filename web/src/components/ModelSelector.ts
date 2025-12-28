import { escapeHtml, getElementById } from '../utils/dom';
import { useStore } from '../state/store';
import { conversations as conversationsApi } from '../api/client';
import { toast } from './Toast';
import { createLogger } from '../utils/logger';

const log = createLogger('model-selector');

/**
 * Initialize model selector event handlers
 */
export function initModelSelector(): void {
  const btn = getElementById<HTMLButtonElement>('model-selector-btn');
  const dropdown = getElementById<HTMLDivElement>('model-dropdown');

  if (!btn || !dropdown) return;

  // Toggle dropdown
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleModelDropdown();
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (
      !dropdown.contains(e.target as Node) &&
      !btn.contains(e.target as Node)
    ) {
      closeModelDropdown();
    }
  });

  // Handle model selection (event delegation)
  dropdown.addEventListener('click', (e) => {
    const option = (e.target as HTMLElement).closest('[data-model-id]');
    if (option) {
      const modelId = (option as HTMLElement).dataset.modelId;
      if (modelId) {
        selectModel(modelId);
      }
    }
  });
}

/**
 * Toggle model dropdown visibility
 */
function toggleModelDropdown(): void {
  const dropdown = getElementById<HTMLDivElement>('model-dropdown');
  dropdown?.classList.toggle('hidden');
}

/**
 * Close model dropdown
 */
function closeModelDropdown(): void {
  const dropdown = getElementById<HTMLDivElement>('model-dropdown');
  dropdown?.classList.add('hidden');
}

/**
 * Check if a conversation ID is temporary (not yet saved to DB)
 */
function isTempConversation(convId: string): boolean {
  return convId.startsWith('temp-');
}

/**
 * Select a model
 */
async function selectModel(modelId: string): Promise<void> {
  const store = useStore.getState();
  const { currentConversation, models } = store;

  // Get the model to display
  const model = models.find((m) => m.id === modelId);
  if (!model) return;

  // Get previous model for rollback
  const previousModelId = currentConversation?.model || store.defaultModel;
  const previousModel = models.find((m) => m.id === previousModelId);

  // Update UI immediately (optimistic update)
  updateCurrentModelDisplay(model.name);
  closeModelDropdown();

  // Update conversation on server if one is selected
  if (currentConversation) {
    // For temp conversations (not yet persisted), just update locally
    // The model will be used when the conversation is created on first message
    if (isTempConversation(currentConversation.id)) {
      store.updateConversation(currentConversation.id, { model: modelId });
      log.debug('Updated model for temp conversation', { modelId, conversationId: currentConversation.id });
      return;
    }

    // For persisted conversations, update on server
    try {
      await conversationsApi.update(currentConversation.id, { model: modelId });
      store.updateConversation(currentConversation.id, { model: modelId });
    } catch (error) {
      log.error('Failed to update model', { error, modelId, conversationId: currentConversation.id });
      // Revert optimistic update on failure
      if (previousModel) {
        updateCurrentModelDisplay(previousModel.name);
      }
      toast.error('Failed to change model. Please try again.');
    }
  }
}

/**
 * Update current model display text
 */
function updateCurrentModelDisplay(name: string): void {
  const display = getElementById<HTMLSpanElement>('current-model-name');
  if (display) {
    display.textContent = name;
  }
}

/**
 * Render model dropdown options
 */
export function renderModelDropdown(): void {
  const dropdown = getElementById<HTMLDivElement>('model-dropdown');
  if (!dropdown) return;

  const { models, currentConversation, defaultModel } = useStore.getState();
  const currentModelId = currentConversation?.model || defaultModel;

  dropdown.innerHTML = models
    .map(
      (model) => `
      <div class="model-option ${model.id === currentModelId ? 'selected' : ''}"
           data-model-id="${model.id}">
        <span class="model-name">${escapeHtml(model.name)}</span>
        ${model.id === currentModelId ? '<span class="model-check">✓</span>' : ''}
      </div>
    `
    )
    .join('');

  // Update current model display
  const currentModel = models.find((m) => m.id === currentModelId);
  if (currentModel) {
    updateCurrentModelDisplay(currentModel.name);
  }
}