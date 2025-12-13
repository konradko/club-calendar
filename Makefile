.PHONY: install test lint build clean dmg

# Install dependencies
install:
	uv sync

# Install with menubar app support
install-menubar:
	uv sync --extra menubar

# Run tests
test:
	uv run pytest tests/ -v

# Run tests with coverage
test-cov:
	uv run pytest tests/ -v --cov=club_calendar --cov-report=term-missing

# Lint and fix
lint:
	uv run ruff check --fix src/ tests/

# Build DMG
dmg: install-menubar
	./macos/menubar/build-dmg.sh

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage

# Run the CLI
run:
	uv run club-calendar

# Run the menu bar app (dev mode)
menubar:
	uv run club-calendar-menubar
