from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

COLOMBIA_TZ = ZoneInfo("America/Bogota")
DATETIME_DISPLAY_FMT = "%d/%m/%Y %H:%M"
FILENAME_TIMESTAMP_FMT = "%Y%m%d-%H%M%S"


def utc_now() -> datetime:
    """Hora actual en UTC, sin tzinfo (compatible con el almacenamiento actual)."""
    return datetime.now(UTC).replace(tzinfo=None)


def colombia_now() -> datetime:
    return datetime.now(COLOMBIA_TZ)


def assume_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_colombia(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return assume_utc(value).astimezone(COLOMBIA_TZ)


def format_datetime(value: datetime | None) -> str:
    if not value:
        return ""
    localized = to_colombia(value)
    assert localized is not None
    return localized.strftime(DATETIME_DISPLAY_FMT)


def format_filename_timestamp(value: datetime | None = None) -> str:
    localized = to_colombia(value) if value is not None else colombia_now()
    assert localized is not None
    return localized.strftime(FILENAME_TIMESTAMP_FMT)


def format_now_colombia() -> str:
    return colombia_now().strftime(DATETIME_DISPLAY_FMT)
