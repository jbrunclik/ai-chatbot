# AI Chatbot

A personal AI chatbot web application using Google Gemini APIs, similar to ChatGPT.

## Features

- Chat with Google Gemini AI models (Pro and Flash)
- **Web tools**: Real-time web search (DuckDuckGo) and URL fetching
- Multiple conversations with history
- Model selection (Gemini 3 Pro for complex tasks, Flash for speed)
- Markdown rendering with syntax highlighting
- Google OAuth authentication with email whitelist
- Modern dark theme, mobile-first responsive design
- Local development mode (no auth required)

## Tech Stack

- **Backend**: Python 3, Flask, LangGraph/LangChain
- **Frontend**: Pure JavaScript (ES modules, no build step)
- **Database**: SQLite
- **Auth**: Google OAuth + JWT tokens

## Quick Start

### Prerequisites

- Python 3.11+
- Google Gemini API key ([Get one here](https://aistudio.google.com/apikey))
- (Optional) Google OAuth credentials for authentication

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-chatbot.git
cd ai-chatbot

# Setup virtual environment and install dependencies
make setup

# Copy environment template
cp .env.example .env
```

### Configuration

Edit `.env` with your settings:

```bash
# Required
GEMINI_API_KEY=your-gemini-api-key

# For local development (no auth)
LOCAL_MODE=true

# For production with Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
JWT_SECRET_KEY=your-secret-key
ALLOWED_EMAILS=user1@gmail.com,user2@gmail.com
```

### Running

```bash
# Development
make run

# Visit http://localhost:8000
```

## Commands

```bash
make setup      # Create venv and install dependencies
make run        # Run development server
make lint       # Run ruff and mypy
make test       # Run tests
```

## Deployment

A systemd user service file is included for Linux deployment:

```bash
# Copy service file
cp ai-chatbot.service ~/.config/systemd/user/

# Edit paths in the service file
vim ~/.config/systemd/user/ai-chatbot.service

# Enable and start
systemctl --user enable ai-chatbot
systemctl --user start ai-chatbot
```

## Project Structure

```
ai-chatbot/
├── src/
│   ├── app.py              # Flask application entry point
│   ├── config.py           # Configuration from environment
│   ├── auth/               # Google OAuth + JWT authentication
│   ├── api/                # REST API routes
│   ├── agent/              # LangGraph agent and tools
│   ├── db/                 # SQLite models
│   └── static/             # Frontend assets (HTML, JS, CSS)
├── Makefile                # Build and run targets
├── pyproject.toml          # Python project configuration
├── requirements.txt        # Python dependencies
└── .env.example            # Environment template
```

## License

MIT
