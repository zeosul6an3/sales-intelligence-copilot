"""Markdown report of a forecasting run (selection, and holdout once available)."""

LABELS = {
    "naive": "Naive (last week)",
    "moving_average_4": "Moving average (4 weeks)",
    "seasonal_naive": "Seasonal naive (same week last year)",
    "ridge": "Ridge (pooled)",
    "hist_gradient_boosting": "HistGradientBoosting (pooled)",
    "hist_gradient_boosting_lag52": "HistGradientBoosting + 52-week lag (experiment)",
}
GROUP_LABELS = {"total": "Business total", "products": "Top products (pooled)"}


def fmt(cell: dict | None, kind: str) -> str:
    if not cell or cell.get("value") is None:
        return f"n/a ({cell['reason']})" if cell else "n/a"
    v = cell["value"]
    if kind == "money":
        return f"£{v:,.0f}"
    if kind == "pct":
        return f"{v:.1%}"
    return f"{v:+.1%}"


def _horizon_rows(table: dict, group: str, models: list[str], horizons: dict) -> list[str]:
    lines = [
        "| Model | h | n | MAE | RMSE | WAPE | Bias | Skill vs naive | Skill vs seasonal naive |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model in models:
        for h, m in table.get(model, {}).get(group, {}).items():
            tag = " (provisional)" if horizons[str(h)]["provisional"] else ""
            lines.append(
                f"| {LABELS.get(model, model)} | {h}{tag} | {m['n']} | {fmt(m['mae'], 'money')} "
                f"| {fmt(m['rmse'], 'money')} | {fmt(m['wape'], 'pct')} | "
                f"{fmt(m['bias'], 'signed')} | {fmt(m['skill_vs_naive'], 'signed')} | "
                f"{fmt(m['skill_vs_seasonal_naive'], 'signed')} |"
            )
    return lines


def _mean_wape(table: dict, model: str, group: str) -> str:
    values = [m["wape"]["value"] for m in table.get(model, {}).get(group, {}).values()]
    if not values or any(v is None for v in values):
        return "n/a"
    return f"{sum(values) / len(values):.1%}"


def markdown(run: dict) -> str:
    models = list(LABELS)
    out = [
        f"# Forecast evaluation: {run['dataset_id']}",
        "",
        f"- Target: **{run['target']['label']}**. {run['target']['description']}",
        f"- Weeks: {run['target']['week']}. Calendar features: `{run['calendar']}`.",
        f"- Config SHA-256: `{run['config_sha256']}`",
        f"- Selection stage: {run.get('selection_created_at_utc', run.get('created_at_utc'))} "
        f"UTC, commit `{(run.get('selection_code') or run.get('code', {})).get('commit')}`",
    ]
    if "holdout_created_at_utc" in run:
        out.append(
            f"- Holdout stage: {run['holdout_created_at_utc']} UTC, commit "
            f"`{run['holdout_code']['commit']}`"
        )
        out += ["", f"> {run['holdout_note']}"]
    out += ["", "## Windows", "", "| Window | Weeks | From | To |", "|---|---|---|---|"]
    for name, w in run["windows"].items():
        out.append(f"| {name} | {w['weeks']} ({w['count']}) | {w['from']} | {w['to']} |")

    out += ["", "## Forecasting-only corrections", ""]
    for c in run["corrections"] or []:
        out.append(
            f"- **{c['id']}**: −£{c['amount']:,.2f} in the week of {c['week_start']} "
            f"(product {c['product_id']}, {c['product_name']}). Applied to: "
            f"{', '.join(c['applied_to'])}. Business total that week: "
            f"£{c['total_week_reported']:,.2f} reported → £{c['total_week_adjusted']:,.2f} "
            f"adjusted. Source rows: sale {c['source_rows']['sale']['invoice_id']} "
            f"(row {c['source_rows']['sale']['source_row']}), reversal "
            f"{c['source_rows']['reversal']['invoice_id']} "
            f"(row {c['source_rows']['reversal']['source_row']})."
        )
    if not run["corrections"]:
        out.append("None.")

    out += [
        "",
        "## Model selection (validation)",
        "",
        "Rule: lowest WAPE averaged with equal weight over horizons 1–8; products pooled "
        "(revenue-weighted). Ties within 0.5 percentage points go to the simpler model. "
        "The 52-week-lag model is an experiment and is never eligible.",
        "",
        "| Model | Business total | Top products |",
        "|---|---:|---:|",
    ]
    for model in models:
        out.append(
            f"| {LABELS[model]} | {_mean_wape(run['validation_metrics'], model, 'total')} "
            f"| {_mean_wape(run['validation_metrics'], model, 'products')} |"
        )
    out.append("")
    for group, d in run["decision"].items():
        out.append(
            f"- **{GROUP_LABELS[group]}: {LABELS.get(d['selected'], d['selected'])}**"
            + (" (tie rule applied)" if d.get("tie_rule_applied") else "")
        )

    if "holdout_metrics" in run:
        out += ["", "## Final holdout", ""]
        out += [
            "| Model | Business total, mean WAPE | Top products, mean WAPE |",
            "|---|---:|---:|",
        ]
        for model in models:
            out.append(
                f"| {LABELS[model]} | {_mean_wape(run['holdout_metrics'], model, 'total')} "
                f"| {_mean_wape(run['holdout_metrics'], model, 'products')} |"
            )
        for group in ("total", "products"):
            out += ["", f"### {GROUP_LABELS[group]}: holdout by horizon", ""]
            out += _horizon_rows(run["holdout_metrics"], group, models, run["horizons"])
        out += [
            "",
            "### 80% interval coverage on the holdout (selected models)",
            "",
            "| Group | h | Calibration n | Holdout n | Coverage |",
            "|---|---:|---:|---:|---:|",
        ]
        for group, by_h in run["holdout_coverage"].items():
            for h, c in by_h.items():
                cal_n = run["calibration_quantiles"][group][str(h)]["n"]
                tag = " (provisional)" if run["horizons"][str(h)]["provisional"] else ""
                out.append(
                    f"| {GROUP_LABELS[group]} | {h}{tag} | {cal_n} | {c['n']} | "
                    f"{c['coverage']:.0%} |"
                )
        out += [
            "",
            "### Individual products: holdout WAPE (mean over horizons)",
            "",
            "| Product | Selected model | Seasonal naive | Naive |",
            "|---|---:|---:|---:|",
        ]
        selected = run["decision"]["products"]["selected"]
        names = {s["id"]: s["name"] for s in run["series"]}
        for sid in [s["id"] for s in run["series"] if s["id"] != "total"]:
            row = []
            for model in (selected, "seasonal_naive", "naive"):
                vals = [
                    m["wape"]["value"]
                    for m in run["holdout_metrics_by_series"].get(model, {}).get(sid, {}).values()
                ]
                row.append("n/a" if not vals or None in vals else f"{sum(vals) / len(vals):.1%}")
            out.append(f"| {sid} {names[sid]} | {row[0]} | {row[1]} | {row[2]} |")
    out.append("")
    return "\n".join(out)
