# Makefile for EcomReview AI (1-Click Operations & Reproducibility)

PYTHON ?= .venv/Scripts/python.exe
PYTEST ?= .venv/Scripts/pytest.exe

.PHONY: help seed api ui test lint eval-rq12 eval-rq3 error-analysis docker-up docker-down

help:
	@echo "EcomReview AI - Available Commands:"
	@echo "  make seed            - Seed demo database (real_shop + S1..S10)"
	@echo "  make api             - Start FastAPI backend on port 8000"
	@echo "  make ui              - Start Streamlit dashboard on port 8501"
	@echo "  make test            - Run full Pytest suite"
	@echo "  make lint            - Run Ruff linter and format check"
	@echo "  make eval-rq12       - Reproduce RQ1 & RQ2 benchmarks"
	@echo "  make eval-rq3        - Reproduce RQ3 groundedness, blind A/B & adoption"
	@echo "  make error-analysis  - Generate Pareto E1-E10 taxonomy & PNG figures"
	@echo "  make docker-up       - Launch 3-service Docker Compose stack"
	@echo "  make docker-down     - Stop Docker Compose stack"

seed:
	$(PYTHON) scripts/seed_demo.py

api:
	$(PYTHON) -m uvicorn ecomreview.api.main:app --host 0.0.0.0 --port 8000 --reload

ui:
	$(PYTHON) -m streamlit run src/ecomreview/ui/app.py --server.port 8501

test:
	$(PYTEST) -v

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format . --check

eval-rq12:
	$(PYTHON) -m ecomreview.eval.run_rq1_rq2

eval-rq3:
	$(PYTHON) scripts/make_blind_eval.py

error-analysis:
	$(PYTHON) scripts/analyze_errors_and_figures.py

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# CreBy: MenBoyBMN

