"""Memory check: one assistant model loaded while the app is running.

Re-run this whenever the app grows (dashboard in Milestone 2, assistant in
Milestone 4) to see whether the computer stays out of memory pressure.

Steps:
  1. Confirm the app answers at --app-url and unload every Ollama model.
  2. Record a baseline memory snapshot.
  3. Load the configured assistant model at --num-ctx and send --requests
     prompts of agent-like size, then record memory again.

Writes JSON and Markdown to evaluation/memory/.

Usage (start the app first with `uv run sic serve`):
    uv run python scripts/memory_check.py
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_feasibility import (  # noqa: E402
    SEED,
    Ollama,
    fmt,
    machine_description,
    memory_snapshot,
    ollama_ps_text,
    speed_prompt,
    timing_fields,
)

from sic.config import get_settings  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "memory"


def top_apps(limit: int = 6) -> list[dict]:
    """Largest memory users, summed per application (names only, macOS)."""
    try:
        output = subprocess.run(
            ["ps", "-axo", "rss=,comm="], capture_output=True, text=True, timeout=10
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    totals: dict[str, int] = {}
    for line in output.splitlines():
        rss, _, command = line.strip().partition(" ")
        if not rss.isdigit():
            continue
        name = command.split(".app/")[0] + ".app" if ".app/" in command else command
        name = name.rsplit("/", 1)[-1]
        totals[name] = totals.get(name, 0) + int(rss)
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [{"app": name, "rss_mb": round(kb / 1024)} for name, kb in ranked]


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=settings.ollama_model)
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--requests", type=int, default=5)
    parser.add_argument("--app-url", default=f"http://127.0.0.1:{settings.port}")
    args = parser.parse_args()

    try:
        health = httpx.get(f"{args.app_url}/api/health", timeout=5).json()
    except httpx.HTTPError:
        print(f"The app is not answering at {args.app_url}. Start it with `uv run sic serve`.")
        return 1

    ollama = Ollama(settings.ollama_url)
    for entry in ollama.get("/api/ps").get("models", []):
        ollama.unload(entry["name"])
    time.sleep(2)
    baseline = memory_snapshot()
    baseline_apps = top_apps()

    runs = []
    for i in range(args.requests):
        response, wall_s = ollama.chat(
            {
                "model": args.model,
                "messages": [{"role": "user", "content": speed_prompt(i)}],
                "options": {"seed": SEED, "num_ctx": args.num_ctx, "num_predict": 256},
            }
        )
        runs.append({"wall_s": round(wall_s, 2), **timing_fields(response)})

    loaded_models = ollama.get("/api/ps").get("models", [])
    data = {
        "run_at_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "machine": machine_description(),
        "app_health": health,
        "model": args.model,
        "num_ctx": args.num_ctx,
        "models_loaded": [
            {
                "name": m["name"],
                "size_gb": round(m["size"] / 1e9, 2),
                "gpu_percent": round(m["size_vram"] / m["size"] * 100) if m["size"] else None,
                "context_length": m.get("context_length"),
            }
            for m in loaded_models
        ],
        "ollama_ps": ollama_ps_text(),
        "baseline": baseline,
        "baseline_top_apps": baseline_apps,
        "after_requests": memory_snapshot(),
        "after_top_apps": top_apps(),
        "runs": runs,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    machine = data["machine"]
    stem = f"{datetime.now().strftime('%Y-%m-%d')}_{machine['os'].lower()}-{machine['arch']}"
    (OUTPUT_DIR / f"{stem}.json").write_text(json.dumps(data, indent=2, default=str))
    (OUTPUT_DIR / f"{stem}.md").write_text(markdown_report(data))
    print(f"Wrote {OUTPUT_DIR / (stem + '.md')}")
    return 0


def markdown_report(data: dict) -> str:
    before, after = data["baseline"], data["after_requests"]
    lines = [
        "# Memory check: one model loaded with the app running",
        "",
        f"- Run at (UTC): {data['run_at_utc']}",
        f"- Machine: {data['machine']}",
        f"- App health: {data['app_health']}",
        f"- Model: `{data['model']}` at num_ctx {data['num_ctx']}, {len(data['runs'])} requests",
        "",
        "| Measure | Baseline (no model loaded) | After requests |",
        "|---|---|---|",
        f"| macOS memory pressure | {before.get('pressure_level')} | "
        f"{after.get('pressure_level')} |",
        f"| System free % | {fmt(before.get('system_free_percent'))} | "
        f"{fmt(after.get('system_free_percent'))} |",
        f"| Swap used (MB) | {fmt(before.get('swap_used_mb'))} | "
        f"{fmt(after.get('swap_used_mb'))} |",
        "",
        "Models loaded after the requests:",
        "",
    ]
    lines += [
        f"- `{m['name']}`: {m['size_gb']} GB, {fmt(m['gpu_percent'])}% GPU, "
        f"context {fmt(m['context_length'])}"
        for m in data["models_loaded"]
    ]
    gen = [r["generation_tokens_per_s"] for r in data["runs"] if r["generation_tokens_per_s"]]
    if gen:
        lines += ["", f"Generation speed across requests: {min(gen)}–{max(gen)} tokens/s."]
    lines += ["", "Largest memory users after the requests (summed per app):", ""]
    lines += [f"- {a['app']}: {a['rss_mb']} MB" for a in data["after_top_apps"]]
    lines += [
        "",
        "Note: on Apple Silicon, GPU memory is shared with the system, so the model's "
        "memory may not appear fully in per-app figures. The loaded size above is "
        "Ollama's own figure.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
