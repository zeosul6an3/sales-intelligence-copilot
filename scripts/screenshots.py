"""Capture dashboard screenshots in light and dark mode with Playwright.

Start the app first (`uv run sic serve`). Screenshots go to docs/screenshots/
unless --out is given. Uses Playwright's bundled Chromium
(`uv run playwright install chromium` once per computer).

Usage:
    uv run python scripts/screenshots.py
    uv run python scripts/screenshots.py --width 390 --out /tmp/mobile
"""

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ("overview", "Overview", None),
    ("products", "Products", "WHITE HANGING HEART T-LIGHT HOLDER"),
    ("forecast", "Forecast", None),
    ("data-quality", "Data quality", None),
    ("datasets", "Datasets & upload", None),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "docs" / "screenshots")
    parser.add_argument("--width", type=int, default=1280)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("light", "dark"):
            page = browser.new_page(
                viewport={"width": args.width, "height": 900}, color_scheme=scheme
            )
            errors: list[str] = []
            page.on("pageerror", lambda exc, errors=errors: errors.append(str(exc)))
            page.goto(args.url)
            page.wait_for_selector(".kpi-value")
            for slug, tab, row_text in PAGES:
                page.get_by_role("tab", name=tab).click()
                if row_text:
                    page.get_by_text(row_text, exact=True).first.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(400)  # let charts finish drawing
                target = args.out / f"{slug}-{scheme}.png"
                page.screenshot(path=str(target), full_page=True)
                print(f"saved {target}")
            if errors:
                print(f"Page errors in {scheme} mode: {errors}")
                return 1
            page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
