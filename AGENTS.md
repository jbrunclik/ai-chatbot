# AI Chatbot - Claude Context

This file contains context for Claude Code to work effectively on this project.

## Quick Reference

- **Dev**: `make dev` (runs Flask + Vite concurrently)
- **Build**: `make build` (production build)
- **Lint**: `make lint` (ruff + mypy + eslint)
- **Test**: `make test` (run all tests)
- **Setup**: `make setup` (venv + deps)
- **Help**: `make` (show all targets)

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
│   │   └── tools.py              # Agent tools (fetch_url, web_search, generate_image)
│   ├── db/
│   │   └── models.py             # SQLite: User, Conversation, Message
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
- **Test all UI changes on both desktop and mobile** - The app has a responsive layout with different behavior at 768px breakpoint. Always verify changes work on both layouts.

## Pre-Commit Checklist

**Before committing any changes, you MUST run:**

```bash
make lint   # Run all linters (ruff, mypy, eslint)
make test   # Run all tests
```

Both commands must pass without errors. If linting fails, run `make lint-fix` to auto-fix issues where possible.

**When implementing new features:**
- Add tests for new backend code to maintain coverage
- Place unit tests in `tests/unit/` and integration tests in `tests/integration/`
- Use existing fixtures from `tests/conftest.py` where applicable
- Mock all external services (never make real API calls in tests)

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
3. **Backend extracts sources**: `extract_metadata_from_response()` in [chat_agent.py](src/agent/chat_agent.py) parses and strips the metadata block. It handles both HTML comment format (preferred) and plain JSON format (fallback), removing both if the LLM outputs metadata in both formats
4. **Streaming filters metadata**: During streaming, the HTML comment metadata marker is detected and not sent to the frontend. Any plain JSON metadata that slips through is cleaned in the final buffer check
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

The metadata block is always at the end of the LLM response and is stripped before storing/displaying content. Sometimes the LLM outputs plain JSON metadata (without HTML comments) instead of or in addition to the HTML comment format. The extraction function handles both formats, preferring HTML comment format but removing both if present.

## Image Generation

The app can generate images using Gemini's image generation model (`gemini-3-pro-image-preview`).

### How it works
1. **Tool available**: `generate_image(prompt, aspect_ratio)` tool in [tools.py](src/agent/tools.py)
2. **Tool returns JSON**: Returns `{"prompt": "...", "image": {"data": "base64...", "mime_type": "image/png"}}`
3. **LLM appends metadata**: System prompt instructs LLM to include `"generated_images": [{"prompt": "..."}]` in the metadata block
4. **Backend extracts images**: `extract_generated_images_from_tool_results()` in [routes.py](src/api/routes.py) parses tool results
5. **Images stored as files**: Generated images are stored as file attachments on the message
6. **Metadata stored in DB**: Messages table has a `generated_images` column (JSON array)
7. **UI shows sparkles button**: A sparkles icon appears in message actions when generated images exist, opening a popup showing the prompt used and the cost of image generation (excluding prompt tokens)

### Key files
- [tools.py](src/agent/tools.py) - `generate_image()` tool using google-genai SDK
- [chat_agent.py](src/agent/chat_agent.py) - System prompt with metadata instructions, tool result capture during streaming
- [models.py](src/db/models.py) - `Message.generated_images` field
- [routes.py](src/api/routes.py) - Image extraction from tool results, API responses
- [ImageGenPopup.ts](web/src/components/ImageGenPopup.ts) - Popup showing generation info
- [InfoPopup.ts](web/src/components/InfoPopup.ts) - Generic popup component used by both sources and image gen
- [Messages.ts](web/src/components/Messages.ts) - Sparkles button rendering

### Metadata format
The metadata block supports both sources and generated_images:
```
<!-- METADATA:
{"sources": [...], "generated_images": [{"prompt": "..."}]}
-->
```

### Aspect ratios
Supported: `1:1` (default), `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`

### Tool result handling
Tool results (including generated images) are returned from both `chat_batch()` and `stream_chat()` methods but are **not persisted** to the database. This is intentional:
1. **Prevents state bloat**: Generated images are large base64 blobs that would grow the state rapidly
2. **Ensures fresh tool calls**: If tool results were persisted, the LLM might skip calling `generate_image` for follow-up requests, thinking the tool was already called
3. **Conversation context is sufficient**: The human/AI message history stored in the `messages` table provides enough context for multi-turn conversations

