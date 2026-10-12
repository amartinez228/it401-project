# BetterBoxd

A Flask movie discovery app with authenticated external APIs, HTML scraping,
SQLAlchemy persistence, and a searchable saved library. Assignment 3 work is on
`adrianmartinez-it401-a3`.

All visitors use the **application owner's RapidAPI account** through Flask.
Visitors need neither a RapidAPI account nor a key. Credentials stay on the server.

## Setup with MySQL

Requires Python 3.10+ and MySQL 8.0+ (or Docker Compose for the supplied MySQL 8.4
service). Run these commands from `it401_project_template` with your virtual
environment activated:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

If `.env` already exists, add the new database/cache settings without overwriting
your existing credentials. Configure these values in `.env` or hosting secrets:

| Setting | Purpose |
|---|---|
| `DATABASE_URL` | `mysql+pymysql://betterboxd:YOUR_PASSWORD@127.0.0.1:3306/betterboxd?charset=utf8mb4` |
| `SECRET_KEY` | Random Flask session secret; required in production |
| `ADMIN_API_TOKEN` | Long random owner token for library mutations |
| `RAPIDAPI_KEY` | Owner's RapidAPI key, shared by all visitors through Flask |
| `RAPIDAPI_HOST` | `streaming-availability.p.rapidapi.com` |
| `RAPIDAPI_BASE_URL` | `https://streaming-availability.p.rapidapi.com` |
| `RAPIDAPI_SEARCH_PATH` | `/shows/search/title` |
| `RAPIDAPI_QUERY_PARAMETER` | `title` |
| `RAPIDAPI_COUNTRY` | Streaming region, default `us` |
| `IMDB_API_KEY` | Optional separate owner key; otherwise uses `RAPIDAPI_KEY` |
| `IMDB_API_HOST` | `imdb236.p.rapidapi.com` |
| `IMDB_API_BASE_URL` | `https://imdb236.p.rapidapi.com` |
| `IMDB_RANDOM_PATH` | `/api/imdb/random` |
| `API_CACHE_TTL_SECONDS` | Streaming search freshness, default 86400 (24 hours) |
| `IMDB_CACHE_TTL_SECONDS` | Surprise pick freshness, default 900 (15 minutes) |
| `SCRAPE_CACHE_TTL_SECONDS` | Box office freshness, default 3600 (1 hour) |
| `CACHE_MAX_STALE_SECONDS` | Maximum age allowed during failure/refresh, default 604800 (7 days) |
| `FLASK_ENV` | `development` or `production` |

URL-encode special characters in the database password when building
`DATABASE_URL`. Subscribe the owner's RapidAPI app to the providers being used.
Never commit `.env`, put tokens in URLs, or distribute credentials with the app.

For the supplied local MySQL service, also set `MYSQL_PASSWORD` and
`MYSQL_ROOT_PASSWORD` in `.env`. `MYSQL_PASSWORD` must match the password in
`DATABASE_URL`. Then run:

```bash
docker compose up -d --wait mysql
python -m flask --app app db upgrade
python app.py
```

Docker binds MySQL to localhost and stores data in the `mysql_data` named volume.
Changing MySQL password environment variables does not change an already
initialized database's password. For an existing MySQL installation, create a
`betterboxd` database using `utf8mb4` and a dedicated application user, then run
`db upgrade` against that database. Use TLS for a remote database connection.

Visit http://127.0.0.1:5000. Restart Flask after configuration changes. Share the
hosted app's URL with visitors. Production requires explicit `DATABASE_URL` and
`SECRET_KEY` settings and disables debug mode.

If `DATABASE_URL` is unset in development, the app uses a persistent SQLite file
at `instance/betterboxd.db` so local work can continue without MySQL. This is a
local fallback, not a live MySQL connection. Tests use isolated SQLite databases.
The instance directory is anchored to `it401_project_template`, so IDE launches
from the workspace root use the same database as Flask migration commands.
Run `db upgrade` before starting either database configuration. Schema changes
are explicit migrations; the app never creates or drops tables during requests.

## Application structure

