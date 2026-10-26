"""Operational forecast: which model the app actually uses, per group.

By default this is the frozen validation selection. A documented override
(configs/forecast_overrides.toml, built-in dataset only) can replace it; the
override is recorded as chosen after the holdout and is never presented as
independently evaluated. The frozen selection and the evaluation history in
evaluation.json are left untouched; this step writes operational.json.

For an overridden group the model's 80% ranges are calibrated on its OWN
calibration-window residuals, and their holdout coverage is measured and
reported together with the caveat that the holdout influenced the choice.
"""

import json
import tomllib
from datetime import UTC, datetime, timedelta

from sic.config import PROJECT_ROOT
from sic.data import storage
from sic.forecast import config as forecast_config
from sic.forecast import evaluate
from sic.forecast.models import Calendar, build_models, forecast_at, series_scale

OVERRIDES_PATH = PROJECT_ROOT / "configs" / "forecast_overrides.toml"
NOT_INDEPENDENT = (
    "Chosen after reviewing holdout results: the holdout figures for this model are not an "
    "independent evaluation of the decision, and no untouched data remains to provide one."
)


def load_overrides(dataset_id: str, path=OVERRIDES_PATH) -> dict[str, dict]:
    """Overrides for this dataset, keyed by group. Uploads can never be overridden."""
    if not path.is_file():
        return {}
    entries = tomllib.loads(path.read_text(encoding="utf-8")).get("override", [])
    cfg = forecast_config.load()
    result = {}
    for entry in entries:
        if entry["dataset"] != storage.BUILTIN_ID:
            raise ValueError("Only the built-in dataset may have an operational override.")
        if entry["group"] not in evaluate.GROUPS:
            raise ValueError(f"Unknown group {entry['group']!r} in overrides.")
        if entry["model"] not in cfg["selection"]["candidates"]:
            raise ValueError(f"Override model {entry['model']!r} is not an evaluated candidate.")
        if entry.get("independent_evaluation") is not False:
            raise ValueError("Overrides must state independent_evaluation = false.")
        if entry["dataset"] == dataset_id:
            result[entry["group"]] = entry
    return result


def build(dataset_id: str, data, evaluation: dict) -> dict:
    """Decide the operational model per group, its intervals and the future forecast."""
    cfg = forecast_config.load()
    overrides = load_overrides(dataset_id)
    horizons = [int(h) for h, v in evaluation["horizons"].items() if v["supported"]]
    max_h = max(horizons)
    weeks = data.weeks + [data.weeks[-1] + timedelta(days=7 * i) for i in range(1, max_h + 1)]
    models = build_models(cfg, Calendar(weeks, evaluation["calendar"]))
    origin = len(data.weeks)
    frozen_quantiles = {
        g: {int(h): q for h, q in v.items()} for g, v in evaluation["calibration_quantiles"].items()
    }

    groups, future, operational_quantiles = {}, {}, {}
    for group in evaluate.GROUPS:
        ids = [s for s in data.series_ids if evaluate.group_of(s) == group]
        frozen = evaluation["decision"][group]["selected"]
        if not ids or not frozen:
            continue
        override = overrides.get(group)
        name = override["model"] if override else frozen
        series = {s: data.adjusted[s] for s in ids}
        if override:
            # The overriding model's own calibration residuals and holdout coverage.
            cal = evaluate.backtest(models[name], series, data.windows.calibration, max_h)
            quantiles = evaluate.calibrate(cal, horizons, cfg["intervals"]["coverage"])
            hold = evaluate.backtest(models[name], series, data.windows.holdout, max_h)
            coverage = evaluate.coverage_table(hold, quantiles)[group]
            calibration_n = {h: q["n"] for h, q in quantiles[group].items()}
        else:
            quantiles = frozen_quantiles
            coverage = {int(h): c for h, c in evaluation["holdout_coverage"][group].items()}
            calibration_n = {h: q["n"] for h, q in quantiles.get(group, {}).items()}
        operational_quantiles[group] = quantiles.get(group, {})
        mean_cov = (
            sum(c["coverage"] for c in coverage.values()) / len(coverage) if coverage else None
        )
        groups[group] = {
            "model": name,
            "source": "override, chosen after the holdout"
            if override
            else "frozen validation selection",
            "frozen_selection": frozen,
            "override": override,
            "evaluation_note": NOT_INDEPENDENT if override else None,
            "interval_calibration_n": calibration_n,
            "interval_holdout_coverage": coverage,
            "interval_mean_holdout_coverage": mean_cov,
            "interval_note": _interval_note(calibration_n, coverage, bool(override)),
        }
        predictions = forecast_at(models[name], data.adjusted, origin, max_h)
        comparison_name = (
            frozen if override else ("seasonal_naive" if name != "seasonal_naive" else None)
        )
        comparison = (
            forecast_at(models[comparison_name], data.adjusted, origin, max_h)
            if comparison_name and models[comparison_name].available(origin)
            else None
        )
        for sid in ids:
            scale = series_scale(data.adjusted[sid])
            points = []
            for h in range(max_h):
                low, high = evaluate.interval(
                    float(predictions[sid][h]), scale, group, h + 1, quantiles
                )
                points.append(
                    {
                        "week_start": weeks[origin + h].isoformat(),
                        "h": h + 1,
                        "forecast": float(predictions[sid][h]),
                        "lower": low,
                        "upper": high,
                        "provisional": evaluation["horizons"][str(h + 1)]["provisional"],
                    }
                )
            entry = {"model": name, "points": points}
            if comparison is not None:
                entry["comparison"] = {
                    "model": comparison_name,
                    "role": "frozen validation selection" if override else "baseline comparison",
                    "points": [
                        {
                            "week_start": p["week_start"],
                            "h": p["h"],
                            "forecast": float(comparison[sid][p["h"] - 1]),
                        }
                        for p in points
                    ],
                }
            future[sid] = entry

    return {
        "dataset_id": dataset_id,
        "created_at_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "config_sha256": evaluation["config_sha256"],
        "data_fingerprint": evaluation["data_fingerprint"],
        "overrides_file": str(OVERRIDES_PATH.relative_to(PROJECT_ROOT)) if overrides else None,
        "groups": groups,
        "quantiles": {
            g: {str(h): q for h, q in v.items()} for g, v in operational_quantiles.items()
        },
        "future_forecast": {"origin_week": weeks[origin].isoformat(), "series": future},
    }


def _interval_note(calibration_n: dict, coverage: dict, overridden: bool) -> str:
    if not coverage:
        return "No interval coverage measured."
    low = min(c["coverage"] for c in coverage.values())
    high = max(c["coverage"] for c in coverage.values())
    note = (
        f"Nominal 80% range from this model's own calibration residuals "
        f"(n = {min(calibration_n.values())}-{max(calibration_n.values())} per horizon); "
        f"measured holdout coverage {low:.0%}-{high:.0%}."
    )
    if high < 0.75:
        note += " The ranges are too narrow to be read as reliable 80% ranges."
    if overridden:
        note += " This coverage is not independent of the override decision."
    return note


def write(dataset_id: str, data, evaluation: dict, folder) -> dict:
    result = build(dataset_id, data, evaluation)
    (folder / "operational.json").write_text(json.dumps(result, indent=2, default=str))
    return result
