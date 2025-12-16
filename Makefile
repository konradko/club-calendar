.PHONY: install test test-core test-cli test-macos pre-commit menubar-icons menubar-dmg menubar-dev \
	menubar-dev-mock menubar-dev-mock-strava menubar-dev-mock-strava-updated menubar-dev-mock-strava-all-deleted \
	mock-strava

# Install dependencies and set up pre-commit hooks
install:
	uv sync --all-packages
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

# Run all tests with coverage
test: test-core test-cli test-macos

test-core:
	uv run pytest packages/core/tests/ -q --tb=short --cov=club_calendar_core --cov-report=term-missing

test-cli:
	uv run pytest packages/cli/tests/ -q --tb=short --cov=club_calendar_cli --cov-report=term-missing

test-macos:
	uv run pytest packages/macos/tests/ -q --tb=short --cov=club_calendar_macos --cov-report=term-missing

# Run all pre-commit hooks manually
pre-commit:
	uv run pre-commit run --all-files

# Build menu bar icons from icon.svg
menubar-icons:
	./deploy/macos-menubar/build-icons.sh

# Build menu bar app DMG (includes icon build)
menubar-dmg:
	./deploy/macos-menubar/build-dmg.sh

# Run menu bar app with hot reload (auto-restart on file changes)
menubar-dev:
	uv sync --all-packages
	uv run watchmedo auto-restart \
		--patterns="*.py" \
		--recursive \
		--directory=packages/macos/src \
		--directory=packages/core/src \
		-- .venv/bin/python -m club_calendar_macos.menubar

# Run menu bar app with mock Strava server for e2e testing
MOCK_PORT ?= 51679
SCENARIOS_DIR = packages/macos/tests/scenarios
TEST_CONFIG_DIR = $(shell pwd)/packages/macos/tests/test-config

# Generate fresh test config using actual Settings class
define create-test-config
	@.venv/bin/python packages/macos/tests/create_test_config.py
endef

define run-mock-strava
	@pkill -f "mock_strava_server.py" 2>/dev/null || true
	@sleep 0.5
	$(call create-test-config)
	uv sync --all-packages
	@echo "Starting mock Strava server with $(1).json..."
	@.venv/bin/python packages/macos/tests/mock_strava_server.py \
		--port $(MOCK_PORT) --data $(SCENARIOS_DIR)/$(1).json &
	@sleep 1
	@echo "Starting menubar with mock Strava API (config: $(TEST_CONFIG_DIR))..."
	CLUB_CALENDAR_CONFIG_DIR=$(TEST_CONFIG_DIR) \
	STRAVA_API_URL=http://localhost:$(MOCK_PORT)/api/v3 \
	STRAVA_TOKEN_URL=http://localhost:$(MOCK_PORT)/oauth/token \
	STRAVA_AUTH_URL=http://localhost:$(MOCK_PORT)/oauth/authorize \
	.venv/bin/python -m club_calendar_macos.menubar || true
	@echo "Cleaning up mock server..."
	@pkill -f "mock_strava_server.py" 2>/dev/null || true
endef

# Run with dynamic mock (generates fresh test config) + hot reload
menubar-dev-mock:
	@pkill -f "mock_strava_server.py" 2>/dev/null || true
	@sleep 0.5
	$(call create-test-config)
	uv sync --all-packages
	@echo "Starting mock Strava server in dynamic mode..."
	@.venv/bin/python packages/macos/tests/mock_strava_server.py --port $(MOCK_PORT) &
	@sleep 1
	@echo "Starting menubar with mock Strava API and hot reload (config: $(TEST_CONFIG_DIR))..."
	CLUB_CALENDAR_CONFIG_DIR=$(TEST_CONFIG_DIR) \
	STRAVA_API_URL=http://localhost:$(MOCK_PORT)/api/v3 \
	STRAVA_TOKEN_URL=http://localhost:$(MOCK_PORT)/oauth/token \
	STRAVA_AUTH_URL=http://localhost:$(MOCK_PORT)/oauth/authorize \
	uv run watchmedo auto-restart \
		--patterns="*.py" \
		--recursive \
		--directory=packages/macos/src \
		--directory=packages/core/src \
		-- .venv/bin/python -m club_calendar_macos.menubar || true
	@echo "Cleaning up mock server..."
	@pkill -f "mock_strava_server.py" 2>/dev/null || true

menubar-dev-mock-strava:
	$(call run-mock-strava,happy)

menubar-dev-mock-strava-updated:
	$(call run-mock-strava,updated)

menubar-dev-mock-strava-all-deleted:
	$(call run-mock-strava,all-deleted)

# Run mock Strava server standalone (foreground, dynamic mode by default)
# Usage: make mock-strava [SCENARIO=happy|updated|all-deleted]
mock-strava:
	@pkill -f "mock_strava_server.py" 2>/dev/null || true
	@sleep 0.5
ifdef SCENARIO
	@echo "Starting mock Strava server on port $(MOCK_PORT) with $(SCENARIO).json..."
	.venv/bin/python packages/macos/tests/mock_strava_server.py \
		--port $(MOCK_PORT) --data $(SCENARIOS_DIR)/$(SCENARIO).json
else
	@echo "Starting mock Strava server on port $(MOCK_PORT) in dynamic mode..."
	.venv/bin/python packages/macos/tests/mock_strava_server.py --port $(MOCK_PORT)
endif
