# Developer entry points. Every target is also what CI runs, so local == CI.
# Requires: uv, az (with bicep), gitleaks.
# Recipes avoid shell-specific syntax so they work under sh (Linux, macOS,
# Git Bash) and cmd.exe (GNU Make started from PowerShell on Windows).

.DEFAULT_GOAL := help
AUDIT_REQ := .venv/audit-requirements.txt
BICEP_FILES := $(shell git ls-files "*.bicep")

define newline


endef

.PHONY: help install fmt lint typecheck test validate-tenants bicep iac-scan secrets audit check
.PHONY: up down data data-verify data-native corpus test-integration docker-build compare-validators

help: ## List targets
	@uv run --quiet python scripts/make_help.py Makefile

install: ## Install locked dependencies and git hooks
	uv sync --locked
	uv run pre-commit install

fmt: ## Format and auto-fix
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Ruff lint and format check
	uv run ruff check .
	uv run ruff format --check .

typecheck: ## mypy (strict)
	uv run mypy

test: ## Unit tests (no cloud, no Docker)
	uv run pytest -m "not integration and not cloud"

validate-tenants: ## Validate every tenants/*/config.yaml
	uv run rechnungscheck tenants validate

bicep: ## Lint every Bicep file
	$(foreach f,$(BICEP_FILES),az bicep lint --file $(f)$(newline))

iac-scan: ## checkov on deployable Bicep (preflight probes are never deployed and are excluded)
	uvx --from checkov checkov -d infra/bicep --framework bicep --skip-path preflight --compact --quiet

secrets: ## gitleaks over the full git history
	gitleaks git . --no-banner --redact

audit: ## pip-audit over the locked dependency set (all groups)
	uv export --format requirements-txt --all-groups --no-emit-project --quiet -o $(AUDIT_REQ)
	uvx pip-audit -r $(AUDIT_REQ) --disable-pip --progress-spinner off

check: lint typecheck test validate-tenants bicep iac-scan secrets audit ## Everything ci.yml runs that exists so far

# --- local stack and data (Phase 2) -------------------------------------------------

up: ## Start Postgres, Azurite and the KoSIT validator (Docker Compose)
	docker compose up -d --build --wait postgres azurite validator

down: ## Stop the local stack (keeps volumes)
	docker compose down

data: ## Generate the dataset in the pinned container (canonical bytes; needs Docker)
	uv run python scripts/datagen_docker.py generate

data-verify: ## Check rendered documents against the committed SHA-256 lists (in the container)
	uv run python scripts/datagen_docker.py verify

data-native: ## Generate with the host Python (fast; PDF/PNG bytes are NOT canonical, never commit them)
	uv run python -m datagen generate

corpus: ## Fetch the public ZUGFeRD corpus at the pinned commit into data/corpus
	uv run python scripts/fetch_corpus.py

test-integration: ## Integration tests (needs `make up`)
	uv run pytest -m integration

docker-build: ## Build the validator images
	docker build -t rechnungscheck/validator-kosit:dev validator/kosit
	docker build -t rechnungscheck/validator-mustang:dev validator/mustang

compare-validators: ## KoSIT vs Mustang on corpus + generated files (needs `make up corpus data docker-build`)
	uv run python -m evals.runners.validator_comparison
