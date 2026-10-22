"""Profile the raw UCI workbook: the evidence behind the cleaning rules.

Prints Markdown tables for each question that shaped a rule in
docs/data_cleaning.md, straight from the downloaded file, so the evidence can
be re-checked on any computer.

Usage:
    uv run python scripts/profile_raw_data.py > /tmp/profile.md
"""

import sys
from pathlib import Path

import duckdb

from sic.data.uci import SHEETS, read_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = PROJECT_ROOT / "data" / "raw" / "online_retail_II.xlsx"
KEY = """concat_ws('|', Invoice, StockCode, coalesce(Description, '<null>'), Quantity,
         InvoiceDate, Price, coalesce(CAST("Customer ID" AS VARCHAR), '<null>'), Country)"""

QUESTIONS = {
    "Rows, dates and distinct values per sheet": """
        SELECT source_sheet, count(*) AS n_rows, min(InvoiceDate) AS first_ts,
               max(InvoiceDate) AS last_ts, count(DISTINCT Invoice) AS invoices,
               count(DISTINCT StockCode) AS stock_codes, count(DISTINCT "Customer ID") AS customers,
               count(*) - count("Customer ID") AS missing_customer,
               count(*) - count(Description) AS missing_description
        FROM raw GROUP BY 1 ORDER BY 1""",
    "Overlap between sheets: identical row groups? (0 differing = identical)": f"""
        WITH a AS (SELECT {KEY} k, count(*) n FROM raw
                   WHERE source_sheet = '{SHEETS[0]}' AND InvoiceDate >= DATE '2010-12-01'
                   GROUP BY 1),
             b AS (SELECT {KEY} k, count(*) n FROM raw
                   WHERE source_sheet = '{SHEETS[1]}' AND InvoiceDate < DATE '2010-12-10'
                   GROUP BY 1)
        SELECT (SELECT sum(n) FROM a) AS sheet1_rows, (SELECT sum(n) FROM b) AS sheet2_rows,
               (SELECT count(*) FROM a FULL JOIN b USING (k) WHERE a.n IS DISTINCT FROM b.n)
                   AS differing_groups""",
    "Invoice prefixes": """
        SELECT regexp_extract(Invoice, '^[A-Za-z]*') AS prefix, count(*) AS n_rows,
               sum(Quantity < 0) AS negative_qty, sum(Price < 0) AS negative_price
        FROM d GROUP BY 1 ORDER BY 2 DESC""",
    "Negative quantity without a C/A invoice": """
        SELECT Price = 0 AS price_is_zero, "Customer ID" IS NULL AS no_customer, count(*) AS n_rows
        FROM d WHERE Quantity < 0 AND Invoice NOT LIKE 'C%' AND Invoice NOT LIKE 'A%'
        GROUP BY ALL""",
    "Most common descriptions on those rows": """
        SELECT coalesce(Description, '<blank>') AS description, count(*) AS n_rows FROM d
        WHERE Quantity < 0 AND Invoice NOT LIKE 'C%' AND Invoice NOT LIKE 'A%'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 12""",
    "Stock codes that are not 5 digits (+ optional letters)": """
        SELECT upper(trim(StockCode)) AS code, count(*) AS n_rows, sum(Invoice LIKE 'C%') AS c_rows,
               round(sum(Quantity * Price), 2) AS line_value, mode(Description) AS description
        FROM d WHERE NOT regexp_matches(upper(trim(StockCode)), '^\\d{5}[A-Z]{0,2}$')
        GROUP BY 1 ORDER BY 2 DESC LIMIT 25""",
    "Codes differing only by letter case or spaces": """
        SELECT count(*) AS codes FROM (SELECT upper(trim(StockCode)) FROM d
                                       GROUP BY 1 HAVING count(DISTINCT StockCode) > 1)""",
    "Exact duplicate copies and how often copies sit on adjacent rows": f"""
        WITH x AS (SELECT *, {KEY} k FROM d),
             y AS (SELECT k, source_row,
                          source_row - lag(source_row) OVER (PARTITION BY k ORDER BY source_row) gap
                   FROM x WHERE k IN (SELECT k FROM x GROUP BY k HAVING count(*) > 1))
        SELECT count(*) FILTER (WHERE gap IS NOT NULL) AS extra_copies,
               round(100.0 * count(*) FILTER (WHERE gap = 1)
                     / count(*) FILTER (WHERE gap IS NOT NULL), 1) AS pct_adjacent
        FROM y""",
    "Largest lines by absolute value": """
        SELECT Invoice, StockCode, Description, Quantity, Price,
               round(Quantity * Price, 2) AS line_value, InvoiceDate
        FROM d ORDER BY abs(Quantity * Price) DESC LIMIT 10""",
    "Rows and trading days per month": """
        SELECT strftime(InvoiceDate, '%Y-%m') AS ym, count(*) AS n_rows,
               count(DISTINCT CAST(InvoiceDate AS DATE)) AS trading_days,
               max(CAST(InvoiceDate AS DATE)) AS last_day
        FROM d GROUP BY 1 ORDER BY 1""",
}


def markdown_table(frame) -> str:
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    rule = "|" + "---|" * len(frame.columns)
    rows = [
        "| " + " | ".join("" if v is None else str(v) for v in row) + " |"
        for row in frame.itertuples(index=False)
    ]
    return "\n".join([header, rule, *rows])


def main() -> int:
    if not WORKBOOK.is_file():
        print("Run scripts/download_data.py first.", file=sys.stderr)
        return 1
    raw, notes = read_workbook(WORKBOOK)
    con = duckdb.connect()
    con.register("raw_df", raw)
    con.execute("CREATE TABLE raw AS SELECT * FROM raw_df")
    # d = both sheets with the duplicated 1-9 Dec 2010 taken from the second sheet only
    con.execute(f"""CREATE VIEW d AS SELECT * FROM raw WHERE NOT (source_sheet = '{SHEETS[0]}'
                    AND InvoiceDate >= DATE '2010-12-01')""")
    print("# UCI Online Retail II: raw-data profile\n")
    print(f"Descriptions stored as numbers (read as text): {notes['numeric_descriptions']}\n")
    for title, sql in QUESTIONS.items():
        print(f"## {title}\n")
        print(markdown_table(con.sql(sql).df()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
