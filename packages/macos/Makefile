.PHONY: run dev

# Run menu bar app
run:
	uv run club-calendar-menubar

# Run with auto-restart on file changes (hot reload)
dev:
	uv run watchmedo auto-restart \
		--patterns="*.py" \
		--recursive \
		--directory=src \
		-- uv run club-calendar-menubar
