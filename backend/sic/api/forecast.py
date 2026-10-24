"""Forecast endpoints: evaluation results, fresh forecasts and training jobs."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from sic import jobs
from sic.data import storage
from sic.forecast import config as forecast_config
from sic.forecast import pipeline
from sic.forecast.series import NotEligible, complete_weeks, make_windows

router = APIRouter(prefix="/api")


def _check(dataset_id: str) -> None:
    try:
        storage.validate_dataset_id(dataset_id)
    except storage.DatasetNotFound as exc:
        raise HTTPException(404, f"Dataset '{dataset_id}' not found.") from exc
    if not storage.is_ready(dataset_id):
        raise HTTPException(404, f"Dataset '{dataset_id}' not found.")


@router.get("/datasets/{dataset_id}/forecast")
def forecast_overview(dataset_id: str) -> dict:
    """Evaluation results (or the reason none exist) and the latest training job."""
    _check(dataset_id)
    cfg = forecast_config.load()
    evaluation = pipeline.load_evaluation(dataset_id)
    eligibility = {"eligible": True, "reason": None}
    if evaluation is None:
        with storage.connect(dataset_id) as con:
            n = len(complete_weeks(con))
        try:
            make_windows(n, cfg)
        except NotEligible as exc:
            eligibility = {"eligible": False, "reason": str(exc)}
    return {
        "dataset_id": dataset_id,
        "target": cfg["target"],
        "eligibility": eligibility,
        "evaluation": evaluation,
        "job": jobs.latest(dataset_id),
    }


@router.get("/datasets/{dataset_id}/forecast/predict")
def predict(
    dataset_id: str,
    series: Annotated[str, Query(max_length=60)] = "total",
    horizon: Annotated[int, Query(ge=1, le=52)] = 8,
) -> dict:
    """A fresh forecast for one evaluated series with the dataset's evaluated model."""
    _check(dataset_id)
    try:
        return pipeline.fresh_forecast(dataset_id, series, horizon)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/datasets/{dataset_id}/forecast/train")
def train(dataset_id: str) -> dict:
    _check(dataset_id)
    try:
        return jobs.start_training(dataset_id)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    return job