The `chat_batch()` method returns `(response_text, tool_results, usage_info)`. The batch and streaming endpoints extract images from `tool_results` for storage, then discard the tool results themselves.

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

1. **PWA viewport height** - In a PWA (no address bar), use `position: fixed; inset: 0` on the root container (`#app`) to fill the viewport. The flex children (sidebar and main panel) should use `align-self: stretch` (default) to fill the container height. Avoid explicit `height: 100vh` or `height: 100%` on flex children - let flexbox handle it naturally. See [main.css](web/src/styles/main.css) for the working implementation.

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

### Token Usage Optimization

The app implements several optimizations to minimize token costs:

1. **History files excluded**: When building conversation history for the LLM, files (images, PDFs) from previous messages are NOT re-sent. Only the current message's files are included. This prevents large base64 data from being sent repeatedly with every request.

2. **Generated images not sent back to LLM**: When the `generate_image` tool runs, the full image data (~500KB base64) is stored in a `_full_result` field that gets stripped before the tool result goes back to the LLM. The LLM only sees a success confirmation message. This prevents ~650K tokens of base64 from being charged on every image generation.

**How the `_full_result` stripping works:**
1. `generate_image` tool returns JSON with `_full_result.image` containing the base64 image data
2. A custom tool node wrapper (`create_tool_node()`) intercepts tool results before they go to the LLM
3. The wrapper captures the FULL tool results (with `_full_result`) in a global dict keyed by request ID
4. It then strips `_full_result` from the tool message content before the LLM sees it
5. After the LLM finishes, the routes layer retrieves the full results using `get_full_tool_results(request_id)`
6. Images and costs are extracted from the full results for storage and display

**Threading considerations for streaming:**
- The streaming endpoint uses a background thread for LLM streaming
- Context variables (used to track request ID) don't automatically inherit to new threads in Python
- The background thread explicitly calls `set_current_request_id()` to set up its own context

**Implementation details:**
- [tools.py](src/agent/tools.py) - `generate_image` returns image in `_full_result` field
- [chat_agent.py](src/agent/chat_agent.py) - `create_tool_node()` wraps ToolNode to strip `_full_result`, `set_current_request_id()` and `get_full_tool_results()` for per-request capture
- [images.py](src/utils/images.py) - `extract_generated_images_from_tool_results()` extracts images from `_full_result`
- [routes.py](src/api/routes.py) - Sets request ID before agent call, retrieves full results after, passes to image extraction and cost calculation

### Scroll-to-Bottom Behavior

The app automatically scrolls to the bottom when loading conversations and when new messages are added, but handles lazy-loaded images specially to avoid scrolling before images have loaded and affected the layout.

**How it works:**
1. **Initial conversation load**: When `renderMessages()` is called, it checks if there are images that need to be loaded from the server
2. **Skip immediate scroll**: If images need loading and scroll-on-image-load is enabled, the immediate scroll is skipped
3. **Track image loads**: Each image that starts loading increments a `pendingImageLoads` counter
4. **Wait for completion**: The code waits for each image's `load` event (not just the fetch) to ensure it has fully rendered
5. **Debounced smooth scroll**: When all images finish loading (`pendingImageLoads === 0`), a smooth scroll animation is triggered after layout has settled
6. **Smooth animation**: Uses custom ease-out-cubic easing with duration based on scroll distance (300-600ms)

**New message additions (batch and streaming):**
When a new message with images is added (via `sendBatchMessage()` or `finalizeStreamingMessage()`):
- Checks if the message has images that need loading (images without `previewUrl`)
- Checks if user was already at the bottom (`isScrolledToBottom()`)
- If both conditions are true: enables `scrollOnImageLoad()` so images are tracked when observed
- **Batch mode**: Message is added via `addMessageToUI()` (images are created and observed synchronously)
- **Streaming mode**: Images are added via `renderMessageFiles()` in `finalizeStreamingMessage()` (images are created and observed synchronously)
- Scrolls to bottom immediately (non-smooth) to ensure images are visible
- Uses double `requestAnimationFrame` to ensure scroll completed and layout settled
- Fallback: Checks if images are visible but haven't started loading, and re-observes them to trigger intersection check
- IntersectionObserver fires for visible images (either immediately or after re-observation)
- Scroll happens automatically after all images finish loading
- If no images or user wasn't at bottom: scrolls immediately (if at bottom)

