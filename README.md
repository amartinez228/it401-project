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
| `/api/rapid/search?q=arrival` | Server-side proxy to a configured RapidAPI search endpoint |

The Explore page accepts `q`, `type`, `genre`, `rating`, and `year` query
parameters. With RapidAPI configured, a title query such as `q=Batman` searches
Streaming Availability and displays live posters, metadata, and US watch links.
Without a title query (or without RapidAPI configured), Explore uses the local demo
catalog. `/api/media` always exposes the local catalog as JSON. Ratings and followed
creators are saved to browser `localStorage`, so they persist across page refreshes
on that device.

## Configuration

Configuration lives in `config.py` and reads from a local `.env` file. On first
setup, copy the safe example file:

```bash
cp .env.example .env
```

The real `.env` file is ignored by Git. Put secrets in `.env`, never directly in
Python, HTML, JavaScript, `.env.example`, or `.gitignore`. The `.gitignore` file
contains only the *name* of the secret file so Git knows not to upload it.

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret |
| `RAPIDAPI_KEY` | Your private `X-RapidAPI-Key` value |
| `RAPIDAPI_HOST` | Streaming Availability's `X-RapidAPI-Host` value |
| `RAPIDAPI_BASE_URL` | Streaming Availability's URL origin |
| `RAPIDAPI_SEARCH_PATH` | Title search endpoint, `/shows/search/title` |
| `RAPIDAPI_QUERY_PARAMETER` | Title search parameter, `title` |
| `RAPIDAPI_COUNTRY` | Two-letter country used for streaming availability, such as `us` |
| `AI_SERVICE_API_KEY` | Reserved for a future AI service |
| `FLASK_ENV` | `development` or `production` |

## Connecting Streaming Availability

BetterBoxd is set up for the Streaming Availability API. The non-secret host,
search path, and country settings are already present in `.env.example`; only the
private key must come from your RapidAPI account.

1. Open an API listing and check its pricing, monthly quota, attribution/license,
   update frequency, and whether it includes posters, cast, ratings, and streaming
   providers you need.
2. Subscribe to its free plan if one is available, open a title-search endpoint,
   and use **Test Endpoint** before adding it to the app.
3. Copy the key into `RAPIDAPI_KEY` in `.env`; do not copy it into application
   code, screenshots, or `.env.example`.
4. Restart Flask after changing `.env`, then test:

   ```bash
   curl "http://127.0.0.1:5000/api/rapid/search?q=arrival"
   ```

The browser calls this project's Flask routes. Flask calls RapidAPI with the secret
headers and converts the returned shows into BetterBoxd cards. This keeps the key
out of the page source and browser developer tools.

## Testing

With the virtual environment activated:

```bash
python -m pytest tests/
```
