"""Forecasting: leakage, windows, metrics, selection rule, calendar and corrections."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from sic.data import storage, uci
from sic.forecast import config, evaluate, series
from sic.forecast.calendar import week_features
from sic.forecast.models import Calendar, build_models, forecast_at

CFG = config.load()
WEEKS = [date(2020, 1, 6) + timedelta(days=7 * i) for i in range(110)]


def synthetic_series(seed=0) -> dict:
    rng = np.random.default_rng(seed)
    t = np.arange(len(WEEKS))
    base = 1000 + 300 * np.sin(2 * np.pi * t / 52)
    return {
        "total": base * 5 + rng.normal(0, 50, len(t)),
        "A": base + rng.normal(0, 30, len(t)),
        "B": base * 0.5 + rng.normal(0, 20, len(t)),
    }


# ---- Leakage -----------------------------------------------------------------------


@pytest.mark.parametrize("name", list(build_models(CFG, Calendar(WEEKS, "none"))))
def test_changing_future_values_does_not_change_forecasts(name):
    """The future-data perturbation test, for every model."""
    models = build_models(CFG, Calendar(WEEKS, "none"))
    data = synthetic_series()
    origin, horizon = 80, 8
    before = forecast_at(models[name], data, origin, horizon)
    perturbed = {k: v.copy() for k, v in data.items()}
    for v in perturbed.values():
        v[origin:] = v[origin:] * 50 + 12345  # wildly different future
    after = forecast_at(
        build_models(CFG, Calendar(WEEKS, "none"))[name], perturbed, origin, horizon
    )
    for k in data:
        np.testing.assert_allclose(before[k], after[k], err_msg=f"{name} leaked future data")


def test_seasonal_naive_uses_the_same_week_last_year():
    models = build_models(CFG, Calendar(WEEKS, "none"))
    data = {"x": np.arange(110, dtype=float)}
    out = forecast_at(models["seasonal_naive"], data, 60, 3)["x"]
    assert list(out) == [8.0, 9.0, 10.0]
    assert not models["seasonal_naive"].available(51)


# ---- Windows -----------------------------------------------------------------------


def test_builtin_layout_matches_the_approved_review():
    w = series.make_windows(104, CFG)
    assert (w.selection, w.validation, w.calibration, w.holdout) == (
        (0, 59),
        (60, 79),
        (80, 91),
        (92, 103),
    )
    weeks = [date(2009, 12, 7) + timedelta(days=7 * i) for i in range(104)]
    w.check(weeks)
    assert w.describe(weeks)["holdout"]["from"] == "2011-09-12"


def test_too_short_datasets_are_not_eligible_with_a_reason():
    with pytest.raises(series.NotEligible, match="at least 70 complete weeks"):
        series.make_windows(69, CFG)


def test_backtests_never_score_weeks_outside_their_window():
    models = build_models(CFG, Calendar(WEEKS, "none"))
    records = evaluate.backtest(models["naive"], synthetic_series(), (60, 79), 8)
    assert {r["target"] for r in records} == set(range(60, 80))
    assert all(r["origin"] <= r["target"] <= 79 for r in records)
    per_h = {h: sum(1 for r in records if r["h"] == h and r["series"] == "A") for h in (1, 8)}
    assert per_h == {1: 20, 8: 13}


def test_horizon_support_and_provisional_flags():
    info = evaluate.supported_horizons({"validation": 20, "calibration": 12, "holdout": 12}, CFG)
    assert all(info[h]["supported"] for h in range(1, 9))
    assert [h for h in info if info[h]["provisional"]] == [6, 7, 8]
    assert info[8]["calibration_points_per_series"] == 5


# ---- Metrics and selection -----------------------------------------------------------


def rec(actual, forecast, series_id="total", h=1, model="m"):
    return {
        "actual": actual,
        "forecast": forecast,
        "series": series_id,
        "h": h,
        "model": model,
        "scale": 1.0,
    }


def test_metrics_and_undefined_cases():
    m = evaluate.metrics([rec(100, 110), rec(200, 180)])
    assert m["mae"]["value"] == 15 and m["wape"]["value"] == pytest.approx(30 / 300)
    assert m["bias"]["value"] == pytest.approx(-10 / 300)  # forecast - actual
    zero = evaluate.metrics([rec(0, 5)])
    assert zero["wape"] == {"value": None, "reason": "sum of absolute actuals is 0"}
    assert evaluate.skill({"value": 5}, {"value": 0}, "naive")["value"] is None


def test_selection_rule_baseline_can_win_and_ties_prefer_simpler():
    def table(scores):
        return {
            m: {g: {h: {"wape": {"value": s}} for h in (1, 2)} for g in ("total", "products")}
            for m, s in scores.items()
        }

    won = evaluate.select(
        table({"naive": 0.30, "seasonal_naive": 0.10, "ridge": 0.20}), [1, 2], CFG
    )
    assert won["total"]["selected"] == "seasonal_naive"
    tie = evaluate.select(
        table({"seasonal_naive": 0.104, "hist_gradient_boosting": 0.100}), [1, 2], CFG
    )
    assert tie["total"]["selected"] == "seasonal_naive" and tie["total"]["tie_rule_applied"]
    exp = evaluate.select(table({"naive": 0.3, "hist_gradient_boosting_lag52": 0.01}), [1, 2], CFG)
    assert exp["total"]["selected"] == "naive"  # experiments are never eligible


def test_intervals_and_coverage():
    cal = [rec(100 + d, 100, h=1) for d in range(-10, 11)]
    q = evaluate.calibrate(cal, [1], 0.8)
    assert q["total"][1]["n"] == 21 and q["total"][1]["lower"] == pytest.approx(-8)
    cov = evaluate.coverage_table([rec(105, 100), rec(150, 100)], q)
    assert cov["total"][1] == {"coverage": 0.5, "n": 2}


# ---- Calendar ----------------------------------------------------------------------


def test_calendar_comes_from_published_dates_not_transactions():
    easter = week_features(date(2011, 4, 18), "england_wales")  # Good Friday 22 Apr
    assert easter["bank_holiday_weekdays"] == 1 and easter["month_4"] == 1
    royal = week_features(date(2011, 4, 25), "england_wales")  # Easter Monday + 29 Apr
    assert royal["bank_holiday_weekdays"] == 2
    christmas = week_features(date(2010, 12, 27), "england_wales")
    assert christmas["christmas_period_days"] == 6  # 27-31 Dec and 1 Jan
    assert "bank_holiday_weekdays" not in week_features(date(2011, 4, 18), "none")


# ---- Corrections and week flags --------------------------------------------------------


def uci_frame(rows):
    df = pd.DataFrame(rows)
    df["source_sheet"] = uci.SHEETS[1]
    df["source_row"] = range(2, len(df) + 2)
    return df


def line(inv, code, qty, price, ts, cust=15098.0):
    return {
        "Invoice": inv,
        "StockCode": code,
        "Description": "X",
        "Quantity": qty,
        "InvoiceDate": pd.Timestamp(ts),
        "Price": price,
        "Customer ID": cust,
        "Country": "United Kingdom",
    }


def test_exact_unique_manual_reversal_is_found_and_ambiguous_ones_are_not(data_dir):
    rows = [
        line("100", "22502", 60, 649.50, "2011-06-10 15:28"),  # the mistaken sale
        line("C101", "M", -1, 38970.0, "2011-06-10 15:31"),  # its exact manual reversal
        line("200", "1", 1, 2000.0, "2011-06-14 10:00", 2.0),  # two identical sales ...
        line("201", "2", 1, 2000.0, "2011-06-14 10:01", 2.0),
        line("C202", "M", -1, 2000.0, "2011-06-14 10:05", 2.0),  # ... so this is ambiguous
        line("300", "3", 1, 5000.0, "2011-06-15 10:00", 3.0),
        line("C301", "M", -1, 5000.0, "2011-06-15 11:00", 3.0),  # 60 minutes: too late
        line("400", "4", 1, 10.0, "2011-06-20 10:00"),
        # Activity before and after so the weeks of 6 and 13 June are complete weeks.
        line("050", "5", 1, 10.0, "2011-06-01 10:00"),
        line("500", "5", 1, 10.0, "2011-06-28 10:00"),
    ]
    uci.build_from_frame(
        uci_frame(rows), {"numeric_descriptions": 0}, {"file": "t", "sha256": "0" * 64}
    )
    with storage.connect("uci") as con:
        found = series.find_corrections(con, series.complete_weeks(con), CFG)
    assert len(found) == 1
    c = found[0]
    assert (c["amount"], c["week_start"], c["product_id"]) == (38970.0, "2011-06-06", "22502")
    assert c["source_rows"]["sale"]["invoice_id"] == "100"
    assert c["source_rows"]["reversal"]["invoice_id"] == "C101"


def test_real_uci_correction_and_closure_flags(real_uci):
    with storage.connect("uci") as con:
        data = series.build(con, CFG)
    assert len(data.weeks) == 104 and len(data.series_ids) == 21
    assert [c["amount"] for c in data.corrections] == [38970.0]
    i = data.weeks.index(date(2011, 6, 6))
    assert data.reported["total"][i] - data.adjusted["total"][i] == pytest.approx(38970.0)
    # Every other week is identical: the correction touches one week only.
    others = np.delete(data.reported["total"] - data.adjusted["total"], i)
    assert np.allclose(others, 0)
    flags = {str(w): f for w, f in zip(data.weeks, data.week_flags(), strict=True) if f}
    assert flags == {
        "2009-12-28": "inferred Christmas closure",
        "2010-12-27": "inferred Christmas closure",
    }
    kinds = data.zero_kind("22086")
    assert kinds.count("no business transactions") == 2
    assert "business active, no recorded sales" in kinds
