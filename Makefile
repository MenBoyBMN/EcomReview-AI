# Makefile for EcomReview AI (Pure Backend API Operations)

ifeq ($(OS),Windows_NT)
    PYTHON ?= .venv/Scripts/python.exe
    PYTEST ?= .venv/Scripts/pytest.exe
else
    PYTHON ?= .venv/bin/python
    PYTEST ?= .venv/bin/pytest
endif

.PHONY: help seed api test lint frontend-dev frontend-build docker-up docker-down

help:
	@echo "EcomReview AI - Production Commands:"
	@echo "  make api             - Start FastAPI backend on port 8000"
	@echo "  make seed            - Seed/verify demo database and export OpenAPI"
	@echo "  make test            - Run full Pytest production test suite"
	@echo "  make lint            - Run Ruff linter and format check"
	@echo "  make frontend-dev    - Start React Vite dev server on port 5173"
	@echo "  make frontend-build  - Build production React bundle"
	@echo "  make docker-up       - Launch 3-service Docker Compose stack (db, api, frontend)"
	@echo "  make docker-down     - Stop Docker Compose stack"

api:
	$(PYTHON) -m uvicorn ecomreview.api.main:app --host 0.0.0.0 --port 8000 --reload

seed:
	$(PYTHON) scripts/seed_demo.py

test:
	$(PYTEST) -v

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format . --check

frontend-dev:
	npm --prefix frontend run dev

frontend-build:
	npm --prefix frontend run build

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# Academic / Research Reproducibility targets (stored in Abount_System):
eval-rq12:
	$(PYTHON) Abount_System/src/ecomreview/eval/run_rq1_rq2.py

eval-rq3:
	$(PYTHON) Abount_System/scripts/make_blind_eval.py

error-analysis:
	$(PYTHON) Abount_System/scripts/analyze_errors_and_figures.py

# CreBy: MenBoyBMN
