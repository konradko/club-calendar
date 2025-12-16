"""EventKit integration for syncing events to Apple Calendar."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from club_calendar_core.strava import ClubEvent

logger = logging.getLogger(__name__)

# Calendar name for club events
CALENDAR_NAME = "Club Calendar"


@dataclass
class SyncResult:
    """Result of calendar sync operation."""

    success: bool
    message: str
    events_added: int = 0
    events_removed: int = 0


def _import_eventkit():
    """Import EventKit framework."""
    try:
        import EventKit

        return EventKit
    except ImportError:
        return None


def _get_event_store():
    """Get EventKit event store with calendar access."""
    EventKit = _import_eventkit()  # noqa: N806
    if not EventKit:
        return None, "EventKit not available"

    store = EventKit.EKEventStore.alloc().init()

    # Request calendar access (will prompt user if needed)
    import threading

    result = {"granted": False, "error": None}
    done = threading.Event()

    def completion_handler(granted, error):
        result["granted"] = granted
        if error:
            result["error"] = str(error)
        done.set()

    store.requestFullAccessToEventsWithCompletion_(completion_handler)
    done.wait(timeout=30)

    if not result["granted"]:
        error_msg = result["error"] or "Calendar access denied"
        return None, error_msg

    return store, None


def _find_or_create_calendar(store) -> tuple:
    """Find or create the Club Calendar calendar.

    Returns:
        Tuple of (calendar, error_message)
    """
    EventKit = _import_eventkit()  # noqa: N806
    if not EventKit:
        return None, "EventKit not available"

    # Look for existing calendar
    calendars = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
    for cal in calendars:
        if cal.title() == CALENDAR_NAME:
            return cal, None

    # Create new calendar
    calendar = EventKit.EKCalendar.calendarForEntityType_eventStore_(
        EventKit.EKEntityTypeEvent, store
    )
    calendar.setTitle_(CALENDAR_NAME)

    # Use default calendar source (usually iCloud or local)
    sources = store.sources()
    local_source = None
    icloud_source = None

    for source in sources:
        source_type = source.sourceType()
        if source_type == EventKit.EKSourceTypeLocal:
            local_source = source
        elif source_type == EventKit.EKSourceTypeCalDAV:
            # iCloud or other CalDAV
            if "icloud" in str(source.title()).lower():
                icloud_source = source

    # Prefer iCloud, fall back to local
    calendar_source = icloud_source or local_source
    if not calendar_source:
        # Use first available source
        if sources:
            calendar_source = sources[0]
        else:
            return None, "No calendar source available"

    calendar.setSource_(calendar_source)

    # Save calendar
    error_ptr = None
    success = store.saveCalendar_commit_error_(calendar, True, error_ptr)
    if not success:
        return None, "Failed to create calendar"

    logger.info(f"Created calendar: {CALENDAR_NAME}")
    return calendar, None


def _create_event(store, calendar, club_event: ClubEvent):
    """Create an EventKit event from a ClubEvent."""
    EventKit = _import_eventkit()  # noqa: N806
    if not EventKit:
        return None

    event = EventKit.EKEvent.eventWithEventStore_(store)
    event.setCalendar_(calendar)
    event.setTitle_(club_event.title)

    # Set start and end time (2 hour default duration)
    start_date = club_event.start_datetime
    end_date = start_date + timedelta(hours=2)

    # Convert to NSDate
    from Foundation import NSDate, NSTimeZone

    start_ns = NSDate.dateWithTimeIntervalSince1970_(start_date.timestamp())
    end_ns = NSDate.dateWithTimeIntervalSince1970_(end_date.timestamp())

    event.setStartDate_(start_ns)
    event.setEndDate_(end_ns)

    # Set timezone from event if available (e.g., "Europe/Warsaw")
    if club_event.zone:
        tz = NSTimeZone.timeZoneWithName_(club_event.zone)
        if tz:
            event.setTimeZone_(tz)

    # Build description
    description_parts = []
    if club_event.description:
        description_parts.append(club_event.description)
    description_parts.append(f"Club: {club_event.club_name}")
    if club_event.organizer_name:
        description_parts.append(f"Organizer: {club_event.organizer_name}")
    if club_event.route_id:
        description_parts.append(f"Route: https://www.strava.com/routes/{club_event.route_id}")
    description_parts.append(
        f"Event: https://www.strava.com/clubs/{club_event.club_id}/group_events/{club_event.id}"
    )

    event.setNotes_("\n\n".join(description_parts))

    # Set location
    if club_event.address:
        event.setLocation_(club_event.address)

    # Set URL
    from Foundation import NSURL

    url = NSURL.URLWithString_(
        f"https://www.strava.com/clubs/{club_event.club_id}/group_events/{club_event.id}"
    )
    event.setURL_(url)

    return event


def _get_strava_event_id_from_url(url_str: str) -> int | None:
    """Extract Strava event ID from URL like .../group_events/12345."""
    if "group_events/" in url_str:
        try:
            return int(url_str.split("group_events/")[-1].split("/")[0].split("?")[0])
        except (ValueError, IndexError):
            return None
    return None


def _find_event_by_strava_id(existing_events, strava_id: int):
    """Find an existing calendar event by Strava event ID."""
    for event in existing_events:
        url = event.URL()
        if url:
            existing_id = _get_strava_event_id_from_url(str(url.absoluteString()))
            if existing_id == strava_id:
                return event
    return None


def sync_events_to_calendar(events: list[ClubEvent]) -> SyncResult:
    """Sync club events to Apple Calendar.

    Smart sync that:
    1. Creates "Club Calendar" if it doesn't exist
    2. Adds new events that don't exist
    3. Updates existing events if changed
    4. Marks cancelled events (no longer in Strava) as "[Cancelled]"

    Args:
        events: List of club events to sync

    Returns:
        SyncResult with success status and counts
    """
    EventKit = _import_eventkit()  # noqa: N806
    if not EventKit:
        return SyncResult(
            success=False, message="EventKit not available (install pyobjc-framework-EventKit)"
        )

    store, error = _get_event_store()
    if error:
        return SyncResult(success=False, message=error)

    calendar, error = _find_or_create_calendar(store)
    if error:
        return SyncResult(success=False, message=error)

    # Get existing future events from our calendar
    from Foundation import NSDate

    now = NSDate.date()
    one_year = NSDate.dateWithTimeIntervalSinceNow_(365 * 24 * 60 * 60)

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(now, one_year, [calendar])
    existing_events = list(store.eventsMatchingPredicate_(predicate))

    # Track which Strava event IDs we've seen
    strava_event_ids = {e.id for e in events}
    added_count = 0
    updated_count = 0
    cancelled_count = 0

    # Add or update events from Strava
    for club_event in events:
        existing = _find_event_by_strava_id(existing_events, club_event.id)

        try:
            if existing:
                # Update existing event
                _update_event(existing, club_event)
                store.saveEvent_span_error_(existing, EventKit.EKSpanThisEvent, None)
                updated_count += 1
            else:
                # Add new event
                event = _create_event(store, calendar, club_event)
                if event:
                    store.saveEvent_span_error_(event, EventKit.EKSpanThisEvent, None)
                    added_count += 1
        except Exception as e:
            logger.warning(f"Failed to sync event {club_event.title}: {e}")

    # Mark cancelled events (in calendar but no longer in Strava)
    for existing in existing_events:
        url = existing.URL()
        if not url:
            continue

        url_str = str(url.absoluteString())
        existing_strava_id = _get_strava_event_id_from_url(url_str)

        if existing_strava_id and existing_strava_id not in strava_event_ids:
            # Event no longer in Strava - mark as cancelled
            title = existing.title()
            if not title.startswith("[Cancelled]"):
                existing.setTitle_(f"[Cancelled] {title}")
                try:
                    store.saveEvent_span_error_(existing, EventKit.EKSpanThisEvent, None)
                    cancelled_count += 1
                    logger.info(f"Marked as cancelled: {title}")
                except Exception as e:
                    logger.warning(f"Failed to mark event as cancelled: {e}")

    # Commit changes
    try:
        store.commit_(None)
    except Exception as e:
        logger.warning(f"Failed to commit: {e}")

    # Build message
    parts = []
    if added_count:
        parts.append(f"{added_count} added")
    if updated_count:
        parts.append(f"{updated_count} updated")
    if cancelled_count:
        parts.append(f"{cancelled_count} cancelled")

    message = ", ".join(parts) if parts else "No changes"

    return SyncResult(
        success=True,
        message=message,
        events_added=added_count,
        events_removed=cancelled_count,
    )


def _update_event(event, club_event: ClubEvent):
    """Update an existing EventKit event from a ClubEvent."""
    from datetime import timedelta

    from Foundation import NSDate, NSTimeZone

    event.setTitle_(club_event.title)

    # Update times
    start_date = club_event.start_datetime
    end_date = start_date + timedelta(hours=2)
    start_ns = NSDate.dateWithTimeIntervalSince1970_(start_date.timestamp())
    end_ns = NSDate.dateWithTimeIntervalSince1970_(end_date.timestamp())
    event.setStartDate_(start_ns)
    event.setEndDate_(end_ns)

    # Update timezone if available
    if club_event.zone:
        tz = NSTimeZone.timeZoneWithName_(club_event.zone)
        if tz:
            event.setTimeZone_(tz)

    # Update location
    if club_event.address:
        event.setLocation_(club_event.address)


def request_calendar_access() -> tuple[bool, str]:
    """Request calendar access from the user.

    Returns:
        Tuple of (granted, error_message)
    """
    EventKit = _import_eventkit()  # noqa: N806
    if not EventKit:
        return False, "EventKit not available"

    store = EventKit.EKEventStore.alloc().init()

    # For macOS 10.14+, we need to request full access
    # This will show a system prompt to the user
    import threading

    result = {"granted": False, "error": None}
    done = threading.Event()

    def completion_handler(granted, error):
        result["granted"] = granted
        if error:
            result["error"] = str(error)
        done.set()

    # Request access
    store.requestFullAccessToEventsWithCompletion_(completion_handler)

    # Wait for response (with timeout)
    done.wait(timeout=30)

    if result["error"]:
        return False, result["error"]

    return result["granted"], "" if result["granted"] else "Calendar access denied"
