# SE Demo & POV Builder — common tasks. Run from this directory.
PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: help install install-backend install-frontend dev backend frontend build serve test test-backend test-frontend lint validate-content seed clean

help:
	@echo "make install           Create .venv, install backend + frontend dependencies"
	@echo "make dev               Run API (127.0.0.1:8000) and UI dev server (127.0.0.1:5173)"
	@echo "make build && make serve   Build the UI and serve everything from 127.0.0.1:8000"
	@echo "make test              Backend pytest + frontend vitest"
	@echo "make lint              ruff + TypeScript type-check"
	@echo "make validate-content  Validate personas/, knowledge/, workflows/"

install: install-backend install-frontend

install-backend:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e "backend[dev]"

install-frontend:
	cd frontend && npm ci

backend:
	$(BIN)/python -m se_pov_builder

frontend:
	cd frontend && npm run dev

dev:
	@echo "API: http://127.0.0.1:8000/docs   UI: http://127.0.0.1:5173"
	@trap 'kill 0' INT TERM EXIT; $(BIN)/python -m se_pov_builder & (cd frontend && npm run dev); wait

build:
	cd frontend && npm run build

serve:
	SEPB_FRONTEND_DIST=$(CURDIR)/frontend/dist $(BIN)/python -m se_pov_builder

test: test-backend test-frontend

test-backend:
	cd backend && ../$(BIN)/pytest

test-frontend:
	cd frontend && npm test

lint:
	cd backend && ../$(BIN)/ruff check .
	cd frontend && npm run typecheck

validate-content:
	$(BIN)/python -m se_pov_builder.validate_content

clean:
	rm -rf $(VENV) frontend/node_modules frontend/dist backend/*.egg-info
