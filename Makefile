# Makefile for EcomReview AI (Pure Backend API Operations)

PYTHON ?= .venv/Scripts/python.exe
PYTEST ?= .venv/Scripts/pytest.exe

.PHONY: help seed api test lint docker-up docker-down

help:
	@echo "EcomReview AI - Backend Production Commands:"
	@echo "  make api             - Start FastAPI backend on port 8000"
	@echo "  make seed            - Seed/verify demo database and export OpenAPI"
	@echo "  make test            - Run full Pytest production test suite"
	@echo "  make lint            - Run Ruff linter and format check"
	@echo "  make docker-up       - Launch 2-service Docker Compose stack (db, api)"
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
