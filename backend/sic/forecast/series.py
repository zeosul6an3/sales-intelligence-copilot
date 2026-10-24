"""Weekly target series for forecasting.

Builds, for one dataset:
  * the complete Monday-Sunday weeks and the evaluation windows (counted back
    from the last complete week, then checked with assertions);
  * the business-total series and the top-N product series, with products
    ranked on the selection window only;
  * documented forecasting-only corrections ("Adjusted net product revenue"),
    applied identically to the total and to the affected product, with the
    unadjusted ("reported") values kept alongside;
  * week flags: weeks with no business transactions at all, and whether they
    fall in the Christmas period ("inferred Christmas closure").
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

import duckdb
import numpy as np

from sic.data.storage import PRODUCT_RETURN, PRODUCT_SALE
from sic.forecast.calendar import is_christmas_period

NET = f"line_type IN ('{PRODUCT_SALE}', '{PRODUCT_RETURN}')"
TOTAL = "total"


class NotEligible(ValueError):
    """The dataset cannot support the frozen evaluation design; the message says why."""


@dataclass(frozen=True)
class Windows:
    """0-based, inclusive week indexes into the complete-week list."""

    selection: tuple[int, int]
    validation: tuple[int, int]
    calibration: tuple[int, int]
    holdout: tuple[int, int]

    def check(self, weeks: list[date]) -> None:
        s, v, c, h = self.selection, self.validation, self.calibration, self.holdout
        assert s[0] == 0 and s[1] + 1 == v[0], "selection must end right before validation"
        assert v[0] <= v[1] < c[0] <= c[1] < h[0] <= h[1], "windows must be ordered and disjoint"
        assert weeks[c[1]] + timedelta(days=6) < weeks[h[0]], "calibration reaches the holdout"
        assert h[1] == len(weeks) - 1, "holdout must end at the last complete week"

    def describe(self, weeks: list[date]) -> dict:
        def span(a: int, b: int) -> dict:
            return {
                "weeks": f"{a + 1}-{b + 1}",
                "count": b - a + 1,
                "from": weeks[a].isoformat(),
                "to": (weeks[b] + timedelta(days=6)).isoformat(),
            }

        return {
            "selection": span(*self.selection),
            "validation": span(*self.validation),
            "calibration": span(*self.calibration),
            "holdout": span(*self.holdout),
        }


def make_windows(n_weeks: int, cfg: dict) -> Windows:
    w = cfg["windows"]
    needed = (
        w["min_selection_weeks"]
        + w["validation_weeks"]
        + w["calibration_weeks"]
        + w["holdout_weeks"]
    )
    if n_weeks < needed:
        raise NotEligible(
            f"Forecasting needs at least {needed} complete weeks "
            f"({w['min_selection_weeks']} history + {w['validation_weeks']} validation + "
            f"{w['calibration_weeks']} calibration + {w['holdout_weeks']} holdout); "
            f"this dataset has {n_weeks}."
        )
    h0 = n_weeks - w["holdout_weeks"]
    c0 = h0 - w["calibration_weeks"]
    v0 = c0 - w["validation_weeks"]
    return Windows((0, v0 - 1), (v0, c0 - 1), (c0, h0 - 1), (h0, n_weeks - 1))


@dataclass
class WeeklyData:
    weeks: list[date]
    windows: Windows
    series_ids: list[str]  # "total" first, then product IDs in selection rank order
    names: dict[str, str]
    adjusted: dict[str, np.ndarray]  # the forecasting target
    reported: dict[str, np.ndarray]  # same as the dashboard's net product revenue
    business_lines: np.ndarray  # lines of any type recorded per week (unfiltered)
    corrections: list[dict] = field(default_factory=list)
    selection_info: dict = field(default_factory=dict)

    def week_flags(self) -> list[str | None]:
        flags = []
        for week, lines in zip(self.weeks, self.business_lines, strict=True):
            if lines == 0:
                christmas = any(is_christmas_period(week + timedelta(days=i)) for i in range(7))
                flags.append(
                    "inferred Christmas closure"
                    if christmas
                    else "no business transactions recorded"
                )
            else:
                flags.append(None)
        return flags

    def zero_kind(self, series_id: str) -> list[str | None]:
        """For each week with zero target: why it is zero."""
        values = self.reported[series_id]
        return [
            None
            if v != 0
            else (
                "no business transactions" if lines == 0 else "business active, no recorded sales"
            )
            for v, lines in zip(values, self.business_lines, strict=True)
        ]


def complete_weeks(con: duckdb.DuckDBPyConnection) -> list[date]:
    first, last = con.execute("SELECT min(invoice_date), max(invoice_date) FROM lines").fetchone()
    start = first + timedelta(days=(7 - first.weekday()) % 7)  # first Monday on/after start
    end = last - timedelta(days=(last.weekday() + 1) % 7)  # last Sunday on/before end
    n = ((end - start).days + 1) // 7
    return [start + timedelta(days=7 * i) for i in range(n)]


def _weekly(con, sql_filter: str, params: list, weeks: list[date]) -> np.ndarray:
    rows = dict(
        con.execute(
            f"""SELECT date_trunc('week', invoice_date)::DATE, sum(line_value) FROM lines
                WHERE {NET} AND invoice_date BETWEEN ? AND ? {sql_filter} GROUP BY 1""",
            [weeks[0], weeks[-1] + timedelta(days=6), *params],
        ).fetchall()
    )
    return np.array([float(rows.get(w, 0.0)) for w in weeks])


def select_products(con, weeks: list[date], windows: Windows, cfg: dict) -> tuple[list, dict]:
    """Top-N eligible products, using the selection window only."""
    a, b = windows.selection
    start, end = weeks[a], weeks[b] + timedelta(days=6)
    trading = int(
        con.execute(
            "SELECT count(DISTINCT date_trunc('week', invoice_date)) FROM lines "
            "WHERE invoice_date BETWEEN ? AND ?",
            [start, end],
        ).fetchone()[0]
    )
    rows = con.execute(
        f"""
        WITH pw AS (SELECT product_id, date_trunc('week', invoice_date)::DATE AS w,
                           sum(line_value) AS net
                    FROM lines WHERE {NET} AND invoice_date BETWEEN ? AND ? GROUP BY 1, 2)
        SELECT product_id, sum(net), count(*) FILTER (WHERE net > 0), min(w)
        FROM pw GROUP BY 1 ORDER BY sum(net) DESC, product_id
        """,
        [start, end],
    ).fetchall()
    share = cfg["products"]["min_active_share"]
    eligible = [r for r in rows if r[2] >= share * trading and r[3] == weeks[a]]
    chosen = eligible[: cfg["products"]["top_n"]]
    info = {
        "rule": (
            f"Net sales in >= {share:.0%} of the selection window's {trading} trading weeks "
            f"and a sale in its first week; top {cfg['products']['top_n']} by net product "
            f"revenue between {start} and {end} (selection window only)."
        ),
        "products_with_sales": sum(1 for r in rows if r[1] > 0),
        "eligible": len(eligible),
        "selected": [
            {"product_id": r[0], "selection_net": round(r[1], 2), "active_weeks": r[2]}
            for r in chosen
        ],
    }
    return [r[0] for r in chosen], info


def find_corrections(con, weeks: list[date], cfg: dict) -> list[dict]:
    """Manual credits that exactly and uniquely reverse one product-sale line."""
    c = cfg["corrections"]
    rows = con.execute(
        f"""
        WITH m AS (SELECT * FROM lines WHERE line_type = 'manual_adjustment'
                   AND invoice_id LIKE 'C%' AND -line_value >= ?),
             s AS (SELECT * FROM lines WHERE line_type = '{PRODUCT_SALE}'),
             pairs AS (
                SELECT m.line_id AS credit_line, s.line_id AS sale_line,
                       count(*) OVER (PARTITION BY m.line_id) AS n_candidates
                FROM m JOIN s ON s.customer_id = m.customer_id
                     AND abs(s.line_value + m.line_value) < 0.005
                     AND s.invoice_ts <= m.invoice_ts
                     AND m.invoice_ts - s.invoice_ts <= to_minutes(CAST(? AS BIGINT)))
        SELECT credit_line, sale_line FROM pairs WHERE n_candidates = 1 ORDER BY credit_line
        """,
        [c["manual_reversal_min_value"], c["manual_reversal_max_minutes"]],
    ).fetchall()

    def line(line_id: int) -> dict:
        cur = con.execute(
            """SELECT line_id, source_sheet, source_row, invoice_id,
                      CAST(invoice_ts AS VARCHAR) AS invoice_ts, product_id, product_name,
                      raw_description,
                      quantity, unit_price, line_value, customer_id, line_type
               FROM lines WHERE line_id = ?""",
            [line_id],
        )
        names = [d[0] for d in cur.description]
        return dict(zip(names, cur.fetchone(), strict=True))

    corrections = []
    for credit_id, sale_id in rows:
        credit, sale = line(credit_id), line(sale_id)
        day = date.fromisoformat(sale["invoice_ts"][:10])
        week = day - timedelta(days=day.weekday())
        if not weeks or week < weeks[0] or week > weeks[-1]:
            continue  # outside the complete-week range: no effect on the target
        corrections.append(
            {
                "id": f"manual-reversal-{credit['invoice_id']}",
                "rule": (
                    f"Manual credit on a cancellation invoice that exactly reverses one, and only "
                    f"one, product-sale line of the same customer within "
                    f"{c['manual_reversal_max_minutes']} minutes (value >= "
                    f"{c['manual_reversal_min_value']:,.0f})."
                ),
                "rationale": (
                    "The reversal was booked with the non-product code M, so under the approved "
                    "policy it sits outside net product revenue while the sale it reverses stays "
                    "inside. For forecasting only, the reversal is applied to the product and the "
                    "business total; the dashboard and stored transactions are unchanged."
                ),
                "amount": round(-credit["line_value"], 2),
                "week_start": week.isoformat(),
                "product_id": sale["product_id"],
                "product_name": sale["product_name"],  # display name, as in rankings
                "customer_id": sale["customer_id"],
                "source_rows": {"sale": sale, "reversal": credit},
            }
        )
    return corrections


def build(con: duckdb.DuckDBPyConnection, cfg: dict) -> WeeklyData:
    weeks = complete_weeks(con)
    windows = make_windows(len(weeks), cfg)
    windows.check(weeks)
    products, selection_info = select_products(con, weeks, windows, cfg)
    names = {TOTAL: "Business total"}
    names |= dict(
        con.execute(
            "SELECT product_id, any_value(product_name) FROM lines "
            "WHERE list_contains(?, product_id) GROUP BY 1",
            [products],
        ).fetchall()
    )
    reported = {TOTAL: _weekly(con, "", [], weeks)}
    for p in products:
        reported[p] = _weekly(con, "AND product_id = ?", [p], weeks)
    business = dict(
        con.execute(
            "SELECT date_trunc('week', invoice_date)::DATE, count(*) FROM lines GROUP BY 1"
        ).fetchall()
    )
    adjusted = {k: v.copy() for k, v in reported.items()}
    corrections = find_corrections(con, weeks, cfg)
    for corr in corrections:
        i = weeks.index(date.fromisoformat(corr["week_start"]))
        adjusted[TOTAL][i] -= corr["amount"]
        corr["applied_to"] = [TOTAL]
        if corr["product_id"] in adjusted:
            adjusted[corr["product_id"]][i] -= corr["amount"]
            corr["applied_to"].append(corr["product_id"])
        product_week = float(_weekly(con, "AND product_id = ?", [corr["product_id"]], weeks)[i])
        corr["product_in_forecast_set"] = corr["product_id"] in adjusted
        corr["product_week_reported"] = round(product_week, 2)
        corr["product_week_adjusted"] = round(product_week - corr["amount"], 2)
        corr["total_week_reported"] = round(float(reported[TOTAL][i]), 2)
        corr["total_week_adjusted"] = round(float(adjusted[TOTAL][i]), 2)
    return WeeklyData(
        weeks=weeks,
        windows=windows,
        series_ids=[TOTAL, *products],
        names=names,
        adjusted=adjusted,
        reported=reported,
        business_lines=np.array([int(business.get(w, 0)) for w in weeks]),
        corrections=corrections,
        selection_info=selection_info,
    )