```text
app.py                       App factory and extension initialization
config.py                    Environment configuration and test settings
extensions.py                SQLAlchemy and Flask-Migrate instances
models/__init__.py           Record and ResponseCache ORM models
migrations/                  Versioned Alembic schema migrations
routes/main.py               Discovery pages and provider JSON routes
routes/records.py            Saved-library page and CRUD API blueprint
routes/errors.py             Safe database/validation errors and cache headers
services/integrations.py     Provider construction and cache orchestration
services/cache_service.py    Shared persistent cache and refresh leases
services/record_service.py   Ingestion, CRUD, and local text retrieval
services/validation.py       Incoming query and JSON validation
services/api_service.py      HTTPS requests and server-side authentication
services/streaming_service.py Streaming JSON normalization
services/imdb_service.py     Selected random-title JSON fields
services/scraping_service.py HTML retrieval and structured extraction
services/search_service.py   Original local demo catalog search
templates/                   Discovery, library, and error pages
tests/                       Offline integration and persistence tests
compose.yaml                 Optional local MySQL service and persistent volume
```

## Persistence and API cost control

The first successful query is normalized and stored in `response_cache`, and its
records are captured in `records` in the same database transaction. Repeat queries
reuse the saved payload until its TTL expires, including after app restarts and
across workers sharing the same database. No raw upstream response or API key is
stored. The existing local JSON demo catalog remains available separately.

Cache keys hash the provider, normalization version, endpoint, and relevant
parameters. Streaming searches normalize case/whitespace and include format and
country. Genre, year, and rating filters are applied locally on Explore, allowing
the same fetched search to support different filters. Empty successful results
are cached too. A database update atomically claims a 60-second refresh lease;
other requests receive eligible stale results or a 503 with `Retry-After` while
that refresh is in progress. A crashed worker's lease expires automatically.

Failures are not saved as successful responses. A failed fetch starts a 60-second
cooldown; eligible old results are marked stale. Responses expose `X-Data-Cache:
hit`, `miss`, or `stale`, and stale data includes a Warning header. Explore and
Box office display stale-data messages. When the database is unavailable, the
app returns a safe 503 and does **not** bypass the cache to make paid requests.
SQLAlchemy checks pooled connections before use and recycles them periodically.

The IMDb surprise result is reused for 15 minutes for the same filters. This
reduces paid calls but means repeated clicks can choose the same title. A new
query or expired cache may still consume quota; caching is not a spending cap.
The saved library can be searched without any external API call or credentials.
Cache rows are retained until overwritten; a retention/pruning policy can be
added as usage grows. Check provider storage/redistribution terms for deployment.

## Routes and CRUD

| Method and route | Purpose |
|---|---|
| `GET /` | Home |
| `GET /explore` | Discover titles; query parameters: `q`, `type`, `genre`, `rating`, `year` |
| `GET /box-office` | Search scraped box office records |
| `GET /library` | Search persisted records without external requests |
| `GET /api/media` | Original filtered local demo catalog |
| `GET /api/rapid/search?q=arrival` | Cached normalized streaming results: `{count, results}` |
| `GET /api/imdb/random?type=Movie&genre=Comedy` | Cached `[{primaryTitle: "..."}]` |
| `GET /api/box-office?q=avatar` | Scraped records plus source, retrieval time, and stale flag |
| `GET /api/records?q=space&source=streaming&page=1&limit=20` | Paginated saved-record search |
| `GET /api/records/1` | Read a saved record |
| `POST /api/records` | Create a record; owner token required |
| `PATCH /api/records/1` | Update selected fields; owner token required |
| `DELETE /api/records/1` | Soft-delete a record; owner token required |

The prototype email/password sign-in is **not real authentication** and grants no
write permission. Mutations require `Authorization: Bearer <ADMIN_API_TOKEN>`.
Keep this token in trusted owner tooling; it is not embedded in public HTML or JS.
The saved library is public, so its notes and tags are also public.

For example, with the owner token already exported in your shell:

```bash
curl -X POST http://127.0.0.1:5000/api/records \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Arrival","year":2016,"media_type":"Movie","genres":["Science Fiction"],"tags":["language"],"notes":"Watch again"}'

curl 'http://127.0.0.1:5000/api/records?q=language'

curl -X PATCH http://127.0.0.1:5000/api/records/1 \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"notes":"Discuss the communication themes"}'

curl -X DELETE http://127.0.0.1:5000/api/records/1 \
  -H "Authorization: Bearer $ADMIN_API_TOKEN"
```

