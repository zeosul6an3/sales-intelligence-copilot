"""End-to-end check of the CSV upload journey in a real browser (Playwright).

Uploads a small CSV with deliberate problems, checks the validation screen,
imports it, confirms the dashboard switches to the new dataset with the
expected net revenue, then deletes it again. Start the app first.

Usage:
    uv run python scripts/e2e_upload_check.py [--screenshot docs/screenshots/upload-check-light.png]
"""

import argparse
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

CSV = """Order No,Order Date,SKU,Item,Qty,Price,Client,Country
5001,2024-03-04,MUG-1,Blue mug,4,4.50,K1,United Kingdom
5001,2024-03-04,TOWEL-2,Tea towel,10,2.25,K1,United Kingdom
5002,2024-03-06,MUG-1,Blue mug,2,4.50,,France
5003,not a date,MUG-1,Blue mug,1,4.50,K2,France
R5004,2024-03-08,TOWEL-2,Tea towel,-2,2.25,K1,United Kingdom
"""
# Net revenue = 18 + 22.50 + 9 - 4.50 = £45.00 (the undated row is excluded)
EXPECTED_NET = "£45"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        path = Path(tmp) / "shop_sales.csv"
        path.write_text(CSV, encoding="utf-8")
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("dialog", lambda dialog: dialog.accept())

        page.goto(args.url)
        page.get_by_role("tab", name="Datasets & upload").click()
        page.locator("input[type=file]").set_input_files(str(path))
        expect(page.get_by_text("Suggested matches are filled in")).to_be_visible()
        page.get_by_role("button", name="Check file").click()
        expect(page.get_by_text("Check results")).to_be_visible()
        expect(page.get_by_text("Dates that could not be read; rows excluded.")).to_be_visible()
        expect(page.get_by_text("5 rows read · 4 usable · 1 excluded")).to_be_visible()
        print("validation screen: OK (1 unreadable date reported, 4 usable rows)")
        if args.screenshot:
            page.screenshot(path=str(args.screenshot), full_page=True)
            print(f"saved {args.screenshot}")

        page.get_by_role("button", name="Import dataset").click()
        expect(page.get_by_role("tab", name="Overview")).to_have_attribute("aria-selected", "true")
        net_tile = page.locator(".kpi").filter(has_text="Net revenue").locator(".kpi-value")
        expect(net_tile).to_have_text(EXPECTED_NET)
        print(f"imported and opened: net revenue tile shows {EXPECTED_NET}: OK")

        page.get_by_role("tab", name="Datasets & upload").click()
        page.get_by_role("button", name="Delete").click()
        expect(page.get_by_role("button", name="Delete")).to_have_count(0)
        print("deleted again: OK")
        browser.close()
    if errors:
        print(f"Page errors: {errors}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