**Smooth scroll implementation:**
- Custom animation in `scrollToBottom()` with ease-out-cubic easing
- Used both for button clicks and automatic scrolls after image loading
- Prevents abrupt flashing when images load and push content down

**Key files:**
- [thumbnails.ts](web/src/utils/thumbnails.ts) - Image load tracking, `enableScrollOnImageLoad()`, `scheduleScrollAfterImageLoad()`
- [dom.ts](web/src/utils/dom.ts) - `scrollToBottom()` with smooth animation, `isScrolledToBottom()`
- [Messages.ts](web/src/components/Messages.ts) - `renderMessages()` skips immediate scroll when images need loading
- [main.ts](web/src/main.ts) - `sendBatchMessage()` handles scroll logic for new messages with images
- [ScrollToBottom.ts](web/src/components/ScrollToBottom.ts) - Button component that triggers smooth scroll

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

## Cost Tracking

The app tracks API costs per conversation and per user per calendar month, accounting for token usage and image generation.

### How it works
1. **Token usage tracking**: Token counts are extracted from `usage_metadata` in LangChain's `AIMessage` and `AIMessageChunk` objects (both batch and streaming modes)
2. **Image generation costs**: Image generation costs are calculated from `usage_metadata` returned by the Gemini image generation API
3. **Cost calculation**: Costs are calculated using model pricing from [config.py](src/config.py) and converted to the configured currency (default: CZK)
4. **Database storage**: Costs are stored in the `message_costs` table with token counts and total cost in USD
5. **UI display**:
   - Conversation cost is shown under the input box (updates after each message)
   - Monthly cost is shown in the sidebar footer (clickable to view history)
   - Cost history popup shows monthly breakdown with total
   - Message cost button (dollar icon) appears on assistant messages, opening a popup with detailed cost breakdown
   - Image generation popup shows the cost of image generation only (excluding prompt tokens)

### Key files
- [costs.py](src/utils/costs.py) - Cost calculation and currency conversion utilities
- [config.py](src/config.py) - Model pricing (`MODEL_PRICING`) and currency rates (`CURRENCY_RATES`)
- [models.py](src/db/models.py) - `save_message_cost()`, `get_message_cost()`, `get_conversation_cost()`, `get_user_monthly_cost()`, `get_user_cost_history()` (note: `delete_conversation()` intentionally preserves cost data for accurate reporting)
- [chat_agent.py](src/agent/chat_agent.py) - Token usage extraction from `usage_metadata` (memory efficient - only tracks numbers, not message objects)
- [tools.py](src/agent/tools.py) - Image generation tool includes `usage_metadata` in response
- [api/utils.py](src/api/utils.py) - `calculate_and_save_message_cost()` centralizes cost calculation and saving for both batch and streaming, `calculate_image_generation_cost_from_tool_results()` extracts image costs from tool results
- [routes.py](src/api/routes.py) - Calls `calculate_and_save_message_cost()` in batch/stream endpoints, cost API endpoints (`/api/messages/<message_id>/cost`, `/api/conversations/<conv_id>/cost`, `/api/users/me/costs/*`)
- [main.ts](web/src/main.ts) - `updateConversationCost()` updates cost display after messages
- [CostHistoryPopup.ts](web/src/components/CostHistoryPopup.ts) - Cost history popup component
- [MessageCostPopup.ts](web/src/components/MessageCostPopup.ts) - Message cost popup component
- [ImageGenPopup.ts](web/src/components/ImageGenPopup.ts) - Image generation popup (shows image generation cost)
- [Sidebar.ts](web/src/components/Sidebar.ts) - Monthly cost display in footer
- [Messages.ts](web/src/components/Messages.ts) - Cost button rendering in message actions

### Cost calculation details
- **Token costs**: Calculated from `input_tokens` and `output_tokens` using per-million-token pricing
- **Image generation costs**: Calculated from `usage_metadata` with separate pricing for prompt tokens (input) and candidate/thought tokens (output). Stored separately in `image_generation_cost_usd` column for display in image generation popup
- **Other tools**: Web search and URL fetching are free (no cost tracking)
- **Currency conversion**: Costs are stored in USD, converted to display currency (configurable via `COST_CURRENCY` env var)

