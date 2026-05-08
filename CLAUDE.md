# Code Style
- Use type hints as much as possible
- Try to use enums instead of magic strings or plain values if possible.

# Configuration and secrets
There are example files @.env.example and @.test.env.example where you can see what configs and secrets are required to run the app, but the real values are hidden from you, you do not need to know them.

# Database
- The main database runs in a `db` Docker service (`postgres:17-alpine`). Data persists in a named volume (`postgres-data`) mounted at `/var/lib/postgresql/data`. It survives `docker compose down`; only `docker compose down -v` removes it. The `DATABASE_URL` env var controls the connection string.
- The test database runs in a separate `test-db` service (profile: `test`) with no named volume — it is ephemeral and discarded when the test container exits. The `TEST_DATABASE_URL` env var controls the test connection string.
- All tables are defined in @app/models.py, reference it if you need to know how to structure the data when you need to store the records in the DB or what type of data you can get when you read from the DB.

# News collection
- On startup, `app/scheduler.py` launches a `BackgroundScheduler` (APScheduler) that calls `app/news_fetcher.py` every `NEWS_POLL_INTERVAL_MINUTES` minutes (default 30). The first poll fires immediately on startup.
- `app/news_fetcher.py` fetches Google News RSS for each tracked ticker, filters articles older than `NEWS_MAX_AGE_DAYS` days, deduplicates by URL, and detects cross-mentions of other tracked symbols in article titles.
- Articles are stored in the `articles` table. The `article_tickers` join table handles the many-to-many relationship between articles and tickers.

# Commands
Most common commands, try to use them instead of creating your own
- make up: start the app
- make down: stop the app and tests
- make test: start tests suite
- make lint: start ruff check
- make lint-fix: start ruff check and fix
- make format: format the code
- make format-check: check the code format
