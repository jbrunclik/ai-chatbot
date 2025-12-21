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

    // Clean up thumbnail observer for previous conversation
    if (thumbnailObserver) {
        thumbnailObserver.disconnect();
        thumbnailObserver = null;
    }

    // Clear current messages and show loading indicator
    elements.messages.innerHTML = '';
    showConversationLoader();

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
        // Show error message
        elements.messages.innerHTML = `
            <div class="welcome-message">
                <h2>Error loading conversation</h2>
                <p>${escapeHtml(error.message || 'Unknown error')}</p>
            </div>
        `;
    } finally {
        hideConversationLoader();
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
                    img.alt = file.name || 'Image';
                    img.className = 'message-attachment-image';
                    img.loading = 'lazy'; // Native browser lazy loading

                    // Store message ID and file index for fetching full image from API
                    if (file.messageId) {
                        img.dataset.messageId = file.messageId;
                        img.dataset.fileIndex = file.fileIndex;
                    }

                    // For images: prefer previewUrl (just-uploaded), then lazy load thumbnail from API
                    // Thumbnails are not included in conversation payload - fetched on-demand
                    if (file.previewUrl) {
                        // Just-uploaded file, use preview URL
                        img.src = file.previewUrl;
                    } else if (file.data) {
                        // Fallback: if full data is present (shouldn't happen with optimization)
                        img.src = `data:${file.type};base64,${file.data}`;
                    } else if (file.messageId && file.fileIndex !== undefined) {
                        // Will lazy load thumbnail from API when visible
                        img.dataset.needsThumbnail = 'true';
                        img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iIzI1MjUyNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiNhMGEwYTAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj5JbWFnZTwvdGV4dD48L3N2Zz4=';
                        img.style.opacity = '0.7';
                        img.title = 'Loading image...';
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

function showConversationLoader() {
    // Remove any existing loader
    hideConversationLoader();

    const loader = document.createElement('div');
    loader.className = 'conversation-loader';
    loader.innerHTML = `
        <div class="conversation-loader-content">
            <div class="loading">
                <span></span><span></span><span></span>
            </div>
            <p>Loading conversation...</p>
        </div>
    `;
    elements.messages.appendChild(loader);
}

function hideConversationLoader() {
    const loader = elements.messages.querySelector('.conversation-loader');
    if (loader) {
        loader.remove();
    }
}

// Lazy load thumbnails in parallel using Intersection Observer
let thumbnailObserver = null;
const MAX_CONCURRENT_THUMBNAILS = 6; // Limit concurrent fetches

function setupThumbnailLazyLoading() {
    // Clean up existing observer
    if (thumbnailObserver) {
        thumbnailObserver.disconnect();
    }

    // Find all images that need thumbnails
    const imagesNeedingThumbnails = elements.messages.querySelectorAll(
        'img.message-attachment-image[data-needs-thumbnail="true"]'
    );

    if (imagesNeedingThumbnails.length === 0) {
        return;
    }

    // Create Intersection Observer
    thumbnailObserver = new IntersectionObserver(
        async (entries) => {
            // Collect all images that are now visible and not already loading/loaded
            const visibleImages = entries
                .filter(entry => entry.isIntersecting)
                .map(entry => entry.target)
                .filter(img => img.dataset.loading !== 'true' && img.dataset.loaded !== 'true');

            if (visibleImages.length === 0) return;

            // Limit concurrent fetches
            const imagesToFetch = visibleImages.slice(0, MAX_CONCURRENT_THUMBNAILS);

            // Fetch thumbnails for visible images in parallel (with concurrency limit)
            const fetchPromises = imagesToFetch.map(async (img) => {
                // Skip if already fetching or loaded
                if (img.dataset.loading === 'true' || img.dataset.loaded === 'true') {
                    return;
                }

                const messageId = img.dataset.messageId;
                const fileIndex = img.dataset.fileIndex;

                if (!messageId || fileIndex === undefined) {
                    return;
                }

                // Mark as loading
                img.dataset.loading = 'true';
                img.classList.add('thumbnail-loading');

                try {
                    // Fetch thumbnail from API (server will return thumbnail or fall back to full image)
                    const apiUrl = `/api/messages/${messageId}/files/${fileIndex}/thumbnail`;
                    const response = await fetch(apiUrl, {
                        headers: state.token ? { 'Authorization': `Bearer ${state.token}` } : {}
                    });

                    if (!response.ok) {
                        throw new Error('Failed to load thumbnail');
                    }

                    // Create blob URL for the thumbnail
                    const blob = await response.blob();
                    const blobUrl = URL.createObjectURL(blob);

                    // Update image source
                    img.src = blobUrl;
                    img.style.opacity = '1';
                    img.title = '';
                    img.dataset.loaded = 'true';
                    img.classList.remove('thumbnail-loading');

                    // Store blob URL for cleanup
                    img.dataset.blobUrl = blobUrl;
                } catch (error) {
                    console.error('Failed to load thumbnail:', error);
                    img.classList.remove('thumbnail-loading');
                    img.title = 'Failed to load image';
                } finally {
                    img.dataset.loading = 'false';
                    // Stop observing this image
                    thumbnailObserver.unobserve(img);
                }
            });

            // Wait for all parallel fetches to complete
            await Promise.all(fetchPromises);
        },
        {
            root: elements.messages,
            rootMargin: '100px', // Start loading 100px before image is visible
            threshold: 0.01
        }
    );

    // Clean up blob URLs when images are removed
    const cleanupObserver = new MutationObserver(() => {
        elements.messages.querySelectorAll('img[data-blob-url]').forEach(img => {
            if (!img.isConnected) {
                const blobUrl = img.dataset.blobUrl;
                if (blobUrl) {
                    URL.revokeObjectURL(blobUrl);
                }
            }
        });
    });
    cleanupObserver.observe(elements.messages, { childList: true, subtree: true });

    // Observe all images that need thumbnails
    imagesNeedingThumbnails.forEach(img => {
        thumbnailObserver.observe(img);
    });
}


// Model Functions
async function loadModels() {
    try {
        const data = await api('/api/models');
        state.models = data.models;
        state.defaultModel = data.default;
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

    renderModelDropdown();
    updateCurrentModelDisplay();
    closeModelDropdown();
}

// Render Functions
function renderConversationsList() {
    elements.conversationsList.innerHTML = state.conversations.map(conv => `
        <div class="conversation-item-wrapper" data-conv-id="${conv.id}">
            <div class="conversation-item ${conv.id === state.currentConversation?.id ? 'active' : ''}">
                <span class="conversation-title">${escapeHtml(conv.title)}</span>
                <button class="conversation-delete" data-delete-id="${conv.id}">×</button>
            </div>
            <button class="conversation-delete-swipe" data-delete-id="${conv.id}">Delete</button>
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

    // Setup lazy loading for thumbnails after rendering
    // Use setTimeout to ensure DOM is ready
    setTimeout(() => {
        setupThumbnailLazyLoading();
    }, 0);
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
    const isOpen = elements.sidebar.classList.contains('open');
    overlay.classList.toggle('visible', isOpen);
    // Clear inline styles to let CSS classes control visibility
    if (!isOpen) {
        overlay.style.display = '';
        overlay.style.opacity = '';
    }
}

function closeSidebar() {
    elements.sidebar.classList.remove('open');
    const overlay = document.querySelector('.sidebar-overlay');
    if (overlay) {
        overlay.classList.remove('visible');
        // Clear any inline styles that might have been set during swipe
        overlay.style.display = '';
        overlay.style.opacity = '';
    }
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

    const closeSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';

    elements.filePreview.classList.remove('hidden');
    elements.filePreview.innerHTML = state.pendingFiles.map((file, index) => {
        if (file.previewUrl) {
            // Image preview
            return `
                <div class="file-preview-item" data-index="${index}">
                    <img src="${file.previewUrl}" alt="${escapeHtml(file.name)}">
                    <button class="file-preview-remove" data-remove-index="${index}">${closeSvg}</button>
                </div>
            `;
        } else {
            // Non-image file
            return `
                <div class="file-preview-item file-preview-doc" data-index="${index}">
                    <span class="file-preview-name">${escapeHtml(file.name)}</span>
                    <button class="file-preview-remove" data-remove-index="${index}">${closeSvg}</button>
                </div>
            `;
        }
    }).join('');
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

    // Drag and drop file upload
    const dropZone = document.querySelector('.input-area');
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('drag-over');
        });

        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');

            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                addFilesToPending(files);
            }
        });
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
    const handleConversationInteraction = (e) => {
        // Handle delete button (both regular and swipe)
        const deleteBtn = e.target.closest('[data-delete-id]');
        if (deleteBtn) {
            e.stopPropagation();
            e.preventDefault();
            // Close any open swipes before showing delete confirmation
            resetSwipeStates();
            const id = deleteBtn.dataset.deleteId;
            if (confirm('Delete this conversation?')) {
                deleteConversationById(id);
            }
            return;
        }

        // Handle conversation selection (only on the conversation-item, not wrapper)
        const convItem = e.target.closest('.conversation-item');
        if (convItem) {
            e.preventDefault();
            const wrapper = convItem.closest('[data-conv-id]');
            if (wrapper) {
                // Reset any open swipe states first
                resetSwipeStates();
                const id = wrapper.dataset.convId;
                selectConversation(id);
            }
        }
    };

    elements.conversationsList.addEventListener('click', handleConversationInteraction);

    // Generic swipe handler factory
    function createSwipeHandler(config) {
        const {
            shouldStart,           // (e) => boolean - whether to start swipe
            getTarget,              // (e) => element - get the element to transform
            getTransform,           // (deltaX, isOpen, config) => string - calculate transform
            getInitialState,        // (target) => boolean - check if already "open"
            onSwipeMove,            // (target, deltaX, progress) => void - optional callback during swipe
            onComplete,             // (target, deltaX) => void - called when swipe completes
            onSnapBack,            // (target) => void - called when snapping back
            threshold = 50,         // minimum distance to complete
            maxDistance = 80,       // maximum swipe distance
            minMovement = 10        // minimum movement to start swipe
        } = config;

        let swipeStartX = 0;
        let swipeStartY = 0;
        let swipeCurrentX = 0;
        let swipeTarget = null;
        let isSwiping = false;
        let swipeStartTime = 0;

        const handleTouchStart = (e) => {
            if (!shouldStart(e)) return;

            swipeStartX = e.touches[0].clientX;
            swipeStartY = e.touches[0].clientY;
            swipeCurrentX = swipeStartX;
            swipeTarget = getTarget(e);
            isSwiping = false;
            swipeStartTime = Date.now();
        };

        const handleTouchMove = (e) => {
            if (!swipeTarget) return;

            swipeCurrentX = e.touches[0].clientX;
            const currentY = e.touches[0].clientY;
            const deltaX = swipeStartX - swipeCurrentX;
            const deltaY = Math.abs(swipeStartY - currentY);

            // Only start swiping if horizontal movement is greater than vertical
            if (Math.abs(deltaX) > minMovement && Math.abs(deltaX) > deltaY) {
                isSwiping = true;
            }

            if (isSwiping) {
                const isOpen = getInitialState(swipeTarget);
                const transform = getTransform(deltaX, isOpen, { maxDistance, threshold });

                if (transform !== null) {
                    swipeTarget.style.transform = transform;
                    swipeTarget.style.transition = 'none';

                    if (onSwipeMove) {
                        const progress = Math.min(Math.abs(deltaX) / maxDistance, 1);
                        onSwipeMove(swipeTarget, deltaX, progress);
                    }
                }
            }
        };

        const handleTouchEnd = (e) => {
            if (!swipeTarget) return false;

            const deltaX = swipeStartX - swipeCurrentX;
            const deltaY = Math.abs(swipeStartY - (e.changedTouches[0]?.clientY || swipeStartY));
            const timeElapsed = Date.now() - swipeStartTime;

            // Restore transition
            swipeTarget.style.transition = '';

            let handled = false;

            if (isSwiping && Math.abs(deltaX) > deltaY) {
                // It was a swipe
                handled = true;
                if (Math.abs(deltaX) > threshold) {
                    // Swiped far enough - complete action
                    swipeTarget.style.transform = '';
                    onComplete(swipeTarget, deltaX);
                } else {
                    // Snap back
                    swipeTarget.style.transform = '';
                    if (onSnapBack) {
                        onSnapBack(swipeTarget);
                    }
                }
            } else if (!isSwiping && timeElapsed < 300 && Math.abs(deltaX) < 10 && Math.abs(deltaY) < 10) {
                // It was a tap - let it bubble up for normal click handling
                handled = false;
            } else {
                // Reset transform if it was just a scroll
                swipeTarget.style.transform = '';
                handled = true;
            }

            swipeTarget = null;
            isSwiping = false;
            return handled;
        };

        return { handleTouchStart, handleTouchMove, handleTouchEnd };
    }

    // Swipe-to-reveal delete for touch devices
    const SWIPE_THRESHOLD = 60;
    const SWIPE_DISTANCE = 80;

    function resetSwipeStates(exceptWrapper = null) {
        document.querySelectorAll('.conversation-item-wrapper.swiped').forEach(el => {
            if (el !== exceptWrapper) {
                el.classList.remove('swiped');
                const convItem = el.querySelector('.conversation-item');
                if (convItem) {
                    convItem.style.transform = '';
                }
            }
        });
    }

    const conversationSwipe = createSwipeHandler({
        shouldStart: (e) => {
            const wrapper = e.target.closest('.conversation-item-wrapper');
            if (!wrapper) {
                resetSwipeStates();
                return false;
            }
            // Don't start swipe if clicking on delete button
            return !e.target.closest('.conversation-delete-swipe');
        },
        getTarget: (e) => {
            const wrapper = e.target.closest('.conversation-item-wrapper');
            return wrapper?.querySelector('.conversation-item');
        },
        getTransform: (deltaX, isOpen, { maxDistance }) => {
            if (isOpen && deltaX < 0) {
                // Swiping right to close
                const translateX = Math.max(deltaX + maxDistance, 0);
                return `translateX(-${translateX}px)`;
            } else if (!isOpen && deltaX > 0) {
                // Swiping left to open
                const translateX = Math.min(deltaX, maxDistance);
                return `translateX(-${translateX}px)`;
            }
            return null;
        },
        getInitialState: (target) => {
            return target?.closest('.conversation-item-wrapper')?.classList.contains('swiped') || false;
        },
        onComplete: (target, deltaX) => {
            const wrapper = target.closest('.conversation-item-wrapper');
            if (!wrapper) return;

            const isOpen = wrapper.classList.contains('swiped');
            if (isOpen && deltaX < -SWIPE_THRESHOLD) {
                // Swiped right to close
                wrapper.classList.remove('swiped');
            } else if (!isOpen && deltaX > SWIPE_THRESHOLD) {
                // Swiped left to open
                resetSwipeStates(wrapper);
                wrapper.classList.add('swiped');
            }
        },
        onSnapBack: (target) => {
            const wrapper = target.closest('.conversation-item-wrapper');
            if (wrapper) {
                wrapper.classList.remove('swiped');
            }
        },
        threshold: SWIPE_THRESHOLD,
        maxDistance: SWIPE_DISTANCE
    });

    elements.conversationsList.addEventListener('touchstart', conversationSwipe.handleTouchStart, { passive: true });
    elements.conversationsList.addEventListener('touchmove', conversationSwipe.handleTouchMove, { passive: true });
    elements.conversationsList.addEventListener('touchend', (e) => {
        const handled = conversationSwipe.handleTouchEnd(e);
        // If it was a tap (not handled by swipe), handle as conversation interaction
        if (handled === false) {
            handleConversationInteraction(e);
        }
    }, { passive: true });

    // Close swipe when tapping elsewhere (touch and click)
    function handleOutsideClick(e) {
        if (!e.target.closest('.conversation-item-wrapper')) {
            resetSwipeStates();
        }
    }
    document.addEventListener('touchstart', handleOutsideClick, { passive: true });
    document.addEventListener('click', handleOutsideClick);

    // Swipe to open/close sidebar on touch devices
    const SIDEBAR_SWIPE_EDGE_THRESHOLD = 50; // Pixels from left edge to trigger
    const SIDEBAR_SWIPE_THRESHOLD = 50; // Minimum swipe distance
    const SIDEBAR_WIDTH = 280; // Match CSS variable

    // Only enable on mobile (touch devices)
    if (window.matchMedia('(hover: none)').matches) {
        const sidebarSwipe = createSwipeHandler({
            shouldStart: (e) => {
                // Don't start if touching on a conversation item (let conversation swipe handle it)
                // This prevents conflicts when trying to swipe conversations
                if (e.target.closest('.conversation-item-wrapper') ||
                    e.target.closest('.conversations-list')) {
                    return false;
                }

                const isOpen = elements.sidebar.classList.contains('open');
                // Start if touching near left edge and sidebar is closed, or if sidebar is open (can close from main content)
                return (e.touches[0].clientX <= SIDEBAR_SWIPE_EDGE_THRESHOLD && !isOpen) || isOpen;
            },
            getTarget: () => elements.sidebar,
            getTransform: (deltaX, isOpen, { maxDistance }) => {
                // Generic handler uses: deltaX = swipeStartX - swipeCurrentX (negative when swiping right)
                // For sidebar: we need positive deltaX for right swipe, so invert
                const actualDeltaX = -deltaX;

                if (!isOpen && actualDeltaX > 0) {
                    // Swiping right to open - sidebar starts at -100%, move it based on swipe
                    const translateX = Math.min(-maxDistance + actualDeltaX, 0);
                    return `translateX(${translateX}px)`;
                } else if (isOpen && actualDeltaX < 0) {
                    // Swiping left to close - sidebar starts at 0, move it left
                    const translateX = Math.max(actualDeltaX, -maxDistance);
                    return `translateX(${translateX}px)`;
                }
                return null;
            },
            getInitialState: () => elements.sidebar.classList.contains('open'),
            onSwipeMove: (target, deltaX, progress) => {
                // Show overlay with opacity based on swipe progress
                let overlay = document.querySelector('.sidebar-overlay');
                if (!overlay) {
                    overlay = document.createElement('div');
                    overlay.className = 'sidebar-overlay';
                    overlay.onclick = closeSidebar;
                    elements.app.appendChild(overlay);
                }
                overlay.style.display = 'block';
                const isOpen = elements.sidebar.classList.contains('open');
                const opacity = isOpen ? (1 - progress) * 0.5 : progress * 0.5;
                overlay.style.opacity = opacity.toString();
            },
            onComplete: (target, deltaX) => {
                // Invert deltaX for sidebar direction
                const actualDeltaX = -deltaX;
                const isOpen = elements.sidebar.classList.contains('open');

                if (!isOpen && actualDeltaX > SIDEBAR_SWIPE_THRESHOLD) {
                    toggleSidebar();
                } else if (isOpen && actualDeltaX < -SIDEBAR_SWIPE_THRESHOLD) {
                    closeSidebar();
                }
            },
            onSnapBack: (target) => {
                const isOpen = elements.sidebar.classList.contains('open');
                if (isOpen) {
                    target.style.transform = 'translateX(0)';
                } else {
                    target.style.transform = 'translateX(-100%)';
                    const overlay = document.querySelector('.sidebar-overlay');
                    if (overlay) {
                        // Clear inline styles to let CSS classes control visibility
                        overlay.style.display = '';
                        overlay.style.opacity = '';
                        overlay.classList.remove('visible');
                    }
                }
            },
            threshold: SIDEBAR_SWIPE_THRESHOLD,
            maxDistance: SIDEBAR_WIDTH
        });

        document.addEventListener('touchstart', sidebarSwipe.handleTouchStart, { passive: true });
        document.addEventListener('touchmove', sidebarSwipe.handleTouchMove, { passive: true });
        document.addEventListener('touchend', sidebarSwipe.handleTouchEnd, { passive: true });
    }

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
