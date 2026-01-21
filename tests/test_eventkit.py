"""Tests for EventKit integration module."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from club_calendar.core.strava import ClubEvent


@pytest.fixture
def mock_eventkit():
    """Mock EventKit framework."""
    mock_ek = MagicMock()
    mock_ek.EKEntityTypeEvent = 0
    mock_ek.EKSourceTypeLocal = 0
    mock_ek.EKSourceTypeCalDAV = 1
    mock_ek.EKSpanThisEvent = 0
    return mock_ek


@pytest.fixture
def mock_foundation():
    """Mock Foundation framework."""
    mock_ns = MagicMock()
    mock_ns.NSDate.date.return_value = MagicMock()
    mock_ns.NSDate.dateWithTimeIntervalSinceNow_.return_value = MagicMock()
    mock_ns.NSDate.dateWithTimeIntervalSince1970_.return_value = MagicMock()
    mock_ns.NSTimeZone.timeZoneWithName_.return_value = MagicMock()
    mock_ns.NSURL.URLWithString_.return_value = MagicMock()
    return mock_ns


@pytest.fixture
def sample_club_event():
    """Create a sample club event for testing."""
    return ClubEvent(
        id=1001,
        title="Morning Ride",
        description="A nice ride",
        start_datetime=datetime(2099, 1, 15, 8, 0, tzinfo=UTC),
        address="Pioneer Square, Portland",
        club_id=123,
        club_name="Test Cycling Club",
        organizer_name="Alice",
        route_id=789,
        activity_type="Ride",
        zone="America/Los_Angeles",
    )


class TestGetStravaEventIdFromUrl:
    """Tests for _get_strava_event_id_from_url function."""

    def test_extract_id_from_valid_url(self):
        """Test extracting event ID from valid URL."""
        from club_calendar.menubar.eventkit import _get_strava_event_id_from_url

        url = "https://www.strava.com/clubs/123/group_events/12345"
        assert _get_strava_event_id_from_url(url) == 12345

    def test_extract_id_with_query_params(self):
        """Test extracting event ID from URL with query params."""
        from club_calendar.menubar.eventkit import _get_strava_event_id_from_url

        url = "https://www.strava.com/clubs/123/group_events/12345?utm_source=test"
        assert _get_strava_event_id_from_url(url) == 12345

    def test_returns_none_for_invalid_url(self):
        """Test returns None for URL without group_events."""
        from club_calendar.menubar.eventkit import _get_strava_event_id_from_url

        assert _get_strava_event_id_from_url("https://strava.com/athlete") is None
        assert _get_strava_event_id_from_url("") is None

    def test_returns_none_for_non_numeric_id(self):
        """Test returns None when ID is not numeric."""
        from club_calendar.menubar.eventkit import _get_strava_event_id_from_url

        url = "https://www.strava.com/clubs/123/group_events/abc"
        assert _get_strava_event_id_from_url(url) is None


class TestImportEventkit:
    """Tests for _import_eventkit function."""

    def test_returns_none_when_not_available(self):
        """Test returns None when EventKit is not available."""
        from club_calendar.menubar.eventkit import _import_eventkit

        with patch.dict("sys.modules", {"EventKit": None}):
            # Force import to fail
            with patch(
                "builtins.__import__",
                side_effect=lambda name, *args: (_ for _ in ()).throw(ImportError())
                if name == "EventKit"
                else __builtins__.__import__(name, *args),
            ):
                result = _import_eventkit()
                assert result is None

    def test_returns_module_when_available(self, mock_eventkit):
        """Test returns EventKit module when available."""
        from club_calendar.menubar.eventkit import _import_eventkit

        with patch.dict("sys.modules", {"EventKit": mock_eventkit}):
            result = _import_eventkit()
            assert result is mock_eventkit


class TestGetEventStore:
    """Tests for _get_event_store function."""

    def test_returns_error_when_eventkit_not_available(self):
        """Test returns error when EventKit is not available."""
        from club_calendar.menubar.eventkit import _get_event_store

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=None):
            store, error = _get_event_store()
            assert store is None
            assert error == "EventKit not available"

    def test_returns_error_when_access_denied(self, mock_eventkit):
        """Test returns error when calendar access is denied."""
        from club_calendar.menubar.eventkit import _get_event_store

        mock_store = MagicMock()
        mock_eventkit.EKEventStore.alloc.return_value.init.return_value = mock_store

        def mock_request(callback):
            callback(False, None)

        mock_store.requestFullAccessToEventsWithCompletion_ = mock_request

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            store, error = _get_event_store()
            assert store is None
            assert error == "Calendar access denied"

    def test_returns_error_message_from_callback(self, mock_eventkit):
        """Test returns error message from EventKit callback."""
        from club_calendar.menubar.eventkit import _get_event_store

        mock_store = MagicMock()
        mock_eventkit.EKEventStore.alloc.return_value.init.return_value = mock_store

        def mock_request(callback):
            callback(False, "User denied access")

        mock_store.requestFullAccessToEventsWithCompletion_ = mock_request

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            store, error = _get_event_store()
            assert store is None
            assert error == "User denied access"

    def test_returns_store_when_access_granted(self, mock_eventkit):
        """Test returns store when calendar access is granted."""
        from club_calendar.menubar.eventkit import _get_event_store

        mock_store = MagicMock()
        mock_eventkit.EKEventStore.alloc.return_value.init.return_value = mock_store

        def mock_request(callback):
            callback(True, None)

        mock_store.requestFullAccessToEventsWithCompletion_ = mock_request

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            store, error = _get_event_store()
            assert store is mock_store
            assert error is None


class TestFindOrCreateCalendar:
    """Tests for _find_or_create_calendar function."""

    def test_returns_error_when_eventkit_not_available(self):
        """Test returns error when EventKit is not available."""
        from club_calendar.menubar.eventkit import _find_or_create_calendar

        mock_store = MagicMock()
        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=None):
            cal, error = _find_or_create_calendar(mock_store)
            assert cal is None
            assert error == "EventKit not available"

    def test_finds_existing_calendar(self, mock_eventkit):
        """Test finds existing calendar by name."""
        from club_calendar.menubar.eventkit import _find_or_create_calendar

        mock_store = MagicMock()
        existing_cal = MagicMock()
        existing_cal.title.return_value = "Club Calendar"
        mock_store.calendarsForEntityType_.return_value = [existing_cal]

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            cal, error = _find_or_create_calendar(mock_store, "Club Calendar")
            assert cal is existing_cal
            assert error is None

    def test_creates_calendar_with_icloud_source(self, mock_eventkit):
        """Test creates calendar using iCloud source when available."""
        from club_calendar.menubar.eventkit import _find_or_create_calendar

        mock_store = MagicMock()
        mock_store.calendarsForEntityType_.return_value = []

        # Mock sources
        local_source = MagicMock()
        local_source.sourceType.return_value = 0  # EKSourceTypeLocal
        icloud_source = MagicMock()
        icloud_source.sourceType.return_value = 1  # EKSourceTypeCalDAV
        icloud_source.title.return_value = "iCloud"
        mock_store.sources.return_value = [local_source, icloud_source]

        new_cal = MagicMock()
        mock_eventkit.EKCalendar.calendarForEntityType_eventStore_.return_value = new_cal
        mock_store.saveCalendar_commit_error_.return_value = True

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            cal, error = _find_or_create_calendar(mock_store, "Club Calendar")
            assert cal is new_cal
            assert error is None
            new_cal.setSource_.assert_called_once_with(icloud_source)

    def test_creates_calendar_with_local_source(self, mock_eventkit):
        """Test creates calendar using local source when iCloud not available."""
        from club_calendar.menubar.eventkit import _find_or_create_calendar

        mock_store = MagicMock()
        mock_store.calendarsForEntityType_.return_value = []

        local_source = MagicMock()
        local_source.sourceType.return_value = 0  # EKSourceTypeLocal
        mock_store.sources.return_value = [local_source]

        new_cal = MagicMock()
        mock_eventkit.EKCalendar.calendarForEntityType_eventStore_.return_value = new_cal
        mock_store.saveCalendar_commit_error_.return_value = True

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            cal, error = _find_or_create_calendar(mock_store, "Club Calendar")
            assert cal is new_cal
            assert error is None

    def test_returns_error_when_no_sources(self, mock_eventkit):
        """Test returns error when no calendar sources available."""
        from club_calendar.menubar.eventkit import _find_or_create_calendar

        mock_store = MagicMock()
        mock_store.calendarsForEntityType_.return_value = []
        mock_store.sources.return_value = []

        new_cal = MagicMock()
        mock_eventkit.EKCalendar.calendarForEntityType_eventStore_.return_value = new_cal

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            cal, error = _find_or_create_calendar(mock_store, "Club Calendar")
            assert cal is None
            assert error == "No calendar source available"

    def test_returns_error_when_save_fails(self, mock_eventkit):
        """Test returns error when saving calendar fails."""
        from club_calendar.menubar.eventkit import _find_or_create_calendar

        mock_store = MagicMock()
        mock_store.calendarsForEntityType_.return_value = []

        local_source = MagicMock()
        local_source.sourceType.return_value = 0
        mock_store.sources.return_value = [local_source]

        new_cal = MagicMock()
        mock_eventkit.EKCalendar.calendarForEntityType_eventStore_.return_value = new_cal
        mock_store.saveCalendar_commit_error_.return_value = False

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            cal, error = _find_or_create_calendar(mock_store, "Club Calendar")
            assert cal is None
            assert error == "Failed to create calendar"


class TestCreateEvent:
    """Tests for _create_event function."""

    def test_returns_none_when_eventkit_not_available(self, sample_club_event):
        """Test returns None when EventKit is not available."""
        from club_calendar.menubar.eventkit import _create_event

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=None):
            result = _create_event(MagicMock(), MagicMock(), sample_club_event)
            assert result is None

    def test_creates_event_with_all_fields(self, mock_eventkit, mock_foundation, sample_club_event):
        """Test creates event with all fields set."""
        from club_calendar.menubar.eventkit import _create_event

        mock_store = MagicMock()
        mock_calendar = MagicMock()
        mock_event = MagicMock()
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = mock_event

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = _create_event(mock_store, mock_calendar, sample_club_event)

            assert result is mock_event
            mock_event.setCalendar_.assert_called_once_with(mock_calendar)
            mock_event.setTitle_.assert_called_once()
            mock_event.setStartDate_.assert_called_once()
            mock_event.setEndDate_.assert_called_once()
            mock_event.setNotes_.assert_called_once()
            mock_event.setLocation_.assert_called_once_with("Pioneer Square, Portland")
            mock_event.setURL_.assert_called_once()


class TestSyncEventsToCalendar:
    """Tests for sync_events_to_calendar function."""

    def test_returns_error_when_eventkit_not_available(self):
        """Test returns error when EventKit is not available."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=None):
            result = sync_events_to_calendar([])
            assert result.success is False
            assert "EventKit not available" in result.message

    def test_returns_error_when_store_fails(self, mock_eventkit):
        """Test returns error when getting event store fails."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store",
                return_value=(None, "Access denied"),
            ),
        ):
            result = sync_events_to_calendar([])
            assert result.success is False
            assert result.message == "Access denied"

    def test_returns_error_when_calendar_creation_fails(self, mock_eventkit):
        """Test returns error when calendar creation fails."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(None, "Failed to create"),
            ),
        ):
            result = sync_events_to_calendar([])
            assert result.success is False
            assert result.message == "Failed to create"

    def test_sync_success_with_new_events(self, mock_eventkit, mock_foundation, sample_club_event):
        """Test successful sync with new events."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()
        mock_event = MagicMock()

        mock_store.eventsMatchingPredicate_.return_value = []
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = mock_event

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([sample_club_event])
            assert result.success is True
            assert result.events_added == 1

    def test_sync_updates_existing_events(self, mock_eventkit, mock_foundation, sample_club_event):
        """Test sync updates existing events."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        # Existing event with matching URL
        existing_event = MagicMock()
        mock_url = MagicMock()
        mock_url.absoluteString.return_value = "https://www.strava.com/clubs/123/group_events/1001"
        existing_event.URL.return_value = mock_url
        mock_store.eventsMatchingPredicate_.return_value = [existing_event]

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([sample_club_event])
            assert result.success is True
            # Event should be updated, not added
            existing_event.setTitle_.assert_called()


