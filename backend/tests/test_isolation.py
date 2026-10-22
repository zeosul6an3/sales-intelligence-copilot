"""Dataset isolation: uploads cannot read, change or reach other datasets."""

import hashlib
from datetime import date

import pytest
from fastapi.testclient import TestClient

from sic.data import storage, upload
from sic.main import create_app
from sic.metrics import queries
from sic.metrics.periods import Period
from sic.metrics.queries import Filters

from .conftest import METRICS_CSV
from .test_uci_rules import SOURCE, sheet_rows

OTHER_CSV = """invoice_id,invoice_date,product_id,quantity,unit_price
X1,2024-01-02,Z,100,1.00
"""
EVERYTHING = Period(date(2000, 1, 1), date(2100, 1, 1))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def net(dataset_id):
    with storage.connect(dataset_id) as con:
        return queries.kpis(con, Filters(EVERYTHING))["net_revenue"]


def test_uploads_are_separate_from_each_other_and_from_builtin(data_dir, make_upload):
    from sic.data import uci

    uci.build_from_frame(sheet_rows(), {"numeric_descriptions": 0}, SOURCE)
    builtin_file = storage.warehouse_path("uci")
    builtin_before, builtin_net = digest(builtin_file), net("uci")

    first = make_upload(METRICS_CSV)
    second = make_upload(OTHER_CSV)

    assert net(first) == 57.0 and net(second) == 100.0
    assert digest(builtin_file) == builtin_before and net("uci") == builtin_net
    assert (
        storage.dataset_dir(first).parent
        == storage.dataset_dir(second).parent
        == data_dir / "uploads"
    )
    assert {d["id"] for d in storage.list_datasets()} == {"uci", first, second}

    upload.delete_upload(second)
    assert net(first) == 57.0 and net("uci") == builtin_net
    with pytest.raises(storage.DatasetNotFound):
        storage.connect(second)


@pytest.mark.parametrize(
    "bad_id",
    [
        "../processed/uci",
        "upload-../../etc",
        "UCI",
        "upload-ABCDEF123456",
        "upload-123",
        "",
        "uci/../x",
    ],
)
def test_malformed_dataset_ids_are_rejected(data_dir, bad_id):
    with pytest.raises(storage.DatasetNotFound):
        storage.dataset_dir(bad_id)


def test_api_cannot_delete_builtin_or_reach_outside(data_dir):
    client = TestClient(create_app())
    assert client.delete("/api/datasets/uci").status_code == 400
    assert client.get("/api/datasets/..%2F..%2Fetc/summary").status_code == 404
    assert (
        client.post("/api/uploads/uci/import", json={"mapping": {}, "currency": "GBP"}).status_code
        == 404
    )


def test_staged_upload_is_invisible_until_imported(data_dir):
    staged = upload.stage(METRICS_CSV.encode(), "staged.csv")
    assert storage.list_datasets() == []
    with pytest.raises(storage.DatasetNotFound):
        storage.connect(staged["upload_id"])
