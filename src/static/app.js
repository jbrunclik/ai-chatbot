// AI Chatbot Frontend Application

// Constants
// Sparkle icon with silver/white theme
const AI_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none"><path d="M12 2L13.5 8.5L20 10L13.5 11.5L12 18L10.5 11.5L4 10L10.5 8.5L12 2Z" fill="white"/><path d="M19 14L19.75 16.25L22 17L19.75 17.75L19 20L18.25 17.75L16 17L18.25 16.25L19 14Z" fill="white" opacity="0.7"/><path d="M6 16L6.5 17.5L8 18L6.5 18.5L6 20L5.5 18.5L4 18L5.5 17.5L6 16Z" fill="white" opacity="0.5"/></svg>';

// State
const state = {
    token: localStorage.getItem('token'),
    user: null,
    conversations: [],
    currentConversation: null,
    models: [],
    defaultModel: 'gemini-3-flash-preview',
    isLoading: false,
    googleClientId: null,
    streamingEnabled: localStorage.getItem('streamingEnabled') !== 'false',  // Default: true
    // File upload state
    pendingFiles: [],
    uploadConfig: {
        maxFileSize: 20 * 1024 * 1024,  // 20 MB default
        maxFilesPerMessage: 10,
        allowedFileTypes: []
    }
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
    modelDropdown: document.getElementById('model-dropdown'),
    // Streaming toggle
    streamingToggle: document.getElementById('streaming-toggle'),
    // File upload
    fileInput: document.getElementById('file-input'),
    attachBtn: document.getElementById('attach-btn'),
    filePreview: document.getElementById('file-preview'),
    // Lightbox
    lightbox: document.getElementById('lightbox'),
    lightboxImg: document.getElementById('lightbox-img'),
    lightboxClose: document.querySelector('.lightbox-close')
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
            // No client ID means local mode - skip Google Sign In
            return;
        }

        // Wait for Google Identity Services to load
        if (typeof google === 'undefined') {
            // GIS not loaded yet, wait for it
            await new Promise((resolve) => {
                const checkGoogle = setInterval(() => {
                    if (typeof google !== 'undefined') {
                        clearInterval(checkGoogle);
                        resolve();
                    }
                }, 100);
                // Timeout after 5 seconds
                setTimeout(() => {
                    clearInterval(checkGoogle);
                    resolve();
                }, 5000);
            });
        }

        if (typeof google === 'undefined') {
            console.error('Google Identity Services failed to load');
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
    // Close sidebar immediately for better mobile UX
    closeSidebar();

    try {
        const data = await api(`/api/conversations/${id}`);
        state.currentConversation = data;
        renderMessages();
        updateTitle(data.title);
        highlightActiveConversation();
        updateCurrentModelDisplay();
        renderModelDropdown();
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

async function deleteConversation(id, event) {
    event.stopPropagation();

    if (!confirm('Delete this conversation?')) return;

    await deleteConversationById(id);
}

async function deleteConversationById(id) {
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
    const hasFiles = state.pendingFiles.length > 0;

    if ((!content && !hasFiles) || state.isLoading) return;

    // Create conversation if none selected
    if (!state.currentConversation) {
        await createConversation();
    }

    // Capture files before clearing
    const filesToSend = [...state.pendingFiles];

    // Add user message to UI (with file info)
    addMessageToUI('user', content, filesToSend);

    // Clear input and files
    elements.messageInput.value = '';
    clearPendingFiles();
    autoResizeTextarea();
    updateSendButton();

    // iOS Safari: blur input to dismiss keyboard and fix viewport
    elements.messageInput.blur();
    // Force scroll reset to fix iOS viewport bug
    window.scrollTo(0, 0);

    // Choose streaming or batch mode
    if (state.streamingEnabled) {
        await sendMessageStream(content, filesToSend);
    } else {
        await sendMessageBatch(content, filesToSend);
    }
}

async function sendMessageBatch(content, files = []) {
    // Show loading indicator
    state.isLoading = true;
    updateSendButton();
    const loadingEl = addLoadingIndicator();

    try {
        // Build request body with optional files
        const requestBody = { message: content };
        if (files.length > 0) {
            // Strip previewUrl before sending (not needed by backend)
            requestBody.files = files.map(f => ({
                name: f.name,
                type: f.type,
                data: f.data
            }));
        }

        const data = await api(`/api/conversations/${state.currentConversation.id}/chat/batch`, {
            method: 'POST',
            body: JSON.stringify(requestBody)
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
        updateSendButton();
    }
}

async function sendMessageStream(content, files = []) {
    state.isLoading = true;
    updateSendButton();

    // Create streaming message element
    const messageEl = addStreamingMessage();
    const contentEl = messageEl.querySelector('.message-content');
    let fullResponse = '';

    try {
        // Build request body with optional files
        const requestBody = { message: content };
        if (files.length > 0) {
            // Strip previewUrl before sending (not needed by backend)
            requestBody.files = files.map(f => ({
                name: f.name,
                type: f.type,
                data: f.data
            }));
        }

        const response = await fetch(`/api/conversations/${state.currentConversation.id}/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': state.token ? `Bearer ${state.token}` : ''
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error('Stream request failed');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process complete SSE lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';  // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.type === 'token') {
                            fullResponse += data.text;
                            updateStreamingMessage(contentEl, fullResponse);
                        } else if (data.type === 'done') {
                            finalizeStreamingMessage(messageEl, fullResponse);
                            await loadConversations();  // Refresh for title update
                        } else if (data.type === 'error') {
                            finalizeStreamingMessage(messageEl, 'Sorry, an error occurred: ' + data.message);
                        }
                    } catch (e) {
                        console.error('Failed to parse SSE data:', e);
                    }
                }
            }
        }

        // Handle any remaining buffer
        if (buffer.startsWith('data: ')) {
            try {
                const data = JSON.parse(buffer.slice(6));
                if (data.type === 'token') {
                    fullResponse += data.text;
                }
                if (data.type === 'done' || data.type === 'token') {
                    finalizeStreamingMessage(messageEl, fullResponse);
                }
            } catch (e) {
                // Ignore incomplete final data
            }
        }

    } catch (error) {
        console.error('Stream error:', error);
        finalizeStreamingMessage(messageEl, fullResponse || 'Sorry, an error occurred. Please try again.');
    } finally {
        state.isLoading = false;
    }
}

function addStreamingMessage() {
    // Remove welcome message if present
    const welcome = elements.messages.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant streaming';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = AI_AVATAR_SVG;

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';
    contentEl.innerHTML = '<span class="cursor">|</span>';

    messageEl.appendChild(avatar);
    messageEl.appendChild(contentEl);
    elements.messages.appendChild(messageEl);

    elements.messages.scrollTop = elements.messages.scrollHeight;

    return messageEl;
}

function updateStreamingMessage(contentEl, content) {
    // Render markdown with cursor at end
    contentEl.innerHTML = marked.parse(content, {
        breaks: true,
        gfm: true
    }) + '<span class="cursor">|</span>';

    // Scroll to bottom
    elements.messages.scrollTop = elements.messages.scrollHeight;
}

function finalizeStreamingMessage(messageEl, content) {
    messageEl.classList.remove('streaming');
    const contentEl = messageEl.querySelector('.message-content');

    // Final render with syntax highlighting
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

    elements.messages.scrollTop = elements.messages.scrollHeight;
}

function getUserAvatar() {
    if (state.user?.picture) {
        return `<img src="${state.user.picture}" alt="Avatar" referrerpolicy="no-referrer">`;
    }
    // Get initials from name
    if (state.user?.name) {
        const parts = state.user.name.trim().split(/\s+/);
        if (parts.length >= 2) {
            return parts[0][0].toUpperCase() + parts[parts.length - 1][0].toUpperCase();
        }
        return parts[0][0].toUpperCase();
    }
    return 'U';
}

function addMessageToUI(role, content, files = []) {
    // Remove welcome message if present
    const welcome = elements.messages.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    if (role === 'user') {
        avatar.innerHTML = getUserAvatar();
    } else {
        avatar.innerHTML = AI_AVATAR_SVG;
    }

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';

    // Handle structured content (from database)
    let textContent = content;
    let attachedFiles = files;

    if (typeof content === 'object' && content !== null) {
        textContent = content.text || '';
        attachedFiles = content.files || [];
    }

    if (role === 'assistant') {
        // Render markdown for assistant messages
        contentEl.innerHTML = marked.parse(textContent, {
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
        // User message - show text and file attachments
        if (textContent) {
            const textEl = document.createElement('div');
            textEl.className = 'message-text';
            textEl.textContent = textContent;
            contentEl.appendChild(textEl);
        }

        // Render file attachments - separate images and files
        if (attachedFiles && attachedFiles.length > 0) {
            const images = attachedFiles.filter(f => f.type && f.type.startsWith('image/'));
            const files = attachedFiles.filter(f => !f.type || !f.type.startsWith('image/'));

            // Render images first (horizontal row)
            if (images.length > 0) {
                const imagesEl = document.createElement('div');
                imagesEl.className = 'message-attachments-images';

                for (const file of images) {
                    const attachEl = document.createElement('div');
                    attachEl.className = 'message-attachment';

                    const img = document.createElement('img');
                    // Prefer thumbnail, then previewUrl (for just-uploaded), then full data
                    if (file.thumbnail) {
                        img.src = `data:${file.type};base64,${file.thumbnail}`;
                    } else if (file.previewUrl) {
                        img.src = file.previewUrl;
                    } else if (file.data) {
                        img.src = `data:${file.type};base64,${file.data}`;
                    }
                    img.alt = file.name || 'Image';
                    img.className = 'message-attachment-image';
                    // Store message ID and file index for fetching full image from API
                    if (file.messageId) {
                        img.dataset.messageId = file.messageId;
                        img.dataset.fileIndex = file.fileIndex;
                    }
                    attachEl.appendChild(img);
                    imagesEl.appendChild(attachEl);
                }

                contentEl.appendChild(imagesEl);
            }

            // Render files second (vertical stack)
            if (files.length > 0) {
                const filesEl = document.createElement('div');
                filesEl.className = 'message-attachments-files';

                for (const file of files) {
                    const attachEl = document.createElement('div');
                    attachEl.className = 'message-attachment-file';

                    // Add file type icon
                    const iconEl = document.createElement('span');
                    iconEl.className = 'file-icon';
                    iconEl.innerHTML = getFileIconSvg(file.type);
                    attachEl.appendChild(iconEl);

                    // Add filename
                    const nameEl = document.createElement('span');
                    nameEl.className = 'file-name';
                    nameEl.textContent = file.name || 'File';
                    attachEl.appendChild(nameEl);

                    // Store message ID and file index for download
                    if (file.messageId !== undefined) {
                        attachEl.dataset.messageId = file.messageId;
                        attachEl.dataset.fileIndex = file.fileIndex;
                        attachEl.dataset.fileName = file.name || 'file';
                    }

                    filesEl.appendChild(attachEl);
                }

                contentEl.appendChild(filesEl);
            }
        }
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
    avatar.innerHTML = AI_AVATAR_SVG;

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
             data-conv-id="${conv.id}">
            <span class="conversation-title">${escapeHtml(conv.title)}</span>
            <button class="conversation-delete" data-delete-id="${conv.id}">×</button>
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
        // Pass message ID with files for fetching full images from API
        const filesWithMsgId = (msg.files || []).map((f, idx) => ({
            ...f,
            messageId: msg.id,
            fileIndex: idx
        }));
        addMessageToUI(msg.role, msg.content, filesWithMsgId);
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
        <button class="btn-logout" title="Sign out">↪</button>
    `;

    // Add logout handler
    const logoutBtn = elements.userInfo.querySelector('.btn-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }
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
    const hasText = elements.messageInput.value.trim().length > 0;
    const hasFiles = state.pendingFiles.length > 0;
    elements.sendBtn.disabled = (!hasText && !hasFiles) || state.isLoading;
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

// Streaming toggle
function toggleStreaming() {
    state.streamingEnabled = !state.streamingEnabled;
    localStorage.setItem('streamingEnabled', state.streamingEnabled);
    updateStreamingToggle();
}

function updateStreamingToggle() {
    if (elements.streamingToggle) {
        elements.streamingToggle.checked = state.streamingEnabled;
    }
}

// File Upload Functions
async function loadUploadConfig() {
    try {
        const data = await api('/api/config/upload');
        state.uploadConfig = data;
        // Set accept attribute on file input based on allowed types
        if (elements.fileInput) {
            elements.fileInput.accept = data.allowedFileTypes.join(',');
        }
    } catch (error) {
        console.error('Failed to load upload config:', error);
    }
}

function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    addFilesToPending(files);
    // Reset input so same file can be selected again
    event.target.value = '';
}

function addFilesToPending(files) {
    const { maxFileSize, maxFilesPerMessage, allowedFileTypes } = state.uploadConfig;

    for (const file of files) {
        // Check max files
        if (state.pendingFiles.length >= maxFilesPerMessage) {
            alert(`Maximum ${maxFilesPerMessage} files per message`);
            break;
        }

        // Check file type
        if (allowedFileTypes.length > 0 && !allowedFileTypes.includes(file.type)) {
            alert(`File type "${file.type}" is not allowed`);
            continue;
        }

        // Check file size
        if (file.size > maxFileSize) {
            const maxMB = Math.round(maxFileSize / (1024 * 1024));
            alert(`File "${file.name}" exceeds ${maxMB}MB limit`);
            continue;
        }

        // Read file as base64
        readFileAsBase64(file);
    }
}

function readFileAsBase64(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        // Extract base64 data (remove data:...;base64, prefix)
        const base64 = e.target.result.split(',')[1];
        state.pendingFiles.push({
            name: file.name,
            type: file.type,
            data: base64,
            // Keep original for preview
            previewUrl: file.type.startsWith('image/') ? e.target.result : null
        });
        renderFilePreview();
        updateSendButton();
    };
    reader.readAsDataURL(file);
}

function removeFile(index) {
    state.pendingFiles.splice(index, 1);
    renderFilePreview();
    updateSendButton();
}

function clearPendingFiles() {
    state.pendingFiles = [];
    renderFilePreview();
    updateSendButton();
}

function renderFilePreview() {
    if (!elements.filePreview) return;

    if (state.pendingFiles.length === 0) {
        elements.filePreview.classList.add('hidden');
        elements.filePreview.innerHTML = '';
        return;
    }

    elements.filePreview.classList.remove('hidden');
    elements.filePreview.innerHTML = state.pendingFiles.map((file, index) => {
        if (file.previewUrl) {
            // Image preview
            return `
                <div class="file-preview-item" data-index="${index}">
                    <img src="${file.previewUrl}" alt="${escapeHtml(file.name)}">
                    <button class="file-preview-remove" data-remove-index="${index}">&times;</button>
                </div>
            `;
        } else {
            // Non-image file
            return `
                <div class="file-preview-item file-preview-doc" data-index="${index}">
                    <span class="file-preview-name">${escapeHtml(file.name)}</span>
                    <button class="file-preview-remove" data-remove-index="${index}">&times;</button>
                </div>
            `;
        }
    }).join('');
}

function getFileIcon(mimeType) {
    if (mimeType === 'application/pdf') return '📄';
    if (mimeType.startsWith('text/')) return '📝';
    if (mimeType === 'application/json') return '{ }';
    return '📎';
}

function getFileIconSvg(mimeType) {
    // PDF icon
    if (mimeType === 'application/pdf') {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 15h.01M12 15h.01M15 15h.01"/></svg>';
    }
    // Text/code files
    if (mimeType?.startsWith('text/') || mimeType === 'application/json' || mimeType === 'application/javascript') {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="12" y2="17"/></svg>';
    }
    // Default file icon
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
}

// Lightbox Functions
function openLightbox(imageSrc) {
    if (elements.lightbox && elements.lightboxImg) {
        elements.lightboxImg.src = imageSrc;
        elements.lightbox.classList.remove('hidden');
        elements.lightbox.classList.remove('loading');
        document.body.style.overflow = 'hidden';
    }
}

async function openLightboxWithLoading(apiUrl) {
    if (!elements.lightbox || !elements.lightboxImg) return;

    // Show lightbox with loading state
    elements.lightbox.classList.remove('hidden');
    elements.lightbox.classList.add('loading');
    elements.lightboxImg.src = '';
    document.body.style.overflow = 'hidden';

    try {
        // Fetch full-size image from API with auth header
        const response = await fetch(apiUrl, {
            headers: state.token ? { 'Authorization': `Bearer ${state.token}` } : {}
        });

        if (!response.ok) {
            throw new Error('Failed to load image');
        }

        // Create blob URL from response
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);

        // Display the image
        elements.lightboxImg.src = blobUrl;
        elements.lightbox.classList.remove('loading');

        // Clean up blob URL when lightbox closes
        elements.lightboxImg.dataset.blobUrl = blobUrl;
    } catch (error) {
        console.error('Failed to load full-size image:', error);
        closeLightbox();
    }
}

function closeLightbox() {
    if (elements.lightbox) {
        elements.lightbox.classList.add('hidden');
        elements.lightbox.classList.remove('loading');

        // Clean up blob URL if present
        const blobUrl = elements.lightboxImg.dataset.blobUrl;
        if (blobUrl) {
            URL.revokeObjectURL(blobUrl);
            delete elements.lightboxImg.dataset.blobUrl;
        }

        elements.lightboxImg.src = '';
        document.body.style.overflow = '';
    }
}

// File Download Functions
async function downloadFile(messageId, fileIndex, fileName) {
    try {
        const apiUrl = `/api/messages/${messageId}/files/${fileIndex}`;
        const response = await fetch(apiUrl, {
            headers: state.token ? { 'Authorization': `Bearer ${state.token}` } : {}
        });

        if (!response.ok) {
            throw new Error('Failed to download file');
        }

        // Create blob and trigger download
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Clean up blob URL
        URL.revokeObjectURL(blobUrl);
    } catch (error) {
        console.error('Failed to download file:', error);
        alert('Failed to download file');
    }
}

// Make removeFile available globally
window.removeFile = removeFile;

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

    // Streaming toggle
    if (elements.streamingToggle) {
        elements.streamingToggle.addEventListener('change', toggleStreaming);
    }

    // File upload
    if (elements.attachBtn) {
        elements.attachBtn.addEventListener('click', () => {
            elements.fileInput?.click();
        });
    }
    if (elements.fileInput) {
        elements.fileInput.addEventListener('change', handleFileSelect);
    }

    // File preview remove buttons (event delegation for iOS compatibility)
    if (elements.filePreview) {
        elements.filePreview.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('[data-remove-index]');
            if (removeBtn) {
                const index = parseInt(removeBtn.dataset.removeIndex, 10);
                removeFile(index);
            }
        });
    }

    // Conversation list event delegation (for iOS Safari compatibility)
    // Use both click and touchend for responsive single-tap on mobile
    const handleConversationInteraction = (e) => {
        // Handle delete button
        const deleteBtn = e.target.closest('[data-delete-id]');
        if (deleteBtn) {
            e.stopPropagation();
            e.preventDefault();
            const id = deleteBtn.dataset.deleteId;
            if (confirm('Delete this conversation?')) {
                deleteConversationById(id);
            }
            return;
        }

        // Handle conversation selection
        const convItem = e.target.closest('[data-conv-id]');
        if (convItem) {
            e.preventDefault();
            const id = convItem.dataset.convId;
            selectConversation(id);
        }
    };

    elements.conversationsList.addEventListener('click', handleConversationInteraction);

    // Touchend for instant response on iOS (avoids 300ms delay)
    let touchMoved = false;
    elements.conversationsList.addEventListener('touchstart', () => {
        touchMoved = false;
    }, { passive: true });
    elements.conversationsList.addEventListener('touchmove', () => {
        touchMoved = true;
    }, { passive: true });
    elements.conversationsList.addEventListener('touchend', (e) => {
        if (!touchMoved) {
            handleConversationInteraction(e);
        }
    });

    // Lightbox - click on message images to open fullscreen
    // File download - click on file chips to download
    elements.messages.addEventListener('click', async (e) => {
        // Handle image clicks - open in lightbox
        const img = e.target.closest('.message-attachment-image');
        if (img) {
            // If we have message ID and file index, fetch full-size from API
            const messageId = img.dataset.messageId;
            const fileIndex = img.dataset.fileIndex;

            if (messageId && fileIndex !== undefined) {
                // Fetch full-size image from API
                const apiUrl = `/api/messages/${messageId}/files/${fileIndex}`;
                openLightboxWithLoading(apiUrl);
            } else {
                // Fallback: use current src (for just-uploaded images)
                openLightbox(img.src);
            }
            return;
        }

        // Handle file chip clicks - download file
        const fileChip = e.target.closest('.message-attachment-file');
        if (fileChip && fileChip.dataset.messageId) {
            const { messageId, fileIndex, fileName } = fileChip.dataset;
            downloadFile(messageId, fileIndex, fileName);
        }
    });

    // Lightbox close handlers
    if (elements.lightbox) {
        elements.lightbox.addEventListener('click', (e) => {
            // Close when clicking on background, not on the image
            if (e.target === elements.lightbox) {
                closeLightbox();
            }
        });
    }
    if (elements.lightboxClose) {
        elements.lightboxClose.addEventListener('click', closeLightbox);
    }

    // Close lightbox with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !elements.lightbox?.classList.contains('hidden')) {
            closeLightbox();
        }
    });
}

// Make functions available globally for onclick handlers
window.selectConversation = selectConversation;
window.deleteConversation = deleteConversation;
window.selectModel = selectModel;

// Initialize
async function init() {
    // Setup event listeners
    setupEventListeners();

    // Initialize streaming toggle state
    updateStreamingToggle();

    // Initialize Google Sign In (will render button when needed)
    await initGoogleSignIn();

    // Check authentication
    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) return;

    // Load data
    await Promise.all([
        loadConversations(),
        loadModels(),
        loadUploadConfig()
    ]);
}

// Start the app
init();
