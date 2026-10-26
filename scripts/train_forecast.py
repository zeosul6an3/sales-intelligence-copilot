"""Train and evaluate the weekly forecast for a dataset, in two frozen stages.

    uv run python scripts/train_forecast.py --stage selection   # validation + calibration
    uv run python scripts/train_forecast.py --stage holdout     # final holdout + future forecast
    uv run python scripts/train_forecast.py --stage operational # model the app uses (overrides)
    uv run python scripts/train_forecast.py --stage all         # all three, in order

The holdout stage refuses to run unless the selection stage used the same
configuration (configs/forecast.toml) and the same data. For the built-in
dataset, the selection and evaluation summaries are also written to
evaluation/forecast/uci/ (tracked in Git). Uploads are never written there.
"""

import argparse
import json
import sys
import time

from sic.config import PROJECT_ROOT
from sic.data.storage import BUILTIN_ID
from sic.forecast import pipeline, report

TRACKED = PROJECT_ROOT / "evaluation" / "forecast" / BUILTIN_ID
SUMMARY_KEYS_EXCLUDED = ("history", "holdout_predictions", "validation_metrics_by_series")


def progress(fraction: float, message: str) -> None:
    print(f"\r[{fraction:5.0%}] {message:<60}", end="", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", default=BUILTIN_ID)
    parser.add_argument(
        "--stage", choices=["selection", "holdout", "operational", "all"], required=True
    )
    args = parser.parse_args()

    started = time.perf_counter()
    if args.stage in ("selection", "all"):
        run = pipeline.run_selection(args.dataset, progress)
        print()
        for group, d in run["decision"].items():
            print(
                f"Selected for {group}: {d['selected']}  (mean validation WAPE "
                f"{d['mean_validation_wape'][d['selected']]:.3f})"
            )
        if args.dataset == BUILTIN_ID:
            TRACKED.mkdir(parents=True, exist_ok=True)
            summary = {k: v for k, v in run.items() if k not in SUMMARY_KEYS_EXCLUDED}
            (TRACKED / "selection.json").write_text(json.dumps(summary, indent=2, default=str))
            (TRACKED / "selection_report.md").write_text(report.markdown(run))
    if args.stage in ("holdout", "all"):
        run = pipeline.run_holdout(args.dataset, progress)
        print()
        if args.dataset == BUILTIN_ID:
            summary = {k: v for k, v in run.items() if k not in SUMMARY_KEYS_EXCLUDED}
            (TRACKED / "evaluation.json").write_text(json.dumps(summary, indent=2, default=str))
            (TRACKED / "report.md").write_text(report.markdown(run))
            print(f"Report: {TRACKED / 'report.md'}")
    if args.stage in ("operational", "all"):
        current = pipeline.run_operational(args.dataset)
        for group, g in current["groups"].items():
            print(f"Operational model for {group}: {g['model']} ({g['source']})")
        if args.dataset == BUILTIN_ID:
            TRACKED.mkdir(parents=True, exist_ok=True)
            (TRACKED / "operational.json").write_text(json.dumps(current, indent=2, default=str))
    print(f"Done in {time.perf_counter() - started:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
