.PHONY: up down test lint format check check-env eval _sync

# Validates the environment before any container starts. Derived from app/config.py's
# Settings model (see backend/app/infrastructure/env_check.py) — never a hand-kept list.
check-env:
	docker compose run --rm --no-deps backend python -m app.infrastructure.env_check
	@if [ -d frontend ]; then \
		cd frontend && npm run check-env; \
	else \
		echo "frontend/ not present yet — skipping frontend env check"; \
	fi

# Rebuilds the image: needed after changing requirements.txt or the Dockerfile.
up: check-env
	docker compose up --build -d --wait

# Starts the stack without rebuilding: app/tests are bind-mounted, so code is always fresh.
_sync:
	docker compose up -d --wait

down:
	docker compose down -v

test: _sync
	docker compose exec -T backend pytest -v
	@if [ -d frontend ]; then \
		cd frontend && npm run test -- --run; \
	else \
		echo "frontend/ not present yet — skipping frontend tests"; \
	fi

lint: _sync
	docker compose exec -T backend ruff check app tests
	docker compose exec -T backend ruff format --check app tests
	docker compose exec -T backend mypy app
	@if [ -d frontend ]; then \
		cd frontend && npm run lint && npx tsc --noEmit; \
	else \
		echo "frontend/ not present yet — skipping frontend lint"; \
	fi

format: _sync
	docker compose exec -T backend ruff check --fix app tests
	docker compose exec -T backend ruff format app tests
	@if [ -d frontend ]; then \
		cd frontend && npx prettier --write src; \
	else \
		echo "frontend/ not present yet — skipping frontend format"; \
	fi

# Exactly what CI runs.
check: lint test

eval:
	@test -f backend/evals/run.py \
		|| { echo "Eval suite arrives in SPEC 2 (see docs/SPEC-2.md)."; exit 1; }
	docker compose exec -T backend python -m evals.run
