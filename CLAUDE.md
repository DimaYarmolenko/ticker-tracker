# Project
This is a Fast API app (python 3.13) that uses sqlalchemy and sqllite database.

# Code Style
- Use type hints as much as possible
- Try to use enums instead of magic strings or plain values if possible.

# Tests
The tests are located in @tests/ folder, writen with PyTest and have test database with fixtures that mimics the application database.

# Docker
The app runs in Docker. The Dockerfile uses a multi-stage build:
- `app` stage: runs the FastAPI server
- `test` stage: runs the pytest suite in isolation

```bash
# Build and start the app
docker compose up --build

# Run tests in a separate container
docker compose --profile test run --rm test
```
# Database
- The SQLite database is stored in a named volume (`ticker-data`) mounted at `/app/data/tickers.db` inside the container. It persists across `docker compose down` restarts; only `docker compose down -v` removes it. The `DATABASE_URL` env var controls the DB path.
- All tables are defined in @app/models.py, reference it if you need to know how to structure the data when you need to store the records in the DB or what type of data you can get when you read from the DB.


# Commands
See @README.md for the full list of commands to run the app, tests, and linter.
