# VTOL-1 digital twin - operator entry points. Run from vtol-twin/.
SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help env htpasswd up down restart ps logs wait setup reset-thing verify-phase1 test test-js test-py demo clean

help: ## list targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-16s %s\n",$$1,$$2}'

env: ## create .env from .env.example if missing
	@test -f .env || { cp .env.example .env && echo "created .env - review it"; }

htpasswd: env ## generate nginx basic-auth file from .env
	@./scripts/gen-htpasswd.sh

up: htpasswd ## start the stack (detached)
	$(COMPOSE) up -d

down: ## stop the stack (volumes kept)
	$(COMPOSE) down

restart: down up ## restart the stack

ps: ## service status incl. health
	$(COMPOSE) ps

logs: ## follow logs (SERVICE=name to filter)
	$(COMPOSE) logs -f --tail=200 $(SERVICE)

wait: ## block until all healthchecks pass
	@./scripts/wait-healthy.sh

setup: ## create policy, Thing and MQTT connection in Ditto (idempotent)
	@./ditto/setup.sh

reset-thing: ## overwrite the Thing with ditto/thing-VTOL-1.json
	@./ditto/setup.sh --reset

verify-phase1: ## publish sample telemetry over MQTT and read it back from the Thing
	@./scripts/verify-phase1.sh

test: test-js test-py ## run unit tests

test-js: ## mapper tests (node)
	node ditto/tests/test_mapping.js

test-py: ## model / compose tests (pytest)
	python3 -m pytest -q ditto/tests

demo: up wait setup verify-phase1 ## cold start to a verified Phase 1 twin (later phases extend this)

clean: down ## stop and delete all data volumes
	$(COMPOSE) down -v --remove-orphans
