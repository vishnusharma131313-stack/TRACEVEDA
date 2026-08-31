"""
One representation for every timestamp this API stores.

WHY
---
Event timestamps arrive from clients and are stored as ISO strings, then
sorted by MongoDB. MongoDB sorts strings lexicographically, which only
matches chronological order when every string is in the SAME format and the
SAME offset.

They were not. `datetime.isoformat()` preserves whatever the caller sent, so
these three describe one instant and sort in the wrong order:

    2026-08-29T10:00:00        (naive - an ESP32 with no timezone)
    2026-08-29T10:00:00Z       (the browser, via toISOString())
    2026-08-29T15:30:00+05:30  (a client sending local time)

Normalising on write makes the stored strings both correct and comparable,
so a batch's telemetry and custody events come back in the order they
actually happened.
"""

from datetime import datetime, timezone


def to_utc(value):
    """
    A timezone-aware UTC datetime.

    A naive datetime is ASSUMED to be UTC rather than rejected: the IoT nodes
    send bare timestamps and dropping their readings would be worse than
    interpreting them the way the rest of the system already does.
    """

    if not isinstance(value, datetime):
        return value

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def to_utc_iso(value):
    """
    Canonical ISO-8601 UTC string: 2026-08-29T10:00:00+00:00

    Every stored timestamp goes through here, so string comparison on any
    timestamp field is equivalent to chronological comparison.
    """

    converted = to_utc(value)

    if not isinstance(converted, datetime):
        return converted

    return converted.isoformat()


def now_utc():
    """The current instant, timezone-aware. Replaces datetime.utcnow()."""

    return datetime.now(timezone.utc)


def sort_key(value):
    """
    A comparable string for a timestamp of unknown type.

    Documents from the seeded CSVs hold strings; documents this API writes
    hold datetimes. Sorting a merged list without normalising raises
    TypeError on Python 3.
    """

    if value is None:
        return ""

    if isinstance(value, datetime):
        return to_utc_iso(value)

    return str(value)
