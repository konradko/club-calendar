"""CLI interface for club-calendar."""

import sys

import click

from club_calendar.config import get_settings
from club_calendar.core import ClubCalendarService, create_service_from_settings
from club_calendar.strava import StravaError


@click.group()
@click.version_option()
def main() -> None:
    """Sync club events to ICS calendar files."""


@main.command()
def auth() -> None:
    """Authenticate with Strava and obtain refresh token.

    Opens browser for OAuth flow and captures the authorization code.
    Saves the refresh token to config.
    """
    settings = get_settings()

    if not settings.has_strava_credentials():
        click.echo("Error: STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET must be set", err=True)
        click.echo("Get these from https://www.strava.com/settings/api", err=True)
        sys.exit(1)

    service = ClubCalendarService(
        client_id=settings.strava_client_id,
        client_secret=settings.strava_client_secret,
    )

    redirect_uri = "http://localhost:8000/callback"
    auth_url = service.get_authorization_url(redirect_uri)

    click.echo("Opening browser for Strava authorization...")
    click.echo(f"If browser doesn't open, visit: {auth_url}")

    result = service.run_oauth_flow(redirect_uri=redirect_uri, port=8000)

    if not result.success:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)

    # Save token to config
    settings.strava_refresh_token = result.refresh_token
    settings.save()

    click.echo()
    click.echo("Success! Refresh token saved to config.")
    click.echo()


@main.command()
@click.option("--save", is_flag=True, help="Save local club IDs to config")
@click.option("--cities", envvar="CLUB_CITY_FILTER", help="Filter by cities (comma-separated)")
def clubs(save: bool, cities: str | None) -> None:
    """List clubs you belong to (shows IDs for configuration)."""
    settings = get_settings()

    if not settings.has_strava_credentials():
        click.echo("Error: Strava credentials not configured", err=True)
        sys.exit(1)

    if not settings.has_refresh_token():
        click.echo("Error: No refresh token - run 'club-calendar auth' first", err=True)
        sys.exit(1)

    service = create_service_from_settings(settings)

    try:
        clubs_list = service.get_clubs()
    except StravaError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not clubs_list:
        click.echo("You don't belong to any clubs.")
        return

    # Filter to local clubs
    city_filter = [c.strip() for c in cities.split(",") if c.strip()] if cities else None
    local_clubs, local_cities = service.filter_local_clubs(clubs_list, city_filter)

    # Display clubs
    click.echo("Your clubs:")
    click.echo()
    for club in clubs_list:
        location = ", ".join(filter(None, [club.city, club.state, club.country]))
        location_str = f" ({location})" if location else ""
        is_local = club in local_clubs
        marker = "*" if is_local else " "
        click.echo(f" {marker} {club.id}: {club.name}{location_str} - {club.member_count} members")

    if local_clubs:
        click.echo()
        click.echo(f"* = local clubs ({', '.join(local_cities)})")

    if save and local_clubs:
        settings.club_ids = [c.id for c in local_clubs]
        settings.save()
        click.echo()
        click.echo(f"Saved {len(local_clubs)} local club IDs to config")
    elif not save:
        click.echo()
        click.echo("Run with --save to save local club IDs to config")


@main.command()
@click.option("--stdout", is_flag=True, help="Output combined calendar to stdout instead of files")
@click.option("--club-id", "-c", multiple=True, type=int, help="Override club IDs")
def sync(stdout: bool, club_id: tuple[int, ...]) -> None:
    """Sync club events and generate ICS calendar files."""
    settings = get_settings()

    if not settings.has_strava_credentials():
        click.echo("Error: Strava credentials not configured", err=True)
        sys.exit(1)

    if not settings.has_refresh_token():
        click.echo("Error: No refresh token - run 'club-calendar auth' first", err=True)
        sys.exit(1)

    club_ids = list(club_id) if club_id else settings.get_club_ids()

    if not club_ids:
        click.echo("Error: No club IDs configured", err=True)
        click.echo("Set CLUB_IDS in .env or use --club-id option", err=True)
        click.echo("Run 'club-calendar clubs' to see available clubs", err=True)
        sys.exit(1)

    service = create_service_from_settings(settings)

    if stdout:
        ics_data, result = service.sync_to_stdout(club_ids)
        if not result.success:
            click.echo(f"Error: {result.message}", err=True)
            sys.exit(1)
        if result.event_count == 0:
            click.echo("No events found for configured clubs.", err=True)
            sys.exit(0)
        click.echo(f"Found {result.event_count} events from {len(club_ids)} clubs", err=True)
        sys.stdout.buffer.write(ics_data)
    else:
        output_dir = settings.ensure_output_dir()
        result = service.sync_to_files(club_ids, output_dir)

        if not result.success:
            click.echo(f"Error: {result.message}", err=True)
            sys.exit(1)

        if result.event_count == 0:
            click.echo("No events found for configured clubs.", err=True)
            sys.exit(0)

        click.echo(f"Found {result.event_count} events from {len(club_ids)} clubs", err=True)
        click.echo(f"Written {len(result.files_written)} calendar files to {output_dir}:", err=True)
        for name, path in result.files_written.items():
            click.echo(f"  {name}: {path}", err=True)


if __name__ == "__main__":
    main()
