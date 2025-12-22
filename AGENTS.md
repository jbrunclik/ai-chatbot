# AI Chatbot - Claude Context

This file contains context for Claude Code to work effectively on this project.

## Quick Reference

- **Dev**: `make dev` (runs Flask + Vite concurrently)
- **Build**: `make build` (production build)
- **Lint**: `make lint` (ruff + mypy)
- **Setup**: `make setup` (venv + deps)

## Project Structure

```
ai-chatbot/
├── src/                          # Flask backend
│   ├── app.py                    # Flask entry point, Vite manifest loading
│   ├── config.py                 # Environment config
│   ├── templates/
│   │   └── index.html            # Jinja2 shell (meta tags, asset injection)
│   ├── auth/
│   │   ├── jwt_auth.py           # JWT token handling, @require_auth decorator
│   │   └── google_auth.py        # GIS token validation, email whitelist
│   ├── api/
│   │   └── routes.py             # REST endpoints (/api/*, /auth/*)
│   ├── agent/
│   │   ├── chat_agent.py         # LangGraph agent with Gemini
│   │   └── tools.py              # Web tools (fetch_url, web_search)
│   ├── db/
│   │   └── models.py             # SQLite: User, Conversation, Message, AgentState
│   └── utils/
│       └── images.py             # Thumbnail generation (Pillow)
├── web/                          # Vite + TypeScript frontend
│   ├── vite.config.ts            # Vite config with Flask proxy
│   ├── tsconfig.json             # TypeScript config
│   ├── package.json              # Frontend dependencies
│   └── src/
│       ├── main.ts               # Entry point, app shell, event wiring
│       ├── types/                # TypeScript interfaces
│       │   ├── api.ts            # API response types
│       │   └── google.d.ts       # Google Identity Services types
│       ├── api/client.ts         # Typed fetch wrapper, streaming
│       ├── auth/google.ts        # Google Sign-In, JWT handling
│       ├── state/store.ts        # Zustand store
│       ├── components/           # UI modules
│       │   ├── Sidebar.ts        # Conversation list
│       │   ├── Messages.ts       # Message rendering
│       │   ├── MessageInput.ts   # Input area, file preview
│       │   ├── ModelSelector.ts  # Model dropdown
│       │   ├── FileUpload.ts     # File handling, base64
│       │   ├── VoiceInput.ts     # Speech-to-text input
│       │   ├── Lightbox.ts       # Image viewer
│       │   ├── ScrollToBottom.ts # Scroll-to-bottom button
│       │   └── VersionBanner.ts  # New version notification
│       ├── gestures/swipe.ts     # Touch handlers
│       ├── utils/
│       │   ├── dom.ts            # DOM helpers, escapeHtml
│       │   ├── markdown.ts       # marked + highlight.js
│       │   ├── thumbnails.ts     # Intersection Observer lazy loading
│       │   └── icons.ts          # SVG icon constants
│       └── styles/main.css       # Dark theme, responsive layout
└── static/                       # Build output + PWA assets
    ├── assets/                   # Vite output (hashed JS/CSS)
    ├── manifest.json
    └── icons/
```

## Key Files

- [config.py](src/config.py) - All env vars, model definitions
- [routes.py](src/api/routes.py) - API endpoints
- [chat_agent.py](src/agent/chat_agent.py) - LangGraph graph, Gemini integration
- [models.py](src/db/models.py) - Database schema and operations
- [images.py](src/utils/images.py) - Thumbnail generation for uploaded images
- [main.ts](web/src/main.ts) - Frontend entry point
- [store.ts](web/src/state/store.ts) - Zustand state management

## Development Workflow

### Local Development
```bash
make dev  # Runs Flask (8000) + Vite (5173) concurrently
```
- Vite dev server proxies API calls to Flask
- HMR enabled for instant CSS/JS updates
- TypeScript type checking on save

### Production Build
```bash
make build  # Outputs to static/assets/
```
- Vite generates hashed filenames for cache busting
- Flask reads manifest.json to inject correct asset paths

### Deployment (Hetzner)
systemd runs `npm install && npm run build` via ExecStartPre before starting gunicorn.

## Gemini API Notes

