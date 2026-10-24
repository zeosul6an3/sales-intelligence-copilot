"""Two-stage training and evaluation pipeline.

Stage 1, `run_selection`: validation backtests for every candidate and the
experiment, the frozen selection rule, then calibration backtests for the
selected models and interval quantiles. Writes selection.json.

Stage 2, `run_holdout`: refuses to run unless selection.json was produced
with the same configuration and the same data. Evaluates every model on the
holdout (the selected ones are already fixed), measures interval coverage,
refits the selected models on all complete weeks and writes the future
forecast and model file.

All artifacts go to the dataset's own folder (ignored by Git).
"""

import hashlib
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import joblib
import numpy as np

from sic.config import PROJECT_ROOT
from sic.data import storage
from sic.forecast import config as forecast_config
from sic.forecast import evaluate, series
from sic.forecast.models import Calendar, PooledML, build_models, forecast_at, series_scale

HOLDOUT_NOTE = (
    "The holdout weeks are not completely unseen: aggregate weekly totals for them were "
    "inspected during the feasibility review (2026-10-24) before the candidates, selection "
    "rule, correction policy and windows were frozen. No model forecast for a holdout week "
    "existed before the model choice was fixed in selection.json."
)

Progress = Callable[[float, str], None]


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _git_commit() -> dict:
    def run(*args):
        try:
            return subprocess.run(
                ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return ""

    return {
        "commit": run("rev-parse", "HEAD") or None,
        "uncommitted_changes": bool(run("status", "--porcelain")),
    }


def forecast_dir(dataset_id: str):
    return storage.dataset_dir(dataset_id) / "forecast"


def calendar_name(dataset_id: str, cfg: dict) -> str:
    return cfg["calendar"]["builtin" if dataset_id == storage.BUILTIN_ID else "uploads"]


def fingerprint(data: series.WeeklyData) -> str:
    digest = hashlib.sha256()
    digest.update("|".join(w.isoformat() for w in data.weeks).encode())
    for sid in data.series_ids:
        digest.update(sid.encode())
        digest.update(np.round(data.adjusted[sid], 2).tobytes())
    return digest.hexdigest()


def load_data(dataset_id: str, cfg: dict) -> series.WeeklyData:
    with storage.connect(dataset_id) as con:
        return series.build(con, cfg)


def _window_counts(data: series.WeeklyData) -> dict:
    w = data.windows
    return {
        name: b - a + 1
        for name, (a, b) in {
            "validation": w.validation,
            "calibration": w.calibration,
            "holdout": w.holdout,
        }.items()
    }


def run_selection(dataset_id: str, progress: Progress | None = None) -> dict:
    cfg = forecast_config.load()
    report = progress or (lambda f, m: None)
    data = load_data(dataset_id, cfg)
    horizons_info = evaluate.supported_horizons(_window_counts(data), cfg)
    horizons = [h for h, v in horizons_info.items() if v["supported"]]
    if not horizons:
        raise series.NotEligible("No forecast horizon has enough validation points.")
    max_h = max(horizons)
    cal_name = calendar_name(dataset_id, cfg)
    calendar = Calendar(data.weeks, cal_name)
    models = build_models(cfg, calendar)
    adjusted = data.adjusted

    steps = len(models) * (data.windows.validation[1] - data.windows.validation[0] + 1)
    done = [0]

    def tick(message):
        done[0] += 1
        report(0.8 * done[0] / steps, message)

    validation_records = []
    for name, model in models.items():
        validation_records += evaluate.backtest(
            model,
            adjusted,
            data.windows.validation,
            max_h,
            on_origin=lambda n=name: tick(f"Validation backtest: {n}"),
        )
    validation_table = evaluate.metric_table(validation_records, max_h)
    decision = evaluate.select(validation_table, horizons, cfg)

    report(0.85, "Calibration backtest for the selected models")
    selected = {d["selected"] for d in decision.values() if d["selected"]}
    calibration_records = []
    for name in selected:
        recs = evaluate.backtest(models[name], adjusted, data.windows.calibration, max_h)
        calibration_records += [
            r for r in recs if decision[evaluate.group_of(r["series"])]["selected"] == name
        ]
    quantiles = evaluate.calibrate(calibration_records, horizons, cfg["intervals"]["coverage"])

    result = {
        "stage": "selection",
        "created_at_utc": _now(),
        "dataset_id": dataset_id,
        "config_sha256": cfg["_sha256"],
        "data_fingerprint": fingerprint(data),
        "code": _git_commit(),
        "target": cfg["target"],
        "calendar": cal_name,
        "windows": data.windows.describe(data.weeks),
        "horizons": horizons_info,
        "series": [{"id": s, "name": data.names.get(s, s)} for s in data.series_ids],
        "product_selection": data.selection_info,
        "corrections": data.corrections,
        "selection_rule": cfg["selection"],
        "decision": decision,
        "validation_metrics": validation_table,
        "validation_metrics_by_series": evaluate.metric_table(validation_records, max_h, True),
        "calibration_metrics": evaluate.metric_table(calibration_records, max_h),
        "calibration_quantiles": quantiles,
    }
    out = forecast_dir(dataset_id)
    out.mkdir(parents=True, exist_ok=True)
    (out / "selection.json").write_text(json.dumps(result, indent=2, default=str))
    report(0.9, "Selection stage complete")
    return result


def run_holdout(dataset_id: str, progress: Progress | None = None) -> dict:
    cfg = forecast_config.load()
    report = progress or (lambda f, m: None)
    out = forecast_dir(dataset_id)
    selection_path = out / "selection.json"
    if not selection_path.is_file():
        raise RuntimeError("Run the selection stage first.")
    selection = json.loads(selection_path.read_text())
    data = load_data(dataset_id, cfg)
    if selection["config_sha256"] != cfg["_sha256"]:
        raise RuntimeError("The configuration changed after selection; run a new selection.")
    if selection["data_fingerprint"] != fingerprint(data):
        raise RuntimeError("The data changed after selection; run a new selection.")

    horizons = [int(h) for h, v in selection["horizons"].items() if v["supported"]]
    max_h = max(horizons)
    calendar = Calendar(
        data.weeks + [data.weeks[-1] + timedelta(days=7 * i) for i in range(1, max_h + 1)],
        selection["calendar"],
    )
    models = build_models(cfg, calendar)
    decision = selection["decision"]
    quantiles = {
        g: {int(h): q for h, q in v.items()} for g, v in selection["calibration_quantiles"].items()
    }

    holdout_records = []
    for i, (name, model) in enumerate(models.items()):
        report(0.9 + 0.07 * i / len(models), f"Holdout backtest: {name}")
        holdout_records += evaluate.backtest(model, data.adjusted, data.windows.holdout, max_h)
    chosen = [
        r
        for r in holdout_records
        if decision[evaluate.group_of(r["series"])]["selected"] == r["model"]
    ]

    report(0.97, "Refitting the selected models on all complete weeks")
    origin = len(data.weeks)
    future, fitted = {}, {}
    for group in evaluate.GROUPS:
        name = decision[group]["selected"]
        ids = [s for s in data.series_ids if evaluate.group_of(s) == group]
        if not name or not ids:
            continue
        preds = forecast_at(models[name], data.adjusted, origin, max_h)
        if isinstance(models[name], PooledML):
            fitted[name] = models[name]
        for sid in ids:
            scale = series_scale(data.adjusted[sid])
            rows = []
            for h in range(max_h):
                low, high = evaluate.interval(preds[sid][h], scale, group, h + 1, quantiles)
                rows.append(
                    {
                        "week_start": (data.weeks[-1] + timedelta(days=7 * (h + 1))).isoformat(),
                        "h": h + 1,
                        "forecast": float(preds[sid][h]),
                        "lower": low,
                        "upper": high,
                        "provisional": selection["horizons"][str(h + 1)]["provisional"],
                    }
                )
            future[sid] = {"model": name, "points": rows}
    joblib.dump(
        {
            "models": fitted,
            "decision": decision,
            "config_sha256": cfg["_sha256"],
            "data_fingerprint": selection["data_fingerprint"],
        },
        out / "model.joblib",
    )

    weeks = [w.isoformat() for w in data.weeks]
    keep = {(r["series"], r["model"]) for r in chosen} | {
        (r["series"], r["model"]) for r in holdout_records if r["model"] == "seasonal_naive"
    }
    chart_records = []
    for r in holdout_records:
        if (r["series"], r["model"]) in keep:
            group = evaluate.group_of(r["series"])
            low, high = (
                evaluate.interval(r["forecast"], r["scale"], group, r["h"], quantiles)
                if decision[group]["selected"] == r["model"]
                else (None, None)
            )
            chart_records.append(
                {**r, "week_start": weeks[r["target"]], "lower": low, "upper": high}
            )

    result = {
        **{
            k: selection[k]
            for k in (
                "dataset_id",
                "config_sha256",
                "data_fingerprint",
                "target",
                "calendar",
                "windows",
                "horizons",
                "series",
                "product_selection",
                "corrections",
                "selection_rule",
                "decision",
                "validation_metrics",
                "validation_metrics_by_series",
                "calibration_metrics",
                "calibration_quantiles",
            )
        },
        "selection_created_at_utc": selection["created_at_utc"],
        "selection_code": selection["code"],
        "holdout_created_at_utc": _now(),
        "holdout_code": _git_commit(),
        "holdout_note": HOLDOUT_NOTE,
        "holdout_metrics": evaluate.metric_table(holdout_records, max_h),
        "holdout_metrics_by_series": evaluate.metric_table(holdout_records, max_h, True),
        "holdout_coverage": evaluate.coverage_table(chosen, quantiles),
        "history": {
            "weeks": weeks,
            "week_flags": data.week_flags(),
            "adjusted": {
                s: [round(float(v), 2) for v in data.adjusted[s]] for s in data.series_ids
            },
            "reported": {
                s: [round(float(v), 2) for v in data.reported[s]] for s in data.series_ids
            },
            "zero_kind": {s: data.zero_kind(s) for s in data.series_ids},
        },
        "holdout_predictions": chart_records,
        "future_forecast": {
            "origin_week": (data.weeks[-1] + timedelta(days=7)).isoformat(),
            "series": future,
        },
    }
    (out / "evaluation.json").write_text(json.dumps(result, indent=2, default=str))
    report(1.0, "Training and evaluation complete")
    return result


def run_all(dataset_id: str, progress: Progress | None = None) -> dict:
    run_selection(dataset_id, progress)
    return run_holdout(dataset_id, progress)


def load_evaluation(dataset_id: str) -> dict | None:
    path = forecast_dir(dataset_id) / "evaluation.json"
    return json.loads(path.read_text()) if path.is_file() else None


def fresh_forecast(dataset_id: str, series_id: str, horizon: int) -> dict:
    """Forecast one eligible series now, with the evaluated (selected) model."""
    evaluation = load_evaluation(dataset_id)
    if evaluation is None:
        raise LookupError("No evaluated model exists for this dataset; train it first.")
    supported = [int(h) for h, v in evaluation["horizons"].items() if v["supported"]]
    if horizon < 1 or horizon > max(supported):
        raise ValueError(
            f"Horizon must be between 1 and {max(supported)} weeks (the evaluated range)."
        )
    ids = [s["id"] for s in evaluation["series"]]
    if series_id not in ids:
        raise LookupError(f"'{series_id}' is not one of the evaluated series.")
    cfg = forecast_config.load()
    data = load_data(dataset_id, cfg)
    if fingerprint(data) != evaluation["data_fingerprint"]:
        raise RuntimeError("The data changed since the model was evaluated; retrain first.")
    saved = joblib.load(forecast_dir(dataset_id) / "model.joblib")
    group = evaluate.group_of(series_id)
    name = saved["decision"][group]["selected"]
    origin = len(data.weeks)
    if name in saved["models"]:
        model = saved["models"][name]
        history = {k: np.asarray(v, dtype=float) for k, v in data.adjusted.items()}
        preds = model.predict(history, origin, horizon)[series_id]
    else:
        calendar = Calendar(data.weeks, evaluation["calendar"])
        preds = forecast_at(build_models(cfg, calendar)[name], data.adjusted, origin, horizon)[
            series_id
        ]
    quantiles = {
        g: {int(h): q for h, q in v.items()} for g, v in evaluation["calibration_quantiles"].items()
    }
    scale = series_scale(data.adjusted[series_id])
    points = []
    for h in range(horizon):
        low, high = evaluate.interval(float(preds[h]), scale, group, h + 1, quantiles)
        points.append(
            {
                "week_start": (data.weeks[-1] + timedelta(days=7 * (h + 1))).isoformat(),
                "h": h + 1,
                "forecast": float(preds[h]),
                "lower": low,
                "upper": high,
                "provisional": evaluation["horizons"][str(h + 1)]["provisional"],
            }
        )
    return {
        "dataset_id": dataset_id,
        "series_id": series_id,
        "series_name": next(s["name"] for s in evaluation["series"] if s["id"] == series_id),
        "target": evaluation["target"]["label"],
        "model": name,
        "last_complete_week": data.weeks[-1].isoformat(),
        "points": points,
    }
