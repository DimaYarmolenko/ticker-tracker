# Project
This is a FastAPI app (Python 3.13) that uses SQLAlchemy and a PostgreSQL database.

# Code Style
- Use type hints as much as possible
- Try to use enums instead of magic strings or plain values if possible.

# Tests
The tests are located in @tests/ folder, writen with PyTest and have test database with fixtures that mimics the application database.

# Configuration and secrets
There are example files @.env.example and @.test.env.example where you can see what configs and secrets are required to run the app, but the real values are hidden from you, you do not need to know them.

# Docker
The app runs in Docker. The Dockerfile uses a multi-stage build:
- `app` stage: runs the FastAPI server
- `test` stage: runs the pytest suite in isolation

# Database
- The main database runs in a `db` Docker service (`postgres:17-alpine`). Data persists in a named volume (`postgres-data`) mounted at `/var/lib/postgresql/data`. It survives `docker compose down`; only `docker compose down -v` removes it. The `DATABASE_URL` env var controls the connection string.
- The test database runs in a separate `test-db` service (profile: `test`) with no named volume — it is ephemeral and discarded when the test container exits. The `TEST_DATABASE_URL` env var controls the test connection string.
- All tables are defined in @app/models.py, reference it if you need to know how to structure the data when you need to store the records in the DB or what type of data you can get when you read from the DB.

# News collection
- On startup, `app/scheduler.py` launches a `BackgroundScheduler` (APScheduler) that calls `app/news_fetcher.py` every `NEWS_POLL_INTERVAL_MINUTES` minutes (default 30). The first poll fires immediately on startup.
- `app/news_fetcher.py` fetches Google News RSS for each tracked ticker, filters articles older than `NEWS_MAX_AGE_DAYS` days, deduplicates by URL, and detects cross-mentions of other tracked symbols in article titles.
- Articles are stored in the `articles` table. The `article_tickers` join table handles the many-to-many relationship between articles and tickers.

# Commands
See @README.md for the full list of commands to run the app, tests, and linter. There is also a @Makefile that contains the most used commands.
