"""CLI interface for club-calendar."""

import sys

import click
from club_calendar_core.service import ClubCalendarService
from club_calendar_core.strava import StravaAuthError, StravaError, StravaRateLimitError

from club_calendar_cli.config import get_config

# User-friendly error messages
ERROR_MESSAGES = {
    "auth_expired": "Your Strava connection has expired. Run 'club-calendar auth' to reconnect.",
    "rate_limit": "Strava rate limit reached. Please wait a few minutes and try again.",
    "no_credentials": "Strava API credentials not configured.\n"
    "Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env file.\n"
    "Get credentials from: https://www.strava.com/settings/api",
    "no_token": "Not authenticated with Strava. Run 'club-calendar auth' first.",
    "no_clubs": "No club IDs configured.\n"
    "Set STRAVA_CLUB_IDS in .env or use --club-id option.\n"
    "Run 'club-calendar clubs' to see available clubs.",
}


def get_user_error(error: Exception) -> str:
    """Convert exception to user-friendly message."""
    if isinstance(error, StravaAuthError):
        return ERROR_MESSAGES["auth_expired"]
    if isinstance(
        error, StravaRateLimitError
    ):  # pragma: no cover - rate limits handled in strava module
        return ERROR_MESSAGES["rate_limit"]
    return str(error)


pass_quiet = click.make_pass_decorator(dict, ensure=True)


@click.group()
@click.version_option()
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-error output")
@click.pass_context
def main(ctx: click.Context, quiet: bool) -> None:
    """Sync Strava club events to ICS calendar files."""
    ctx.ensure_object(dict)
    ctx.obj["quiet"] = quiet


def echo_info(ctx: click.Context, message: str) -> None:
    """Print info message to stderr unless --quiet."""
    if not ctx.obj.get("quiet"):
        click.echo(message, err=True)


@main.command()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Authenticate with Strava and obtain refresh token.

    Opens browser for OAuth flow and captures the authorization code.
    Saves the refresh token to .env file.
    """
    config = get_config()

    if not config.has_credentials():
        click.echo(f"Error: {ERROR_MESSAGES['no_credentials']}", err=True)
        sys.exit(1)

    service = ClubCalendarService(
        client_id=config.client_id,
        client_secret=config.client_secret,
        token_store=config.token_store,
    )

    redirect_uri = "http://localhost:8000/callback"
    auth_url = service.get_authorization_url(redirect_uri)

    echo_info(ctx, "Opening browser for Strava authorization...")
    echo_info(ctx, f"If browser doesn't open, visit: {auth_url}")

    result = service.run_oauth_flow(redirect_uri=redirect_uri, port=8000)

    if not result.success:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)

    echo_info(ctx, "")
    echo_info(ctx, "Success! Refresh token saved to .env file.")


@main.command()
@click.option("--save", is_flag=True, help="Save local club IDs to .env file")
@click.option("--cities", envvar="CLUB_CITY_FILTER", help="Filter by cities (comma-separated)")
@click.pass_context
def clubs(ctx: click.Context, save: bool, cities: str | None) -> None:
    """List clubs you belong to (shows IDs for configuration)."""
    config = get_config()

    if not config.has_credentials():
        click.echo(f"Error: {ERROR_MESSAGES['no_credentials']}", err=True)
        sys.exit(1)

    if not config.has_refresh_token():
        click.echo(f"Error: {ERROR_MESSAGES['no_token']}", err=True)
        sys.exit(1)

    service = ClubCalendarService(
        client_id=config.client_id,
        client_secret=config.client_secret,
        token_store=config.token_store,
    )

    try:
        clubs_list = service.get_clubs()
    except StravaError as e:
        click.echo(f"Error: {get_user_error(e)}", err=True)
        sys.exit(1)

    if not clubs_list:
        echo_info(ctx, "You don't belong to any clubs.")
        return

    # Filter to local clubs
    city_filter = [c.strip() for c in cities.split(",") if c.strip()] if cities else None
    local_clubs, local_cities = service.filter_local_clubs(clubs_list, city_filter)

    # Display clubs (always shown, even with --quiet, as this is the command's primary output)
    click.echo("Your clubs:", err=True)
    click.echo(err=True)
    for club in clubs_list:
        location = ", ".join(filter(None, [club.city, club.state, club.country]))
        location_str = f" ({location})" if location else ""
        is_local = club in local_clubs
        marker = "*" if is_local else " "
        info = f" {marker} {club.id}: {club.name}{location_str} - {club.member_count} members"
        click.echo(info, err=True)

    if local_clubs:
        click.echo(err=True)
        click.echo(f"* = local clubs ({', '.join(local_cities)})", err=True)

    if save and local_clubs:
        config.club_ids = [c.id for c in local_clubs]
        echo_info(ctx, "")
        echo_info(ctx, f"Saved {len(local_clubs)} local club IDs to .env file")
    elif not save:
        echo_info(ctx, "")
        echo_info(ctx, "Run with --save to save local club IDs to .env file")


@main.command()
@click.option("--stdout", is_flag=True, help="Output combined calendar to stdout instead of files")
@click.option("--club-id", "-c", multiple=True, type=int, help="Override club IDs")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.pass_context
def sync(ctx: click.Context, stdout: bool, club_id: tuple[int, ...], output: str | None) -> None:
    """Sync club events and generate ICS calendar files."""
    from pathlib import Path

    from club_calendar_cli.calendar import generate_combined_calendar, write_calendars

    config = get_config()

    if not config.has_credentials():
        click.echo(f"Error: {ERROR_MESSAGES['no_credentials']}", err=True)
        sys.exit(1)

    if not config.has_refresh_token():
        click.echo(f"Error: {ERROR_MESSAGES['no_token']}", err=True)
        sys.exit(1)

    club_ids = list(club_id) if club_id else config.club_ids

    if not club_ids:
        click.echo(f"Error: {ERROR_MESSAGES['no_clubs']}", err=True)
        sys.exit(1)

    service = ClubCalendarService(
        client_id=config.client_id,
        client_secret=config.client_secret,
        token_store=config.token_store,
    )

    quiet = ctx.obj.get("quiet", False)

    if not quiet:
        click.echo(f"Syncing {len(club_ids)} club(s)...", err=True)

    try:
        events = service.get_club_events(club_ids)
    except StravaError as e:
        click.echo(f"Error: {get_user_error(e)}", err=True)
        sys.exit(1)

    if not events:
        echo_info(ctx, "No upcoming events found.")
        sys.exit(0)

    if stdout:
        ics_data = generate_combined_calendar(events)
        echo_info(ctx, f"Found {len(events)} events")
        sys.stdout.buffer.write(ics_data)
    else:
        output_dir = Path(output) if output else config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            written = write_calendars(events, output_dir)
        except OSError as e:
            click.echo(f"Error: File error: {e}", err=True)
            sys.exit(1)

        echo_info(ctx, f"Synced {len(events)} events to {output_dir}")
        if not quiet:
            for name, path in written.items():
                click.echo(f"  {name}: {path}", err=True)


if __name__ == "__main__":
    main()
