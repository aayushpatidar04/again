"""Lunch-aware schedule-board time calculations shared by all five boards."""

from datetime import timedelta


LUNCH_START = timedelta(hours=12)
LUNCH_END = timedelta(hours=13)


def spans_lunch(start, end):
    """A visit may pause for lunch only when it has work on both sides."""
    return start < LUNCH_START and end > LUNCH_END


def work_intervals(start, end):
    """Return the visible work blocks for one continuous visit booking."""
    if spans_lunch(start, end):
        return [(start, LUNCH_START), (LUNCH_END, end)]
    return [(start, end)]
