# Ticker Tracker

A simple REST API for storing and managing stock ticker symbols, built with FastAPI and SQLite.

## Running the app

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.  
Interactive docs (Swagger UI) at `http://localhost:8000/docs`.

The database is stored in a Docker named volume and persists across container restarts. Only `docker compose down -v` will remove it.

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
```
