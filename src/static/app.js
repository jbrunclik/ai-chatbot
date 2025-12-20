// AI Chatbot Frontend Application

// State
const state = {
    token: localStorage.getItem('token'),
    user: null,
    conversations: [],
    currentConversation: null,
    models: [],
    defaultModel: 'gemini-3-flash-preview',
    isLoading: false,
    googleClientId: null
};

// DOM Elements
const elements = {
    app: document.getElementById('app'),
    sidebar: document.getElementById('sidebar'),
    conversationsList: document.getElementById('conversations-list'),
    messages: document.getElementById('messages'),
    messageInput: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn'),
    newChatBtn: document.getElementById('new-chat-btn'),
    menuBtn: document.getElementById('menu-btn'),
    modelBtn: document.getElementById('model-btn'),
    modelModal: document.getElementById('model-modal'),
    modelOptions: document.getElementById('model-options'),
    closeModalBtn: document.getElementById('close-modal-btn'),
    loginOverlay: document.getElementById('login-overlay'),
    googleLoginBtn: document.getElementById('google-login-btn'),
    userInfo: document.getElementById('user-info'),
    currentChatTitle: document.getElementById('current-chat-title'),
    // New model selector dropdown
    modelSelectorBtn: document.getElementById('model-selector-btn'),
    currentModelName: document.getElementById('current-model-name'),
    modelDropdown: document.getElementById('model-dropdown')
};

// API Functions
async function api(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (state.token) {
        headers['Authorization'] = `Bearer ${state.token}`;
    }

    const response = await fetch(endpoint, {
        ...options,
        headers
    });

    const data = await response.json();

    if (!response.ok) {
        // Don't logout on 401 if we're in local mode (no token needed)
        if (response.status === 401 && state.token) {
            logout();
        }
        throw new Error(data.error || 'API Error');
    }

    return data;
}

// Auth Functions
async function checkAuth() {
    try {
        // Try to call /auth/me - in local mode this works without a token
        const data = await api('/auth/me');
        state.user = data.user;
        hideLoginOverlay();
        renderUserInfo();
        return true;
    } catch (error) {
        // If we have no token and auth failed, show login
        if (!state.token) {
            showLoginOverlay();
        }
        return false;
    }
}

async function initGoogleSignIn() {
    // Fetch client ID from backend
    try {
        const data = await fetch('/auth/client-id').then(r => r.json());
        state.googleClientId = data.client_id;

        if (!state.googleClientId) {
            console.error('Google Client ID not configured');
            return;
        }

        // Initialize Google Identity Services
        google.accounts.id.initialize({
            client_id: state.googleClientId,
            callback: handleGoogleCredential,
            auto_select: false
        });

        // Render the Google Sign In button
        google.accounts.id.renderButton(
            elements.googleLoginBtn,
            {
                theme: 'filled_black',
                size: 'large',
                text: 'signin_with',
                shape: 'rectangular',
                width: 280
            }
        );
    } catch (error) {
        console.error('Failed to initialize Google Sign In:', error);
    }
}

async function handleGoogleCredential(response) {
    try {
        const data = await api('/auth/google', {
            method: 'POST',
            body: JSON.stringify({ credential: response.credential })
        });

        if (data.token) {
            state.token = data.token;
            state.user = data.user;
            localStorage.setItem('token', data.token);
            hideLoginOverlay();
            renderUserInfo();

            // Load data after login
            await Promise.all([
                loadConversations(),
                loadModels()
            ]);
        }
    } catch (error) {
        console.error('Google auth error:', error);
        alert('Authentication failed: ' + error.message);
    }
}

function logout() {
    state.token = null;
    state.user = null;
    localStorage.removeItem('token');
    // Revoke Google session
    if (state.googleClientId) {
        google.accounts.id.disableAutoSelect();
    }
    showLoginOverlay();
}

function showLoginOverlay() {
    elements.loginOverlay.classList.remove('hidden');
    // Re-render the Google button when overlay is shown
    if (state.googleClientId && typeof google !== 'undefined') {
        google.accounts.id.renderButton(
            elements.googleLoginBtn,
            {
                theme: 'filled_black',
                size: 'large',
                text: 'signin_with',
                shape: 'rectangular',
                width: 280
            }
        );
    }
}

function hideLoginOverlay() {
    elements.loginOverlay.classList.add('hidden');
}

