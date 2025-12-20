# AI Chatbot - Claude Context

This file contains context for Claude Code to work effectively on this project.

## Quick Reference

- **Run**: `make run` (starts on port 8000)
- **Lint**: `make lint` (ruff + mypy)
- **Setup**: `make setup` (venv + deps)

## Project Structure

```
src/
├── app.py              # Flask entry point
├── config.py           # Environment config
├── auth/
│   ├── jwt_auth.py     # JWT token handling, @require_auth decorator
│   └── google_oauth.py # OAuth flow, email whitelist
├── api/
│   └── routes.py       # REST endpoints (/api/*, /auth/*)
├── agent/
│   ├── chat_agent.py   # LangGraph agent with Gemini
│   └── tools.py        # Web tools (fetch_url, web_search)
├── db/
│   └── models.py       # SQLite: User, Conversation, Message, AgentState
└── static/
    ├── index.html
    ├── app.js          # Frontend state management, API calls
    └── styles.css      # Dark theme, responsive layout
```

## Key Files

- [config.py](src/config.py) - All env vars, model definitions
- [routes.py](src/api/routes.py) - API endpoints
- [chat_agent.py](src/agent/chat_agent.py) - LangGraph graph, Gemini integration
- [models.py](src/db/models.py) - Database schema and operations

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

1. `LOCAL_MODE=true` → Skip all auth, use "local@localhost" user
2. Otherwise: Google OAuth → JWT token → `@require_auth` decorator

## Code Style

- Type hints in all Python code
- Conventional Commits: `type(scope): description`
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Run `make lint` before committing
- Frontend: ES modules, no build step

## Common Tasks

### Add a new API endpoint
Edit [routes.py](src/api/routes.py), add route to `api` blueprint.

### Add a new tool to the agent
Edit [tools.py](src/agent/tools.py), add function with `@tool` decorator and add to `TOOLS` list.

### Change available models
Edit [config.py](src/config.py) `MODELS` dict.

## Related Files

- [TODO.md](TODO.md) - Memory bank for planned work
- [README.md](README.md) - User-facing documentation