class TestRequestCalendarAccess:
    """Tests for request_calendar_access function."""

    def test_returns_error_when_eventkit_not_available(self):
        """Test returns error when EventKit is not available."""
        from club_calendar.menubar.eventkit import request_calendar_access

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=None):
            granted, error = request_calendar_access()
            assert granted is False
            assert error == "EventKit not available"

    def test_returns_granted_when_access_allowed(self, mock_eventkit):
        """Test returns granted when access is allowed."""
        from club_calendar.menubar.eventkit import request_calendar_access

        mock_store = MagicMock()
        mock_eventkit.EKEventStore.alloc.return_value.init.return_value = mock_store

        def mock_request(callback):
            callback(True, None)

        mock_store.requestFullAccessToEventsWithCompletion_ = mock_request

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            granted, error = request_calendar_access()
            assert granted is True
            assert error == ""

    def test_returns_denied_when_access_refused(self, mock_eventkit):
        """Test returns denied when access is refused."""
        from club_calendar.menubar.eventkit import request_calendar_access

        mock_store = MagicMock()
        mock_eventkit.EKEventStore.alloc.return_value.init.return_value = mock_store

        def mock_request(callback):
            callback(False, None)

        mock_store.requestFullAccessToEventsWithCompletion_ = mock_request

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            granted, error = request_calendar_access()
            assert granted is False
            assert error == "Calendar access denied"

    def test_returns_error_message(self, mock_eventkit):
        """Test returns error message from callback."""
        from club_calendar.menubar.eventkit import request_calendar_access

        mock_store = MagicMock()
        mock_eventkit.EKEventStore.alloc.return_value.init.return_value = mock_store

        def mock_request(callback):
            callback(False, "User explicitly denied")

        mock_store.requestFullAccessToEventsWithCompletion_ = mock_request

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            granted, error = request_calendar_access()
            assert granted is False
            assert error == "User explicitly denied"


