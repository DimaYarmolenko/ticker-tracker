# Ticker Tracker

A REST API for tracking stock ticker symbols and collecting related signal — news headlines, periodic price snapshots, and (optionally) LLM-scored news importance / per-ticker impact. Built with FastAPI and PostgreSQL.

## Running the app

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.  
Interactive docs (Swagger UI) at `http://localhost:8000/docs`.

The app container runs `alembic upgrade head` before starting uvicorn, so a fresh database is bootstrapped automatically. The PostgreSQL database persists in a named Docker volume (`postgres-data`) across container restarts. Only `docker compose down -v` will remove it.

## Running tests

```bash
make test
```

This rebuilds the test image (so new migrations are picked up) and runs the suite against the ephemeral `test-db` service.

## Local development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For development (linter & formatter):

```bash
pip install -r requirements-dev.txt
```

```bash
uvicorn app.main:app --reload
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/tickers` | List all tickers |
| `POST` | `/tickers` | Add a ticker `{"symbol": "AAPL"}` |
| `DELETE` | `/tickers/{symbol}` | Remove a ticker by symbol |
| `GET` | `/tickers/{symbol}/news` | News for a ticker (supports `?limit=20&offset=0`). Each article includes `importance`, `evaluated_at`, `impact`, `impact_confidence` when the evaluator has processed it. |
| `GET` | `/tickers/{symbol}/prices` | Price snapshots for a ticker (supports `?limit=20&offset=0`) |

## News collection

On startup the app launches a background scheduler that polls Google News RSS for all tracked tickers. Each poll:

- Fetches one RSS feed per ticker (`https://news.google.com/rss/search?q={SYMBOL}+stock`)
- Skips articles older than `NEWS_MAX_AGE_DAYS` days (default `2`)
- Deduplicates articles by URL — the same article appearing in multiple ticker feeds is stored once and linked to all relevant tickers
- Scans article titles for cross-mentions of other tracked symbols and links those too

## Stock prices

The same scheduler also polls Yahoo Finance (via `yfinance`) every `PRICE_POLL_INTERVAL_MINUTES` minutes. Each poll appends one row per tracked ticker to the `prices` table (`price`, `open`, `high`, `low`, `volume`, `fetched_at`) — snapshots are retained, not overwritten.

## Article evaluation

When `EVALUATOR_ENABLED=true`, a third scheduler job scores unevaluated articles for *importance* (1-5) and *per-ticker impact* (`positive` / `negative` / `neutral` + a confidence in `[0, 1]`). Results are persisted on the `articles` and `article_tickers` tables and surfaced through `GET /tickers/{symbol}/news`.

Backends are selected via `EVALUATOR_BACKEND`:

- `noop` (default): the job runs but writes nothing — useful for local dev and tests.
- `gemini`: calls Google Gemini via the `google-genai` SDK. Requires `GEMINI_API_KEY`.

## Migrations

Schema is managed by Alembic; revisions live under `alembic/versions/`. `make migrate` runs `alembic upgrade head` inside the running `app` container, and `make migrate-revision name="..."` autogenerates a new revision from the SQLAlchemy models.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NEWS_POLL_INTERVAL_MINUTES` | `30` | How often to poll news feeds |
| `PRICE_POLL_INTERVAL_MINUTES` | `30` | How often to poll price snapshots |
| `NEWS_MAX_AGE_DAYS` | `2` | Maximum article age to collect |
| `EVALUATOR_ENABLED` | `false` | Whether to register the article-evaluation job |
| `EVALUATOR_BACKEND` | `noop` | `noop` or `gemini` |
| `EVALUATION_POLL_INTERVAL_MINUTES` | _(required when enabled)_ | How often to score unevaluated articles |
| `EVALUATOR_BATCH_SIZE` | `10` | Articles per LLM request |
| `EVALUATOR_MAX_PER_RUN` | `100` | Maximum articles processed per poll |
| `EVALUATOR_VERSION` | `v1` | Stamp written to `articles.evaluator_version` |
| `GEMINI_API_KEY` | — | Required when `EVALUATOR_BACKEND=gemini` |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |

See `.env.example` for the full list of required environment variables.

## Linting & Formatting

[Ruff](https://docs.astral.sh/ruff/) is used for both linting and formatting.

```bash
# Check for lint errors
ruff check .

# Fix lint errors automatically
ruff check --fix .

# Format code
ruff format .

# Check formatting without applying changes
ruff format --check .
```

## Examples

```bash
# Add a ticker
curl -X POST http://localhost:8000/tickers \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL"}'

# List all tickers
curl http://localhost:8000/tickers

# Delete a ticker
curl -X DELETE http://localhost:8000/tickers/AAPL

# Get news for a ticker (first page)
curl "http://localhost:8000/tickers/AAPL/news"

# Get news with pagination
curl "http://localhost:8000/tickers/AAPL/news?limit=10&offset=20"

# Get price snapshots for a ticker
curl "http://localhost:8000/tickers/AAPL/prices?limit=10"
```
