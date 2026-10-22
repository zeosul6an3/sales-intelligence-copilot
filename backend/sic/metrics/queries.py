"""Parametrised DuckDB queries over one dataset's `lines` table.

Every function takes an open connection (from sic.data.storage.connect) and a
Filters object, and returns small JSON-ready results. Values are never pasted
into SQL text: filters are passed as query parameters.
"""

from dataclasses import dataclass
from datetime import date

import duckdb

from sic.data.storage import PRODUCT_RETURN, PRODUCT_SALE
from sic.metrics.periods import Period

SALE = f"line_type = '{PRODUCT_SALE}'"
RETURN = f"line_type = '{PRODUCT_RETURN}'"

# One definition of each metric, reused by every query below.
METRIC_SQL = {
    "gross_sales": f"coalesce(sum(line_value) FILTER (WHERE {SALE}), 0)",
    "returns": f"coalesce(-sum(line_value) FILTER (WHERE {RETURN}), 0)",
    "net_revenue": (
        f"coalesce(sum(line_value) FILTER (WHERE {SALE}), 0)"
        f" + coalesce(sum(line_value) FILTER (WHERE {RETURN}), 0)"
    ),
    "orders": f"count(DISTINCT invoice_id) FILTER (WHERE {SALE})",
    "units": f"coalesce(sum(quantity) FILTER (WHERE {SALE}), 0)",
    "customers": f"count(DISTINCT customer_id) FILTER (WHERE {SALE} AND customer_id IS NOT NULL)",
}
SORTABLE_PRODUCT_METRICS = ("net_revenue", "gross_sales", "returns", "units", "orders")


@dataclass(frozen=True)
class Filters:
    period: Period
    country: str | None = None
    product_id: str | None = None

    def where(self) -> tuple[str, list]:
        clauses, params = ["invoice_date BETWEEN ? AND ?"], [self.period.start, self.period.end]
        if self.country:
            clauses.append("country = ?")
            params.append(self.country)
        if self.product_id:
            clauses.append("product_id = ?")
            params.append(self.product_id)
        return " AND ".join(clauses), params

    def describe(self) -> dict:
        return {
            **self.period.as_dict(),
            "country": self.country,
            "product_id": self.product_id,
        }


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: list) -> list[dict]:
    cursor = con.execute(sql, params)
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def _round(value, digits: int = 2):
    return None if value is None else round(float(value), digits)


def coverage(con: duckdb.DuckDBPyConnection) -> tuple[date, date]:
    return con.execute("SELECT min(invoice_date), max(invoice_date) FROM lines").fetchone()


def kpis(con: duckdb.DuckDBPyConnection, filters: Filters) -> dict:
    where, params = filters.where()
    row = _rows(
        con,
        f"SELECT {', '.join(f'{sql} AS {name}' for name, sql in METRIC_SQL.items())} "
        f"FROM lines WHERE {where}",
        params,
    )[0]
    result = {name: _round(row[name]) for name in ("gross_sales", "returns", "net_revenue")}
    result |= {name: int(row[name]) for name in ("orders", "customers")}
    result["units"] = _round(row["units"], 0)
    result["avg_order_value"] = (
        _round(row["gross_sales"] / row["orders"]) if row["orders"] else None
    )
    return result


def summary(con: duckdb.DuckDBPyConnection, filters: Filters) -> dict:
    """KPIs for the period, plus the same KPIs for the equal-length previous period."""
    current = kpis(con, filters)
    previous_filters = Filters(filters.period.previous(), filters.country, filters.product_id)
    previous = kpis(con, previous_filters)
    first, _ = coverage(con)
    return {
        "filters": filters.describe(),
        "current": current,
        "previous": previous,
        "previous_period": previous_filters.period.as_dict(),
        # A comparison is only meaningful if the previous period lies inside the data.
        "previous_period_covered": previous_filters.period.start >= first,
    }


