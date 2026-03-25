.PHONY: help build up down restart logs shell migrate makemigrations superuser test lint format flush seed collectstatic celery beat

COMPOSE = docker compose
BACKEND = $(COMPOSE) exec backend
MANAGE = $(BACKEND) python manage.py

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build all Docker images
	$(COMPOSE) build

up: ## Start all services in detached mode
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

restart: ## Restart all services
	$(COMPOSE) restart

logs: ## Tail logs from all containers
	$(COMPOSE) logs -f

logs-backend: ## Tail backend logs
	$(COMPOSE) logs -f backend

logs-celery: ## Tail Celery worker logs
	$(COMPOSE) logs -f celery_worker

logs-beat: ## Tail Celery Beat logs
	$(COMPOSE) logs -f celery_beat

shell: ## Open Django interactive shell
	$(MANAGE) shell_plus

dbshell: ## Open database shell
	$(MANAGE) dbshell

migrate: ## Run database migrations
	$(MANAGE) migrate --noinput

makemigrations: ## Create new migration files
	$(MANAGE) makemigrations

superuser: ## Create a superuser account
	$(MANAGE) createsuperuser

test: ## Run backend tests with coverage
	$(BACKEND) pytest --cov=apps --cov-report=term-missing -v

test-app: ## Run tests for a specific app (usage: make test-app APP=contacts)
	$(BACKEND) pytest apps/$(APP)/ -v

lint: ## Lint backend code with flake8 and isort check
	$(BACKEND) flake8 .
	$(BACKEND) isort --check-only .

format: ## Format backend code with black and isort
	$(BACKEND) black .
	$(BACKEND) isort .

flush: ## Flush the database (WARNING: destroys all data)
	$(MANAGE) flush --noinput

collectstatic: ## Collect static files
	$(MANAGE) collectstatic --noinput

seed: ## Load seed data
	$(MANAGE) loaddata fixtures/*.json

# Frontend commands
frontend-install: ## Install frontend dependencies
	$(COMPOSE) exec frontend npm install

frontend-build: ## Build frontend for production
	$(COMPOSE) exec frontend npm run build

frontend-test: ## Run frontend tests
	$(COMPOSE) exec frontend npm test

# Infrastructure
ps: ## Show running containers
	$(COMPOSE) ps

volumes: ## List Docker volumes
	docker volume ls | grep clienthub

clean: ## Remove all containers, volumes, and images
	$(COMPOSE) down -v --rmi all --remove-orphans

rebuild: ## Full rebuild (down + build + up + migrate)
	$(COMPOSE) down -v
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	$(MANAGE) migrate --noinput
	$(MANAGE) collectstatic --noinput
	@echo "Rebuild complete."
