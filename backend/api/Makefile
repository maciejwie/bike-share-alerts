.PHONY: install dev test lint format help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync --extra dev

dev: ## Run development server
	uv run uvicorn index:app --reload

test: ## Run tests
	uv run pytest

lint: ## Run linting
	uv run ruff check . --fix

format: ## Format code
	uv run ruff format .
