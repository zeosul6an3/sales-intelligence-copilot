"""CSV uploads: staging, column mapping, validation and import.

Flow: stage the file -> suggest a column mapping -> validate with the user's
mapping (issues + preview, nothing stored yet) -> import into its own dataset
folder. Uploaded content is only ever parsed as data: values are never
evaluated, and text is never used to build SQL or file paths.
"""

import csv
import io
import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime

import duckdb
import pandas as pd

from sic.data.storage import (
    PRODUCT_RETURN,
    PRODUCT_SALE,
    DatasetNotFound,
    dataset_dir,
    is_ready,
    validate_dataset_id,
    write_dataset,
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ROWS = 2_000_000
PREVIEW_ROWS = 50
EXAMPLES_PER_ISSUE = 5

REQUIRED_FIELDS = ("invoice_id", "invoice_date", "product_id", "quantity", "unit_price")
OPTIONAL_FIELDS = ("product_name", "customer_id", "country", "currency")
FIELD_DESCRIPTIONS = {
    "invoice_id": "Order or invoice number; lines with the same value form one order.",
    "invoice_date": "Date (and optionally time) of the order, e.g. 2024-03-15 or 15/03/2024.",
    "product_id": "Product code or SKU.",
    "quantity": "Units on the line. Negative quantities are treated as returns.",
    "unit_price": "Price per unit in the dataset's currency (positive number).",
    "product_name": "Product description (optional).",
    "customer_id": "Customer identifier (optional; needed for customer counts).",
    "country": "Customer country (optional).",
    "currency": "Currency code per line (optional; must be a single currency).",
}
# Header names we recognise automatically (compared case- and punctuation-insensitively).
SYNONYMS = {
    "invoice_id": [
        "invoice",
        "invoiceno",
        "invoiceid",
        "invoicenumber",
        "orderid",
        "order",
        "ordernumber",
        "orderno",
        "transactionid",
    ],
    "invoice_date": [
        "invoicedate",
        "date",
        "orderdate",
        "transactiondate",
        "datetime",
        "timestamp",
        "saledate",
    ],
    "product_id": ["stockcode", "productid", "productcode", "sku", "itemcode", "itemid", "article"],
    "quantity": ["quantity", "qty", "units", "unitssold", "quantitysold"],
    "unit_price": ["price", "unitprice", "priceperunit", "itemprice", "sellingprice"],
    "product_name": [
        "description",
        "productname",
        "product",
        "itemname",
        "itemdescription",
        "name",
    ],
    "customer_id": ["customerid", "customer", "customerno", "customernumber", "clientid"],
    "country": ["country", "customercountry", "region"],
    "currency": ["currency", "currencycode"],
}
TEMPLATE_CSV = (
    "invoice_id,invoice_date,product_id,product_name,quantity,unit_price,customer_id,country\n"
    "1001,2024-01-08 10:15,SKU-001,Blue mug,6,4.50,C-17,United Kingdom\n"
    "1001,2024-01-08 10:15,SKU-002,Tea towel,12,2.25,C-17,United Kingdom\n"
    "1002,2024-01-09 14:02,SKU-001,Blue mug,2,4.50,,France\n"
    "R1003,2024-01-12 09:30,SKU-002,Tea towel,-3,2.25,C-17,United Kingdom\n"
)
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_THOUSANDS = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")


class UploadError(ValueError):
    """A problem the user can fix (shown as a validation message)."""


def _normalise_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def suggest_mapping(columns: list[str]) -> dict[str, str | None]:
    normalised = {_normalise_header(c): c for c in columns}
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
        candidates = [_normalise_header(field), *SYNONYMS[field]]
        match = next((normalised[c] for c in candidates if c in normalised), None)
        mapping[field] = match if match not in used else None
        if match:
            used.add(match)
    return mapping


def _upload_dir(upload_id: str):
    validate_dataset_id(upload_id)
    if not upload_id.startswith("upload-"):
        raise DatasetNotFound(upload_id)
    return dataset_dir(upload_id)


def _decode(raw: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UploadError("The file is not readable text (tried UTF-8 and Windows-1252).")


def _read_csv(text: str, nrows: int | None = None) -> pd.DataFrame:
    try:
        dialect = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    try:
        frame = pd.read_csv(
            io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False, nrows=nrows
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise UploadError(f"The file could not be read as CSV: {exc}") from exc
    frame.columns = [str(c).strip() for c in frame.columns]
    if frame.columns.duplicated().any():
        raise UploadError("The header row contains duplicate column names.")
    return frame


def stage(raw: bytes, filename: str) -> dict:
    """Save an uploaded file under a new upload ID and describe its columns."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise UploadError(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not raw.strip():
        raise UploadError("The file is empty.")
    text, encoding = _decode(raw)
    sample = _read_csv(text, nrows=20)
    if sample.empty or len(sample.columns) < len(REQUIRED_FIELDS):
        raise UploadError(
            f"Found {len(sample.columns)} column(s); at least {len(REQUIRED_FIELDS)} are needed."
        )
    upload_id = f"upload-{secrets.token_hex(6)}"
    folder = _upload_dir(upload_id)
    folder.mkdir(parents=True)
    (folder / "original.csv").write_text(text, encoding="utf-8")
    display_name = re.sub(r"[^\w .()-]", "_", filename)[:120] or "upload.csv"
    (folder / "staging.txt").write_text(display_name, encoding="utf-8")
    return {
        "upload_id": upload_id,
        "filename": display_name,
        "encoding": encoding,
        "columns": list(sample.columns),
        "sample_rows": sample.head(10).to_dict(orient="records"),
        "suggested_mapping": suggest_mapping(list(sample.columns)),
        "fields": {
            "required": list(REQUIRED_FIELDS),
            "optional": list(OPTIONAL_FIELDS),
            "descriptions": FIELD_DESCRIPTIONS,
        },
    }


@dataclass
class Options:
    mapping: dict[str, str | None]
    currency: str
    day_first: bool = False
    name: str | None = None


def _parse_number(series: pd.Series) -> pd.Series:
    cleaned = series.str.strip().str.replace(r"[£$€\s]", "", regex=True)
    cleaned = cleaned.where(~cleaned.str.match(_THOUSANDS), cleaned.str.replace(",", ""))
    return pd.to_numeric(cleaned, errors="coerce")


_ISO_DATE = r"^\d{4}-\d{2}-\d{2}"


_NUMERIC_DATE = r"^(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}"


def _parse_dates(values: pd.Series, day_first: bool) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Parse dates. Returns (dates, ambiguous mask, wrong-order mask).

    ISO dates (YYYY-MM-DD...) are unambiguous and always read as ISO. The
    day-first setting applies only to other formats such as 05/02/2024.
    "Wrong order" marks values that are only valid in the other order (e.g.
    25/02/2024 with month-first selected), which means the setting is wrong.
    """
    iso = values.str.match(_ISO_DATE)
    dates = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    dates[iso] = pd.to_datetime(values[iso], errors="coerce", format="ISO8601")
    other = ~iso
    chosen = pd.to_datetime(values[other], errors="coerce", dayfirst=day_first, format="mixed")
    flipped = pd.to_datetime(values[other], errors="coerce", dayfirst=not day_first, format="mixed")
    dates[other] = chosen
    ambiguous = pd.Series(False, index=values.index)
    ambiguous[other] = chosen.notna() & flipped.notna() & (chosen != flipped)

    parts = values.str.extract(_NUMERIC_DATE).astype(float)
    month_part = parts[0] if not day_first else parts[1]
    wrong_order = (month_part > 12).fillna(False)
    return dates, ambiguous, wrong_order


def _examples(frame: pd.DataFrame, mask: pd.Series, column: str | None) -> list[dict]:
    rows = frame.loc[mask].head(EXAMPLES_PER_ISSUE)
    return [
        {"row": int(r["_row"]), "value": (r[column] if column else None)}
        for _, r in rows.iterrows()
    ]


def _parse(upload_id: str, options: Options) -> tuple[pd.DataFrame, list[dict], dict]:
    folder = _upload_dir(upload_id)
    source = folder / "original.csv"
    if not source.is_file():
        raise DatasetNotFound(upload_id)
    frame = _read_csv(source.read_text(encoding="utf-8"))
    if len(frame) > MAX_ROWS:
        raise UploadError(f"The file has {len(frame):,} rows; the limit is {MAX_ROWS:,}.")

    if not _CURRENCY.match(options.currency or ""):
        raise UploadError("Choose the dataset's currency as a 3-letter code, e.g. GBP or EUR.")
    mapping = {k: v for k, v in options.mapping.items() if v}
    unknown = [f for f in mapping if f not in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS)]
    if unknown:
        raise UploadError(f"Unknown field(s) in mapping: {unknown}")
    missing = [f for f in REQUIRED_FIELDS if f not in mapping]
    if missing:
        raise UploadError(f"Map a column to each required field. Missing: {', '.join(missing)}.")
    absent = [c for c in mapping.values() if c not in frame.columns]
    if absent:
        raise UploadError(f"Mapped column(s) not found in the file: {absent}")
    if len(set(mapping.values())) != len(mapping):
        raise UploadError("Each column can be mapped to only one field.")

    frame.insert(0, "_row", range(2, len(frame) + 2))  # spreadsheet-style row numbers
    issues: list[dict] = []

    def issue(code, severity, message, mask=None, column=None):
        count = int(mask.sum()) if mask is not None else None
        if mask is not None and count == 0:
            return
        issues.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "rows": count,
                "examples": _examples(frame, mask, column) if mask is not None else [],
            }
        )

    col = mapping
    text = {f: frame[col[f]].str.strip() if f in col else None for f in col}

    dates, ambiguous, wrong_order = _parse_dates(text["invoice_date"], options.day_first)
    order = "day first" if options.day_first else "month first"
    issue(
        "date_order_conflict",
        "warning",
        f"Dates that are only valid in the opposite day/month order to the selected "
        f"setting ({order}). The file probably uses the other order: change the setting.",
        wrong_order,
        col["invoice_date"],
    )
    issue(
        "ambiguous_dates",
        "warning",
        "Dates that read differently as day/month and month/day. Check the date-order "
        f"setting (currently {'day first' if options.day_first else 'month first'}).",
        ambiguous,
        col["invoice_date"],
    )
    quantity = _parse_number(frame[col["quantity"]])
    price = _parse_number(frame[col["unit_price"]])

    bad_date = dates.isna()
    bad_qty = quantity.isna()
    bad_price = price.isna()
    no_invoice = text["invoice_id"] == ""
    no_product = text["product_id"] == ""
    issue(
        "unparseable_date",
        "error",
        "Dates that could not be read; rows excluded.",
        bad_date,
        col["invoice_date"],
    )
    issue(
        "non_numeric_quantity",
        "error",
        "Quantities that are not numbers; rows excluded.",
        bad_qty,
        col["quantity"],
    )
    issue(
        "non_numeric_price",
        "error",
        "Prices that are not numbers (use a dot for decimals); rows excluded.",
        bad_price,
        col["unit_price"],
    )
    issue(
        "missing_invoice_id",
        "error",
        "Missing invoice ID; rows excluded.",
        no_invoice,
        col["invoice_id"],
    )
    issue(
        "missing_product_id",
        "error",
        "Missing product ID; rows excluded.",
        no_product,
        col["product_id"],
    )
    invalid = bad_date | bad_qty | bad_price | no_invoice | no_product

    if "currency" in col:
        values = sorted(set(text["currency"][text["currency"] != ""].str.upper()))
        if len(values) > 1:
            raise UploadError(
                f"The file mixes currencies ({', '.join(values)}). Upload one currency per dataset."
            )
        if values and values[0] != options.currency:
            raise UploadError(
                f"The file's currency column says {values[0]}, but {options.currency} was selected."
            )

    valid = ~invalid
    issue(
        "negative_price",
        "warning",
        "Negative prices; rows excluded from sales metrics.",
        valid & (price < 0),
        col["unit_price"],
    )
    issue(
        "zero_price",
        "info",
        "Zero prices; excluded from sales and units.",
        valid & (price == 0),
        col["unit_price"],
    )
    issue(
        "zero_quantity",
        "info",
        "Zero quantities; excluded from metrics.",
        valid & (quantity == 0),
        col["quantity"],
    )
    issue(
        "returns",
        "info",
        "Negative quantities, treated as returns.",
        valid & (quantity < 0) & (price > 0),
        col["quantity"],
    )
    if "customer_id" in col:
        issue(
            "missing_customer",
            "info",
            "No customer ID; counted in revenue but not in customer counts.",
            valid & (text["customer_id"] == ""),
            col["customer_id"],
        )
    else:
        issue(
            "no_customer_column",
            "info",
            "No customer column mapped; customer counts will be unavailable.",
        )

    parsed = pd.DataFrame(
        {
            "line_id": range(1, len(frame) + 1),
            "source_row": frame["_row"],
            "invoice_id": text["invoice_id"],
            "invoice_ts": dates,
            "product_id": text["product_id"].str.upper(),
            "raw_description": text["product_name"].replace("", None)
            if "product_name" in col
            else None,
            "quantity": quantity,
            "unit_price": price,
            "customer_id": text["customer_id"].replace("", None) if "customer_id" in col else None,
            "country": text["country"].replace("", "Unspecified")
            if "country" in col
            else "Unspecified",
            "invalid": invalid,
        }
    )
    info = {"rows_total": len(frame), "rows_invalid": int(invalid.sum())}
    return parsed, issues, info


