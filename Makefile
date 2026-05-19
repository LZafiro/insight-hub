.PHONY: help up down logs migrate seed test lint format typecheck clean

help:
	@echo "Targets:"
	@echo "  up         Spin up Docker stack (postgres, redis, backend)"
	@echo "  down       Stop stack and remove volumes"
	@echo "  logs       Tail backend logs"
	@echo "  migrate    Apply database migrations"
	@echo "  seed       Seed demo workspace, user, and document"
	@echo "  test       Run backend test suite with coverage"
	@echo "  lint       Lint backend"
	@echo "  format     Format backend code"
	@echo "  typecheck  Run mypy"
	@echo "  clean      Remove caches and build artifacts"

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m scripts.seed_data

test:
	cd backend && uv run pytest --cov=app

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format .

typecheck:
	cd backend && uv run mypy app

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .mypy_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
