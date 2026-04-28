.PHONY: up down test lint lint-fix format format-check

up:
	docker compose up --build

down:
	docker compose --profile test down

test:
	docker compose --profile test run --rm test; docker compose --profile test down

lint:
	ruff check .

lint-fix:
	ruff check --fix .

format:
	ruff format .

format-check:
	ruff format --check .
