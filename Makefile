.PHONY: install test test-core test-cli test-macos pre-commit

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