### Models
- `gemini-3-pro-preview` - Complex tasks, advanced reasoning
- `gemini-3-flash-preview` - Fast, cheap (default)

### Response Format
Gemini may return content in various formats:
- String: `"response text"`
- List: `[{'type': 'text', 'text': '...', 'extras': {...}}]`
- Dict: `{'type': 'text', 'text': '...'}`

Use `extract_text_content()` in [chat_agent.py](src/agent/chat_agent.py) to normalize.

### Parameters
- `thinking_level`: Controls reasoning (minimal/low/medium/high)
- Temperature: Keep at 1.0 (Gemini 3 default)

## Auth Flow

Uses Google Identity Services (GIS) for client-side authentication:

1. `FLASK_ENV=development` → Skip all auth, use "local@localhost" user
2. Otherwise:
   - Frontend loads GIS library and renders "Sign in with Google" button
   - User clicks → Google popup → Returns ID token to frontend
   - Frontend sends token to `POST /auth/google`
   - Backend validates token via Google's tokeninfo endpoint
   - Backend checks email whitelist, returns JWT
   - Frontend stores JWT for subsequent API calls

## Code Style

- Type hints in all Python code
- TypeScript for all frontend code (strict mode)
- Conventional Commits: `type(scope): description`
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Run `make lint` before committing
- **Test all UI changes on both desktop and mobile** - The app has a responsive layout with different behavior at 768px breakpoint. Always verify changes work on both layouts.

## Input Toolbar

The input area has a toolbar row above the textarea with controls:

```
[Model dropdown] [Stream] [Search]              [Mic] [Attach]
┌────────────────────────────────────────────────────────────┐
│ Textarea                                          [Send]   │
└────────────────────────────────────────────────────────────┘
```

- **Model selector**: Dropdown to switch between Gemini models
- **Stream toggle**: Enable/disable streaming responses (persisted to localStorage)
- **Search toggle**: One-shot button to force `web_search` tool for the next message only
- **Mic**: Voice input (see Voice Input section below)
- **Attach**: File upload

### Force Tools System

The `forceTools` state in Zustand allows forcing specific tools to be used. Currently only `web_search` is exposed via UI, but the system supports any tool name. The force tools instruction is added to the system prompt when tools are specified.

- Frontend: `store.forceTools: string[]` with `toggleForceTool(tool)` and `clearForceTools()`
- Backend: `force_tools` parameter in `/chat/batch` and `/chat/stream` endpoints
- Agent: `get_force_tools_prompt()` in [chat_agent.py](src/agent/chat_agent.py)

## Web Search Sources

When the LLM uses `web_search` or `fetch_url` tools, it cites sources that are displayed to the user.

### How it works
1. **Tool returns JSON**: `web_search` returns `{"query": "...", "results": [{title, url, snippet}, ...]}` instead of plain text
2. **LLM appends metadata**: System prompt instructs LLM to append `<!-- METADATA:\n{"sources": [...]}\n-->` at the end of responses when web tools are used
3. **Backend extracts sources**: `extract_metadata_from_response()` in [chat_agent.py](src/agent/chat_agent.py) parses and strips the metadata block
4. **Streaming filters metadata**: During streaming, the metadata marker is detected and not sent to the frontend
5. **Sources stored in DB**: Messages table has a `sources` column (JSON array)
6. **Sources in API response**: Both batch and streaming responses include `sources` array
7. **UI shows sources button**: A globe icon appears in message actions when sources exist, opening a popup with clickable links

### Key files
- [tools.py](src/agent/tools.py) - `web_search()` returns structured JSON
- [chat_agent.py](src/agent/chat_agent.py) - `TOOLS_SYSTEM_PROMPT`, `extract_metadata_from_response()`, streaming filter
- [models.py](src/db/models.py) - `Message.sources` field, `add_message()` with sources param
- [routes.py](src/api/routes.py) - Sources included in batch/stream responses
- [SourcesPopup.ts](web/src/components/SourcesPopup.ts) - Popup component
- [Messages.ts](web/src/components/Messages.ts) - Sources button rendering

### Metadata format
```
<!-- METADATA:
{"sources": [{"title": "Source Title", "url": "https://..."}]}
-->
```

