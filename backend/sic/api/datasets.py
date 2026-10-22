"""Dataset and metrics endpoints used by the dashboard."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from sic.data import storage
from sic.data.upload import delete_upload
from sic.metrics import queries
from sic.metrics.definitions import METRICS, NOT_AVAILABLE
from sic.metrics.periods import Period, presets
from sic.metrics.queries import Filters

router = APIRouter(prefix="/api")

LINE_TYPE_LABELS = {
    "product_sale": "Product sales",
    "product_return": "Product returns / cancellations",
    "shipping": "Shipping charges",
    "fees_commission": "Fees and commission",
    "discount": "Discounts",
    "manual_adjustment": "Manual adjustments",
    "samples": "Samples",
    "gift_voucher": "Gift vouchers",
    "test": "Test lines",
    "bad_debt_adjustment": "Bad-debt adjustments",
    "zero_value_stock_note": "Zero-value stock notes",
    "zero_price_line": "Zero-price lines",
    "negative_price": "Negative-price lines",
    "zero_quantity": "Zero-quantity lines",
    "invalid_row": "Invalid rows (excluded)",
    "unclassified": "Unclassified",
}

StartQ = Annotated[date | None, Query(description="First day (inclusive); default: data start")]
EndQ = Annotated[date | None, Query(description="Last day (inclusive); default: data end")]
CountryQ = Annotated[str | None, Query(max_length=100)]
ProductQ = Annotated[str | None, Query(max_length=60)]


@contextmanager
def opened(dataset_id: str) -> Iterator:
    try:
        con = storage.connect(dataset_id)
    except storage.DatasetNotFound as exc:
        raise HTTPException(404, f"Dataset '{dataset_id}' not found.") from exc
    try:
        yield con
    finally:
        con.close()


def build_filters(con, start, end, country, product_id) -> Filters:
    first, last = queries.coverage(con)
    period = Period(start or first, end or last)
    if period.start > period.end:
        raise HTTPException(400, "The start date must not be after the end date.")
    return Filters(period, country or None, product_id or None)


@router.get("/definitions")
def definitions() -> dict:
    return {"metrics": METRICS, "not_available": NOT_AVAILABLE, "line_types": LINE_TYPE_LABELS}


@router.get("/datasets")
def list_datasets() -> list[dict]:
    return storage.list_datasets()


@router.get("/datasets/{dataset_id}")
def dataset_info(dataset_id: str) -> dict:
    with opened(dataset_id) as con:
        first, last = queries.coverage(con)
        return {
            "metadata": storage.read_json(dataset_id, "metadata.json"),
            "coverage": {"first_date": first.isoformat(), "last_date": last.isoformat()},
            "presets": presets(first, last),
            "countries": queries.country_list(con),
        }


@router.get("/datasets/{dataset_id}/summary")
def summary(
    dataset_id: str,
    start: StartQ = None,
    end: EndQ = None,
    country: CountryQ = None,
    product_id: ProductQ = None,
) -> dict:
    with opened(dataset_id) as con:
        return queries.summary(con, build_filters(con, start, end, country, product_id))


@router.get("/datasets/{dataset_id}/timeseries")
def timeseries(
    dataset_id: str,
    freq: Literal["day", "week", "month"] = "week",
    start: StartQ = None,
    end: EndQ = None,
    country: CountryQ = None,
    product_id: ProductQ = None,
) -> dict:
    with opened(dataset_id) as con:
        filters = build_filters(con, start, end, country, product_id)
        if freq == "day" and filters.period.days > 400:
            raise HTTPException(400, "Daily series are limited to 400 days; use week or month.")
        return {
            "filters": filters.describe(),
            "freq": freq,
            "points": queries.timeseries(con, filters, freq),
        }


@router.get("/datasets/{dataset_id}/products")
def products(
    dataset_id: str,
    sort_by: Literal["net_revenue", "gross_sales", "returns", "units", "orders"] = "net_revenue",
    order: Literal["desc", "asc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 10,
    search: Annotated[str | None, Query(max_length=60)] = None,
    start: StartQ = None,
    end: EndQ = None,
    country: CountryQ = None,
) -> dict:
    with opened(dataset_id) as con:
        filters = build_filters(con, start, end, country, None)
        result = queries.products(con, filters, sort_by, order == "desc", limit, search or None)
        return {"filters": filters.describe(), "sort_by": sort_by, "order": order, **result}


@router.get("/datasets/{dataset_id}/countries")
def countries(
    dataset_id: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    start: StartQ = None,
    end: EndQ = None,
    product_id: ProductQ = None,
) -> dict:
    with opened(dataset_id) as con:
        filters = build_filters(con, start, end, None, product_id)
        return {"filters": filters.describe(), "countries": queries.countries(con, filters, limit)}


@router.get("/datasets/{dataset_id}/other-lines")
def other_lines(
    dataset_id: str,
    start: StartQ = None,
    end: EndQ = None,
    country: CountryQ = None,
) -> dict:
    with opened(dataset_id) as con:
        filters = build_filters(con, start, end, country, None)
        rows = queries.other_lines(con, filters)
        for row in rows:
            row["label"] = LINE_TYPE_LABELS.get(row["line_type"], row["line_type"])
        return {"filters": filters.describe(), "lines": rows}


@router.get("/datasets/{dataset_id}/quality")
def quality(dataset_id: str) -> dict:
    try:
        report = storage.read_json(dataset_id, "quality_report.json")
    except storage.DatasetNotFound as exc:
        raise HTTPException(404, f"Dataset '{dataset_id}' not found.") from exc
    for rule in report.get("rules", []):
        rule["label"] = LINE_TYPE_LABELS.get(rule["line_type"], rule["line_type"])
    return report


@router.delete("/datasets/{dataset_id}")
def remove_dataset(dataset_id: str) -> dict:
    if dataset_id == storage.BUILTIN_ID:
        raise HTTPException(400, "The built-in dataset cannot be deleted.")
    try:
        delete_upload(dataset_id)
    except storage.DatasetNotFound as exc:
        raise HTTPException(404, f"Dataset '{dataset_id}' not found.") from exc
    return {"deleted": dataset_id}
