# Club Calendar

Sync Strava club events to ICS calendar feeds.

## Structure

```
club-calendar/
├── core/     # club-calendar-core - SDK/library
├── cli/      # club-calendar-cli - Command-line interface
└── macos/    # macOS-specific clients
    ├── launchd/   # Background sync service
    └── menubar/   # Menu bar app (future)
```

## Packages

| Package | Description | Command |
|---------|-------------|---------|
| [core](core/) | Core SDK - Strava API, ICS generation, business logic | Library |
| [cli](cli/) | CLI interface | `club-calendar` |

## Quick Start

```bash
# Install CLI
cd cli && uv sync
uv run club-calendar --help

# Install launchd service (daily sync)
./macos/launchd/install.sh --hour 6 --minute 0
```

## Development

Each package has its own virtual environment and can be developed independently.

The `cli` package depends on `core` via path dependencies:

```toml
[tool.uv.sources]
club-calendar-core = { path = "../core" }
```

## Architecture

```
┌─────────────────────────────────────────┐
│            club-calendar-core           │
│  (Strava API, ICS gen, services, config)│
└───────────────────┬─────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────┐       ┌───────────────┐
│club-calendar- │       │    macos/     │
│     cli       │       │   menubar     │
│  (Click CLI)  │       │   (future)    │
└───────────────┘       └───────────────┘
        ▲
        │
┌───────────────┐
│    macos/     │
│   launchd     │
│  (runs CLI)   │
└───────────────┘
```

## License

MIT