The metadata block is always at the end of the LLM response and is stripped before storing/displaying content.

## Voice Input

Voice input uses the Web Speech API (`SpeechRecognition`) in [VoiceInput.ts](web/src/components/VoiceInput.ts):

- **Chrome/Edge**: Uses Google's cloud servers (requires internet, may fail with `network` error behind VPNs/firewalls)
- **Safari (iOS 14.5+/macOS)**: Uses on-device Siri speech recognition (works offline)
- **Firefox**: Not supported (button is hidden)

The button shows a pulsing red indicator while recording. Transcribed text is appended to the textarea in real-time.

**Language selection**: Long-press (500ms) on the microphone button to open a language selector popup. Currently supports English (en-US) and Czech (cs-CZ). The browser's preferred language is shown first if supported. The selected language is persisted to localStorage.

**Auto-stop on send**: Voice recording is automatically stopped when a message is sent (via `stopVoiceRecording()` in `sendMessage()`), preventing transcribed text from being re-added to the cleared input.

## Touch Gestures

The app uses a reusable swipe gesture system (`createSwipeHandler` in [swipe.ts](web/src/gestures/swipe.ts)):

1. **Conversation swipe-to-delete**: Swipe left on a conversation item to reveal delete button, swipe right to close
2. **Sidebar swipe-to-open**: Swipe from left edge (within 50px) to open sidebar, swipe left on main content to close

The swipe handler prevents conflicts by giving priority to more specific gestures (conversation swipes) over global gestures (sidebar edge swipe).

**Important implementation details:**
- All touch handlers include `touchcancel` listeners for iOS Safari, which can cancel touches during system gestures
- The `activeSwipeType` state variable tracks whether a `'conversation'` or `'sidebar'` swipe is in progress to prevent conflicts
- **Critical**: `activeSwipeType` must only be set when actual swiping starts (in `onSwipeMove`), NOT in `shouldStart`. Setting it on touch start causes taps (non-swipes) to block subsequent sidebar swipes since `onComplete`/`onSnapBack` only run when `isSwiping` is true

## iOS Safari Gotchas

When working on mobile/PWA features, beware of these iOS Safari issues:

1. **`100vh` is broken** - Use `height: 100%` on containers instead of `100vh`. iOS Safari calculates `100vh` as if the address bar is hidden, causing content overflow.

2. **Inline `onclick` handlers don't work reliably** - Use event delegation instead of inline `onclick` on dynamically created elements. Attach listeners to parent containers.

3. **PWA caching is aggressive** - Users may need to remove and re-add the app to home screen to see changes. Vite handles cache busting via hashed filenames.

4. **Touch events can be cancelled** - iOS Safari may cancel touch sequences during system gestures (e.g., Control Center swipe, incoming calls). Always handle `touchcancel` events to reset gesture state.

## Performance Optimizations

### Conversation Loading
- **Optimized payload**: `/api/conversations/<conv_id>` only sends file metadata (name, type, messageId, fileIndex), not thumbnails or full file data
- **Thumbnails on demand**: Thumbnails are fetched via `/api/messages/<message_id>/files/<file_index>/thumbnail` when images come into view
- **Full files on demand**: Full files are fetched via `/api/messages/<message_id>/files/<file_index>` when needed (lightbox, downloads)
- **Lazy loading**: Frontend uses Intersection Observer to load thumbnails in parallel as user scrolls
- **Parallel fetching**: Up to 6 thumbnails fetch concurrently when images come into viewport
- **Loading indicators**: Visual feedback during conversation switching and thumbnail loading

### File Handling
- Thumbnails are generated server-side using Pillow (400x400px max) and stored in the database with messages
- Frontend prefers thumbnails over full images for display
- If a thumbnail is missing (e.g., old messages), the full image is fetched from API on-demand when visible
- Native browser lazy loading (`loading="lazy"`) is used for all images
- Parallel fetching: Up to 6 missing images fetch concurrently when they come into viewport

## Version Update Banner

The app detects when a new version is deployed and shows a banner prompting users to reload.