UPLOAD_RULES = (
    ("invalid_row", "invalid", "Excluded: a required value is missing or unreadable."),
    ("zero_quantity", "quantity = 0", "Excluded from metrics."),
    ("negative_price", "unit_price < 0", "Excluded from sales metrics."),
    ("zero_price_line", "unit_price = 0", "Excluded from sales and units."),
    (PRODUCT_RETURN, "quantity < 0", "Counted in returns."),
    (PRODUCT_SALE, "quantity > 0", "Counted in gross sales, units and orders."),
)


def _classify(con: duckdb.DuckDBPyConnection, parsed: pd.DataFrame) -> None:
    con.register("parsed_df", parsed)
    whens = "\n".join(f"WHEN {cond} THEN '{lt}'" for lt, cond, _ in UPLOAD_RULES)
    con.execute(f"""
        CREATE OR REPLACE TABLE pre AS
        SELECT line_id, CAST(NULL AS VARCHAR) AS source_sheet, source_row, invoice_id,
               invoice_ts, CAST(invoice_ts AS DATE) AS invoice_date, product_id,
               -- Optional columns may be entirely empty; declare them as text explicitly
               CAST(raw_description AS VARCHAR) AS raw_description, quantity, unit_price,
               quantity * unit_price AS line_value, CAST(customer_id AS VARCHAR) AS customer_id,
               CAST(country AS VARCHAR) AS country, CASE {whens} END AS line_type
        FROM parsed_df
    """)
    # Unusual lines: same relative rule as the built-in data (4x the 99.99th percentile).
    threshold = con.execute(f"""
        SELECT 4 * quantile_cont(abs(line_value), 0.9999) FROM pre
        WHERE line_type IN ('{PRODUCT_SALE}', '{PRODUCT_RETURN}')
    """).fetchone()[0]
    con.execute(
        f"""
        CREATE OR REPLACE TABLE classified AS
        SELECT *, coalesce(line_type IN ('{PRODUCT_SALE}', '{PRODUCT_RETURN}')
                           AND abs(line_value) >= ?, false) AS is_unusual
        FROM pre
        """,
        [threshold],  # NULL when there are no product lines -> nothing flagged
    )


