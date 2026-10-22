"""Per-dataset storage.

Every dataset (the built-in UCI data and each upload) lives in its own folder
with its own DuckDB file. Queries open exactly one dataset's file, so one
dataset can never read another's rows. Dataset IDs are validated against a
strict pattern before any path is built from them.

Folder contents:
    warehouse.duckdb     table `lines`: one cleaned, classified row per input row
    lines.parquet        the same table, for inspection with other tools
    metadata.json        name, source, currency, row counts, date range
    quality_report.json  every cleaning rule with affected row counts
"""

import json
import os
import re
from pathlib import Path

import duckdb

from sic.config import DATA_DIR

BUILTIN_ID = "uci"
_DATASET_ID = re.compile(r"^(uci|upload-[0-9a-f]{12})$")

# Columns of the canonical `lines` table, shared by every dataset.
CANONICAL_COLUMNS = """
    line_id BIGINT, source_sheet VARCHAR, source_row BIGINT,
    invoice_id VARCHAR, invoice_ts TIMESTAMP, invoice_date DATE,
    product_id VARCHAR, raw_description VARCHAR,
    quantity DOUBLE, unit_price DOUBLE, line_value DOUBLE,
    customer_id VARCHAR, country VARCHAR, line_type VARCHAR, is_unusual BOOLEAN
"""

# Line types that feed the business metrics. Everything else is reported
# separately as "other lines" and never mixed into product revenue.
PRODUCT_SALE = "product_sale"
PRODUCT_RETURN = "product_return"


class DatasetNotFound(Exception):
    pass


def validate_dataset_id(dataset_id: str) -> str:
    if not _DATASET_ID.match(dataset_id):
        raise DatasetNotFound(dataset_id)
    return dataset_id


def dataset_dir(dataset_id: str) -> Path:
    validate_dataset_id(dataset_id)
    if dataset_id == BUILTIN_ID:
        return DATA_DIR / "processed" / BUILTIN_ID
    return DATA_DIR / "uploads" / dataset_id


def warehouse_path(dataset_id: str) -> Path:
    return dataset_dir(dataset_id) / "warehouse.duckdb"


def is_ready(dataset_id: str) -> bool:
    folder = dataset_dir(dataset_id)
    return (folder / "warehouse.duckdb").is_file() and (folder / "metadata.json").is_file()


def connect(dataset_id: str) -> duckdb.DuckDBPyConnection:
    """Open one dataset's warehouse read-only. Raises DatasetNotFound if absent."""
    if not is_ready(dataset_id):
        raise DatasetNotFound(dataset_id)
    return duckdb.connect(str(warehouse_path(dataset_id)), read_only=True)


def read_json(dataset_id: str, name: str) -> dict:
    path = dataset_dir(dataset_id) / name
    if not path.is_file():
        raise DatasetNotFound(dataset_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_datasets() -> list[dict]:
    candidates = [BUILTIN_ID]
    uploads = DATA_DIR / "uploads"
    if uploads.is_dir():
        candidates += sorted(p.name for p in uploads.iterdir() if _DATASET_ID.match(p.name))
    return [read_json(d, "metadata.json") for d in candidates if is_ready(d)]


def write_dataset(
    con: duckdb.DuckDBPyConnection, dataset_id: str, metadata: dict, quality: dict
) -> None:
    """Persist the `classified` table of `con` as this dataset's warehouse.

    Adds the canonical product name and the duplicate flag, writes to temporary
    files and renames them into place, so readers never see a half-written file.
    """
    folder = dataset_dir(dataset_id)
    folder.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        CREATE OR REPLACE TABLE final AS
        WITH names AS (
            -- Display name: the most frequent description on the product's sale lines.
            -- Descriptions on other lines (e.g. stock notes such as "damages") only
            -- count when a product has no sale lines at all.
            SELECT product_id, arg_max(raw_description, rank_key) AS product_name
            FROM (
                SELECT product_id, raw_description,
                       count(*) FILTER (WHERE line_type = '{PRODUCT_SALE}') * 1000000
                           + count(*) AS rank_key
                FROM classified
                WHERE raw_description IS NOT NULL
                GROUP BY ALL
            )
            GROUP BY product_id
        )
        SELECT c.*, coalesce(names.product_name, c.product_id) AS product_name,
               row_number() OVER (
                   PARTITION BY invoice_id, product_id, raw_description, quantity,
                                unit_price, invoice_ts, customer_id, country
                   ORDER BY line_id
               ) > 1 AS is_duplicate
        FROM classified c LEFT JOIN names USING (product_id)
        ORDER BY line_id
    """)

    tmp_db = folder / "warehouse.duckdb.tmp"
    tmp_db.unlink(missing_ok=True)
    con.execute(f"ATTACH '{tmp_db.as_posix()}' AS out")
    con.execute("CREATE TABLE out.lines AS SELECT * FROM final")
    con.execute("DETACH out")
    con.execute(f"COPY final TO '{(folder / 'lines.parquet.tmp').as_posix()}' (FORMAT parquet)")

    duplicates = con.execute(
        "SELECT count(*), coalesce(sum(line_value), 0) FROM final WHERE is_duplicate"
    ).fetchone()
    quality.setdefault("flags", {})["exact_duplicate_copies"] = {
        "rows": duplicates[0],
        "value": round(duplicates[1], 2),
        "treatment": "Kept as genuine line items (user decision); flagged and reported.",
    }

    os.replace(tmp_db, folder / "warehouse.duckdb")
    os.replace(folder / "lines.parquet.tmp", folder / "lines.parquet")
    (folder / "quality_report.json").write_text(json.dumps(quality, indent=2, default=str))
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))
