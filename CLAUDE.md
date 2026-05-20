# Code Style
- Use type hints as much as possible
- Try to use enums instead of magic strings or plain values if possible.

# Configuration and secrets
There are example files @.env.example and @.test.env.example where you can see what configs and secrets are required to run the app, but the real values are hidden from you, you do not need to know them.

# Database
- The main database runs in a `db` Docker service (`postgres:17-alpine`). Data persists in a named volume (`postgres-data`) mounted at `/var/lib/postgresql/data`. It survives `docker compose down`; only `docker compose down -v` removes it.
- The test database runs in a separate `test-db` service (profile: `test`) with no named volume — it is ephemeral and discarded when the test container exits.
- Both connection strings are assembled from `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`. The app reads them in @app/database.py; `alembic/env.py` and @tests/conftest.py do the same.
- All tables are defined in @app/models.py, reference it if you need to know how to structure the data when you need to store the records in the DB or what type of data you can get when you read from the DB.

# Migrations
- Schema is managed by Alembic. Revision files live in `alembic/versions/`.
- The app container runs `alembic upgrade head` before starting uvicorn (see @Dockerfile). The test container runs the same upgrade once per session from @tests/conftest.py.
- The baseline revision (`0001_baseline`) bootstraps `tickers`, `articles`, `article_tickers`, `prices` on a fresh DB and is a no-op against pre-Alembic databases where those tables already exist.
- Subsequent migrations (e.g. `0002_add_article_evaluation`) use `IF NOT EXISTS` / `IF EXISTS` so they remain idempotent for the same reason.

# News collection
- On startup, @app/scheduler.py launches a `BackgroundScheduler` (APScheduler) that calls @app/news_fetcher.py every `NEWS_POLL_INTERVAL_MINUTES` minutes (default 30). The first poll fires immediately on startup.
- @app/news_fetcher.py fetches Google News RSS for each tracked ticker, filters articles older than `NEWS_MAX_AGE_DAYS` days, deduplicates by URL, and detects cross-mentions of other tracked symbols in article titles.
- Articles are stored in the `articles` table. The `article_tickers` join table handles the many-to-many relationship between articles and tickers.

# Stock prices
- The same scheduler calls @app/price_fetcher.py every `PRICE_POLL_INTERVAL_MINUTES` minutes (default 30). Prices come from Yahoo Finance via `yfinance` (`fast_info`).
- Each poll appends one row per ticker to the `prices` table (`price`, `open`, `high`, `low`, `volume`, `fetched_at`). Historical snapshots are retained — nothing is overwritten.

# Article evaluation
- Optional scheduler job (registered only when `EVALUATOR_ENABLED=true`) that scores unevaluated articles for importance and per-ticker impact. Implementation lives in @app/evaluator/ and @app/repository/evaluation.py.
- Backend is selected by `EVALUATOR_BACKEND`: `noop` (default — used in tests and for local dev) or `gemini` (calls Google Gemini via `google-genai`, requires `GEMINI_API_KEY`).
- Results land in `articles.importance` (1-5), `articles.evaluated_at`, `articles.evaluator_version`, and per-link `article_tickers.impact` (`positive` / `negative` / `neutral`) + `article_tickers.impact_confidence`. The `ImpactLabel` StrEnum in @app/models.py is the source of truth for impact values.
- Tunables: `EVALUATION_POLL_INTERVAL_MINUTES`, `EVALUATOR_BATCH_SIZE`, `EVALUATOR_MAX_PER_RUN`, `EVALUATOR_VERSION`, `GEMINI_MODEL`.

# Web UI
- A minimal web UI is served at `/` by the same FastAPI app — Jinja2 templates progressively enhanced with HTMX (no build step, no SPA framework). Routes live in @app/ui.py; the JSON API in @app/main.py is untouched.
- Templates live in `app/templates/` (`base.html`, `index.html`, `_tickers.html`, `_articles.html`). Static assets (`style.css`, vendored `htmx.min.js`) live in `app/static/` and are mounted at `/static`.
- HTML routes: `GET /` (full page), `GET/POST/DELETE /ui/tickers` (sidebar partial), `GET /ui/tickers/{symbol}/articles?limit&offset` (articles partial). The article partial renders as a full `<section id="articles">` when `offset == 0` and as bare rows + a new "Load more" link when `offset > 0`, so HTMX `outerHTML` swaps append cleanly.
- UI mutations return rendered partials (never raise `HTTPException`); user-facing errors (duplicate add, unknown delete) render as an inline `.error` banner in the sidebar partial.

# Commands
Most common commands, try to use them instead of creating your own
- make up: start the app
- make down: stop the app and tests
- make test: start tests suite (rebuilds the test image so new migrations are picked up)
- make lint: start ruff check
- make lint-fix: start ruff check and fix
- make format: format the code
- make format-check: check the code format
- make migrate: run `alembic upgrade head` inside the running `app` container
- make migrate-revision name="...": autogenerate a new Alembic revision
