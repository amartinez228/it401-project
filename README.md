# BetterBoxd

A Flask movie and show recommendation prototype. BetterBoxd lets visitors explore a
local JSON catalog, filter recommendations, rate titles, follow creators, and use a
demo sign-in flow.

## Project Structure

```
project/
├── app.py                 # App factory, entry point
├── config.py               # Environment-based configuration
├── routes/                  # View functions
├── requirements.txt
├── services/                # Business logic and external integrations
│   ├── api_service.py       # Generic outbound HTTP client
│   ├── search_service.py    # Search logic
│   └── ai_service.py        # AI/LLM integration
├── models/                  # Data models
├── templates/                # Jinja2 HTML templates
├── static/                   # CSS, JS, images
├── data/media.json            # Local movie and show catalog
└── tests/                      # Test suite
```

## Prerequisites

- Python 3.10+
- Git

## Setup

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd project
   ```

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv

   # macOS / Linux
   source .venv/bin/activate

   # Windows (Command Prompt / PowerShell)
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the App

With the virtual environment activated:

```bash
python app.py
```

The app will be available at [http://127.0.0.1:5000](http://127.0.0.1:5000).

By default it runs in development mode. Set `FLASK_ENV=production` to use the production config.

## App routes

| Route | Purpose |
|---|---|
| `/` | BetterBoxd home page |
| `/explore` | Search and filter the media catalog |
| `/signin` | Local prototype sign-in page |
| `/api/media` | JSON version of the filtered catalog |

The Explore page and API accept `q`, `type`, `genre`, `rating`, and `year` query
parameters. For example, `/api/media?type=Movie&genre=Science%20Fiction&rating=4.5`
returns highly rated science-fiction movies. Ratings and followed creators are saved
to browser `localStorage`, so they persist across page refreshes on that device.

## Configuration

Configuration lives in `config.py` and reads from environment variables:

| Variable            | Description                          |
|---------------------|---------------------------------------|
| `SECRET_KEY`         | Flask secret key                      |
| `API_KEY`             | Key for external API service          |
| `AI_SERVICE_API_KEY`   | Key for AI service integration        |
| `FLASK_ENV`             | `development` or `production`         |

## Testing

With the virtual environment activated:

```bash
python -m pytest tests/
```
