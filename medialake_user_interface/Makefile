# ──────────────────────────────────────────────────────────────
# MediaLake Playwright Test Runner
# ──────────────────────────────────────────────────────────────
#
# Usage:
#   make test                          # Run all E2E tests (default config)
#   make test-pipelines                # All pipeline import tests
#   make test-marengo3os               # Marengo 3.0 OpenSearch pipeline tests
#   make test-marengo3s3v              # Marengo 3.0 S3 Vectors pipeline tests
#   make test-marengo27os              # Marengo 2.7 OpenSearch pipeline tests
#   make test-marengo27s3v             # Marengo 2.7 S3 Vectors pipeline tests
#   make test-collections              # Collections E2E tests
#   make test-system                   # System / semantic provider tests
#   make test-perf                     # Performance benchmarks
#   make test-integration              # CI integration tests
#
# Override AWS profile:
#   make test-marengo3os AWS_PROFILE=ml-uat4
#
# Override base URL directly:
#   make test-pipelines PLAYWRIGHT_BASE_URL=https://d1234.cloudfront.net
#
# Pass extra Playwright flags:
#   make test-marengo3os EXTRA="--headed --debug"
#
# ──────────────────────────────────────────────────────────────

SHELL := /bin/bash

# AWS profile — set via env or override on the command line
#   make test-marengo3os profile=ml-uat4
profile ?= $(shell echo $$AWS_PROFILE)
EXTRA   ?=

# Export as AWS_PROFILE so Playwright / resolveCloudFrontUrlSync picks it up
export AWS_PROFILE := $(profile)

# Base playwright command
PW := npx playwright test

# ── Configs ──────────────────────────────────────────────────
CFG_DEFAULT     := playwright.config.ts
CFG_PIPELINES   := playwright.pipelines.config.ts
CFG_COLLECTIONS := playwright.collections.config.ts
CFG_PERF        := playwright.perf.config.ts
CFG_CI          := playwright.ci.config.ts

# ── Default ──────────────────────────────────────────────────
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'

# ── All tests ────────────────────────────────────────────────
.PHONY: test
test: ## Run all E2E tests (default config)
	$(PW) --config=$(CFG_DEFAULT) $(EXTRA)

# ── Pipeline tests ───────────────────────────────────────────
.PHONY: test-pipelines
test-pipelines: ## All pipeline import & deploy tests
	$(PW) --config=$(CFG_PIPELINES) $(EXTRA)

# Marengo 3.0
.PHONY: test-marengo3os
test-marengo3os: ## Marengo 3.0 Bedrock → OpenSearch pipelines
	$(PW) --config=$(CFG_PIPELINES) --grep "Marengo 3.0.*OpenSearch" $(EXTRA)

.PHONY: test-marengo3s3v
test-marengo3s3v: ## Marengo 3.0 Bedrock → S3 Vectors pipelines
	$(PW) --config=$(CFG_PIPELINES) --grep "Marengo 3.0.*S3 Vectors" $(EXTRA)

.PHONY: test-marengo3
test-marengo3: ## All Marengo 3.0 pipeline tests
	$(PW) --config=$(CFG_PIPELINES) --grep "Marengo 3.0" $(EXTRA)

# Marengo 2.7
.PHONY: test-marengo27os
test-marengo27os: ## Marengo 2.7 Bedrock → OpenSearch pipelines
	$(PW) --config=$(CFG_PIPELINES) --grep "Marengo 2.7.*OpenSearch" $(EXTRA)

.PHONY: test-marengo27s3v
test-marengo27s3v: ## Marengo 2.7 Bedrock → S3 Vectors pipelines
	$(PW) --config=$(CFG_PIPELINES) --grep "Marengo 2.7.*S3 Vectors" $(EXTRA)

.PHONY: test-marengo27
test-marengo27: ## All Marengo 2.7 pipeline tests
	$(PW) --config=$(CFG_PIPELINES) --grep "Marengo 2.7" $(EXTRA)

