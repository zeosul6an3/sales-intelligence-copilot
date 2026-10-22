"""Metric correctness.

1. A small dataset whose expected values were calculated by hand.
2. The real UCI dataset: every metric recomputed independently with pandas
   from the stored lines and compared with the SQL metrics layer.
"""

from datetime import date

import pandas as pd
import pytest

from sic.data import storage
from sic.metrics import queries
from sic.metrics.periods import Period, presets
from sic.metrics.queries import Filters

from .conftest import METRICS_CSV

JAN = Period(date(2024, 1, 1), date(2024, 1, 31))
ALL = Period(date(2024, 1, 1), date(2024, 2, 8))


@pytest.fixture
def con(make_upload):
    dataset_id = make_upload(METRICS_CSV)
    connection = storage.connect(dataset_id)
    yield connection
    connection.close()


def test_kpis_match_hand_calculation(con):
    assert queries.kpis(con, Filters(JAN)) == {
        "gross_sales": 55.0,  # 20 + 5 + 10 + 20
        "returns": 4.0,  # 2 x 2.00
        "net_revenue": 51.0,
        "orders": 3,  # 1001, 1002, 1003 (R1 is a return, not an order)
        "customers": 2,  # C1, C2; invoice 1003 has no customer
        "units": 20.0,
        "avg_order_value": 18.33,  # 55 / 3
    }


def test_excluded_line_types_do_not_count(con):
    k = queries.kpis(con, Filters(ALL))
    assert (k["gross_sales"], k["returns"], k["net_revenue"]) == (61.0, 4.0, 57.0)
    assert (k["orders"], k["units"]) == (
        4,
        23.0,
    )  # zero-price, zero-qty and negative-price excluded
    other = {r["line_type"]: r["lines"] for r in queries.other_lines(con, Filters(ALL))}
    assert other == {"zero_price_line": 1, "zero_quantity": 1, "negative_price": 1}


def test_filters(con):
    uk = queries.kpis(con, Filters(ALL, country="UK"))
    assert (uk["gross_sales"], uk["returns"], uk["orders"]) == (45.0, 4.0, 2)
    alpha = queries.kpis(con, Filters(ALL, product_id="A"))
    assert (alpha["net_revenue"], alpha["units"], alpha["orders"]) == (32.0, 18.0, 3)


def test_weekly_series_includes_empty_weeks_and_marks_partial_ones(con):
    points = queries.timeseries(con, Filters(ALL), "week")
    assert [p["period_start"] for p in points] == [
        "2024-01-01",
        "2024-01-08",
        "2024-01-15",
        "2024-01-22",
        "2024-01-29",
        "2024-02-05",
    ]
    assert [p["net_revenue"] for p in points] == [35.0, 16.0, 0.0, 0.0, 0.0, 6.0]
    assert [p["partial"] for p in points] == [False, False, False, False, False, True]
    assert sum(p["net_revenue"] for p in points) == queries.kpis(con, Filters(ALL))["net_revenue"]


def test_rankings(con):
    ranked = queries.products(con, Filters(ALL))["products"]
    assert [(p["product_id"], p["net_revenue"]) for p in ranked] == [("A", 32.0), ("B", 25.0)]
    assert queries.products(con, Filters(ALL), search="bet")["total_matches"] == 1
    countries = queries.countries(con, Filters(ALL))
    assert [(c["country"], c["net_revenue"]) for c in countries] == [("UK", 41.0), ("France", 16.0)]


def test_comparison_with_previous_period(con):
    result = queries.summary(con, Filters(Period(date(2024, 2, 1), date(2024, 2, 29))))
    assert result["previous_period"] == {"start": "2024-01-01", "end": "2024-01-31"}
    assert result["previous"]["net_revenue"] == 51.0
    assert result["previous_period_covered"] is True
    assert queries.summary(con, Filters(JAN))["previous_period_covered"] is False


# ---- Real UCI data: SQL metrics vs an independent pandas calculation --------------


def pandas_kpis(lines: pd.DataFrame, period: Period, country=None) -> dict:
    d = lines[(lines.invoice_date >= period.start) & (lines.invoice_date <= period.end)]
    if country:
        d = d[d.country == country]
    sales = d[d.line_type == "product_sale"]
    returns = d[d.line_type == "product_return"]
    gross = sales.quantity.mul(sales.unit_price).sum()
    ret = -returns.quantity.mul(returns.unit_price).sum()
    orders = sales.invoice_id.nunique()
    return {
        "gross_sales": round(gross, 2),
        "returns": round(ret, 2),
        "net_revenue": round(gross - ret, 2),
        "orders": orders,
        "customers": sales.customer_id.dropna().nunique(),
        "units": round(sales.quantity.sum(), 0),
        "avg_order_value": round(gross / orders, 2) if orders else None,
    }


def test_uci_metrics_match_independent_pandas(real_uci):
    lines = pd.read_parquet(real_uci / "lines.parquet")
    lines["invoice_date"] = pd.to_datetime(lines.invoice_date).dt.date
    con = storage.connect("uci")
    first, last = queries.coverage(con)
    cases = [(Period(first, last), None), (Period(first, last), "Germany")]
    for key in ("last_complete_month", "previous_complete_month", "last_complete_week"):
        p = presets(first, last)[key]
        cases.append((Period(date.fromisoformat(p["start"]), date.fromisoformat(p["end"])), None))
    for period, country in cases:
        expected = pandas_kpis(lines, period, country)
        actual = queries.kpis(con, Filters(period, country))
        for key, value in expected.items():
            assert actual[key] == pytest.approx(value, abs=0.01), (period, country, key)


def test_uci_reference_totals(real_uci):
    """Pinned totals for the official file; fails loudly if the data or rules change."""
    quality = storage.read_json("uci", "quality_report.json")
    if quality["source"]["sha256"] != (
        "bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980"
    ):
        pytest.skip("Different source file; pinned totals do not apply")
    con = storage.connect("uci")
    first, last = queries.coverage(con)
    k = queries.kpis(con, Filters(Period(first, last)))
    assert (k["gross_sales"], k["returns"], k["net_revenue"]) == (
        19700954.46,
        719692.94,
        18981261.52,
    )
    assert quality["row_flow"]["rows_kept"] == 1044848
