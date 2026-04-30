# Ticker Tracker

A REST API for storing and managing stock ticker symbols and collecting related news, built with FastAPI and PostgreSQL.

## Running the app

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.  
Interactive docs (Swagger UI) at `http://localhost:8000/docs`.

The PostgreSQL database persists in a named Docker volume (`postgres-data`) across container restarts. Only `docker compose down -v` will remove it.

## Running tests

```bash
docker compose --profile test run --rm test
```

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
| `GET` | `/tickers/{symbol}/news` | Get news for a ticker (supports `?limit=20&offset=0`) |

## News collection

On startup the app launches a background scheduler that polls Google News RSS for all tracked tickers. Each poll:

- Fetches one RSS feed per ticker (`https://news.google.com/rss/search?q={SYMBOL}+stock`)
- Skips articles older than `NEWS_MAX_AGE_DAYS` days (default `2`)
- Deduplicates articles by URL — the same article appearing in multiple ticker feeds is stored once and linked to all relevant tickers
- Scans article titles for cross-mentions of other tracked symbols and links those too

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NEWS_POLL_INTERVAL_MINUTES` | `30` | How often to poll for new articles |
| `NEWS_MAX_AGE_DAYS` | `2` | Maximum article age to collect |

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
```
