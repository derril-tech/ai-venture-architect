.PHONY: help dev build test lint format clean install

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pnpm install

dev: ## Start development environment
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	pnpm run dev

build: ## Build all applications
	pnpm run build

test: ## Run tests
	pnpm run test

lint: ## Run linting
	pnpm run lint

format: ## Format code
	pnpm run format

type-check: ## Run type checking
	pnpm run type-check

clean: ## Clean build artifacts and dependencies
	pnpm run clean
	docker-compose -f docker-compose.dev.yml down -v

services-up: ## Start development services only
	docker-compose -f docker-compose.dev.yml up -d

services-down: ## Stop development services
	docker-compose -f docker-compose.dev.yml down

services-logs: ## Show service logs
	docker-compose -f docker-compose.dev.yml logs -f

db-migrate: ## Run database migrations
	cd apps/api && alembic upgrade head

db-reset: ## Reset database
	docker-compose -f docker-compose.dev.yml down postgres
	docker volume rm ai-venture-architect_postgres_data
	docker-compose -f docker-compose.dev.yml up -d postgres
