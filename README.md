# BetterBoxd

A Flask movie discovery app with authenticated external APIs, HTML scraping,
SQLAlchemy persistence, and ranked search over a saved movie library.

**Application:** BetterBoxd

**Student:** Adrian Martinez

**Course and assignment:** IT401, Assignment 4 - Searchable Information System

**Branch:** `a4`, based on `origin/adrianmartinez-it401-a3`.

All visitors use the **application owner's RapidAPI account** through Flask.
Visitors need neither a RapidAPI account nor a key. Credentials stay on the server.

## Setup with MySQL

Clone and create an environment first:

```powershell
git clone https://github.com/amartinez228/it401-project.git
cd it401-project
git switch a4
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux, activate with `source .venv/bin/activate`.

Requires Python 3.10+ and MySQL 8.0+ (or Docker Compose for the supplied MySQL 8.4
service). Run these commands from `it401-project` with your virtual
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
| `IMDB_CACHE_TTL_SECONDS` | IMDb cached API freshness, default 900 (15 minutes) |
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
The instance directory is anchored to `it401-project`, so IDE launches
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

Each explicit Surprise me click refreshes the IMDb pick instead of reusing the
same title for 15 minutes. The selected format and genre are sent to IMDb;
unspecified format defaults to Movie. Each successful refresh replaces the same
cache row, persists the acquired record, and redirects to streaming search.
Ordinary `/api/imdb/random` reads still reuse the 15-minute cache. Refresh leases,
failure cooldowns, and eligible stale fallback still apply. Each click may consume
an IMDb API request plus a streaming lookup; providers can randomly repeat titles,
and caching is not a spending cap.
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

The legacy `/api/records` endpoint retains its deterministic ten-term search.
A4 adds `/search` with up to twenty terms, weighted ranking, two filters, and
ten-result pages (described below). It is not semantic search and makes
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

## Project Overview

BetterBoxd helps movie and television viewers discover and revisit useful titles.
Explore acquires normalized information from Streaming Availability and IMDb236;
Box office scrapes public film earnings. A3 persists acquired information in MySQL
through Flask-SQLAlchemy and preserves owner CRUD edits. A4 lets visitors search
that saved collection independently of provider availability or API credentials.
The homepage and discovery features remain available.

Database querying answers precise predicates such as `source = streaming`.
Information retrieval starts with an information need expressed as text and orders
potentially useful records. A4 combines Boolean database predicates with weighted
text relevance and evaluates usefulness against explicit human relevance judgments.

## Search and Retrieval Features

- Dedicated HTML GET form at `/search?q=arrival`; query remains in the URL and input.
- Search across title, synopsis, and the prepared retrieval text.
- Optional source and Movie/Show filters, combined with AND; remove or change both.
- Sort by relevance, newest saved, oldest saved, or title A-Z.
- Weighted relevance scoring and stable ordering by record ID after tie breakers.
- Ten records per page, previous/next links, total matches, range, and page number.
- Links to saved HTML details and structured JSON; descriptions and provenance.
- Anonymous persisted telemetry, including zero-result searches.
- Clear initial, invalid-input, no-results, and unavailable states.

## Search Workflow

```text
GET keyword + filters + sort + page
  -> Validate and normalize query
  -> Retrieve candidates from saved records (exclude deleted records)
  -> Apply Boolean source AND format filters
  -> Rank or sort all matching candidates in SQL
  -> COUNT matches; apply LIMIT 10 / OFFSET
  -> Materialize result dictionaries
  -> Attempt independent telemetry commit
  -> Display results, range, and navigation