class TestFindOrCreateCalendarFallback:
    """Tests for _find_or_create_calendar fallback source."""

    def test_uses_first_source_when_no_local_or_icloud(self, mock_eventkit):
        """Test uses first available source when no local or iCloud."""
        from club_calendar.menubar.eventkit import _find_or_create_calendar

        mock_store = MagicMock()
        mock_store.calendarsForEntityType_.return_value = []

        # Create a source that's neither Local (0) nor CalDAV (1)
        other_source = MagicMock()
        other_source.sourceType.return_value = 2  # Some other type
        other_source.title.return_value = "Exchange"
        mock_store.sources.return_value = [other_source]

        new_cal = MagicMock()
        mock_eventkit.EKCalendar.calendarForEntityType_eventStore_.return_value = new_cal
        mock_store.saveCalendar_commit_error_.return_value = True

        with patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit):
            cal, error = _find_or_create_calendar(mock_store, "Club Calendar")
            assert cal is new_cal
            assert error is None
            # Should use the first available source
            new_cal.setSource_.assert_called_once_with(other_source)


class TestMarkCancelledEvents:
    """Tests for mark cancelled events functionality."""

    def test_marks_cancelled_events(self, mock_eventkit, mock_foundation, sample_club_event):
        """Test that events not in Strava are marked as cancelled."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        # Existing event that is NOT in our events list (should be cancelled)
        existing_event = MagicMock()
        mock_url = MagicMock()
        mock_url.absoluteString.return_value = "https://www.strava.com/clubs/123/group_events/9999"
        existing_event.URL.return_value = mock_url
        existing_event.title.return_value = "Old Event"  # Not already cancelled
        mock_store.eventsMatchingPredicate_.return_value = [existing_event]

        mock_eventkit.EKEvent.eventWithEventStore_.return_value = MagicMock()

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([sample_club_event])
            assert result.success is True
            # The existing event should be marked as cancelled
            existing_event.setTitle_.assert_called_with("[Cancelled] Old Event")
            assert result.events_removed == 1

    def test_skips_event_without_url(self, mock_eventkit, mock_foundation, sample_club_event):
        """Test that events without URL are skipped during cancellation check."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        # Existing event with no URL
        existing_event = MagicMock()
        existing_event.URL.return_value = None
        mock_store.eventsMatchingPredicate_.return_value = [existing_event]

        mock_eventkit.EKEvent.eventWithEventStore_.return_value = MagicMock()

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([sample_club_event])
            assert result.success is True
            # Event without URL should not be modified
            existing_event.setTitle_.assert_not_called()

    def test_skips_already_cancelled_event(self, mock_eventkit, mock_foundation, sample_club_event):
        """Test that already cancelled events are not modified."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        # Existing event that's already marked as cancelled
        existing_event = MagicMock()
        mock_url = MagicMock()
        mock_url.absoluteString.return_value = "https://www.strava.com/clubs/123/group_events/9999"
        existing_event.URL.return_value = mock_url
        existing_event.title.return_value = "[Cancelled] Already Cancelled Event"
        mock_store.eventsMatchingPredicate_.return_value = [existing_event]

        mock_eventkit.EKEvent.eventWithEventStore_.return_value = MagicMock()

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([sample_club_event])
            assert result.success is True
            # Already cancelled event should not be modified again
            existing_event.setTitle_.assert_not_called()


class TestSyncEventExceptionHandling:
    """Tests for exception handling during sync."""

    def test_sync_handles_event_save_error(self, mock_eventkit, mock_foundation, sample_club_event):
        """Test sync continues when individual event save fails."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        mock_store.eventsMatchingPredicate_.return_value = []
        mock_store.saveEvent_span_error_.side_effect = OSError("Save failed")

        mock_eventkit.EKEvent.eventWithEventStore_.return_value = MagicMock()

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([sample_club_event])
            # Should still succeed even if individual event save fails
            assert result.success is True

    def test_sync_handles_commit_error(self, mock_eventkit, mock_foundation):
        """Test sync handles commit error gracefully."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        mock_store.eventsMatchingPredicate_.return_value = []
        mock_store.commit_.side_effect = OSError("Commit failed")

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([])
            # Should still succeed even if commit fails (already synced to store)
            assert result.success is True

    def test_sync_handles_unexpected_exception(
        self, mock_eventkit, mock_foundation, sample_club_event
    ):
        """Test sync handles unexpected exceptions (e.g., pyobjc errors)."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        mock_store.eventsMatchingPredicate_.return_value = []
        mock_store.saveEvent_span_error_.side_effect = RuntimeError("PyObjC error")

        mock_eventkit.EKEvent.eventWithEventStore_.return_value = MagicMock()

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([sample_club_event])
            # Should succeed but event not added
            assert result.success is True
            assert result.events_added == 0

    def test_cancelled_event_save_error_handled(self, mock_eventkit, mock_foundation):
        """Test mark cancelled handles save error gracefully."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        # Existing event that should be cancelled but save fails
        existing_event = MagicMock()
        mock_url = MagicMock()
        mock_url.absoluteString.return_value = "https://www.strava.com/clubs/123/group_events/9999"
        existing_event.URL.return_value = mock_url
        existing_event.title.return_value = "Event To Cancel"
        mock_store.eventsMatchingPredicate_.return_value = [existing_event]
        mock_store.saveEvent_span_error_.side_effect = OSError("Save failed")

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([])  # No new events
            assert result.success is True
            # Event should have been marked as cancelled (title set) even if save fails
            existing_event.setTitle_.assert_called_with("[Cancelled] Event To Cancel")

    def test_cancelled_event_unexpected_error_handled(self, mock_eventkit, mock_foundation):
        """Test mark cancelled handles unexpected (pyobjc) errors gracefully."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        # Existing event that should be cancelled but save raises unexpected error
        existing_event = MagicMock()
        mock_url = MagicMock()
        mock_url.absoluteString.return_value = "https://www.strava.com/clubs/123/group_events/9999"
        existing_event.URL.return_value = mock_url
        existing_event.title.return_value = "Event To Cancel"
        mock_store.eventsMatchingPredicate_.return_value = [existing_event]
        mock_store.saveEvent_span_error_.side_effect = RuntimeError("PyObjC error")

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([])  # No new events
            assert result.success is True
            # Event should have been marked as cancelled (title set) even if save fails
            existing_event.setTitle_.assert_called_with("[Cancelled] Event To Cancel")

    def test_commit_unexpected_error_handled(self, mock_eventkit, mock_foundation):
        """Test commit handles unexpected (pyobjc) errors gracefully."""
        from club_calendar.menubar.eventkit import sync_events_to_calendar

        mock_store = MagicMock()
        mock_calendar = MagicMock()

        mock_store.eventsMatchingPredicate_.return_value = []
        mock_store.commit_.side_effect = RuntimeError("PyObjC commit error")

        with (
            patch("club_calendar.menubar.eventkit._import_eventkit", return_value=mock_eventkit),
            patch(
                "club_calendar.menubar.eventkit._get_event_store", return_value=(mock_store, None)
            ),
            patch(
                "club_calendar.menubar.eventkit._find_or_create_calendar",
                return_value=(mock_calendar, None),
            ),
            patch.dict("sys.modules", {"Foundation": mock_foundation}),
        ):
            result = sync_events_to_calendar([])
            # Should still succeed even if commit fails with unexpected error
            assert result.success is True
