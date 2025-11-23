.PHONY: install dev-api test-api lint-api migrate dev-worker deploy-api deploy-worker help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install backend API dependencies
	$(MAKE) -C backend/api install

dev-api: ## Run backend API development server
	$(MAKE) -C backend/api dev

test-api: ## Run backend API tests
	$(MAKE) -C backend/api test

lint-api: ## Run backend API linting
	$(MAKE) -C backend/api lint

migrate: ## Run database migrations
	cd backend/migrate && go run main.go

dev-worker: ## Run Cloudflare Worker in development mode
	cd cloudflare-worker && wrangler dev

deploy-api: ## Deploy backend API to Vercel
	vercel --prod

deploy-worker: ## Deploy Cloudflare Worker
	cd cloudflare-worker && wrangler deploy
