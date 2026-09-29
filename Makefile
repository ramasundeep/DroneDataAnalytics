# CD Sim — single entry point for developers.
# Run `make help` for the list of targets. Every target is documented in
# README.md and docs/ONBOARDING.md.

SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON      ?= python3.11
VENV        := .venv
PY          := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
CONSOLE_DIR := apps/instructor-console

# Python packages, installed editable into one dev virtualenv.
PY_PACKAGES := services/common services/api services/recorder services/assessment \
               services/sitl services/rl terrain/builder terrain/services

# Profiles started by `make dev`. sitl / multiplayer / rl are opt-in.
DEV_PROFILES := --profile core --profile terrain --profile lms
COMPOSE      := docker compose

.PHONY: help setup dev down status logs smoke test test-py test-console \
        integration lint fmt typecheck schemas docs new-platform new-area \
        sitl package deploy-box clean

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup
setup: ## One-time: venv, Python + Node deps, git-lfs, .env
	@command -v $(PYTHON) >/dev/null || { echo "Need $(PYTHON) on PATH (see docs/ONBOARDING.md)"; exit 1; }
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install $(foreach p,$(PY_PACKAGES),-e $(p))
	cd $(CONSOLE_DIR) && npm ci
	@if command -v git-lfs >/dev/null; then git lfs install --local; else echo "WARN: git-lfs not installed; binary assets will not download"; fi
	@test -f .env || cp .env.example .env
	@echo "setup complete. Next: make dev"

# ---------------------------------------------------------------- run
dev: ## Build + start core, terrain and lms services; wait until healthy
	@test -f .env || cp .env.example .env
	$(COMPOSE) $(DEV_PROFILES) up -d --build --wait
	@./scripts/smoke_dev.sh

down: ## Stop all services (keeps volumes)
	$(COMPOSE) --profile '*' down

status: ## Show service health
	$(COMPOSE) --profile '*' ps

logs: ## Tail logs of running services
	$(COMPOSE) --profile '*' logs -f --tail=100

smoke: ## Curl every Phase-0 health endpoint
	./scripts/smoke_dev.sh

sitl: ## Build + start ArduPilot SITL (opt-in profile; slow first build)
	$(COMPOSE) --profile sitl up -d --build

# ---------------------------------------------------------------- quality
test: test-py test-console ## Unit tests (Python + console). Must be green for DoD.

test-py:
	$(PY) -m pytest -m "not integration"

test-console:
	cd $(CONSOLE_DIR) && npm test

integration: ## Integration tests against running `make dev` stack
	$(PY) -m pytest -m integration tests

lint: schemas ## ruff, eslint, prettier check, compose config
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
	cd $(CONSOLE_DIR) && npm run lint && npm run format:check
	$(COMPOSE) --profile '*' config --quiet

fmt: ## Auto-format Python and TS
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .
	cd $(CONSOLE_DIR) && npm run format

typecheck: ## mypy (strict) + tsc
	$(VENV)/bin/mypy $(foreach p,$(PY_PACKAGES),$(p)/src) scripts
	cd $(CONSOLE_DIR) && npm run typecheck

schemas: ## Validate JSON schemas + all manifests, compile protobuf
	$(PY) scripts/validate_manifests.py
	@mkdir -p schemas/gen/python
	$(PY) -m grpc_tools.protoc -Ischemas --python_out=schemas/gen/python schemas/cdsim/v1/*.proto

docs: ## Build the documentation site (strict)
	$(VENV)/bin/mkdocs build --strict

# ---------------------------------------------------------------- scaffolding
new-platform: ## Scaffold a platform: make new-platform id=<platform_id>
	@test -n "$(id)" || { echo "usage: make new-platform id=<platform_id>"; exit 2; }
	$(PY) scripts/new_platform.py $(id)

new-area: ## Scaffold an area package manifest: make new-area id=<area_id>
	@test -n "$(id)" || { echo "usage: make new-area id=<area_id>"; exit 2; }
	$(PY) scripts/new_area.py $(id)

# ---------------------------------------------------------------- packaging
package: ## (Phase 8) Build installers — not implemented yet
	@echo "make package: not implemented — scheduled for Phase 8 (docs/10_ROADMAP.md)"; exit 1

deploy-box: ## (Phase 8) Produce air-gap bundle — not implemented yet
	@echo "make deploy-box: not implemented — scheduled for Phase 8 (docs/09_DEPLOYMENT_OFFLINE.md)"; exit 1

clean: ## Remove local build caches (not volumes)
	rm -rf schemas/gen site .pytest_cache .mypy_cache .ruff_cache $(CONSOLE_DIR)/dist
