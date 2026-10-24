"""Holiday-calendar indicators, known in advance of every forecast origin.

These come from the published England and Wales bank-holiday list, never from
transactions, so they can be used for future weeks without leakage. They are
model inputs only: the models are never forced to forecast zero on a holiday.
"""

from datetime import date, timedelta

# England and Wales bank holidays, transcribed from https://www.gov.uk/bank-holidays
# (including substitute days, the 29 April 2011 royal wedding and the 2012 jubilee).
ENGLAND_WALES_BANK_HOLIDAYS = frozenset(
    date.fromisoformat(d)
    for d in (
        "2009-01-01 2009-04-10 2009-04-13 2009-05-04 2009-05-25 2009-08-31 2009-12-25 2009-12-28 "
        "2010-01-01 2010-04-02 2010-04-05 2010-05-03 2010-05-31 2010-08-30 2010-12-27 2010-12-28 "
        "2011-01-03 2011-04-22 2011-04-25 2011-04-29 2011-05-02 2011-05-30 2011-08-29 2011-12-26 "
        "2011-12-27 2012-01-02 2012-04-06 2012-04-09 2012-05-07 2012-06-04 2012-06-05 2012-08-27 "
        "2012-12-25 2012-12-26"
    ).split()
)
CALENDAR_COVERAGE = {"england_wales": (date(2009, 1, 1), date(2012, 12, 31))}


class CalendarNotCovered(ValueError):
    pass


def is_christmas_period(day: date) -> bool:
    """24 December to 1 January inclusive (a calendar fact, not a closure claim)."""
    return (day.month == 12 and day.day >= 24) or (day.month == 1 and day.day == 1)


def week_features(week_start: date, calendar: str) -> dict[str, float]:
    """Calendar inputs for the Monday-Sunday week starting on `week_start`."""
    days = [week_start + timedelta(days=i) for i in range(7)]
    features = {f"month_{m}": 0.0 for m in range(1, 13)}
    features[f"month_{(week_start + timedelta(days=3)).month}"] = 1.0  # month of the Thursday
    if calendar == "none":
        return features
    if calendar != "england_wales":
        raise ValueError(f"Unknown calendar {calendar!r}")
    first, last = CALENDAR_COVERAGE[calendar]
    if days[0] < first or days[-1] > last:
        raise CalendarNotCovered(f"Holiday calendar does not cover the week of {week_start}")
    features["bank_holiday_weekdays"] = float(
        sum(d in ENGLAND_WALES_BANK_HOLIDAYS and d.weekday() < 5 for d in days)
    )
    features["christmas_period_days"] = float(sum(is_christmas_period(d) for d in days))
    return features
