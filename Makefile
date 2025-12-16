.PHONY: install test test-core test-cli test-macos pre-commit menubar-icons menubar-dmg menubar-dev \
	menubar-dev-mock-strava menubar-dev-mock-strava-updated menubar-dev-mock-strava-all-deleted

# Install dependencies and set up pre-commit hooks
install:
	uv sync --all-packages
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

# Run all tests with coverage
test: test-core test-cli test-macos

test-core:
	uv run pytest packages/core/tests/ --cov=club_calendar_core --cov-report=term-missing

test-cli:
	uv run pytest packages/cli/tests/ --cov=club_calendar_cli --cov-report=term-missing

test-macos:
	uv run pytest packages/macos/tests/ --cov=club_calendar_macos --cov-report=term-missing

# Run all pre-commit hooks manually
pre-commit:
	uv run pre-commit run --all-files

# Build menu bar icons from icon.png
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
		-- .venv/bin/python -m club_calendar_macos.menubar

# Run menu bar app with mock Strava server for e2e testing
MOCK_PORT ?= 8080
SCENARIOS_DIR = packages/macos/tests/scenarios

define run-mock-strava
	uv sync --all-packages
	@echo "Starting mock Strava server with $(1).json..."
	@.venv/bin/python packages/macos/tests/mock_strava_server.py \
		--port $(MOCK_PORT) --data $(SCENARIOS_DIR)/$(1).json &
	@sleep 1
	@echo "Starting menubar with mock Strava API..."
	STRAVA_API_URL=http://localhost:$(MOCK_PORT)/api/v3 \
	STRAVA_TOKEN_URL=http://localhost:$(MOCK_PORT)/oauth/token \
	STRAVA_AUTH_URL=http://localhost:$(MOCK_PORT)/oauth/authorize \
	.venv/bin/python -m club_calendar_macos.menubar || true
	@echo "Cleaning up mock server..."
	@pkill -f "mock_strava_server.py" 2>/dev/null || true
endef

menubar-dev-mock-strava:
	$(call run-mock-strava,happy)

menubar-dev-mock-strava-updated:
	$(call run-mock-strava,updated)

menubar-dev-mock-strava-all-deleted:
	$(call run-mock-strava,all-deleted)
