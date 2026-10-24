"""Uploads train and evaluate on their own data, through the background job."""

import time
from datetime import date, timedelta

import numpy as np
from fastapi.testclient import TestClient

from sic import jobs
from sic.config import EVALUATION_DIR
from sic.forecast import pipeline
from sic.main import create_app


def weekly_csv(weeks: int, seed: int = 1) -> str:
    rng = np.random.default_rng(seed)
    lines = ["invoice_id,invoice_date,product_id,product_name,quantity,unit_price,customer_id"]
    start = date(2022, 1, 3)  # a Monday
    invoice = 1
    for w in range(weeks):
        for d in range(5):  # Monday to Friday
            day = start + timedelta(days=7 * w + d)
            for product, price in (("P1", 3.0), ("P2", 5.0), ("P3", 2.0)):
                qty = max(1, int(rng.normal(20 + 8 * np.sin(2 * np.pi * w / 52), 4)))
                lines.append(
                    f"{invoice},{day},{product},Item {product},{qty},{price},C{invoice % 7}"
                )
                invoice += 1
    return "\n".join(lines) + "\n"


def wait(job_id: str, timeout: float = 120) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs.get(job_id)
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.2)
    raise TimeoutError(job_id)


def test_upload_trains_on_its_own_data_in_the_background(data_dir, make_upload):
    tracked_before = sorted(p.name for p in EVALUATION_DIR.rglob("*"))
    dataset = make_upload(weekly_csv(80))
    client = TestClient(create_app())

    before = client.get(f"/api/datasets/{dataset}/forecast").json()
    assert before["evaluation"] is None and before["eligibility"]["eligible"]

    job = client.post(f"/api/datasets/{dataset}/forecast/train").json()
    assert (
        client.post(f"/api/datasets/{dataset}/forecast/train").status_code == 409
    )  # one at a time
    done = wait(job["id"])
    assert done["status"] == "succeeded", done
    assert done["progress"] == 1.0

    evaluation = pipeline.load_evaluation(dataset)
    folder = pipeline.forecast_dir(dataset)
    assert folder.parent.parent == data_dir / "uploads"  # stored with the upload, outside Git
    assert (folder / "model.joblib").is_file()
    assert evaluation["dataset_id"] == dataset
    assert evaluation["calendar"] == "none"  # no UK holidays assumed for uploads
    assert evaluation["corrections"] == []
    # Ranked by selection-window revenue: P2 (price 5) > P1 (3) > P3 (2).
    assert [s["id"] for s in evaluation["series"]] == ["total", "P2", "P1", "P3"]
    # Data ends on a Friday, so the last Monday-Sunday week is partial: 79 complete weeks.
    assert sum(w["count"] for w in evaluation["windows"].values()) == 79
    assert sorted(p.name for p in EVALUATION_DIR.rglob("*")) == tracked_before

    fresh = client.get(
        f"/api/datasets/{dataset}/forecast/predict", params={"series": "P2", "horizon": 3}
    ).json()
    assert len(fresh["points"]) == 3 and fresh["series_id"] == "P2"
    too_far = client.get(
        f"/api/datasets/{dataset}/forecast/predict", params={"series": "total", "horizon": 9}
    )
    assert too_far.status_code == 422


def test_short_upload_is_not_eligible_with_a_reason(data_dir, make_upload):
    dataset = make_upload(weekly_csv(30))
    client = TestClient(create_app())
    overview = client.get(f"/api/datasets/{dataset}/forecast").json()
    assert overview["eligibility"]["eligible"] is False
    assert "at least 70 complete weeks" in overview["eligibility"]["reason"]
    job = jobs.start_training(dataset)
    done = wait(job["id"])
    assert done["status"] == "not_eligible" and "has 29" in done["message"]
