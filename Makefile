.PHONY: install test dev dev-mock dmg icons mock-strava pre-commit

# Install dependencies and set up pre-commit hooks
install:
	uv sync
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

# Run all tests with coverage
test:
	uv run pytest tests/ -q --tb=short --cov=club_calendar_core --cov=club_calendar --cov-report=term-missing

# Run pre-commit hooks manually
pre-commit:
	uv run pre-commit run --all-files

# Build menu bar icons from icon.svg
icons:
	./deploy/build-icons.sh

# Build DMG installer (includes icon build)
dmg:
	./deploy/build-dmg.sh

# Run app with hot reload (auto-restart on file changes)
dev:
	uv sync
	uv run watchmedo auto-restart \
		--patterns="*.py" \
		--recursive \
		--directory=src \
		--directory=packages/core/src \
		-- python -m club_calendar.menubar

# Mock server configuration
MOCK_PORT ?= 51679
SCENARIOS_DIR = tests/scenarios
TEST_CONFIG_DIR = $(shell pwd)/tests/test-config

# Generate fresh test config
define create-test-config
	@python tests/create_test_config.py
endef

# Run app with mock Strava server for e2e testing
dev-mock:
	@pkill -f "mock_strava_server.py" 2>/dev/null || true
	@sleep 0.5
	$(call create-test-config)
	uv sync
	@echo "Starting mock Strava server in dynamic mode..."
	@python tests/mock_strava_server.py --port $(MOCK_PORT) &
	@sleep 1
	@echo "Starting app with mock Strava API and hot reload..."
	CLUB_CALENDAR_CONFIG_DIR=$(TEST_CONFIG_DIR) \
	STRAVA_API_URL=http://localhost:$(MOCK_PORT)/api/v3 \
	STRAVA_TOKEN_URL=http://localhost:$(MOCK_PORT)/oauth/token \
	STRAVA_AUTH_URL=http://localhost:$(MOCK_PORT)/oauth/authorize \
	uv run watchmedo auto-restart \
		--patterns="*.py" \
		--recursive \
		--directory=src \
		--directory=packages/core/src \
		-- python -m club_calendar.menubar || true
	@echo "Cleaning up mock server..."
	@pkill -f "mock_strava_server.py" 2>/dev/null || true

# Run mock Strava server standalone
# Usage: make mock-strava [SCENARIO=happy|updated|all-deleted]
mock-strava:
	@pkill -f "mock_strava_server.py" 2>/dev/null || true
	@sleep 0.5
ifdef SCENARIO
	@echo "Starting mock Strava server on port $(MOCK_PORT) with $(SCENARIO).json..."
	python tests/mock_strava_server.py --port $(MOCK_PORT) --data $(SCENARIOS_DIR)/$(SCENARIO).json
else
	@echo "Starting mock Strava server on port $(MOCK_PORT) in dynamic mode..."
	python tests/mock_strava_server.py --port $(MOCK_PORT)
endif