### Database schema
The `message_costs` table stores:
- `cost_usd`: Total cost (tokens + image generation)
- `image_generation_cost_usd`: Cost of image generation only (separate from token costs)
- Token counts and model information for detailed breakdown

### Memory efficiency
Token usage is tracked efficiently during streaming by extracting and accumulating counts immediately from each chunk, rather than storing entire message objects. Only the final token counts are kept in memory.

### Configuration
- `COST_CURRENCY`: Display currency (default: `CZK`)
- `MODEL_PRICING`: Model pricing per million tokens (in [config.py](src/config.py))
- `CURRENCY_RATES`: Exchange rates for currency conversion (in [config.py](src/config.py))

**Note**: Currency rates and model pricing are currently hardcoded in `config.py`. See [TODO.md](TODO.md) for planned automated updates.

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

## Testing

The project has comprehensive test suites for both backend (227 tests, 72% coverage) and frontend (125 Vitest + 114 Playwright tests).

### Backend Test Structure

```
tests/
├── conftest.py                    # Shared fixtures (database, app, auth, mocks)
├── fixtures/
│   └── images.py                  # Test image generators
├── mocks/
│   └── gemini.py                  # Mock LLM response builders
├── unit/                          # Unit tests (isolated function testing)
│   ├── test_costs.py              # Cost calculations
│   ├── test_jwt_auth.py           # JWT token handling
│   ├── test_google_auth.py        # Google token verification
│   ├── test_chat_agent_helpers.py # Agent helper functions
│   ├── test_images.py             # Image processing
│   └── test_tools.py              # Agent tools (mocked externals)
├── integration/                   # Integration tests (multi-component)
│   ├── test_db_models.py          # Database CRUD operations
│   ├── test_routes_auth.py        # Auth endpoints
│   ├── test_routes_conversations.py  # Conversation CRUD
│   ├── test_routes_chat.py        # Chat endpoints
│   └── test_routes_costs.py       # Cost tracking endpoints
└── e2e-server.py                  # Mock Flask server for E2E tests (with SSE streaming)
```

### Frontend Test Structure

```
web/tests/
├── global-setup.ts                # Playwright test setup (DB reset before each test)
├── unit/                          # Vitest unit tests (101 tests)
│   ├── setup.ts                   # Test setup (jsdom config)
│   ├── api-client.test.ts         # API client utilities
│   ├── dom.test.ts                # DOM utilities (escapeHtml, scrollToBottom)
│   └── store.test.ts              # Zustand store
├── component/                     # Component tests with jsdom (24 tests)
│   └── Sidebar.test.ts            # Sidebar interactions
├── e2e/                           # Playwright E2E tests (42 tests × 2 browsers = 84)
│   ├── auth.spec.ts               # Authentication flow
│   ├── chat.spec.ts               # Chat functionality (batch + streaming)
│   ├── conversation.spec.ts       # Conversation CRUD
│   └── mobile.spec.ts             # Mobile viewport tests
└── visual/                        # Visual regression tests (15 tests × 2 browsers = 30)
    ├── chat.visual.ts             # Chat interface screenshots
    └── mobile.visual.ts           # Mobile layout screenshots
```

### Key Testing Patterns

**Backend:**
- **Isolated SQLite per test**: Each test gets its own database file for complete isolation
- **Mocked external services**: Gemini LLM, Google Auth, DuckDuckGo, httpx are all mocked
- **Shared fixtures**: Use `test_user`, `test_conversation`, `auth_headers` from conftest.py
- **Flask test client**: Use the `client` fixture for HTTP testing

**Frontend:**
- **Vitest for unit/component tests**: Fast, TypeScript-native, uses jsdom for DOM simulation
- **Playwright for E2E tests**: Real browser testing (chromium, webkit), mock server
- **E2E test isolation**: Each test resets database via `/test/reset` endpoint
- **Mock LLM server**: `tests/e2e-server.py` runs Flask with mocked Gemini responses
- **E2E auth bypass**: Tests set `E2E_TESTING=true` to skip auth (separate from unit test mode)

### Running Tests

