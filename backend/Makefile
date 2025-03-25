# === Variables ===
PYTHON ?= python
ENV_FILE ?= .env
APP_DIR := ./
TEST_DIR := $(APP_DIR)/app/tests
VENV := .venv
DOCKER_COMPOSE := docker-compose

# === Load .env if exists ===
ifneq ("$(wildcard $(ENV_FILE))","")
	include $(ENV_FILE)
	export
endif

# === Targets ===
.PHONY: help setup-env test test-e2e onboarding db-upgrade db-revision lint

help:
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup-env: ## Install requirements
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

test-unit: ## Run unit tests
	PYTHONPATH=$(APP_DIR) pytest $(TEST_DIR) --ignore=$(TEST_DIR)/workers --disable-warnings -vv

test-integration: ## Run integration tests
	PYTHONPATH=$(APP_DIR) pytest $(TEST_DIR) -m integration --disable-warnings

test-e2e: ## Run integration tests
	PYTHONPATH=./ $(PYTHON) scripts/test_e2e_flow.py

onboarding: ## Run onboarding setup
	PYTHONPATH=./ $(PYTHON) scripts/setup_onboarding.py

lint: ## Run ruff linter
	ruff check $(APP_DIR)

db-upgrade: ## Run latest migrations
	alembic upgrade head

db-revision: ## Generate Alembic revision
ifndef m
	$(error Usage: make db-revision m="message")
endif
	alembic revision --autogenerate -m "$(m)"

db-reset: ## Reset database
	psql -U user -d chatbotdb -h database -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"