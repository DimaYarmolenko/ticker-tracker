.PHONY: up down test lint lint-fix format format-check migrate migrate-revision

up:
	docker compose up --build

down:
	docker compose --profile test down

test:
	docker compose --profile test run --build --rm test; docker compose --profile test down

lint:
	ruff check .

lint-fix:
	ruff check --fix .

format:
	ruff format .

format-check:
	ruff format --check .

migrate:
	docker compose exec app alembic upgrade head

migrate-revision:
	docker compose exec app alembic revision --autogenerate -m "$(name)"