def timeseries(con: duckdb.DuckDBPyConnection, filters: Filters, freq: str) -> list[dict]:
    """Net revenue, gross sales, returns and orders per week or month.

    Empty periods (e.g. Christmas closures) appear with zeros. A period is marked
    partial if it is cut off by the filter range or by the data's coverage.
    """
    if freq not in ("week", "month", "day"):
        raise ValueError("freq must be day, week or month")
    where, params = filters.where()
    first, last = coverage(con)
    step = {"day": "1 day", "week": "7 days", "month": "1 month"}[freq]
    sql = f"""
        WITH buckets AS (
            SELECT CAST(b AS DATE) AS period_start,
                   CAST(b + INTERVAL '{step}' - INTERVAL '1 day' AS DATE) AS period_end
            FROM range(date_trunc('{freq}', CAST(? AS DATE)),
                       CAST(? AS DATE) + INTERVAL '1 day', INTERVAL '{step}') t(b)
        ),
        agg AS (
            SELECT CAST(date_trunc('{freq}', invoice_date) AS DATE) AS period_start,
                   {METRIC_SQL["gross_sales"]} AS gross_sales,
                   {METRIC_SQL["returns"]} AS returns,
                   {METRIC_SQL["net_revenue"]} AS net_revenue,
                   {METRIC_SQL["orders"]} AS orders,
                   bool_or(is_unusual) AS has_unusual
            FROM lines WHERE {where} GROUP BY 1
        )
        SELECT b.period_start, b.period_end,
               coalesce(gross_sales, 0) AS gross_sales, coalesce(returns, 0) AS returns,
               coalesce(net_revenue, 0) AS net_revenue, coalesce(orders, 0) AS orders,
               coalesce(has_unusual, false) AS has_unusual
        FROM buckets b LEFT JOIN agg USING (period_start)
        ORDER BY b.period_start
    """
    rows = _rows(con, sql, [filters.period.start, filters.period.end, *params])
    lower, upper = max(first, filters.period.start), min(last, filters.period.end)
    return [
        {
            "period_start": r["period_start"].isoformat(),
            "period_end": r["period_end"].isoformat(),
            "gross_sales": _round(r["gross_sales"]),
            "returns": _round(r["returns"]),
            "net_revenue": _round(r["net_revenue"]),
            "orders": int(r["orders"]),
            "partial": r["period_start"] < lower or r["period_end"] > upper,
            "has_unusual": bool(r["has_unusual"]),
        }
        for r in rows
    ]


def products(
    con: duckdb.DuckDBPyConnection,
    filters: Filters,
    sort_by: str = "net_revenue",
    descending: bool = True,
    limit: int = 10,
    search: str | None = None,
) -> dict:
    """Products ranked by a metric, with an optional name/code search."""
    if sort_by not in SORTABLE_PRODUCT_METRICS:
        raise ValueError(f"sort_by must be one of {SORTABLE_PRODUCT_METRICS}")
    where, params = filters.where()
    search_sql = ""
    if search:
        search_sql = "HAVING product_id ILIKE ? OR any_value(product_name) ILIKE ?"
        params += [f"%{search}%", f"%{search}%"]
    sql = f"""
        SELECT product_id, any_value(product_name) AS product_name,
               {", ".join(f"{METRIC_SQL[m]} AS {m}" for m in SORTABLE_PRODUCT_METRICS)},
               count(*) OVER () AS total_matches
        FROM lines
        WHERE {where} AND line_type IN ('{PRODUCT_SALE}', '{PRODUCT_RETURN}')
        GROUP BY product_id {search_sql}
        ORDER BY {sort_by} {"DESC" if descending else "ASC"}, product_id
        LIMIT ?
    """
    rows = _rows(con, sql, [*params, limit])
    return {
        "total_matches": int(rows[0]["total_matches"]) if rows else 0,
        "products": [
            {
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "net_revenue": _round(r["net_revenue"]),
                "gross_sales": _round(r["gross_sales"]),
                "returns": _round(r["returns"]),
                "units": _round(r["units"], 0),
                "orders": int(r["orders"]),
            }
            for r in rows
        ],
    }


def countries(con: duckdb.DuckDBPyConnection, filters: Filters, limit: int = 10) -> list[dict]:
    where, params = filters.where()
    sql = f"""
        SELECT country, {METRIC_SQL["net_revenue"]} AS net_revenue,
               {METRIC_SQL["orders"]} AS orders, {METRIC_SQL["customers"]} AS customers
        FROM lines WHERE {where} GROUP BY country
        HAVING {METRIC_SQL["gross_sales"]} <> 0 OR {METRIC_SQL["returns"]} <> 0
        ORDER BY net_revenue DESC
    """
    rows = _rows(con, sql, params)
    top = rows[:limit]
    rest = rows[limit:]
    result = [
        {
            "country": r["country"],
            "net_revenue": _round(r["net_revenue"]),
            "orders": int(r["orders"]),
            "customers": int(r["customers"]),
        }
        for r in top
    ]
    if rest:
        result.append(
            {
                "country": f"Other ({len(rest)} countries)",
                "net_revenue": _round(sum(r["net_revenue"] for r in rest)),
                "orders": None,  # orders and customers cannot be summed across countries safely
                "customers": None,
            }
        )
    return result


def other_lines(con: duckdb.DuckDBPyConnection, filters: Filters) -> list[dict]:
    """Totals for every line type that is not part of product revenue."""
    where, params = filters.where()
    sql = f"""
        SELECT line_type, count(*) AS line_count, sum(line_value) AS value
        FROM lines WHERE {where} AND line_type NOT IN ('{PRODUCT_SALE}', '{PRODUCT_RETURN}')
        GROUP BY line_type ORDER BY abs(sum(line_value)) DESC, line_type
    """
    return [
        {"line_type": r["line_type"], "lines": int(r["line_count"]), "value": _round(r["value"])}
        for r in _rows(con, sql, params)
    ]


def country_list(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [r[0] for r in con.execute("SELECT DISTINCT country FROM lines ORDER BY 1").fetchall()]
