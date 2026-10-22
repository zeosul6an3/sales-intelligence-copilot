from datetime import date

from sic.metrics.periods import Period, last_complete_month, last_complete_week, presets


def test_last_complete_month_skips_a_cut_off_month():
    assert last_complete_month(date(2009, 12, 1), date(2011, 12, 9)) == Period(
        date(2011, 11, 1), date(2011, 11, 30)
    )
    # Data ending exactly on a month end: that month counts.
    assert last_complete_month(date(2024, 1, 1), date(2024, 2, 29)) == Period(
        date(2024, 2, 1), date(2024, 2, 29)
    )
    # Data starting mid-month: the first month is not complete.
    assert last_complete_month(date(2024, 1, 15), date(2024, 2, 10)) is None


def test_last_complete_week_is_monday_to_sunday():
    week = last_complete_week(date(2009, 12, 1), date(2011, 12, 9))  # 9 Dec 2011 is a Friday
    assert week == Period(date(2011, 11, 28), date(2011, 12, 4))
    assert week.start.weekday() == 0 and week.end.weekday() == 6


def test_previous_period():
    assert Period(date(2011, 11, 1), date(2011, 11, 30)).previous() == Period(
        date(2011, 10, 1), date(2011, 10, 31)
    )
    assert Period(date(2011, 9, 1), date(2011, 11, 30)).previous() == Period(
        date(2011, 6, 1), date(2011, 8, 31)
    )
    assert Period(date(2011, 3, 10), date(2011, 3, 16)).previous() == Period(
        date(2011, 3, 3), date(2011, 3, 9)
    )


def test_presets_only_offer_periods_inside_the_data():
    short = presets(date(2024, 1, 1), date(2024, 2, 10))
    assert "last_complete_month" in short and "last_12_complete_months" not in short
    uci = presets(date(2009, 12, 1), date(2011, 12, 9))
    assert uci["last_12_complete_months"] == {
        "label": "Last 12 complete months",
        "start": "2010-12-01",
        "end": "2011-11-30",
    }
