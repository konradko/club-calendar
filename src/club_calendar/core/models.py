"""Data models for the menu bar app."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SyncResult:
    """Result of a sync operation."""

    success: bool
    message: str
    events_added: int = 0
    events_removed: int = 0


@dataclass(frozen=True)
class SetupResult:
    """Result of a setup operation."""

    success: bool
    message: str
