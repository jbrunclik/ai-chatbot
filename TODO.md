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
- [ ] Add loading states and animations
- [ ] Conversation rename/delete functionality
- [ ] Mobile gesture support (swipe to open sidebar)

## Phase 3 - Tools & Extensions
- [x] **Tool framework** - Extensible system for adding agent tools
- [x] Web search tool (DuckDuckGo)
- [x] URL fetch tool (extract text from web pages)
- [ ] Image generation tool (Gemini 3 Pro Image or Imagen)
- [ ] Text-to-speech tool
- [ ] Code execution sandbox
- [ ] File upload and processing

## Phase 4 - Advanced Features
- [ ] Multiple AI providers (Anthropic Claude, OpenAI)
- [ ] Custom system prompts per conversation
- [ ] Conversation export (JSON, Markdown)
- [ ] Conversation sharing (public links)
- [ ] Keyboard shortcuts
- [ ] Voice input

## Phase 5 - Production Hardening
- [ ] Comprehensive test suite
- [ ] Rate limiting
- [ ] Request logging and monitoring
- [ ] Database migrations system
- [ ] Backup and restore
- [ ] Docker deployment option

## CI/CD & DevOps
- [ ] **GitHub Actions** - Workflow for linting (ruff, mypy) on PRs
- [ ] **Dependabot** - Configuration for automated dependency updates
- [ ] Docker image and docker-compose setup

## Technical Debt
- [ ] Add proper database migrations (alembic)
- [ ] Add request validation (pydantic or marshmallow)
- [ ] Consider async Flask (quart) for better concurrency
- [ ] Add OpenAPI/Swagger documentation

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
