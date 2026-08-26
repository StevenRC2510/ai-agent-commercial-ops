.PHONY: up down test lint format check eval _require-stack

up:
	docker compose up --build -d

down:
	docker compose down -v

_require-stack:
	@docker compose ps --status running --services 2>/dev/null | grep -qx backend \
		|| { echo "The stack is not running. Start it with: make up"; exit 1; }

test: _require-stack
	docker compose exec -T backend pytest -v
	@if [ -d frontend ]; then \
		cd frontend && npm run test -- --run; \
	else \
		echo "frontend/ not present yet — skipping frontend tests"; \
	fi

lint: _require-stack
	docker compose exec -T backend ruff check app tests
	docker compose exec -T backend ruff format --check app tests
	docker compose exec -T backend mypy app
	@if [ -d frontend ]; then \
		cd frontend && npm run lint && npx tsc --noEmit; \
	else \
		echo "frontend/ not present yet — skipping frontend lint"; \
	fi

format: _require-stack
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
