# =============================================================================
# ArborWatch — Makefile
# =============================================================================
# Common commands for development, testing, and deployment.
# Usage: make <target>
# =============================================================================

.PHONY: help up down build restart logs shell dbshell migrate makemigrations \
        test coverage lint format typecheck superuser seed clean

# Default target
help: ## Show this help message
	@echo "ArborWatch — Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Docker
# =============================================================================

up: ## Start all Docker services
	docker compose up -d

down: ## Stop all Docker services
	docker compose down

build: ## Build Docker images (no cache)
	docker compose build --no-cache

restart: ## Restart all services
	docker compose restart

logs: ## Follow logs for all services
	docker compose logs -f

logs-web: ## Follow logs for web service only
	docker compose logs -f web

logs-worker: ## Follow logs for Celery worker
	docker compose logs -f celery-worker

# =============================================================================
# Django Management
# =============================================================================

shell: ## Open Django shell (IPython)
	docker compose exec web python manage.py shell_plus

dbshell: ## Open database shell
	docker compose exec web python manage.py dbshell

migrate: ## Run database migrations
	docker compose exec web python manage.py migrate

makemigrations: ## Create new migrations
	docker compose exec web python manage.py makemigrations

superuser: ## Create a superuser
	docker compose exec web python manage.py createsuperuser

collectstatic: ## Collect static files
	docker compose exec web python manage.py collectstatic --noinput

# =============================================================================
# Testing & Quality
# =============================================================================

test: ## Run all tests
	docker compose exec web python -m pytest -v --tb=short

test-fast: ## Run tests without migrations (faster)
	docker compose exec web python -m pytest -v --tb=short --reuse-db

coverage: ## Run tests with coverage report
	docker compose exec web python -m pytest --cov=apps --cov-report=html --cov-report=term-missing

lint: ## Run all linters
	docker compose exec web flake8 apps/ config/
	docker compose exec web isort --check-only apps/ config/
	docker compose exec web black --check apps/ config/

format: ## Auto-format code
	docker compose exec web isort apps/ config/
	docker compose exec web black apps/ config/

typecheck: ## Run type checking
	docker compose exec web mypy apps/ config/

# =============================================================================
# Data & Seeds
# =============================================================================

seed: ## Run all seed commands
	docker compose exec web python manage.py seed_geodata

# =============================================================================
# Celery
# =============================================================================

celery-status: ## Check Celery worker status
	docker compose exec celery-worker celery -A config inspect active

celery-queues: ## Show Celery queue lengths
	docker compose exec celery-worker celery -A config inspect active_queues

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Remove all containers, volumes, and cached data
	docker compose down -v --remove-orphans
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage .pytest_cache/
