.PHONY: help install dev-backend dev-cad dev-frontend up down db test lint

help:
	@echo "install       install backend + frontend deps"
	@echo "dev-backend   run FastAPI orchestrator on :8000 (reload)"
	@echo "dev-cad       run CadQuery worker in Docker on :8001"
	@echo "dev-frontend  run Vite dev server on :5173"
	@echo "up / down     start / stop the full docker compose stack"
	@echo "db            start only the local TimescaleDB"
	@echo "test          backend tests"
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

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint
