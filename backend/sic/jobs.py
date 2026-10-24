"""Background training jobs with progress reporting.

One worker thread runs jobs one at a time, so a long training run never
blocks the API or the assistant. Each job's status is also written to the
dataset's forecast folder, so the page can show the last result after a
restart (a job that was running when the server stopped shows as
"interrupted").
"""

import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from sic.data import storage
from sic.forecast import pipeline
from sic.forecast.series import NotEligible

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="training")
_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _status_path(dataset_id: str):
    return pipeline.forecast_dir(dataset_id) / "job.json"


def _save(job: dict) -> None:
    path = _status_path(job["dataset_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(job, indent=2))


def _update(job_id: str, **changes) -> None:
    with _lock:
        _jobs[job_id].update(changes)
        _save(_jobs[job_id])


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def latest(dataset_id: str) -> dict | None:
    with _lock:
        running = [j for j in _jobs.values() if j["dataset_id"] == dataset_id]
    if running:
        return dict(max(running, key=lambda j: j["created_at_utc"]))
    path = _status_path(dataset_id)
    if not path.is_file():
        return None
    job = json.loads(path.read_text())
    if job["status"] in ("queued", "running"):
        job["status"] = "interrupted"
        job["message"] = "The server stopped before this job finished; start it again."
    return job


def start_training(dataset_id: str) -> dict:
    storage.validate_dataset_id(dataset_id)
    if not storage.is_ready(dataset_id):
        raise storage.DatasetNotFound(dataset_id)
    with _lock:
        if any(
            j["dataset_id"] == dataset_id and j["status"] in ("queued", "running")
            for j in _jobs.values()
        ):
            raise RuntimeError("A training job for this dataset is already running.")
        job = {
            "id": f"job-{secrets.token_hex(6)}",
            "dataset_id": dataset_id,
            "kind": "forecast_training",
            "status": "queued",
            "progress": 0.0,
            "message": "Waiting to start",
            "created_at_utc": _now(),
            "finished_at_utc": None,
            "error": None,
        }
        _jobs[job["id"]] = job
        _save(job)
    _executor.submit(_run, job["id"], dataset_id)
    return dict(job)


def _run(job_id: str, dataset_id: str) -> None:
    _update(job_id, status="running", message="Starting")

    def progress(fraction: float, message: str) -> None:
        _update(job_id, progress=round(min(max(fraction, 0.0), 1.0), 3), message=message)

    try:
        pipeline.run_all(dataset_id, progress)
        _update(job_id, status="succeeded", progress=1.0, message="Done", finished_at_utc=_now())
    except NotEligible as exc:
        _update(
            job_id, status="not_eligible", message=str(exc), error=str(exc), finished_at_utc=_now()
        )
    except Exception as exc:  # reported to the user; the server keeps running
        _update(
            job_id,
            status="failed",
            message="Training failed",
            error=str(exc),
            finished_at_utc=_now(),
        )