```bash
# Backend tests
make test              # Run all backend tests (227 tests)
make test-unit         # Run unit tests only
make test-integration  # Run integration tests only
make test-cov          # Run with coverage report

# Frontend tests (from project root)
make test-fe           # Run unit + component + E2E tests (functional tests)
make test-fe-unit      # Run Vitest unit tests (101 tests)
make test-fe-component # Run component tests (24 tests)
make test-fe-e2e       # Run Playwright E2E tests (84 tests)
make test-fe-visual    # Run visual regression tests (30 tests) - see below
make test-fe-watch     # Run Vitest in watch mode

# All tests
make test-all          # Run backend + frontend (excl. visual)
```

**Note on Visual Tests**: Visual tests are intentionally excluded from `make test-fe` because they:
- Compare screenshots pixel-by-pixel and can fail due to font rendering differences
- Require baseline updates when UI changes intentionally
- Run slower than functional tests

Run visual tests separately after intentional UI changes:
```bash
make test-fe-visual         # Run and compare against baselines
make test-fe-visual-update  # Update baselines after UI changes
```

### Writing New Tests

**Backend:**
1. Add unit tests for pure functions in `tests/unit/`
2. Add integration tests for API endpoints in `tests/integration/`
3. Use existing mock fixtures from `conftest.py` (e.g., `mock_gemini_llm`, `mock_google_tokeninfo`)
4. Never make real API calls - mock at the right level

**Frontend:**
1. Add unit tests for utilities in `web/tests/unit/`
2. Add component tests in `web/tests/components/` (use jsdom for DOM simulation)
3. Add E2E tests in `web/tests/e2e/` for user workflows
4. Use `global-setup.ts` fixtures for isolated test state
5. For mobile tests, use `test.use({ viewport: { width: 375, height: 812 } })`
6. Both batch and streaming modes are fully supported by the mock server

### E2E Test Server

The E2E test server (`tests/e2e-server.py`) is a Flask app that mocks external services:

- **Mock LLM**: Returns mock responses with proper AIMessage objects for LangGraph
- **SSE Streaming**: Custom endpoint streams tokens word-by-word via Server-Sent Events
- **Auth bypass**: `E2E_TESTING=true` skips Google auth and JWT validation
- **Database reset**: `/test/reset` endpoint clears database between tests
- **Isolated DB**: Each test run uses a unique database file

To run E2E tests manually:
```bash
# Terminal 1: Start mock server
cd web && python ../tests/e2e-server.py

# Terminal 2: Run tests
cd web && npx playwright test
```

### Visual Regression Tests

Visual tests capture screenshots and compare against baselines. Use them to verify UI changes haven't broken anything unintentionally.

```bash
make test-fe-visual           # Run visual tests against baselines
make test-fe-visual-update    # Update baselines after intentional UI changes
```

**Baseline locations:**
- `web/tests/visual/chat.visual.ts-snapshots/` - Desktop chat interface
- `web/tests/visual/mobile.visual.ts-snapshots/` - Mobile/iPad layouts

**When to run visual tests:**
- After making CSS changes
- After modifying component structure
- After changing responsive breakpoints
- Before committing UI changes (to verify no regressions)

**When to update baselines:**
- After intentional UI changes (run `make test-fe-visual-update`)
- Commit the new baseline screenshots with your UI changes

**Troubleshooting visual test failures:**
- Check `web/playwright-report/index.html` for diff images
- Ensure tests run with consistent viewport sizes
- Font rendering differences between machines can cause false failures

## Related Files

- [TODO.md](TODO.md) - Memory bank for planned work
- [README.md](README.md) - User-facing documentation

## Structured Logging

The application uses structured JSON logging for easy integration with Loki or other log aggregation systems. All logs include request IDs for correlation.

### Configuration

- **LOG_LEVEL**: Environment variable controlling log verbosity (default: `INFO`)
  - Valid levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  - Set via `.env` file: `LOG_LEVEL=DEBUG`

### Log Format

All logs are JSON-formatted with the following structure:
```json
{
  "timestamp": "2024-01-01 12:00:00",
  "level": "INFO",
  "logger": "src.api.routes",
  "message": "Batch chat request",
  "request_id": "abc-123-def",
  "user_id": "user-123",
  "conversation_id": "conv-456"
}
```

### Request IDs