Use the ID/Location returned by POST. POST returns 201; PATCH returns 200;
DELETE returns 204. Deleted or unknown records return 404. Deletion removes a
record from the library and retrieval results; it keeps a tombstone to prevent
re-ingestion on refresh. It does not remove that film from the separate provider
response cache. Editing a record marks it curated, protecting it from automatic
provider overwrites. Captured data remains available in the record's `data` field.

Writes accept only `title`, `synopsis`, `year`, `media_type`, `genres`, `tags`,
`notes`, and `source_url`. IDs, provenance, hashes, and timestamps are managed by
the server. Titles are required and limited to 300 characters; synopsis/notes to
10,000. Tags/genres allow at most 20 non-empty strings of 80 characters each.
Source URLs must use HTTPS without embedded credentials. JSON bodies are limited
to 64 KB. Search text is limited to 200 characters, page sizes to 100, ratings to
finite values from 0–5, and years to 1800–current year + 10. Unknown formats and
invalid JSON are rejected with 400 before database writes or provider calls.
SQLAlchemy binds query parameters; LIKE wildcard characters are treated literally.

HTTP errors: 400 invalid input, 401 invalid/missing owner token, 404 missing
record, 413 oversized body, 503 missing configuration/database outage/refresh
cooldown, 504 provider timeout, and 502 other provider or parsing failures when
no eligible stale data exists. Logs contain fixed failure messages, not raw
exceptions, credentials, or upstream response bodies. HTTPS API redirects are
rejected to prevent authentication headers from being forwarded.

## Web scraping and provenance

Source URL: https://en.wikipedia.org/wiki/List_of_highest-grossing_films

The scraper fetches public HTML and locates the table by Rank, Title, Worldwide
gross, and Year headers. Beautiful Soup removes citations, scripts, styling,
formatting, whitespace, and release markers. It extracts multiple records with
`title`, `rank`, `year`, `worldwide_gross_usd`, and `source_url`. Numeric fields
are integers or null; rows without titles are skipped. Missing/empty tables
produce explicit errors. Earnings are nominal US dollars, not inflation-adjusted.
Selecting a film opens the application's streaming search.

The URL is fixed in code. Fetches have connect/read timeouts, an HTML content-type
check, a 3 MB decompressed size limit, and no redirects. The shared SQL cache
replaces the earlier per-process in-memory scraper cache. Markup and access
policies can change. Attribution/license information:
https://en.wikipedia.org/wiki/Wikipedia:Copyrights

## Future intelligence and retrieval

Each saved record includes stable identity, provider provenance, source URL,
created/updated/fetched UTC timestamps, structured JSON data, and `schema_version`.
A `retrieval_text` field combines the title, year, format, synopsis, genres, tags,
and notes. `content_hash` changes when searchable content, structured data, or
source URL changes, allowing a future embedding/indexing job to detect updates.
Provider records are deduplicated within each source; cross-provider entity
resolution remains future work.

Current retrieval is deterministic SQL text matching across up to ten query
terms, with pagination and source filtering. It is not semantic search and makes
no AI calls. A future pipeline can chunk `retrieval_text`, index vectors keyed by
record ID/content hash, and cite `source_url` in answers. Such an index must honor
`deleted_at` tombstones and curated changes. The current substring search is
suitable for a small library; use full-text/vector indexes when scale requires it.

## Migrations and verification

```bash
python -m flask --app app db upgrade
python -m flask --app app db check
python -m pytest -q
```

For later schema changes, edit models, generate a migration with
`python -m flask --app app db migrate -m "Describe change"`, review it, then upgrade.
Back up a populated database before schema migrations. Never use `create_all()`
to evolve an existing production schema.

Tests use real isolated SQLite databases and mocked external responses. They
cover persistence across app instances, cache keys/expiry/empty results, refresh
leases, stale limits, cooldowns, ingestion deduplication, CRUD, validation,
authorization, credential safety, database outages, and malformed JSON/HTML.
The migration is also checked by generating MySQL SQL offline. A live MySQL
server and real provider subscriptions must be verified in the deployment
environment; offline dialect checks do not establish live MySQL compatibility.

Implementation references:
- Flask-SQLAlchemy: https://flask-sqlalchemy.palletsprojects.com/en/stable/quickstart/
- SQLAlchemy connections: https://docs.sqlalchemy.org/en/20/core/engines.html
- Streaming provider: https://docs.movieofthenight.com/guide/quickstart