// Conversation Functions
async function loadConversations() {
    try {
        const data = await api('/api/conversations');
        state.conversations = data.conversations;
        renderConversationsList();
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

async function createConversation() {
    try {
        const data = await api('/api/conversations', {
            method: 'POST',
            body: JSON.stringify({ model: state.defaultModel })
        });
        state.conversations.unshift(data);
        await selectConversation(data.id);
        renderConversationsList();
        elements.messageInput.focus();
    } catch (error) {
        console.error('Failed to create conversation:', error);
    }
}

async function selectConversation(id) {
    try {
        const data = await api(`/api/conversations/${id}`);
        state.currentConversation = data;
        renderMessages();
        updateTitle(data.title);
        highlightActiveConversation();
        updateCurrentModelDisplay();
        renderModelDropdown();
        closeSidebar();
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

async function deleteConversation(id, event) {
    event.stopPropagation();

    if (!confirm('Delete this conversation?')) return;

    try {
        await api(`/api/conversations/${id}`, { method: 'DELETE' });
        state.conversations = state.conversations.filter(c => c.id !== id);

        if (state.currentConversation?.id === id) {
            state.currentConversation = null;
            renderWelcome();
        }

        renderConversationsList();
    } catch (error) {
        console.error('Failed to delete conversation:', error);
    }
}

// Chat Functions
async function sendMessage() {
    const content = elements.messageInput.value.trim();
    if (!content || state.isLoading) return;

    // Create conversation if none selected
    if (!state.currentConversation) {
        await createConversation();
    }

    // Add user message to UI
    addMessageToUI('user', content);
    elements.messageInput.value = '';
    autoResizeTextarea();
    updateSendButton();

    // Show loading indicator
    state.isLoading = true;
    const loadingEl = addLoadingIndicator();

    try {
        const data = await api(`/api/conversations/${state.currentConversation.id}/chat`, {
            method: 'POST',
            body: JSON.stringify({ message: content })
        });

        // Remove loading indicator
        loadingEl.remove();

        // Add assistant response
        addMessageToUI('assistant', data.content);

        // Update conversation in list (for title update)
        await loadConversations();

    } catch (error) {
        loadingEl.remove();
        addMessageToUI('assistant', 'Sorry, an error occurred. Please try again.');
        console.error('Chat error:', error);
    } finally {
        state.isLoading = false;
    }
}

function addMessageToUI(role, content) {
    // Remove welcome message if present
    const welcome = elements.messages.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? 'U' : 'AI';

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';

    if (role === 'assistant') {
        // Render markdown for assistant messages
        contentEl.innerHTML = marked.parse(content, {
            breaks: true,
            gfm: true,
            highlight: function(code, lang) {
                if (lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(code, { language: lang }).value;
                }
                return hljs.highlightAuto(code).value;
            }
        });
        // Apply syntax highlighting to code blocks
        contentEl.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });
    } else {
        contentEl.textContent = content;
    }

    messageEl.appendChild(avatar);
    messageEl.appendChild(contentEl);
    elements.messages.appendChild(messageEl);

    // Scroll to bottom
    elements.messages.scrollTop = elements.messages.scrollHeight;
}

function addLoadingIndicator() {
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'AI';

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';

    const loading = document.createElement('div');
    loading.className = 'loading';
    loading.innerHTML = '<span></span><span></span><span></span>';

    contentEl.appendChild(loading);
    messageEl.appendChild(avatar);
    messageEl.appendChild(contentEl);
    elements.messages.appendChild(messageEl);

    elements.messages.scrollTop = elements.messages.scrollHeight;

    return messageEl;
}

// Model Functions
async function loadModels() {
    try {
        const data = await api('/api/models');
        state.models = data.models;
        state.defaultModel = data.default;
        renderModelOptions();
        renderModelDropdown();
        updateCurrentModelDisplay();
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

async function selectModel(modelId) {
    state.defaultModel = modelId;

    if (state.currentConversation) {
        try {
            await api(`/api/conversations/${state.currentConversation.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ model: modelId })
            });
            state.currentConversation.model = modelId;
        } catch (error) {
            console.error('Failed to update model:', error);
        }
    }

    renderModelOptions();
    renderModelDropdown();
    updateCurrentModelDisplay();
    closeModelModal();
    closeModelDropdown();
}

// Render Functions
function renderConversationsList() {
    elements.conversationsList.innerHTML = state.conversations.map(conv => `
        <div class="conversation-item ${conv.id === state.currentConversation?.id ? 'active' : ''}"
             onclick="selectConversation('${conv.id}')">
            <span class="conversation-title">${escapeHtml(conv.title)}</span>
            <button class="conversation-delete" onclick="deleteConversation('${conv.id}', event)">×</button>
        </div>
    `).join('');
}

function renderMessages() {
    if (!state.currentConversation?.messages?.length) {
        renderWelcome();
        return;
    }

    elements.messages.innerHTML = '';
    state.currentConversation.messages.forEach(msg => {
        addMessageToUI(msg.role, msg.content);
    });
}

function renderWelcome() {
    elements.messages.innerHTML = `
        <div class="welcome-message">
            <h2>Welcome to AI Chatbot</h2>
            <p>Start a conversation with Gemini AI</p>
        </div>
    `;
    updateTitle('AI Chatbot');
}

function renderUserInfo() {
    if (!state.user) return;

    elements.userInfo.innerHTML = `
        ${state.user.picture ? `<img src="${state.user.picture}" class="user-avatar" alt="Avatar" referrerpolicy="no-referrer">` : '<div class="user-avatar"></div>'}
        <span class="user-name">${escapeHtml(state.user.name)}</span>
    `;
}

function renderModelOptions() {
    const currentModel = state.currentConversation?.model || state.defaultModel;

    elements.modelOptions.innerHTML = state.models.map(model => `
        <div class="model-option ${model.id === currentModel ? 'selected' : ''}"
             onclick="selectModel('${model.id}')">
            <div class="model-option-name">${escapeHtml(model.name)}</div>
            <div class="model-option-id">${model.id}</div>
        </div>
    `).join('');
}

function renderModelDropdown() {
    const currentModel = state.currentConversation?.model || state.defaultModel;

    elements.modelDropdown.innerHTML = state.models.map(model => `
        <button class="model-dropdown-item ${model.id === currentModel ? 'selected' : ''}"
                onclick="selectModel('${model.id}')">
            <div class="model-dropdown-item-name">${escapeHtml(model.name)}</div>
            <div class="model-dropdown-item-id">${model.id}</div>
        </button>
    `).join('');
}

function updateCurrentModelDisplay() {
    const currentModel = state.currentConversation?.model || state.defaultModel;
    const model = state.models.find(m => m.id === currentModel);
    if (model && elements.currentModelName) {
        elements.currentModelName.textContent = model.name;
    }
}

function toggleModelDropdown() {
    elements.modelDropdown.classList.toggle('hidden');
    elements.modelSelectorBtn.classList.toggle('open');
}

function closeModelDropdown() {
    elements.modelDropdown.classList.add('hidden');
    elements.modelSelectorBtn.classList.remove('open');
}

function highlightActiveConversation() {
    document.querySelectorAll('.conversation-item').forEach(el => {
        el.classList.remove('active');
    });

    if (state.currentConversation) {
        const activeEl = document.querySelector(`.conversation-item[onclick*="${state.currentConversation.id}"]`);
        if (activeEl) activeEl.classList.add('active');
    }
}

function updateTitle(title) {
    elements.currentChatTitle.textContent = title;
}

// UI Helpers
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function autoResizeTextarea() {
    elements.messageInput.style.height = 'auto';
    elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 200) + 'px';
}

function updateSendButton() {
    elements.sendBtn.disabled = !elements.messageInput.value.trim() || state.isLoading;
}

// Sidebar toggle (mobile)
function toggleSidebar() {
    elements.sidebar.classList.toggle('open');

    // Create/show overlay
    let overlay = document.querySelector('.sidebar-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.onclick = closeSidebar;
        elements.app.appendChild(overlay);
    }
    overlay.classList.toggle('visible', elements.sidebar.classList.contains('open'));
}

function closeSidebar() {
    elements.sidebar.classList.remove('open');
    const overlay = document.querySelector('.sidebar-overlay');
    if (overlay) overlay.classList.remove('visible');
}

// Modal functions
function openModelModal() {
    elements.modelModal.classList.remove('hidden');
}

function closeModelModal() {
    elements.modelModal.classList.add('hidden');
}

// Event Listeners
function setupEventListeners() {
    // Send message
    elements.sendBtn.addEventListener('click', sendMessage);

    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    elements.messageInput.addEventListener('input', () => {
        autoResizeTextarea();
        updateSendButton();
    });

    // New chat
    elements.newChatBtn.addEventListener('click', createConversation);

    // Mobile menu
    elements.menuBtn.addEventListener('click', toggleSidebar);

    // Model selector (mobile modal)
    elements.modelBtn.addEventListener('click', openModelModal);
    elements.closeModalBtn.addEventListener('click', closeModelModal);
    elements.modelModal.addEventListener('click', (e) => {
        if (e.target === elements.modelModal) closeModelModal();
    });

    // Model selector dropdown (desktop)
    elements.modelSelectorBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleModelDropdown();
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!elements.modelDropdown.contains(e.target) &&
            !elements.modelSelectorBtn.contains(e.target)) {
            closeModelDropdown();
        }
    });

    // Note: Google login button is rendered by GIS, no click handler needed
}

// Make functions available globally for onclick handlers
window.selectConversation = selectConversation;
window.deleteConversation = deleteConversation;
window.selectModel = selectModel;

// Initialize
async function init() {
    // Setup event listeners
    setupEventListeners();

    // Initialize Google Sign In (will render button when needed)
    await initGoogleSignIn();

    // Check authentication
    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) return;

    // Load data
    await Promise.all([
        loadConversations(),
        loadModels()
    ]);
}

// Start the app
init();
