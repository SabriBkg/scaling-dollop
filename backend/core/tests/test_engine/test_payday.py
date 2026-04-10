"""
Tests for payday calendar scheduling logic.
NO database required — pure Python.
"""
from datetime import date, datetime, timezone
from core.engine.payday import next_payday_retry_window, is_within_payday_window


class TestNextPaydayRetryWindow:
    def test_before_15th_returns_15th(self):
        start, end = next_payday_retry_window(date(2026, 4, 1))
        assert start.day == 15
        assert start.month == 4

    def test_on_14th_returns_15th(self):
        start, end = next_payday_retry_window(date(2026, 4, 14))
        assert start.day == 15
        assert start.month == 4

    def test_on_15th_returns_1st_next_month(self):
        start, end = next_payday_retry_window(date(2026, 4, 15))
        assert start.day == 1
        assert start.month == 5

    def test_after_15th_returns_1st_next_month(self):
        start, end = next_payday_retry_window(date(2026, 4, 20))
        assert start.day == 1
        assert start.month == 5

    def test_december_returns_january_1st(self):
        start, end = next_payday_retry_window(date(2026, 12, 16))
        assert start.day == 1
        assert start.month == 1
        assert start.year == 2027

    def test_window_is_24_hours(self):
        start, end = next_payday_retry_window(date(2026, 4, 1))
        delta = end - start
        assert delta.total_seconds() == 24 * 3600

    def test_window_is_utc_aware(self):
        start, end = next_payday_retry_window(date(2026, 4, 1))
        assert start.tzinfo == timezone.utc
        assert end.tzinfo == timezone.utc

    def test_window_starts_at_midnight_utc(self):
        start, _ = next_payday_retry_window(date(2026, 4, 1))
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0


class TestIsWithinPaydayWindow:
    def test_1st_is_payday_window(self):
        dt = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert is_within_payday_window(dt) is True

    def test_15th_is_payday_window(self):
        dt = datetime(2026, 4, 15, 6, 0, 0, tzinfo=timezone.utc)
        assert is_within_payday_window(dt) is True

    def test_other_days_are_not_payday_window(self):
        for day in [2, 10, 14, 16, 28]:
            dt = datetime(2026, 4, day, 0, 0, 0, tzinfo=timezone.utc)
            assert is_within_payday_window(dt) is False, f"Day {day} should not be payday"
