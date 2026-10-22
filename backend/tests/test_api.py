"""The upload and metrics API, end to end through HTTP."""

from fastapi.testclient import TestClient

from sic.main import create_app

from .conftest import METRICS_CSV


def test_upload_flow_and_metrics_endpoints(data_dir):
    client = TestClient(create_app())

    staged = client.post("/api/uploads", files={"file": ("sales.csv", METRICS_CSV, "text/csv")})
    assert staged.status_code == 200
    body = staged.json()
    options = {"mapping": body["suggested_mapping"], "currency": "GBP", "name": "Test shop"}

    checked = client.post(f"/api/uploads/{body['upload_id']}/validate", json=options).json()
    assert checked["can_import"] and checked["rows_total"] == 9
    assert client.get("/api/datasets").json() == []  # nothing stored before import

    imported = client.post(f"/api/uploads/{body['upload_id']}/import", json=options).json()
    dataset = imported["id"]
    assert imported["name"] == "Test shop"

    summary = client.get(
        f"/api/datasets/{dataset}/summary", params={"start": "2024-01-01", "end": "2024-01-31"}
    ).json()
    assert summary["current"]["net_revenue"] == 51.0
    series = client.get(f"/api/datasets/{dataset}/timeseries", params={"freq": "month"}).json()
    assert [p["net_revenue"] for p in series["points"]] == [51.0, 6.0]
    assert [p["partial"] for p in series["points"]] == [False, True]
    quality = client.get(f"/api/datasets/{dataset}/quality").json()
    assert quality["row_flow"]["reconciles"] is True

    assert client.post(f"/api/uploads/{body['upload_id']}/import", json=options).status_code == 422
    assert client.delete(f"/api/datasets/{dataset}").status_code == 200
    assert client.get(f"/api/datasets/{dataset}/summary").status_code == 404


def test_input_validation(data_dir):
    client = TestClient(create_app())
    assert client.post("/api/uploads", files={"file": ("e.csv", "", "text/csv")}).status_code == 422
    assert client.get("/api/uploads/template.csv").text.startswith("invoice_id,invoice_date")