Every request automatically gets a unique request ID:
- Generated as UUID if not provided in `X-Request-ID` header
- Included in all log entries for that request
- Enables correlation of logs across the request lifecycle

### Logging Guidelines

**When adding new code, always add appropriate logging:**

1. **INFO level**: Important operations that happen per-request
   - Request start/completion
   - Successful authentication
   - Conversation creation/deletion
   - Chat completions

2. **DEBUG level**: Detailed information for troubleshooting
   - Function entry/exit
   - Intermediate state values
   - Payload snippets (use `log_payload_snippet()` helper)
   - Database operations

3. **WARNING level**: Unusual but recoverable situations
   - Validation failures
   - Missing optional data
   - Retryable errors

4. **ERROR level**: Failures that need attention
   - Exceptions (always use `exc_info=True`)
   - Failed operations
   - System errors

**Best Practices:**
- Use structured logging with `extra` dict for context
- Include relevant IDs (user_id, conversation_id, message_id) in logs
- Log payload snippets for debugging (but truncate large data)
- Always log exceptions with `exc_info=True`
- Use appropriate log levels - don't spam INFO with debug details

**Example:**
```python
from src.utils.logging import get_logger, log_payload_snippet

logger = get_logger(__name__)

def my_function(user_id: str, data: dict) -> None:
    logger.debug("Function called", extra={"user_id": user_id})
    log_payload_snippet(logger, data)

    try:
        # ... do work ...
        logger.info("Operation completed", extra={"user_id": user_id, "result": result})
    except Exception as e:
        logger.error("Operation failed", extra={"user_id": user_id, "error": str(e)}, exc_info=True)
        raise
```

### Key Logging Points

- **Routes**: All endpoints log request/response with status codes
- **Agent**: LLM invocations, tool calls, response extraction
- **Tools**: Tool execution start/completion, errors
- **Database**: CRUD operations, state saves
- **Auth**: Token validation, user lookups
- **File processing**: Validation, thumbnail generation

## PWA Viewport Height Fix

The app uses a specific layout approach to ensure the sidebar and main panel fill 100% of the screen height in PWA mode (no address bar, full screen).

### The Problem

Initially, the app had gaps at the bottom of the sidebar and main panel, especially when the keyboard opened/closed. Various approaches were tried (JavaScript viewport fixes, `100vh`, `100dvh`, `100svh`, explicit heights) but none worked reliably.

### The Solution

The final working solution uses:
1. **Root container**: `#app` with `position: fixed; inset: 0` - this naturally fills the viewport without needing explicit height
2. **Flex children**: Sidebar and main panel use `align-self: stretch` (default flexbox behavior) to fill the container height
3. **No explicit heights**: Avoid `height: 100%` or `height: 100vh` on flex children - let flexbox handle it

### Key Implementation Details

```css
#app {
    display: flex;
    position: fixed;
    inset: 0;  /* Fills viewport naturally */
    overflow: hidden;
}

.sidebar {
    display: flex;
    flex-direction: column;
    align-self: stretch;  /* Fills parent height */
    /* No explicit height needed */
}

.main {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-self: stretch;  /* Fills parent height */
    /* No explicit height needed */
}
```

### Why This Works

- `position: fixed; inset: 0` makes `#app` fill the viewport regardless of parent height
- Flexbox's default `align-items: stretch` (on flex container) makes children fill cross-axis (height)
- No JavaScript needed - pure CSS solution
- Works consistently in PWA mode where there's no address bar

### Layout Jump Prevention

The conversation cost display below the input area has `min-height: 16px` and is never hidden (no `:empty { display: none }`). This prevents layout jumping when the cost updates or when switching between conversations with/without costs.

**Key files:**
- [main.css](web/src/styles/main.css) - Layout structure and conversation cost display styling

## Documentation Maintenance

When making significant changes to the codebase:
1. Update [README.md](README.md) if user-facing features change
2. Update this file (AGENTS.md) if architecture, code patterns, or developer workflows change
3. Update [TODO.md](TODO.md) to mark completed items or add new planned work

**Important**: When implementing a new feature, always update documentation as part of the commit - don't wait to be asked. For significant features, add a dedicated section to AGENTS.md explaining how it works, key files, and any testing/debugging tips.

**When adding new code, always add appropriate logging** - see the Structured Logging section above for guidelines.

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