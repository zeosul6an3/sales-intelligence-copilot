"""Rolling-origin backtests, metrics, the frozen selection rule and intervals.

Backtest over a window (a, b): for every origin o in a..b, forecast h = 1..H
and keep only targets o+h-1 <= b. So validation forecasts score only
validation weeks, calibration forecasts only calibration weeks, and nothing
before the holdout ever scores a holdout week. Models are refitted at every
origin on weeks before it (expanding window).
"""

import math
from collections import defaultdict

import numpy as np

from sic.forecast.models import Model, forecast_at, series_scale
from sic.forecast.series import TOTAL

GROUPS = ("total", "products")


def group_of(series_id: str) -> str:
    return "total" if series_id == TOTAL else "products"


def backtest(
    model: Model, series: dict, window: tuple[int, int], horizon: int, on_origin=None
) -> list[dict]:
    a, b = window
    records = []
    for origin in range(a, b + 1):
        if not model.available(origin):
            continue
        steps = min(horizon, b - origin + 1)
        predictions = forecast_at(model, series, origin, steps)
        for sid, values in predictions.items():
            scale = series_scale(np.asarray(series[sid][:origin], dtype=float))
            for h in range(steps):
                t = origin + h
                records.append(
                    {
                        "model": model.name,
                        "series": sid,
                        "origin": origin,
                        "h": h + 1,
                        "target": t,
                        "actual": float(series[sid][t]),
                        "forecast": float(values[h]),
                        "scale": scale,
                    }
                )
        if on_origin:
            on_origin()
    return records


def _na(reason: str) -> dict:
    return {"value": None, "reason": reason}


def metrics(records: list[dict]) -> dict:
    """MAE, RMSE, WAPE and bias for a set of forecasts (error = forecast - actual)."""
    n = len(records)
    if n == 0:
        return {
            "n": 0,
            "mae": _na("no forecasts"),
            "rmse": _na("no forecasts"),
            "wape": _na("no forecasts"),
            "bias": _na("no forecasts"),
        }
    errors = np.array([r["forecast"] - r["actual"] for r in records])
    actuals = np.array([r["actual"] for r in records])
    abs_actual, sum_actual = np.abs(actuals).sum(), actuals.sum()
    return {
        "n": n,
        "mae": {"value": float(np.abs(errors).mean())},
        "rmse": {"value": float(math.sqrt((errors**2).mean()))},
        "wape": {"value": float(np.abs(errors).sum() / abs_actual)}
        if abs_actual > 0
        else _na("sum of absolute actuals is 0"),
        "bias": {"value": float(errors.sum() / sum_actual)}
        if sum_actual != 0
        else _na("sum of actuals is 0"),
    }


def skill(model_mae: dict, baseline_mae: dict, baseline: str) -> dict:
    if baseline_mae["value"] is None:
        return _na(f"{baseline} has no forecasts here")
    if baseline_mae["value"] == 0:
        return _na(f"{baseline} MAE is 0")
    return {"value": 1 - model_mae["value"] / baseline_mae["value"]}


def metric_table(records: list[dict], horizon: int, by_series=False) -> dict:
    """metrics[model][group or series][h] with skill vs naive and seasonal naive."""
    buckets = defaultdict(list)
    for r in records:
        key = r["series"] if by_series else group_of(r["series"])
        buckets[(r["model"], key, r["h"])].append(r)
    table: dict = defaultdict(lambda: defaultdict(dict))
    for (model, key, h), recs in buckets.items():
        table[model][key][h] = metrics(recs)
    for keys in table.values():
        for key, by_h in keys.items():
            for h, m in by_h.items():
                for base in ("naive", "seasonal_naive"):
                    base_m = table.get(base, {}).get(key, {}).get(h)
                    m[f"skill_vs_{base}"] = (
                        skill(m["mae"], base_m["mae"], base)
                        if base_m
                        else _na(f"{base} unavailable at this origin")
                    )
    return {m: {k: dict(sorted(v.items())) for k, v in keys.items()} for m, keys in table.items()}


def supported_horizons(window_counts: dict, cfg: dict) -> dict:
    """Which horizons are supported/provisional, from per-series point counts."""
    hz = cfg["horizon"]
    result = {}
    for h in range(1, hz["max_weeks"] + 1):
        validation = window_counts["validation"] - h + 1
        calibration = window_counts["calibration"] - h + 1
        supported = validation >= hz["min_validation_points"] and calibration >= 1
        provisional = calibration < hz["provisional_below_calibration_points"]
        result[h] = {
            "supported": supported,
            "provisional": supported and provisional,
            "validation_points_per_series": max(validation, 0),
            "calibration_points_per_series": max(calibration, 0),
            "holdout_points_per_series": max(window_counts["holdout"] - h + 1, 0),
        }
    return result


def select(validation_table: dict, horizons: list[int], cfg: dict) -> dict:
    """Apply the frozen rule: lowest mean validation WAPE over horizons, per group."""
    rule = cfg["selection"]
    order = rule["candidates"]
    decision = {}
    for group in GROUPS:
        scores = {}
        for name in order:
            by_h = validation_table.get(name, {}).get(group, {})
            values = [by_h[h]["wape"]["value"] for h in horizons if h in by_h]
            if len(values) == len(horizons) and all(v is not None for v in values):
                scores[name] = float(np.mean(values))
        if not scores:
            decision[group] = {"selected": None, "reason": "no candidate has complete scores"}
            continue
        best = min(scores.values())
        within = [n for n in order if n in scores and scores[n] - best <= rule["tie_tolerance"]]
        chosen = within[0]
        decision[group] = {
            "selected": chosen,
            "mean_validation_wape": scores,
            "best_score": best,
            "tie_rule_applied": chosen != min(scores, key=scores.get),
            "not_scored": [n for n in order if n not in scores],
        }
    return decision


def calibrate(records: list[dict], horizons: list[int], coverage: float) -> dict:
    """Empirical residual quantiles per group and horizon (actual - forecast).

    Total: residuals in currency. Products: residuals divided by each series'
    scale at the origin, pooled across products, then multiplied back.
    """
    lo_q, hi_q = (1 - coverage) / 2, 1 - (1 - coverage) / 2
    result: dict = {g: {} for g in GROUPS}
    for group in GROUPS:
        for h in horizons:
            residuals = [
                (r["actual"] - r["forecast"]) / (1.0 if group == "total" else r["scale"])
                for r in records
                if group_of(r["series"]) == group and r["h"] == h
            ]
            if residuals:
                result[group][h] = {
                    "lower": float(np.quantile(residuals, lo_q)),
                    "upper": float(np.quantile(residuals, hi_q)),
                    "n": len(residuals),
                    "unit": "currency" if group == "total" else "series scale",
                }
    return result


def interval(forecast: float, scale: float, group: str, h: int, quantiles: dict):
    q = quantiles.get(group, {}).get(h)
    if not q:
        return None, None
    factor = 1.0 if group == "total" else scale
    return forecast + q["lower"] * factor, forecast + q["upper"] * factor


def coverage_table(records: list[dict], quantiles: dict) -> dict:
    hits = defaultdict(list)
    for r in records:
        group = group_of(r["series"])
        low, high = interval(r["forecast"], r["scale"], group, r["h"], quantiles)
        if low is not None:
            hits[(group, r["h"])].append(low <= r["actual"] <= high)
    return {
        g: {
            h: {"coverage": float(np.mean(v)), "n": len(v)}
            for (gg, h), v in sorted(hits.items())
            if gg == g
        }
        for g in GROUPS
    }
