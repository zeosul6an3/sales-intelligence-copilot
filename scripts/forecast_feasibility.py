"""Milestone 3 forecasting feasibility review (analysis only; no model is trained).

Reads the cleaned built-in dataset and reports, for the proposed weekly
net-product-revenue target:
  1. complete weeks, closure weeks (no records at all) and short weeks;
  2. the proposed training / validation / calibration / holdout layout, with
     dates checked by assertions, and usable training rows per feature set;
  3. product eligibility, selected using the selection window only;
  4. the effect of the documented picnic-basket reversal on the target.

Writes evaluation/forecast_feasibility/review.json. Narrative and decisions:
docs/forecasting_feasibility_review.md.

Usage:
    uv run python scripts/forecast_feasibility.py
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from sic.data import storage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "forecast_feasibility"

HORIZON = 8  # weeks
SHORT_LAGS = (1, 2, 3, 4)
ROLLING_WINDOW = 8  # weeks; rolling mean/std computed from lags 1..8 only
SEASONAL_LAG = 52
TOP_N = 20
MIN_ACTIVE_SHARE = 0.75  # product must have net sales in >= 75% of trading weeks
# Segments in complete-week numbers (week 1 = first complete Monday-Sunday week).
SELECTION = (1, 60)  # products are ranked using these weeks only
VALIDATION = (61, 80)  # forecast targets used for model selection
CALIBRATION = (81, 92)  # forecast targets used for prediction-interval calibration
# The holdout is every remaining complete week (93..last).

NET = "line_type IN ('product_sale', 'product_return')"


def week_start(first_complete: date, n: int) -> date:
    return first_complete + timedelta(days=7 * (n - 1))


def main() -> int:
    con = storage.connect("uci")
    first, last = con.execute("SELECT min(invoice_date), max(invoice_date) FROM lines").fetchone()
    first_complete = first + timedelta(days=(7 - first.weekday()) % 7)  # first Monday >= first
    last_complete_end = last - timedelta(days=(last.weekday() + 1) % 7)  # last Sunday <= last
    n_weeks = ((last_complete_end - first_complete).days + 1) // 7
    holdout = (CALIBRATION[1] + 1, n_weeks)

    def ws(n: int) -> date:
        return week_start(first_complete, n)

    def we(n: int) -> date:
        return ws(n) + timedelta(days=6)

    weeks = con.execute(
        f"""
        WITH w AS (SELECT unnest(range(?::DATE, ?::DATE + 1, INTERVAL 7 DAY))::DATE AS week_start),
        agg AS (
            SELECT date_trunc('week', invoice_date)::DATE AS week_start, count(*) AS all_lines,
                   coalesce(sum(line_value) FILTER (WHERE {NET}), 0) AS net,
                   count(DISTINCT invoice_date) AS trading_days
            FROM lines GROUP BY 1)
        SELECT week_start, coalesce(all_lines, 0), coalesce(net, 0), coalesce(trading_days, 0)
        FROM w LEFT JOIN agg USING (week_start) ORDER BY week_start
        """,
        [first_complete, ws(n_weeks)],
    ).fetchall()
    assert len(weeks) == n_weeks
    week_rows = [
        {"week": i + 1, "start": str(r[0]), "lines": r[1], "net": round(r[2], 2), "days": r[3]}
        for i, r in enumerate(weeks)
    ]
    closure = [w for w in week_rows if w["lines"] == 0]
    short = [w for w in week_rows if 0 < w["days"] < 4]

    # ---- 2. Layout and window-date assertions -------------------------------------
    segments = {
        "selection (product ranking)": SELECTION,
        "validation targets (model selection)": VALIDATION,
        "calibration targets (intervals)": CALIBRATION,
        "final holdout targets": holdout,
    }
    assert SELECTION[1] < VALIDATION[0], "products must be selected before any forecast window"
    assert VALIDATION[1] < CALIBRATION[0] < CALIBRATION[1] < holdout[0], "segments overlap"
    assert we(CALIBRATION[1]) < ws(holdout[0]), "calibration targets reach the holdout"
    assert holdout[1] - holdout[0] + 1 >= HORIZON, "holdout shorter than the horizon"
    first_seasonal_target = SEASONAL_LAG + 1
    assert first_seasonal_target <= VALIDATION[0], "seasonal naive unavailable in validation"

    first_short_target = max(max(SHORT_LAGS), ROLLING_WINDOW) + 1
    origins = {
        "first validation origin": VALIDATION[0],
        "first calibration origin": CALIBRATION[0],
        "holdout origin": holdout[0],
        "final refit (future forecast)": n_weeks + 1,
    }

    def rows_at(origin: int, first_target: int) -> int:
        return max(0, origin - first_target)

    # ---- 3. Product eligibility (selection window only) -----------------------------
    sel_start, sel_end = ws(SELECTION[0]), we(SELECTION[1])
    trading_weeks_in_selection = sum(
        1 for w in week_rows[SELECTION[0] - 1 : SELECTION[1]] if w["lines"] > 0
    )
    products = con.execute(
        f"""
        WITH pw AS (
            SELECT product_id, date_trunc('week', invoice_date)::DATE AS week_start,
                   sum(line_value) AS net
            FROM lines WHERE {NET} AND invoice_date BETWEEN ? AND ? GROUP BY 1, 2)
        SELECT product_id, sum(net) AS net, count(*) FILTER (WHERE net > 0) AS active_weeks,
               min(week_start) AS first_week
        FROM pw GROUP BY 1 ORDER BY net DESC
        """,
        [sel_start, sel_end],
    ).fetchall()
    total_sel_net = con.execute(
        f"SELECT sum(line_value) FROM lines WHERE {NET} AND invoice_date BETWEEN ? AND ?",
        [sel_start, sel_end],
    ).fetchone()[0]
    eligible = [
        p
        for p in products
        if p[2] >= MIN_ACTIVE_SHARE * trading_weeks_in_selection and p[3] == sel_start
    ]
    selected = eligible[:TOP_N]
    names = dict(
        con.execute(
            "SELECT product_id, any_value(product_name) FROM lines WHERE product_id IN "
            f"({', '.join('?' * len(selected))}) GROUP BY 1",
            [p[0] for p in selected],
        ).fetchall()
    )

    def active_weeks(product_id: str, segment: tuple[int, int]) -> int:
        return con.execute(
            f"""SELECT count(*) FROM (
                SELECT date_trunc('week', invoice_date) w, sum(line_value) net FROM lines
                WHERE {NET} AND product_id = ? AND invoice_date BETWEEN ? AND ? GROUP BY 1)
                WHERE net > 0""",
            [product_id, ws(segment[0]), we(segment[1])],
        ).fetchone()[0]

    selected_rows = [
        {
            "rank": i + 1,
            "product_id": p[0],
            "name": names[p[0]],
            "selection_net": round(p[1], 2),
            "active_weeks_selection": p[2],
            # Reported for transparency only; never used for selection:
            "active_weeks_validation": active_weeks(p[0], VALIDATION),
            "active_weeks_holdout": active_weeks(p[0], holdout),
        }
        for i, p in enumerate(selected)
    ]

    # ---- 4. The picnic-basket reversal ------------------------------------------------
    reversal = con.execute(
        """
        WITH m AS (SELECT * FROM lines WHERE line_type = 'manual_adjustment'
                   AND invoice_id LIKE 'C%' AND line_value <= -1000),
             s AS (SELECT * FROM lines WHERE line_type = 'product_sale')
        SELECT m.invoice_id, s.invoice_id, s.product_id, -m.line_value, m.invoice_ts, s.invoice_ts,
               count(*) OVER (PARTITION BY m.line_id) AS candidates
        FROM m JOIN s ON s.customer_id = m.customer_id
             AND abs(s.line_value + m.line_value) < 0.005
             AND s.invoice_ts <= m.invoice_ts
             AND m.invoice_ts - s.invoice_ts <= INTERVAL 30 MINUTE
        """
    ).fetchall()
    matched = [r for r in reversal if r[6] == 1]
    effects = []
    for credit, sale, product, value, credit_ts, _sale_ts, _ in matched:
        week_no = (credit_ts.date() - first_complete).days // 7 + 1
        total = week_rows[week_no - 1]["net"]
        prod_week = con.execute(
            f"""SELECT sum(line_value) FROM lines WHERE {NET} AND product_id = ?
                AND date_trunc('week', invoice_date)::DATE = ?""",
            [product, ws(week_no)],
        ).fetchone()[0]
        effects.append(
            {
                "credit_invoice": credit,
                "sale_invoice": sale,
                "product_id": product,
                "value": round(value, 2),
                "week": week_no,
                "week_start": str(ws(week_no)),
                "segment": next(
                    k
                    for k, (a, b) in segments.items()
                    if a <= week_no <= b and not k.startswith("selection")
                )
                if week_no > SELECTION[1]
                else "selection",
                "total_week_net_as_reported": total,
                "total_week_net_if_reversal_applied": round(total - value, 2),
                "share_of_total_week": round(value / total, 4),
                "product_week_net_as_reported": round(prod_week, 2),
                "product_week_net_if_reversal_applied": round(prod_week - value, 2),
                "product_selected": product in {p["product_id"] for p in selected_rows},
            }
        )

    result = {
        "complete_weeks": {
            "count": n_weeks,
            "first": f"{ws(1)} – {we(1)}",
            "last": f"{ws(n_weeks)} – {we(n_weeks)}",
            "excluded_partial": [
                f"{first_complete - timedelta(days=7)} week (data starts {first})",
                f"{ws(n_weeks + 1)} week (data ends {last})",
            ],
            "closure_weeks": closure,
            "short_weeks": short,
        },
        "segments": {
            k: {"weeks": f"{a}–{b}", "n_weeks": b - a + 1, "from": str(ws(a)), "to": str(we(b))}
            for k, (a, b) in segments.items()
        },
        "first_trainable_target": {
            "short_lags": {"week": first_short_target, "start": str(ws(first_short_target))},
            "with_lag_52": {"week": first_seasonal_target, "start": str(ws(first_seasonal_target))},
        },
        "training_rows": [
            {
                "origin": name,
                "week": o,
                "origin_date": str(ws(o)),
                "short_lags_per_series": rows_at(o, first_short_target),
                "lag52_per_series": rows_at(o, first_seasonal_target),
                f"short_lags_pooled_{TOP_N + 1}": rows_at(o, first_short_target) * (TOP_N + 1),
                f"lag52_pooled_{TOP_N + 1}": rows_at(o, first_seasonal_target) * (TOP_N + 1),
            }
            for name, o in origins.items()
        ],
        "evaluation_points_per_series": {
            seg: {f"h{h}": max(0, b - a + 1 - (h - 1)) for h in (1, 4, 8)}
            for seg, (a, b) in {
                "validation": VALIDATION,
                "calibration": CALIBRATION,
                "holdout": holdout,
            }.items()
        },
        "products": {
            "products_with_net_sales_in_selection": sum(1 for p in products if p[1] > 0),
            "trading_weeks_in_selection": trading_weeks_in_selection,
            "eligible": len(eligible),
            "rule": (
                f"net sales in >= {MIN_ACTIVE_SHARE:.0%} of trading weeks of the selection "
                f"window and sold in its first week; top {TOP_N} by selection-window net"
            ),
            "selected": selected_rows,
            "selected_share_of_selection_net": round(
                sum(p["selection_net"] for p in selected_rows) / total_sel_net, 4
            ),
        },
        "reversal_effects": effects,
        "unmatched_large_manual_credits_note": (
            "Other large Manual credits have no exactly matching product sale within 30 minutes; "
            "most pair with a Manual charge of the same amount and never touch product revenue."
        ),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "review.json").write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
