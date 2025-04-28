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
ifdef vv
	PYTHONPATH=$(APP_DIR) pytest $(TEST_DIR) -m unit --disable-warnings -vv
else
	PYTHONPATH=$(APP_DIR) pytest $(TEST_DIR) -m unit --disable-warnings
endif

test-integration: ## Run integration tests
	PYTHONPATH=$(APP_DIR) pytest $(TEST_DIR) -m integration --disable-warnings

test-e2e: ## Run integration tests
	PYTHONPATH=$(APP_DIR) $(PYTHON) scripts/test_e2e_flow.py

onboarding: ## Run onboarding setup
	PYTHONPATH=$(APP_DIR) $(PYTHON) scripts/setup_onboarding.py

worker-consumer: ## Run Consumer
	PYTHONPATH=$(APP_DIR) $(PYTHON) app/workers/consumer/message_consumer.py 

worker-response: ## Run Response sender
	PYTHONPATH=$(APP_DIR) $(PYTHON) app/workers/response_sender/response_sender.py

worker-ai: ## Run Response sender
	PYTHONPATH=$(APP_DIR) $(PYTHON) app/workers/ai_replier.py

worker-arq: ## Run Response sender
	PYTHONPATH=$(APP_DIR) arq app.workers.batch_contacts.contact_creator.WorkerSettings

worker-researcher: ## Run Response sender
	PYTHONPATH=$(APP_DIR) arq app.workers.researcher.WorkerSettings

worker-ingester: ## Run Knowledge Ingester
	PYTHONPATH=$(APP_DIR) arq app.workers.knowledge_ingester.WorkerSettings


run-app: ## Run Fast API app
	PYTHONPATH=$(APP_DIR) uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload



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


	
generate-secret: ## Generate Secret Key
	openssl rand -base64 32

gcs-export-key:  ## Export GOOGLE_APPLICATION_CREDENTIALS  Key
	export GOOGLE_APPLICATION_CREDENTIALS=./keys/lambdalabs-gcp-663770819dd9.json
