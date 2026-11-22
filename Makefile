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
