# AI Chatbot

A personal AI chatbot web application using Google Gemini APIs, similar to ChatGPT.

## Features

- Chat with Google Gemini AI models (Pro and Flash)
- **Streaming responses**: Real-time token-by-token display (toggleable)
- **File uploads**: Images, PDFs, and text files with multimodal AI analysis
- **Image lightbox**: Click thumbnails to view full-size images, with lazy loading
- **Web tools**: Real-time web search (DuckDuckGo) and URL fetching
- Multiple conversations with history
- Model selection (Gemini 3 Pro for complex tasks, Flash for speed)
- Markdown rendering with syntax highlighting
- Google Sign In authentication with email whitelist
- Modern dark theme, mobile-first responsive design
- iOS Safari and PWA compatible
- Local development mode (no auth required)

## Tech Stack

- **Backend**: Python 3, Flask, LangGraph/LangChain
- **Frontend**: Pure JavaScript (ES modules, no build step)
- **Database**: SQLite
- **Auth**: Google Identity Services (GIS) + JWT tokens

## Quick Start

### Prerequisites

- Python 3.11+
- Google Gemini API key ([Get one here](https://aistudio.google.com/apikey))
- (Optional) Google Cloud project for authentication

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

# For production with Google Sign In
GOOGLE_CLIENT_ID=your-client-id
JWT_SECRET_KEY=your-secret-key
ALLOWED_EMAILS=user1@gmail.com,user2@gmail.com

# File upload limits (optional)
MAX_FILE_SIZE=20971520              # 20 MB in bytes
MAX_FILES_PER_MESSAGE=10
ALLOWED_FILE_TYPES=image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain,text/markdown,application/json,text/csv
```

### Setting up Google Sign In

To enable authentication (required for production):

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project (or select an existing one)
3. Click **Create Credentials** → **OAuth client ID**
4. Select **Web application** as the application type
5. Add **Authorized JavaScript origins**:
   - `http://localhost:8000` (for development)
   - `https://yourdomain.com` (for production)
6. Copy the **Client ID** to your `.env` file

No client secret is needed - the app uses Google Identity Services which validates tokens server-side.

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
make deploy     # Deploy systemd service (Linux)
```

## Deployment

For production, the app uses Gunicorn as the WSGI server. A systemd user service file is included for Linux:

```bash
# Set production environment in .env
FLASK_ENV=production

# Install dependencies (includes gunicorn)
make setup

# Deploy and start the service
make deploy

# View logs
journalctl --user -u ai-chatbot -f
```

## Project Structure

```
ai-chatbot/
├── src/
│   ├── app.py              # Flask application entry point
│   ├── config.py           # Configuration from environment
│   ├── auth/               # Google Sign In + JWT authentication
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