### How it works
1. **Version source**: The Vite JS bundle hash (e.g., `main-y-VVsbiY.js` → `y-VVsbiY`) serves as the version identifier
2. **Initial load**: Flask extracts the version from the Vite manifest and injects it into the HTML via `data-version` attribute on `#app`
3. **Periodic polling**: Frontend polls `GET /api/version` every 5 minutes (no auth required)
4. **PWA awareness**: Polling pauses when tab is hidden (`document.visibilitychange`), checks immediately on refocus if >5 min since last check
5. **Dismiss persistence**: Dismissed versions are stored in localStorage to avoid re-showing the same banner

### Key files
- [app.py](src/app.py) - Extracts version hash from manifest, stores in `app.config["APP_VERSION"]`
- [routes.py](src/api/routes.py) - `GET /api/version` endpoint
- [VersionBanner.ts](web/src/components/VersionBanner.ts) - Banner component and polling logic
- [store.ts](web/src/state/store.ts) - `appVersion`, `newVersionAvailable`, `versionBannerDismissed` state

### Testing locally
In development mode, the version will be `null` (no manifest). Use the test helper in browser console:
```javascript
window.__testVersionBanner()
```

## Common Tasks

### Add a new API endpoint
Edit [routes.py](src/api/routes.py), add route to `api` blueprint.

### Add a new tool to the agent
Edit [tools.py](src/agent/tools.py), add function with `@tool` decorator and add to `TOOLS` list.

### Change available models
Edit [config.py](src/config.py) `MODELS` dict.

### Add a new UI component
1. Create TypeScript file in `web/src/components/`
2. Export init function and render functions
3. Import and wire in `main.ts`

### Add new icons
Add SVG constants to [icons.ts](web/src/utils/icons.ts) and import where needed.

## Related Files

- [TODO.md](TODO.md) - Memory bank for planned work
- [README.md](README.md) - User-facing documentation

## Documentation Maintenance

When making significant changes to the codebase:
1. Update [README.md](README.md) if user-facing features change
2. Update this file (CLAUDE.md) if architecture, code patterns, or developer workflows change
3. Update [TODO.md](TODO.md) to mark completed items or add new planned work

**Important**: When implementing a new feature, always update documentation as part of the commit - don't wait to be asked. For significant features, add a dedicated section to CLAUDE.md explaining how it works, key files, and any testing/debugging tips.

---

## Preferences & Corrections

When I correct Claude's approach, the reasoning is documented here to prevent repeated mistakes.

### Naming

**Preference**: Use "AI Chatbot" consistently (not "AI Chat")
**Context**: Branding consistency across all UI text, meta tags, and documentation

### Directory Structure

**Preference**: Use `web/` for frontend (not `frontend/`)
**Context**: Leaves room for potential native mobile app later (`ios/`, `android/`)

### State Management

**Preference**: Use Zustand for state management
**Context**: Lightweight, TypeScript-first, simpler than Redux. Avoid custom state management solutions.

### Development Server

**Preference**: Use `concurrently` for running multiple dev servers
**Context**: Background processes are hard to manage. `concurrently` shows both outputs clearly and kills both on Ctrl+C.
**Avoid**: Using `&` or background jobs in Makefile

### UI Patterns

**Preference**: Use event delegation for dynamic elements
**Context**: iOS Safari has issues with inline onclick handlers on dynamically created elements
**Avoid**: Inline `onclick` attributes in template strings

### Icons

**Preference**: Centralize SVG icons in [icons.ts](web/src/utils/icons.ts)
**Context**: Prevents duplication across components, makes icons easy to find and update
**Avoid**: Inline SVG in template strings (import from icons.ts instead)

### Constants

**Preference**: Use `DEFAULT_CONVERSATION_TITLE` constant from [api.ts](web/src/types/api.ts)
**Context**: Avoids magic strings scattered across the codebase
**Avoid**: Hardcoding `'New Conversation'` directly in code

### Conversation Creation

**Pattern**: Lazy conversation creation - conversations are created locally with a `temp-` prefixed ID, only persisted to DB on first message
**Location**: [main.ts](web/src/main.ts) - `createConversation()`, `sendMessage()`, `isTempConversation()`
**Rationale**: Prevents empty conversations from polluting the database when users click "New Chat" but don't send any messages