```

No acquisition, scraping, API request, or LLM call occurs inside `/search`.
Use Explore, the existing provider endpoints, or Box office to acquire information
first. An empty saved collection correctly returns no matching records.

## Searchable Information

| Model / field | Role and reason |
|---|---|
| `Record.title` | Searchable; viewers often know all or part of a title. Highest relevance weight. |
| `Record.synopsis` | Searchable; supports needs expressed as a plot or topic. Lower relevance weight. |
| `Record.retrieval_text` | Searchable; A3's prepared title, synopsis, year, format, genres, tags, and notes expand discovery. Metadata-only matches have no score boost. |
| `Record.source` | Exact optional filter; limits provider provenance without text ambiguity. |
| `Record.media_type` | Exact optional filter for Movie/Show; also present in retrieval text. |
| `Record.deleted_at` | Mandatory exclusion; soft-deleted records never appear. |
| `Record.created_at` | Newest/oldest ordering and display metadata. |
| `Record.updated_at` | More recently updated records win relevance ties. |
| ID, source URL, content hash, schema version | Identification, citation, and future indexing metadata; not keyword fields. |
| `ResponseCache`, `SearchEvent` | Not searched as content. Provider caches and telemetry serve separate purposes. |

## Retrieval Strategy

The input is bounded to 200 characters and twenty whitespace-separated terms.
Leading/trailing whitespace is removed and internal whitespace is collapsed. The
original capitalization is retained for display and telemetry. Matching uses
lowercase terms consistently. Whitespace splitting is a basic form of tokenization;
lowercasing and whitespace cleanup are normalization, as discussed in
[Manning, Raghavan, and Schutze, Introduction to Information Retrieval, Chapter 2](https://nlp.stanford.edu/IR-book/).
Punctuation is retained; there is no stemming, stopword removal, or synonym expansion.
A multiword phrase is accepted as text and processed as AND terms; quoted exact
phrase syntax and user-written Boolean operators are not implemented.

For each term, SQLAlchemy builds `title OR synopsis OR retrieval_text` substring
conditions. Every term condition is ANDed together, then ANDed with source, format,
and `deleted_at IS NULL`. Terms can occur in different fields and in any order.
`icontains(term, autoescape=True)` uses bound parameters and case-insensitive
LIKE semantics; percent, underscore, and escape characters are literal user text.
No raw query is interpolated into SQL. Database collation can additionally affect
accent and Unicode equivalence, so SQLite and MySQL behavior may differ for these.

Relevance is additive: exact normalized full-title match +5, each term in the title
+3, each term in the synopsis +1. Retrieval-text-only matches receive zero points.
For `arrival`, the exact title scores 8, `Arrival Stories` scores 3, and a synopsis
mention scores 1. This favors known-title searches while allowing thematic discovery.
Ties use updated time descending, then ID ascending. Other sort selections replace
the relevance ordering but retain score display. Newest/oldest refer to the record's
saved date, not the film release date.

Count, ordering, LIMIT, and OFFSET execute in the database before rendering. The
application never loads the full result set to sort or paginate. Substring LIKE is
appropriate for this small collection but commonly scans text; there is no MySQL
FULLTEXT index in A4. Deep offsets and multiple LIKE clauses can become expensive.

## Search Telemetry

`search_events` records each completed nonempty valid search, including page
navigation and zero-result searches: cleaned display query, normalized query, UTC
time, total matching count (before pagination), source/format filters, sort, and
actual page. Blank, invalid, and failed retrieval requests are not recorded.
A beyond-last-page request is clamped to the last available page and records that
actual page. Telemetry failure rolls back and leaves the materialized results usable.

No email, IP address, session ID, owner token, or provider credentials are recorded.
Query text itself can contain personal information: this feature is intended for
movie keywords, and deployment should restrict database access and define a query
retention/deletion policy. There is no public telemetry endpoint. The screenshot
script's telemetry view exists only in its disposable local preview application.

High-frequency queries can guide acquisition and query suggestions. No-result
rates can reveal vocabulary gaps, while filter and sort use can inform ranking.
Counts alone do not prove relevance: future opt-in click/rank signals and explicit
judgments could support stronger evaluation. A4 does not record selected results
or link searches to people, so it cannot measure individual refinement sessions.

## Database Schema

All three ORM models share the configured MySQL database. A3's records and cache
migration is retained; `a4_search_events` adds telemetry without replacing data.

| Table | Purpose | Primary key | Important attributes and relationships |
|---|---|---|---|
| `records` | Acquired and owner-created saved content | `id` integer | Unique `source_key`; source, URL, title, synopsis, year, format, genres/tags JSON, notes, data JSON, retrieval_text, content_hash, schema_version, curated, UTC timestamps, deleted_at. Source/year/title/update/hash indexes. |
| `response_cache` | Shared provider cache and refresh coordination | `key` SHA-256 string | Provider, normalized payload JSON, fetched/expires times, lease token/expiry, retry time. Provider and expiry indexes. |
| `search_events` | Anonymous retrieval activity | `id` integer | Query/normalized query (200 chars), searched_at (indexed UTC), result_count, filters JSON, sort, page. |

There are no foreign keys between these tables: one provider response can yield
multiple records, and a search records aggregate results rather than a result-ID
snapshot. Records retain source provenance independently of cache expiry. Telemetry
therefore survives result deletion but cannot recreate a historical result set.

## Current Features

Homepage; Streaming Availability and IMDb API integration; Beautiful Soup web
scraping; MySQL persistence and migrations; protected create/read/update/delete API;
keyword search; filtering; sorting; ranking; pagination; search telemetry; data
validation; provider caching, retry cooldowns, and eligible stale fallback; local
demo sign-in and browser ratings/follows inherited from A3.

## Project Structure (A4 additions)

```text
routes/search.py                       Dedicated request parsing and HTML responses
services/retrieval.py                   Query processing, SQL retrieval/ranking, telemetry
models/__init__.py                     Record, ResponseCache, SearchEvent
migrations/versions/a4_search_events.py Additive telemetry migration
templates/search.html                 GET search interface, feedback, pagination
templates/search_results.html         Ranked result list
templates/record.html                 Saved-record HTML detail
static/style.css                       Existing design plus responsive search styles
tests/test_search.py                   Retrieval and failure regression tests
scripts/verify_search.py               Disposable migrated evaluation and browser capture
docs/search-evaluation.json            Actual five-query evaluation output
docs/screenshots/                      Eight real application captures
requirements-dev.txt                   Optional browser capture dependency
```

The earlier application structure, acquisition services, CRUD routes, and MySQL
installation/environment instructions above still apply. No new runtime environment
variables or external service credentials are required for saved search. Apply the
new migration with `python -m flask --app app db upgrade` before opening `/search`.

## Error Handling

| Condition | Behavior |
|---|---|
| Initial, empty, or whitespace-only query | 200 with "Enter a keyword to begin."; no search or telemetry write. |
| Unknown source, format, or sort | 400 with a helpful message and usable form. |
| Noninteger, zero, negative, or over-10000 page | 400 with page validation message. |
| Valid page beyond last page | Clamp to last page; show actual range and page. |
| Query over 200 characters or twenty terms | 400; no retrieval or telemetry. |
| No matching records | 200 with broader-term/remove-filter guidance; zero-result telemetry. |
| Missing optional fields | Unknown year, empty genre list, and no-synopsis fallback. |
| Database failure | Rollback and 503 with "Search is temporarily unavailable."; no raw exception. |
| Telemetry write failure | Rollback, fixed warning in server logs, and successful result display. |
| Unknown/deleted detail | Helpful 404; tombstones are excluded from search. |

## Search Evaluation

Run `python scripts/verify_search.py` to reproduce the checked-in
[actual results](docs/search-evaluation.json). This uses six deliberately synthetic
records in a disposable SQLite database, applies both Alembic migrations, and
checks for model/schema drift. These are functional evaluations, not claims about
live provider data or a live MySQL server. Pagination screenshots add 23 synthetic
space records through the A3 ingestion pipeline after the evaluation completes.

Relevance judgments were defined for the stated needs before examining results.
Precision is useful returned records / all returned records; recall is useful
returned records / expected relevant records. See
[Manning et al., evaluation of unranked retrieval sets](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-unranked-retrieval-sets-1.html).
The table covers the complete small result sets, not just top-page precision.

| Query / need | Expected relevant | Actual order | Precision / recall | Ranking, false positives, and misses |
|---|---|---|---|---|
| `arrival`: find the film with this title | Arrival | Arrival; Arrival Stories; The Visitor | 1/3 / 1 | Exact film first; two irrelevant matches; no misses. |
| `alien communication`: films about alien communication | Arrival | Arrival | 1 / 1 | Useful result first; no false positives or misses. |
| `concert`: concert stories | Music Room; Silent Stage | Silent Stage; Music Room | 1 / 1 | Both useful; synopsis-score tie favors updated record; no misses. |
| `music`: music or musician stories | Music Room; Silent Stage | Music Room; Silent Stage | 1 / 1 | Title match first; both useful; no misses. |
| `musicians`: musician stories | Music Room; Silent Stage | Music Room | 1 / 0.5 | Useful result first, but singular "musician" in Silent Stage is missed. |

The most useful title is first for the known-title query, but broad substring
retrieval lowers precision. Adding an optional exact-title mode could improve
precision. Linguistic stemming or controlled singular/plural expansion could
increase recall for `musicians`; expansion should be evaluated for new false
positives. This tiny, constructed set is not enough to establish general quality.
A larger held-out collection and user relevance judgments would provide stronger
evidence. Current ranking weights are design choices, not learned optimal values.

## Screenshots

Real Edge browser captures of the application with synthetic test records and a
disposable SQLite database. These demonstrate the build's interface and persisted
telemetry, not a live MySQL connection or live provider acquisition.

Search form:

![Dedicated search form](docs/screenshots/01-search-form.png)

Relevance-ranked results:

![Exact title ranks above partial title and synopsis](docs/screenshots/02-ranked-results.png)

Combined filters:

![Source and format filters](docs/screenshots/03-filtered-results.png)

Alphabetical ordering:

![Results sorted by title](docs/screenshots/04-sorted-results.png)

Pagination with preserved query, filters, and sorting:

![Page two of three, showing records 11-20](docs/screenshots/05-pagination.png)

No matching records:

![Helpful no-results state](docs/screenshots/06-no-results.png)

Persisted search activity (preview-only view):

![SearchEvent database rows after searches](docs/screenshots/07-search-telemetry.png)

Mobile search:

<img src="docs/screenshots/08-mobile-search.png" alt="Search results at a 390-pixel mobile viewport" width="390">

To regenerate, install optional tooling and use an installed Microsoft Edge:

```powershell
python -m pip install -r requirements-dev.txt
python scripts/verify_search.py --screenshots
```

The script does not modify the application's configured database or call providers.

## Design Decisions

Title and synopsis capture known-item and thematic needs; prepared retrieval text
adds genres, tags, and curated notes without requiring an external index. Source
and format are predictable finite filters. Weighted title matches suit film lookup,
and update time only breaks relevance ties. Ten-result pages keep reading and
rendering manageable while SQL limits row retrieval. Anonymous telemetry reveals
aggregate information needs without building identity profiles. Stable IDs, hashes,
source citations, and prepared text support later indexing and intelligence work.

## Known Limitations

- No semantic understanding, synonyms, spelling correction, stemming, or personalized ranking.
- Phrases use AND terms; literal punctuation and singular/plural differences can miss records.
- Rule-based scores favor title matches and lack term rarity or length normalization.
- LIKE scanning and OFFSET paging will need replacement for a large collection.
- Existing B-tree indexes do not accelerate leading-wildcard text matching.
- MySQL collation can differ from SQLite for Unicode, accents, and case equivalence.
- Counts and page retrieval are separate statements; concurrent edits can change page contents.
- Telemetry has no click tracking, session linkage, historical result snapshots, or automatic retention job.
- Live discovery remains a separate external acquisition flow; saved search only finds acquired records.
- Screenshots use disposable SQLite fixtures; follow-up live MySQL acquisition and saved search were verified separately.

## Future Work

For A5, evaluate MySQL full-text search, stemming and query suggestions, then
embeddings/semantic retrieval. Add held-out relevance judgments before tuning
ranking. Later options include autocomplete, opt-in personalized recommendations,
click-based evaluation, and retrieval-augmented generation using record provenance
and source citations. Indexing must honor tombstones and curated changes and use
content hashes to detect stale embeddings. Define telemetry retention before
collecting real user search data at scale.

## A4 Verification Results

- `python -m pytest -q`: 98 tests passed, including the inherited A3 tests.
- Disposable database: both migrations applied; Alembic reported no schema drift.
- Five-query evaluation and eight real browser screenshots regenerated successfully.
- Mobile browser check: no horizontal overflow at 390 pixels.
- MySQL offline migration SQL generated successfully, including `search_events`.
- Actual retrieval statement compiled for MySQL with bound/escaped LIKE parameters,
  ranking, ORDER BY, and LIMIT/OFFSET.
- Follow-up live MySQL verification: an Arrival provider request returned HTTP 200,
  persisted 20 records, and `/search?q=Arrival` returned HTTP 200 with results.
- Fixed a MySQL timestamp-rounding bug that could falsely mark a new cache entry
  as refreshing. New entries start expired; a regression test simulates rounding
  upward and verifies successful acquisition, persistence, and cache reuse. See
  [MySQL fractional-second rounding](https://dev.mysql.com/doc/refman/8.0/en/fractional-seconds.html).

Surprise-button regression tests verify successive picks, default Movie selection,
Show/genre filters, one reused cache row, retained API caching, and lease/cooldown
protection. Tests mock providers and do not spend live API quota.
