"""Named periods resolved by code, never by the language model.

A period counts as *complete* only if the dataset's coverage (first to last
transaction date) spans all of it. Weeks run Monday to Sunday.
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Period:
    start: date  # inclusive
    end: date  # inclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def whole_months(self) -> int:
        """Number of calendar months covered exactly, or 0 if not whole months."""
        if self.start.day != 1 or next_month(self.end) != self.end + timedelta(days=1):
            return 0
        return (self.end.year - self.start.year) * 12 + self.end.month - self.start.month + 1

    def previous(self) -> "Period":
        """The comparable period immediately before this one.

        Whole calendar months compare with the same number of preceding calendar
        months (November -> October); any other range compares with the same
        number of days immediately before it.
        """
        months = self.whole_months()
        if months:
            start = self.start
            for _ in range(months):
                start = month_start(start - timedelta(days=1))
            return Period(start, self.start - timedelta(days=1))
        return Period(self.start - timedelta(days=self.days), self.start - timedelta(days=1))

    def as_dict(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


def month_start(day: date) -> date:
    return day.replace(day=1)


def next_month(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def last_complete_month(first: date, last: date) -> Period | None:
    start = month_start(last)
    end = next_month(start) - timedelta(days=1)
    if end > last:  # the month containing the last date is cut off
        end = start - timedelta(days=1)
        start = month_start(end)
    return Period(start, end) if start >= first else None


def complete_months_back(first: date, last: date, count: int) -> Period | None:
    latest = last_complete_month(first, last)
    if latest is None:
        return None
    start = latest.start
    for _ in range(count - 1):
        start = month_start(start - timedelta(days=1))
    return Period(start, latest.end) if start >= first else None


def last_complete_week(first: date, last: date) -> Period | None:
    end = last - timedelta(days=(last.weekday() + 1) % 7)  # most recent Sunday <= last
    start = end - timedelta(days=6)
    return Period(start, end) if start >= first else None


def presets(first: date, last: date) -> dict[str, dict]:
    """Named periods offered in the dashboard (and later to the assistant)."""
    latest_month = last_complete_month(first, last)
    previous_month = (
        last_complete_month(first, latest_month.start - timedelta(days=1)) if latest_month else None
    )
    candidates = {
        "all_data": ("All data", Period(first, last)),
        "last_complete_month": ("Last complete month", latest_month),
        "previous_complete_month": ("Previous complete month", previous_month),
        "last_3_complete_months": ("Last 3 complete months", complete_months_back(first, last, 3)),
        "last_12_complete_months": (
            "Last 12 complete months",
            complete_months_back(first, last, 12),
        ),
        "last_complete_week": ("Last complete week", last_complete_week(first, last)),
    }
    return {
        key: {"label": label, **period.as_dict()}
        for key, (label, period) in candidates.items()
        if period is not None
    }
