# Club Calendar

Sync Strava club events to ICS calendar feeds.

## Structure

This is a monorepo containing three packages:

```
club-calendar/
├── core/     # club-calendar-core - SDK/library
├── cli/      # club-calendar-cli - Command-line interface
└── web/      # club-calendar-web - Web interface
```

## Packages

| Package | Description | Command |
|---------|-------------|---------|
| [core](core/) | Core SDK - Strava API, ICS generation, business logic | Library |
| [cli](cli/) | CLI interface | `club-calendar` |
| [web](web/) | Web interface (FastAPI + htmx) | `club-calendar-web` |

## Quick Start

```bash
# Install CLI
cd cli && uv sync
uv run club-calendar --help

# Install Web
cd web && uv sync
uv run club-calendar-web
```

## Development

Each package has its own virtual environment and can be developed independently.

The `cli` and `web` packages depend on `core` via path dependencies:

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
│club-calendar- │       │club-calendar- │
│     cli       │       │     web       │
│  (Click CLI)  │       │(FastAPI+htmx) │
└───────────────┘       └───────────────┘
```

## License

MIT
