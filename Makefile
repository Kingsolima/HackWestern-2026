# Keep a sourced ROS (or other) PYTHONPATH from leaking into the uv envs.
unexport PYTHONPATH

.PHONY: help install dev-backend dev-cad dev-frontend up down db test test-cad lint prod-up prod-down deploy smoke

help:
	@echo "install       install backend + frontend deps"
	@echo "dev-backend   run FastAPI orchestrator on :8000 (reload)"
	@echo "dev-cad       run CadQuery worker in Docker on :8001"
	@echo "dev-frontend  run Vite dev server on :5173"
	@echo "up / down     start / stop the full docker compose stack"
	@echo "db            start only the local TimescaleDB"
	@echo "test          backend tests"
	@echo "test-cad      CAD worker tests (inside the CadQuery image)"
	@echo "lint          ruff + frontend lint"
	@echo "prod-up       run the production stack locally on http://localhost:8080"
	@echo "prod-down     stop it"
	@echo "deploy        pull main on the Vultr VM and rebuild (DEPLOY_HOST=vultr-hw)"
	@echo "smoke         replay every demo path on a running site (HOST=http://localhost:8080)"

install:
	cd backend && uv sync
	cd frontend && npm install

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-cad:
	docker compose up --build cad

dev-frontend:
	cd frontend && npm run dev

up:
	docker compose up --build

down:
	docker compose down

db:
	docker compose up -d db

test:
	cd backend && uv run pytest

test-cad:
	docker compose build cad
	docker compose run --rm --no-deps -v ./cad/tests:/app/tests:ro cad \
	  sh -c "pip install -q pytest httpx && python -m pytest -q -p no:cacheprovider tests"

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

# Production stack (Caddy + backend + CAD). Separate project name so it never replaces the
# dev containers.
PROD = docker compose -p hackwestern-prod -f docker-compose.yml -f docker-compose.prod.yml
DEPLOY_HOST ?= vultr-hw

prod-up:
	WEB_HTTP_PORT=8080 WEB_HTTPS_PORT=8443 $(PROD) up -d --build web backend cad

prod-down:
	WEB_HTTP_PORT=8080 WEB_HTTPS_PORT=8443 $(PROD) down

deploy:
	ssh $(DEPLOY_HOST) 'cd /opt/hackwestern && git pull --ff-only && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build web backend cad'

# End-to-end check of a running stack: health, database, then one replay job per demo path.
HOST ?= http://localhost:8080
smoke:
	python3 scripts/smoke.py $(HOST)
