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
	docker compose exec -T backend ruff check app tests scripts
	docker compose exec -T backend ruff format --check app tests scripts
	docker compose exec -T backend mypy app scripts
	@if [ -d frontend ]; then \
		cd frontend && npx prettier --check src && npm run lint && npx tsc --noEmit; \
	else \
		echo "frontend/ not present yet — skipping frontend lint"; \
	fi

format: _sync
	docker compose exec -T backend ruff check --fix app tests scripts
	docker compose exec -T backend ruff format app tests scripts
	@if [ -d frontend ]; then \
		cd frontend && npx prettier --write src; \
	else \
		echo "frontend/ not present yet — skipping frontend format"; \
	fi

# Demo and acceptance runs mutate data; this makes them repeatable.
reset: _sync
	docker compose exec -T backend python -m scripts.reset_demo_data

# Sizes the cacheable prompt prefix against LLM_MODEL's floor (docs/adr/0011).
measure-prompt: _sync
	docker compose exec -T backend python -m scripts.measure_prompt_prefix

# Exactly what CI runs.
check: lint test

# Measures the real model (docs/SPEC-2.md 11.1): needs DEMO_MODE=false, a funded
# ANTHROPIC_API_KEY and network. Refuses to run on the fake clients, and never runs in CI.
# Mounts the working tree over the image's copy so a case edit needs no rebuild.
# Another model: make eval EVAL_ARGS="--model claude-sonnet-5"
eval: _sync
	@test -f backend/evals/run.py \
		|| { echo "Eval suite arrives in SPEC 2 (see docs/SPEC-2.md)."; exit 1; }
	docker compose run --rm -v "$(CURDIR)/backend/evals:/app/evals" \
		backend python -m evals.run $(EVAL_ARGS)
