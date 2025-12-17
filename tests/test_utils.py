"""Tests for utils module."""

from club_calendar.menubar.utils import DayLabel, get_activity_emoji


class TestGetActivityEmoji:
    """Tests for get_activity_emoji function."""

    def test_ride_emoji(self):
        """Test ride emoji from activity type."""
        assert get_activity_emoji("Ride") == "🚴"
        assert get_activity_emoji("Cycling") == "🚴"
        assert get_activity_emoji("ride") == "🚴"  # case insensitive

    def test_run_emoji(self):
        """Test run emoji from activity type."""
        assert get_activity_emoji("Run") == "🏃"
        assert get_activity_emoji("run") == "🏃"

    def test_swim_emoji(self):
        """Test swim emoji from activity type."""
        assert get_activity_emoji("Swim") == "🏊"
        assert get_activity_emoji("swim") == "🏊"

    def test_hike_emoji(self):
        """Test hike/walk emoji from activity type."""
        assert get_activity_emoji("Hike") == "🥾"
        assert get_activity_emoji("Walk") == "🥾"

    def test_default_emoji_none(self):
        """Test default emoji when activity type is None."""
        assert get_activity_emoji(None) == "📅"

    def test_default_emoji_empty(self):
        """Test default emoji when activity type is empty."""
        assert get_activity_emoji("") == "📅"

    def test_default_emoji_unknown(self):
        """Test default emoji for unknown activity type."""
        assert get_activity_emoji("Unknown") == "📅"
        assert get_activity_emoji("Yoga") == "📅"


class TestDayLabel:
    """Tests for DayLabel NamedTuple."""

    def test_day_label_creation(self):
        """Test DayLabel can be created with all fields."""
        label = DayLabel(
            label="Today (Wed, 17 Dec):",
            is_this_week=True,
            is_today=True,
            is_next_week=False,
        )
        assert label.label == "Today (Wed, 17 Dec):"
        assert label.is_this_week is True
        assert label.is_today is True
        assert label.is_next_week is False

    def test_day_label_tuple_unpacking(self):
        """Test DayLabel supports tuple unpacking."""
        label = DayLabel(
            label="Tomorrow (Thu, 18 Dec):",
            is_this_week=True,
            is_today=False,
            is_next_week=False,
        )
        text, this_week, today, next_week = label
        assert text == "Tomorrow (Thu, 18 Dec):"
        assert this_week is True
        assert today is False
        assert next_week is False
