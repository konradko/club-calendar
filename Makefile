.PHONY: help install test lint typecheck dev run dmg icons strava-mock-server pre-commit clean

# Show available targets
help:
	@echo "Available targets:"
	@echo "  make install       - Install dependencies and pre-commit hooks"
	@echo "  make test          - Run tests with coverage (90% minimum)"
	@echo "  make lint          - Run linter and formatter"
	@echo "  make typecheck     - Run type checker"
	@echo "  make pre-commit    - Run all pre-commit hooks"
	@echo "  make dev           - Run app with mock Strava server"
	@echo "  make run           - Run app with production API"
	@echo "  make icons         - Build menu bar icons from icon.svg"
	@echo "  make dmg           - Build DMG installer"
	@echo "  make clean         - Remove build artifacts"

# Install dependencies and set up pre-commit hooks
install:
	uv sync
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

# Run all tests with coverage (matches CI requirements)
test:
	uv run pytest tests/ -q --tb=short --cov=club_calendar --cov-report=term-missing --cov-fail-under=90

# Run linter and formatter
lint:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

# Run type checker
typecheck:
	uv run mypy src/

# Run pre-commit hooks manually
pre-commit:
	uv run pre-commit run --all-files

# Build menu bar icons from icon.svg
icons:
	./deploy/build-icons.sh

# Build DMG installer (includes icon build)
dmg:
	./deploy/build-dmg.sh

# Mock server configuration
MOCK_PORT ?= 51679
SCENARIOS_DIR = tests/scenarios
TEST_CONFIG_DIR = $(shell pwd)/tests/test-config

# Generate fresh test config
define create-test-config
	@python tests/create_test_config.py
endef
# Run app with mock Strava server for e2e testing
dev: icons
	@pkill -f "mock_strava_server.py" 2>/dev/null || true
	@sleep 0.5
	MOCK_PORT=$(MOCK_PORT) $(call create-test-config)
	uv sync
	@echo "Starting mock Strava server in dynamic mode..."
	@python tests/mock_strava_server.py --port $(MOCK_PORT) &
	@sleep 1
	@echo "Starting app with mock Strava API and hot reload..."
	CLUB_CALENDAR_CONFIG_DIR=$(TEST_CONFIG_DIR) \
	uv run watchmedo auto-restart \
		--patterns="*.py" \
		--recursive \
		--directory=src \
		-- python -m club_calendar.menubar || true
	@echo "Cleaning up mock server..."
	@pkill -f "mock_strava_server.py" 2>/dev/null || true

# Run app with hot reload (production API)
# Note: Set sync_on_startup: false in config.yaml to skip initial sync
run: icons
	uv sync
	@echo "Starting app with production Strava API and hot reload..."
	uv run watchmedo auto-restart \
		--patterns="*.py" \
		--recursive \
		--directory=src \
		-- python -m club_calendar.menubar

# Run mock Strava server standalone
# Usage: make strava-mock-server [SCENARIO=happy|updated|all-deleted]
strava-mock-server:
	@pkill -f "mock_strava_server.py" 2>/dev/null || true
	@sleep 0.5
ifdef SCENARIO
	@echo "Starting mock Strava server on port $(MOCK_PORT) with $(SCENARIO).json..."
	python tests/mock_strava_server.py --port $(MOCK_PORT) --data $(SCENARIOS_DIR)/$(SCENARIO).json
else
	@echo "Starting mock Strava server on port $(MOCK_PORT) in dynamic mode..."
	python tests/mock_strava_server.py --port $(MOCK_PORT)
endif

# Remove build artifacts
clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
