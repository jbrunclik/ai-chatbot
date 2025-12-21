# AI Chatbot - TODO / Memory Bank

This file tracks planned features, improvements, and technical debt.

## Phase 1 - MVP (Current)
- [x] Project structure and configuration
- [x] Flask backend with Gemini integration
- [x] SQLite chat storage
- [x] Google Sign In with email whitelist
- [x] Basic dark theme UI
- [x] Model selection (Pro/Flash)
- [x] Markdown rendering

## Phase 2 - Streaming & Polish
- [x] **Streaming responses** - Display tokens as they arrive from Gemini (with toggle)
- [ ] **Show thinking/tool details** - Display model reasoning and tool execution behind a toggle
- [ ] Improve error handling and user feedback
- [x] **Add loading states and animations** - Conversation loading spinner, thumbnail loading indicators
- [x] Conversation delete functionality
- [ ] Conversation rename functionality
- [x] Mobile gesture support (swipe to open sidebar, swipe to delete conversations)
- [ ] **Version update banner** - Show banner to user when new version is available, prompting to reload the page

## Phase 3 - Tools & Extensions
- [x] **Tool framework** - Extensible system for adding agent tools
- [x] Web search tool (DuckDuckGo)
- [x] URL fetch tool (extract text from web pages)
- [ ] **Forcing search/browser tool** - Allow users to force the agent to use search or browser tools for specific queries
- [ ] Image generation tool (Gemini 3 Pro Image or Imagen)
- [ ] Text-to-speech tool
- [ ] Code execution sandbox
- [x] File upload and processing (images, PDFs, text files)
- [x] **Image thumbnails & lightbox** - Thumbnails in chat, click to view full-size with on-demand loading
- [x] **Performance optimizations** - Optimized conversation payload (metadata only), parallel thumbnail fetching

## Phase 4 - Advanced Features
- [ ] Multiple AI providers (Anthropic Claude, OpenAI)
- [ ] Custom system prompts per conversation
- [ ] Conversation export (JSON, Markdown)
- [ ] Conversation sharing (public links)
- [ ] Keyboard shortcuts
- [ ] Voice input
- [ ] **Voice conversation mode** - Full voice-based conversation with speech-to-text input and text-to-speech output

## Phase 5 - Production Hardening
- [ ] Comprehensive test suite
- [ ] Rate limiting
- [ ] Request logging and monitoring
- [x] Database migrations system (yoyo-migrations)
- [ ] **Cost tracking** - Track API costs per user and per conversation
- [ ] Backup and restore
- [ ] Docker deployment option

## CI/CD & DevOps
- [ ] **GitHub Actions** - Workflow for linting (ruff, mypy) on PRs
- [ ] **Dependabot** - Configuration for automated dependency updates
- [ ] Docker image and docker-compose setup

## Technical Debt
- [x] Add proper database migrations (yoyo-migrations)
- [ ] Add request validation (pydantic or marshmallow)
- [ ] Consider async Flask (quart) for better concurrency
- [ ] Add OpenAPI/Swagger documentation
- [ ] **Store files and thumbnails outside DB** - Move file data and thumbnails to object storage (S3, MinIO, etc.) for better scalability and performance
- [ ] **Split JavaScript into modules** - Break up monolithic app.js into multiple files with a lightweight build system (e.g., esbuild, Vite, or Rollup)
- [x] **Remove test delay code** - Remove `?delay=` parameter handling from production code in routes.py
- [ ] **Add structured logging** - Replace print statements with proper logging framework (Python logging module)
- [ ] **Database connection pooling** - Consider connection pooling for SQLite (though SQLite has limitations)
- [ ] **Add database indexes** - Add indexes on frequently queried columns (conversations.user_id, messages.conversation_id, etc.)
- [ ] **Error handling standardization** - Create consistent error response format across all API endpoints
- [ ] **Frontend error boundaries** - Add error handling for failed API calls with retry logic
- [ ] **Remove inline onclick handlers** - Replace inline onclick in HTML with event delegation (already partially done, but model selector still uses it)
- [ ] **Add request timeout handling** - Handle timeouts for long-running Gemini API calls gracefully
- [ ] **Pagination for conversations** - Add pagination to conversations list endpoint for users with many conversations
- [ ] **Add database query optimization** - Review and optimize N+1 query patterns (e.g., loading conversations with message counts)
- [ ] **Frontend bundle optimization** - Bundle and minify JS/CSS instead of loading from CDN (marked.js, highlight.js)
- [ ] **Add service worker** - Implement service worker for offline support and better caching
- [ ] **TypeScript migration** - Consider migrating frontend to TypeScript for better type safety
- [ ] **Add file upload progress** - Show upload progress indicator for large file uploads
- [ ] **Accessibility improvements** - Add ARIA labels, improve keyboard navigation, ensure screen reader compatibility
- [ ] **Add request/response logging middleware** - Log all API requests and responses (with sensitive data redaction)
- [ ] **Environment variable validation** - Validate all required env vars at startup with clear error messages
- [ ] **Add health check endpoint** - `/health` endpoint for monitoring and load balancer checks
- [ ] **Frontend state management** - Consider using a state management library (Zustand, Redux) instead of global state object
- [ ] **Add request ID tracking** - Include request IDs in logs and error responses for easier debugging
- [ ] **Optimize image processing** - Consider async/background processing for thumbnail generation on large images
- [ ] **Add database backup automation** - Automated daily backups of SQLite database
- [ ] **Frontend code splitting** - Split frontend code into chunks for better initial load performance
- [ ] **Add API response compression** - Enable gzip compression for API responses
- [ ] **Remove unused dependencies** - Audit and remove any unused npm/Python dependencies
- [ ] **Add database vacuum** - Periodic SQLite VACUUM to reclaim space and optimize database
- [ ] **Frontend error reporting** - Add error reporting service (Sentry, Rollbar) for production error tracking
- [ ] **Add request size limits** - Enforce request body size limits in Flask to prevent DoS
- [ ] **Improve JWT token handling** - Add token refresh mechanism instead of fixed expiration
- [ ] **Add CORS configuration** - Explicitly configure CORS if needed for cross-origin requests
- [ ] **Frontend performance monitoring** - Add performance monitoring (Web Vitals, custom metrics)
- [ ] **Add database query logging** - Log slow queries for optimization (in development/debug mode)
- [ ] **Frontend bundle analysis** - Analyze bundle size and identify optimization opportunities

## Notes

### Gemini API Data Privacy
- Logs are NOT used for training by default on billing-enabled projects
- Logs auto-expire after 55 days
- No explicit opt-out parameter, but data sharing requires explicit opt-in

### Model IDs (as of Dec 2025)
- `gemini-3-pro-preview` - Best for complex reasoning
- `gemini-3-flash-preview` - Faster and cheaper

### Thinking Level Parameter
Gemini 3 uses `thinking_level` instead of `thinking_budget`:
- `minimal` - Fastest, least reasoning
- `low` - Good for simple tasks
- `medium` - Balanced
- `high` - Maximum reasoning depth (default)
