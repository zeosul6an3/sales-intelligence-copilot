"""Cleaning pipeline for the built-in UCI Online Retail II dataset.

Every input row is kept and given exactly one `line_type`. The rules below were
derived from inspecting both sheets (see docs/data_cleaning.md); each rule's
evidence is stored with it so the quality report explains itself. Only two
line types feed the business metrics: product_sale and product_return.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
from python_calamine import CalamineWorkbook

from sic.data.storage import BUILTIN_ID, PRODUCT_RETURN, PRODUCT_SALE, write_dataset

SHEETS = ("Year 2009-2010", "Year 2010-2011")
UNUSUAL_LINE_VALUE = 10_000.0  # £; about 4x the 99.99th percentile of product line values

SHIPPING_CODES = ("POST", "DOT", "C2", "C3")
FEE_CODES = ("AMAZONFEE", "BANK CHARGES", "CRUK")
MANUAL_CODES = ("M", "ADJUST", "ADJUST2")


@dataclass(frozen=True)
class Rule:
    line_type: str
    condition: str  # SQL over the normalised columns; rules are applied in order
    treatment: str
    evidence: str


def _codes(codes: tuple[str, ...]) -> str:
    return ", ".join(f"'{c}'" for c in codes)


RULES = (
    Rule(
        "bad_debt_adjustment",
        "invoice_id LIKE 'A%'",
        "Excluded from sales metrics; reported under other lines.",
        "6 'Adjust bad debt' lines (stock code B), ±£11k-£54k, no customer.",
    ),
    Rule(
        "shipping",
        f"product_id IN ({_codes(SHIPPING_CODES)})",
        "Excluded from product revenue; reported under other lines.",
        "POSTAGE, DOTCOM POSTAGE and CARRIAGE codes; not merchandise.",
    ),
    Rule(
        "fees_commission",
        f"product_id IN ({_codes(FEE_CODES)})",
        "Excluded from product revenue; reported under other lines.",
        "AMAZON FEE, Bank Charges and CRUK Commission lines.",
    ),
    Rule(
        "discount",
        "product_id = 'D'",
        "Excluded from product revenue; reported under other lines.",
        "'Discount' lines, almost all on cancellation invoices.",
    ),
    Rule(
        "manual_adjustment",
        f"product_id IN ({_codes(MANUAL_CODES)})",
        "Excluded from product revenue; reported separately (user decision).",
        "Mix of manual charges (+£349k) and credits (-£425k) that cannot be tied to a "
        "product; e.g. a £38,970 manual credit corrected a mispriced picnic-basket sale.",
    ),
    Rule(
        "samples",
        "product_id = 'S'",
        "Excluded from product revenue; reported under other lines.",
        "'SAMPLES' lines, mostly credits.",
    ),
    Rule(
        "gift_voucher",
        "product_id LIKE 'GIFT%'",
        "Excluded from product revenue; reported under other lines.",
        "Dotcomgiftshop gift vouchers are stored value, not merchandise.",
    ),
    Rule(
        "test",
        "product_id LIKE 'TEST%'",
        "Excluded from all metrics.",
        "Descriptions say 'This is a test product.'",
    ),
    Rule(
        PRODUCT_RETURN,
        "invoice_id LIKE 'C%' AND quantity < 0",
        "Counted in returns (cancellations and returns cannot be told apart).",
        "UCI documents C-prefixed invoices as cancellations; all have negative quantity.",
    ),
    Rule(
        "zero_value_stock_note",
        "quantity < 0 AND unit_price = 0",
        "Excluded from sales and units; contributes £0 in any case.",
        "Every negative-quantity line without a C invoice has price £0 and no customer; "
        "descriptions are warehouse notes ('damages', 'check', 'missing', '?') or blank.",
    ),
    Rule(
        "zero_price_line",
        "unit_price = 0",
        "Excluded from sales and units; contributes £0.",
        "Positive quantity at price £0, 98% without a customer.",
    ),
    Rule(
        PRODUCT_SALE,
        "quantity > 0 AND unit_price > 0",
        "Counted in gross sales, units and orders.",
        "Ordinary product lines.",
    ),
)
UNCLASSIFIED = "unclassified"  # anything no rule matches; excluded and reported


def classification_sql() -> str:
    whens = "\n".join(f"WHEN {r.condition} THEN '{r.line_type}'" for r in RULES)
    return f"CASE {whens} ELSE '{UNCLASSIFIED}' END"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_workbook(path: Path) -> tuple[pd.DataFrame, dict]:
    """Read both sheets as-is, keeping sheet name and spreadsheet row number."""
    names = CalamineWorkbook.from_path(str(path)).sheet_names
    missing = [s for s in SHEETS if s not in names]
    if missing:
        raise ValueError(f"Workbook is missing expected sheets: {missing}")
    frames, numeric_descriptions = [], 0
    for sheet in SHEETS:
        frame = pd.read_excel(
            path, sheet_name=sheet, engine="calamine", dtype={"Invoice": str, "StockCode": str}
        )
        description = frame["Description"]
        is_text = description.map(lambda v: isinstance(v, str))
        numeric = description.notna() & ~is_text
        numeric_descriptions += int(numeric.sum())
        frame["Description"] = description.where(~numeric, description.astype(str)).where(
            description.notna(), None
        )
        frame["source_sheet"] = sheet
        frame["source_row"] = range(2, len(frame) + 2)  # row 1 is the header
        frames.append(frame)
    return pd.concat(frames, ignore_index=True), {"numeric_descriptions": numeric_descriptions}


def build(workbook: Path) -> dict:
    """Clean and classify the workbook and store it as the built-in dataset."""
    raw, read_notes = read_workbook(workbook)
    source = {"file": workbook.name, "sha256": file_sha256(workbook)}
    return build_from_frame(raw, read_notes, source)


def build_from_frame(raw: pd.DataFrame, read_notes: dict, source: dict) -> dict:
    """Apply the cleaning rules to rows read from the workbook (also used by tests)."""
    con = duckdb.connect()
    con.register("raw_df", raw)
    con.execute("CREATE TABLE raw AS SELECT * FROM raw_df")

    sheets = con.execute("""
        SELECT source_sheet, count(*), min(InvoiceDate), max(InvoiceDate)
        FROM raw GROUP BY 1 ORDER BY 1
    """).fetchall()

    # 1. Sheet overlap: both sheets contain 1-9 Dec 2010. Confirm the copies are
    #    identical (null-safe), then keep the second sheet's copy only.
    overlap_start = con.execute(
        "SELECT min(InvoiceDate) FROM raw WHERE source_sheet = ?", [SHEETS[1]]
    ).fetchone()[0]
    overlap_start_day = pd.Timestamp(overlap_start).normalize()
    row_key = """concat_ws('|', Invoice, StockCode, coalesce(Description, '<null>'), Quantity,
                 InvoiceDate, Price, coalesce(CAST("Customer ID" AS VARCHAR), '<null>'), Country)"""
    differing = con.execute(
        f"""
        WITH a AS (SELECT {row_key} k, count(*) n FROM raw
                   WHERE source_sheet = ? AND InvoiceDate >= ? GROUP BY 1),
             b AS (SELECT {row_key} k, count(*) n FROM raw
                   WHERE source_sheet = ? AND InvoiceDate <= (SELECT max(InvoiceDate) FROM raw
                                                             WHERE source_sheet = ?) GROUP BY 1)
        SELECT count(*) FROM a FULL OUTER JOIN b USING (k) WHERE a.n IS DISTINCT FROM b.n
    """,
        [SHEETS[0], overlap_start_day, SHEETS[1], SHEETS[0]],
    ).fetchone()[0]
    if differing:
        raise ValueError(
            f"The two sheets' overlapping period differs in {differing} row groups; "
            "the overlap rule assumes identical copies. Inspect before continuing."
        )
    overlap_rows = con.execute(
        "SELECT count(*) FROM raw WHERE source_sheet = ? AND InvoiceDate >= ?",
        [SHEETS[0], overlap_start_day],
    ).fetchone()[0]

    # 2. Normalise identifiers and text, then classify.
    con.execute(f"""
        CREATE TABLE normalised AS
        SELECT row_number() OVER (ORDER BY source_sheet, source_row) AS line_id,
               source_sheet, source_row,
               trim(Invoice) AS invoice_id,
               InvoiceDate AS invoice_ts, CAST(InvoiceDate AS DATE) AS invoice_date,
               upper(trim(StockCode)) AS product_id, StockCode AS original_code,
               nullif(trim(Description), '') AS raw_description,
               CAST(Quantity AS DOUBLE) AS quantity, CAST(Price AS DOUBLE) AS unit_price,
               CAST(Quantity AS DOUBLE) * CAST(Price AS DOUBLE) AS line_value,
               CAST(CAST("Customer ID" AS BIGINT) AS VARCHAR) AS customer_id,
               Country AS country
        FROM raw
        WHERE NOT (source_sheet = '{SHEETS[0]}' AND InvoiceDate >= TIMESTAMP '{overlap_start_day}')
    """)
    con.execute(f"""
        CREATE TABLE classified AS
        SELECT line_id, source_sheet, source_row, invoice_id, invoice_ts, invoice_date,
               product_id, raw_description, quantity, unit_price, line_value, customer_id,
               country, line_type,
               line_type IN ('{PRODUCT_SALE}', '{PRODUCT_RETURN}')
                   AND abs(line_value) >= {UNUSUAL_LINE_VALUE} AS is_unusual
        FROM (SELECT *, {classification_sql()} AS line_type FROM normalised)
    """)

    quality = quality_report(con, source, sheets, overlap_rows, read_notes)
    metadata = dataset_metadata(con, source)
    write_dataset(con, BUILTIN_ID, metadata, quality)
    con.close()
    return quality


def quality_report(con, source: dict, sheets, overlap_rows: int, read_notes: dict) -> dict:
    total_read = sum(s[1] for s in sheets)
    kept = con.execute("SELECT count(*) FROM classified").fetchone()[0]
    by_type = {
        row[0]: {"rows": row[1], "value": round(row[2], 2)}
        for row in con.execute(
            "SELECT line_type, count(*), sum(line_value) FROM classified GROUP BY 1"
        ).fetchall()
    }
    rules = [
        {
            "line_type": r.line_type,
            "condition": r.condition,
            "treatment": r.treatment,
            "evidence": r.evidence,
            **by_type.get(r.line_type, {"rows": 0, "value": 0.0}),
        }
        for r in (*RULES, Rule(UNCLASSIFIED, "no rule matched", "Excluded; reported.", "-"))
    ]

    def one(sql: str) -> tuple:
        return con.execute(sql).fetchone()

    case_variants = one("""
        SELECT count(*) FROM (SELECT product_id FROM normalised
                              GROUP BY 1 HAVING count(DISTINCT original_code) > 1)
    """)[0]
    missing_customer = one(f"""
        SELECT count(*), coalesce(sum(line_value), 0) FROM classified
        WHERE line_type = '{PRODUCT_SALE}' AND customer_id IS NULL
    """)
    unusual = con.execute("""
        SELECT invoice_id, product_id, raw_description, quantity, unit_price,
               round(line_value, 2), invoice_ts
        FROM classified WHERE is_unusual ORDER BY abs(line_value) DESC
    """).fetchall()
    first_date, last_date, last_ts = one(
        "SELECT min(invoice_date), max(invoice_date), max(invoice_ts) FROM classified"
    )

    return {
        "dataset_id": BUILTIN_ID,
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "source": {
            **source,
            "sheets": [
                {"name": s[0], "rows": s[1], "first_ts": str(s[2]), "last_ts": str(s[3])}
                for s in sheets
            ],
        },
        "row_flow": {
            "rows_read": total_read,
            "sheet_overlap_removed": overlap_rows,
            "sheet_overlap_note": (
                "1-9 Dec 2010 appears identically in both sheets; the first sheet's copy "
                "was dropped after a null-safe row-by-row comparison found no differences."
            ),
            "rows_kept": kept,
            "rows_by_line_type_total": sum(t["rows"] for t in by_type.values()),
            "reconciles": total_read - overlap_rows
            == kept
            == sum(t["rows"] for t in by_type.values()),
        },
        "rules": rules,
        "flags": {
            "missing_customer_id_on_product_sales": {
                "rows": missing_customer[0],
                "value": round(missing_customer[1], 2),
                "treatment": "Kept in revenue; excluded only from customer counts.",
            },
            "missing_description": {
                "rows": one("SELECT count(*) FROM classified WHERE raw_description IS NULL")[0],
                "treatment": "Kept; product name taken from other lines with the same code.",
            },
            "numeric_descriptions_read_as_text": read_notes["numeric_descriptions"],
            "product_codes_differing_only_by_case_or_spaces": {
                "codes": case_variants,
                "treatment": "Codes upper-cased and trimmed; variants had identical descriptions.",
            },
            "unusual_lines": {
                "rule": f"Product sale/return lines with |value| >= £{UNUSUAL_LINE_VALUE:,.0f}",
                "treatment": "Kept (user decision); flagged for charts and reports.",
                "lines": [
                    {
                        "invoice_id": u[0],
                        "product_id": u[1],
                        "description": u[2],
                        "quantity": u[3],
                        "unit_price": u[4],
                        "line_value": u[5],
                        "invoice_ts": str(u[6]),
                    }
                    for u in unusual
                ],
            },
        },
        "coverage": {
            "first_date": str(first_date),
            "last_date": str(last_date),
            "last_timestamp": str(last_ts),
            "notes": [
                "December 2011 is partial (data ends on 9 Dec 2011).",
                "No trading recorded 24 Dec-3 Jan in either year (closures, not missing data).",
                "Almost no Saturday trading.",
            ],
        },
    }


def dataset_metadata(con, source: dict) -> dict:
    first, last, lines, products, customers, countries = con.execute(f"""
        SELECT min(invoice_date), max(invoice_date), count(*),
               count(DISTINCT product_id) FILTER (WHERE line_type = '{PRODUCT_SALE}'),
               count(DISTINCT customer_id) FILTER (WHERE line_type = '{PRODUCT_SALE}'),
               count(DISTINCT country)
        FROM classified
    """).fetchone()
    return {
        "id": BUILTIN_ID,
        "name": "UCI Online Retail II (built-in example)",
        "kind": "builtin",
        "description": (
            "Historical transactions of a UK-based online gift-ware retailer, "
            "1 Dec 2009 to 9 Dec 2011, many of whose customers are wholesalers."
        ),
        "currency": "GBP",
        "currency_symbol": "£",
        "first_date": str(first),
        "last_date": str(last),
        "lines": lines,
        "products": products,
        "customers": customers,
        "countries": countries,
        "source_sha256": source["sha256"],
        "attribution": (
            "Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. "
            "https://doi.org/10.24432/C5CG6D. Licensed under CC BY 4.0."
        ),
        "built_at_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
    }
