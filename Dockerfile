FROM python:3.13-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM base AS app

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]


FROM base AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY app/ ./app/
COPY tests/ ./tests/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY pyproject.toml .

CMD ["python", "-m", "pytest", "tests/", "-v"]
