"""Data models for the menu bar app."""

from dataclasses import dataclass


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    message: str


@dataclass
class CommandResult:
    """Result of a shell command."""

    success: bool
    output: str


@dataclass
class SetupResult:
    """Result of a setup operation."""

    success: bool
    message: str
