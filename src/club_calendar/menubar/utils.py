"""Utility functions for Club Calendar."""

from typing import NamedTuple


class DayLabel(NamedTuple):
    """Result of day label computation for event grouping."""

    label: str
    is_this_week: bool
    is_today: bool
    is_next_week: bool


def get_activity_emoji(activity_type: str | None) -> str:
    """Get emoji for event based on Strava activity type.

    Args:
        activity_type: Strava activity type (e.g., "Ride", "Run")

    Returns:
        Emoji string representing the activity type
    """
    if not activity_type:
        return "📅"
    activity_lower = activity_type.lower()
    if "ride" in activity_lower or "cycling" in activity_lower:
        return "🚴"
    if "run" in activity_lower:
        return "🏃"
    if "swim" in activity_lower:
        return "🏊"
    if "hike" in activity_lower or "walk" in activity_lower:
        return "🥾"
    return "📅"


# OAuth HTML response templates
def oauth_success_html() -> bytes:
    """Generate HTML for successful OAuth callback."""
    return (
        b"<html><body>"
        b"<h1>Club Calendar</h1>"
        b"<p><strong>Authentication successful!</strong></p>"
        b"<p>You can close this window.</p>"
        b"</body></html>"
    )


def oauth_error_html(message: str) -> bytes:
    """Generate HTML for failed OAuth callback."""
    return (
        f"<html><body>"
        f"<h1>Club Calendar</h1>"
        f"<p><strong>Authentication failed</strong></p>"
        f"<p>{message}</p>"
        f"</body></html>"
    ).encode()
