"""
Payday-aware retry scheduling for insufficient_funds failures.

FR11: SafeNet schedules insufficient_funds retries within a 24-hour window
after the 1st or 15th of the month — payday dates when subscribers are most
likely to have funds available.

NO Django imports. Pure Python.
Uses only stdlib datetime.
"""

from datetime import date, datetime, timedelta, timezone


def next_payday_retry_window(from_date: date) -> tuple[datetime, datetime]:
    """
    Given a reference date, returns the start and end of the next payday retry window.

    Payday dates: 1st and 15th of each month.
    Window: 24 hours starting from midnight UTC on the payday date.

    Rules:
    - If from_date is before the 15th: next window is the 15th of the same month.
    - If from_date is on or after the 15th: next window is the 1st of the next month.
    - If from_date IS a payday (1st or 15th): next window is still in the future
      (use the NEXT payday, not today — failure was detected today, not pre-scheduled).

    Args:
        from_date: The date from which to calculate the next window.
                   Typically: today's date when the failure is detected.

    Returns:
        (window_start, window_end) as UTC-aware datetimes.
        window_end = window_start + 24 hours.
    """
    year = from_date.year
    month = from_date.month

    # Is there a 15th window still upcoming this month?
    if from_date.day < 15:
        payday = date(year, month, 15)
    else:
        # Move to 1st of next month
        if month == 12:
            payday = date(year + 1, 1, 1)
        else:
            payday = date(year, month + 1, 1)

    window_start = datetime(payday.year, payday.month, payday.day, 0, 0, 0, tzinfo=timezone.utc)
    window_end = window_start + timedelta(hours=24)
    return window_start, window_end


def is_within_payday_window(dt: datetime) -> bool:
    """
    Returns True if the given datetime falls within a payday retry window.
    Used to determine if an immediate retry is appropriate for payday-aware codes.

    Args:
        dt: UTC-aware datetime to check.

    Returns:
        True if dt is on the 1st or 15th of the month (UTC).
    """
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.day in (1, 15)
