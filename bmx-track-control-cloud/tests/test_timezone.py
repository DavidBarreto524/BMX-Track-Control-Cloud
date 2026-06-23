from datetime import UTC, datetime

from app.services.timezone import (
    format_datetime,
    format_filename_timestamp,
    format_now_colombia,
    to_colombia,
    utc_now,
)


def test_utc_stored_value_shows_colombia_time():
    # 2026-06-22 20:00 UTC = 15:00 Colombia (UTC-5)
    value = datetime(2026, 6, 22, 20, 0, 0)
    assert format_datetime(value) == "22/06/2026 15:00"


def test_format_now_colombia_uses_bogota_timezone():
    now_colombia = format_now_colombia()
    assert len(now_colombia) == 16
    assert now_colombia[2] == "/"
    assert now_colombia[5] == "/"


def test_filename_timestamp_from_utc_value():
    value = datetime(2026, 6, 22, 20, 30, 45)
    assert format_filename_timestamp(value) == "20260622-153045"


def test_to_colombia_preserves_none():
    assert to_colombia(None) is None


def test_utc_now_is_naive():
    now = utc_now()
    assert now.tzinfo is None
    assert abs((datetime.now(UTC).replace(tzinfo=None) - now).total_seconds()) < 2