def _line_type_counts(con) -> list[dict]:
    return [
        {"line_type": r[0], "rows": r[1], "value": round(r[2] or 0, 2)}
        for r in con.execute(
            "SELECT line_type, count(*), sum(line_value) FROM classified GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()
    ]


def validate(upload_id: str, options: Options) -> dict:
    """Check the file with the given mapping. Nothing is stored."""
    parsed, issues, info = _parse(upload_id, options)
    con = duckdb.connect()
    _classify(con, parsed)
    first, last = con.execute(
        "SELECT min(invoice_date), max(invoice_date) FROM classified "
        "WHERE line_type <> 'invalid_row'"
    ).fetchone()
    dupes = con.execute("""
        SELECT count(*) - count(DISTINCT (invoice_id, product_id, raw_description, quantity,
               unit_price, invoice_ts, customer_id, country))
        FROM classified WHERE line_type <> 'invalid_row'
    """).fetchone()[0]
    if dupes:
        issues.append(
            {
                "code": "exact_duplicates",
                "severity": "info",
                "rows": int(dupes),
                "message": "Rows identical to another row; kept and flagged.",
                "examples": [],
            }
        )
    preview = con.execute(f"""
        SELECT source_row, invoice_id, CAST(invoice_ts AS VARCHAR) AS invoice_ts, product_id,
               raw_description AS product_name, quantity, unit_price, customer_id, country,
               line_type
        FROM classified ORDER BY line_id LIMIT {PREVIEW_ROWS}
    """).df()
    usable = info["rows_total"] - info["rows_invalid"]
    result = {
        "upload_id": upload_id,
        **info,
        "rows_usable": usable,
        "first_date": str(first) if first else None,
        "last_date": str(last) if last else None,
        "line_types": _line_type_counts(con),
        "issues": issues,
        "can_import": usable > 0,
        "preview": preview.astype(object).where(preview.notna(), None).to_dict(orient="records"),
    }
    con.close()
    return result


def import_upload(upload_id: str, options: Options) -> dict:
    """Validate, classify and store the upload as its own dataset."""
    if is_ready(upload_id):
        raise UploadError("This upload has already been imported.")
    parsed, issues, info = _parse(upload_id, options)
    if info["rows_total"] == info["rows_invalid"]:
        raise UploadError("No usable rows: every row has a missing or unreadable required value.")
    folder = _upload_dir(upload_id)
    filename = (folder / "staging.txt").read_text(encoding="utf-8")
    con = duckdb.connect()
    _classify(con, parsed)
    # Invalid rows are counted in the quality report but not stored in `lines`.
    con.execute("DELETE FROM classified WHERE line_type = 'invalid_row'")
    first, last, lines, products, customers, countries = con.execute(f"""
        SELECT min(invoice_date), max(invoice_date), count(*),
               count(DISTINCT product_id) FILTER (WHERE line_type = '{PRODUCT_SALE}'),
               count(DISTINCT customer_id) FILTER (WHERE line_type = '{PRODUCT_SALE}'),
               count(DISTINCT country) FROM classified
    """).fetchone()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    metadata = {
        "id": upload_id,
        "name": (options.name or filename)[:120],
        "kind": "upload",
        "description": f"Uploaded from {filename}.",
        "currency": options.currency,
        "currency_symbol": {"GBP": "£", "EUR": "€", "USD": "$"}.get(options.currency, ""),
        "first_date": str(first),
        "last_date": str(last),
        "lines": lines,
        "products": products,
        "customers": customers if options.mapping.get("customer_id") else None,
        "countries": countries,
        "source_filename": filename,
        "mapping": {k: v for k, v in options.mapping.items() if v},
        "day_first": options.day_first,
        "built_at_utc": now,
    }
    by_type = {r["line_type"]: r for r in _line_type_counts(con)}
    quality = {
        "dataset_id": upload_id,
        "generated_at_utc": now,
        "source": {"file": filename, "encoding_note": "Stored as UTF-8."},
        "row_flow": {
            "rows_read": info["rows_total"],
            "rows_invalid_excluded": info["rows_invalid"],
            "rows_kept": info["rows_total"] - info["rows_invalid"],
            "reconciles": info["rows_total"]
            == info["rows_invalid"] + sum(r["rows"] for r in by_type.values()),
        },
        "rules": [
            {
                "line_type": lt,
                "condition": cond,
                "treatment": treatment,
                "rows": info["rows_invalid"]
                if lt == "invalid_row"
                else by_type.get(lt, {}).get("rows", 0),
                "value": by_type.get(lt, {}).get("value", 0.0),
                "evidence": "Upload rule.",
            }
            for lt, cond, treatment in UPLOAD_RULES
        ],
        "issues": issues,
        "coverage": {"first_date": str(first), "last_date": str(last), "notes": []},
    }
    write_dataset(con, upload_id, metadata, quality)
    con.close()
    (folder / "staging.txt").unlink(missing_ok=True)
    return metadata


def delete_upload(upload_id: str) -> None:
    folder = _upload_dir(upload_id)
    if not folder.is_dir():
        raise DatasetNotFound(upload_id)
    shutil.rmtree(folder)