# API-based pipelines (require TWELVELABS_API_KEY)
.PHONY: test-pipelines-api
test-pipelines-api: ## TwelveLabs API pipeline tests (needs TWELVELABS_API_KEY)
	$(PW) --config=$(CFG_PIPELINES) --grep "TwelveLabs API" $(EXTRA)

# Coactive pipelines (require COACTIVE_API_KEY)
.PHONY: test-pipelines-coactive
test-pipelines-coactive: ## Coactive pipeline tests (needs COACTIVE_API_KEY)
	$(PW) --config=$(CFG_PIPELINES) --grep "Coactive" $(EXTRA)

# Default pipelines
.PHONY: test-pipelines-default
test-pipelines-default: ## Default Audio/Image/Video pipelines
	$(PW) --config=$(CFG_PIPELINES) --grep "Default" $(EXTRA)

# Enrichment pipelines
.PHONY: test-pipelines-enrichment
test-pipelines-enrichment: ## Enrichment pipelines (Pegasus, External Metadata)
	$(PW) --config=$(CFG_PIPELINES) --grep "Enrichment\|Pegasus" $(EXTRA)

# Transcription pipelines
.PHONY: test-pipelines-transcription
test-pipelines-transcription: ## Transcription pipelines
	$(PW) --config=$(CFG_PIPELINES) --grep "Transcription" $(EXTRA)

# ── Collections tests ────────────────────────────────────────
.PHONY: test-collections
test-collections: ## All collections E2E tests
	$(PW) --config=$(CFG_COLLECTIONS) $(EXTRA)

.PHONY: test-collections-crud
test-collections-crud: ## Collections CRUD tests
	$(PW) --config=$(CFG_COLLECTIONS) collection-crud $(EXTRA)

.PHONY: test-collections-sharing
test-collections-sharing: ## Collections sharing tests
	$(PW) --config=$(CFG_COLLECTIONS) collection-sharing $(EXTRA)

.PHONY: test-collections-groups
test-collections-groups: ## Collection groups tests
	$(PW) --config=$(CFG_COLLECTIONS) collection-groups $(EXTRA)

.PHONY: test-collections-subcollections
test-collections-subcollections: ## Sub-collections tests
	$(PW) --config=$(CFG_COLLECTIONS) sub-collections $(EXTRA)

# ── System / Semantic tests ──────────────────────────────────
.PHONY: test-system
test-system: ## All system tests (semantic provider config, search E2E)
	$(PW) --config=$(CFG_DEFAULT) tests/system/ $(EXTRA)

.PHONY: test-semantic-e2e
test-semantic-e2e: ## Full semantic search E2E (all 7 provider/store combos)
	$(PW) --config=$(CFG_DEFAULT) tests/system/semantic-search-e2e.spec.ts $(EXTRA)

.PHONY: test-semantic-props
test-semantic-props: ## Semantic provider property-based tests
	$(PW) --config=$(CFG_DEFAULT) tests/system/semantic-provider-properties.spec.ts $(EXTRA)

# ── Performance tests ────────────────────────────────────────
.PHONY: test-perf
test-perf: ## Performance benchmark tests
	$(PW) --config=$(CFG_PERF) $(EXTRA)

# ── Integration (CI) tests ───────────────────────────────────
.PHONY: test-integration
test-integration: ## CI integration tests
	$(PW) --config=$(CFG_CI) $(EXTRA)

# ── Connectors ───────────────────────────────────────────────
.PHONY: test-connectors
test-connectors: ## Connector management tests
	$(PW) --config=$(CFG_DEFAULT) tests/connectors/ $(EXTRA)

# ── Utilities ────────────────────────────────────────────────
.PHONY: test-report
test-report: ## Open the HTML test report
	npx playwright show-report test-results/playwright-report

.PHONY: install
install: ## Install Playwright browsers
	npx playwright install --with-deps chromium
