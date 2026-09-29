.PHONY: demo test test-postgis db-up db-down migrate

DB_URL ?= postgresql://iris:iris@localhost:5433/iris

# one command: install, run the fixture adapter, print summary
demo:
	uv run iris-ingest run fixture-nrw-csv --out out --fetched-at 2026-09-01T12:00:00Z

test:
	uv run pytest

db-up:
	docker compose up -d --wait

migrate:
	psql "$(DB_URL)" -f migrations/001_staging.sql

test-postgis: db-up
	IRIS_DATABASE_URL=$(DB_URL) uv run pytest -m postgis

db-down:
	docker compose down -v
