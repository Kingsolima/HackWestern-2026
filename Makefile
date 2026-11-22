# Keep a sourced ROS (or other) PYTHONPATH from leaking into the uv envs.
unexport PYTHONPATH

.PHONY: help install dev-backend dev-cad dev-frontend up down db test test-cad lint

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
