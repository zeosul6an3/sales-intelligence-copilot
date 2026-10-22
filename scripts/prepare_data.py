"""Clean and classify the downloaded UCI workbook into the built-in dataset.

Run scripts/download_data.py first. Output goes to data/processed/uci/
(ignored by Git). Re-running produces the same row counts on any computer.

Usage:
    uv run python scripts/prepare_data.py
"""

import sys
import time
from pathlib import Path

from sic.data import uci

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = PROJECT_ROOT / "data" / "raw" / "online_retail_II.xlsx"


def main() -> int:
    if not WORKBOOK.is_file():
        print(f"{WORKBOOK} not found. Run: uv run python scripts/download_data.py")
        return 1
    started = time.perf_counter()
    quality = uci.build(WORKBOOK)
    flow = quality["row_flow"]
    print(f"Rows read:               {flow['rows_read']:>10,}")
    print(f"Sheet overlap removed:   {flow['sheet_overlap_removed']:>10,}")
    print(f"Rows kept and classified:{flow['rows_kept']:>10,}")
    for rule in quality["rules"]:
        print(f"  {rule['line_type']:<24}{rule['rows']:>10,}   £{rule['value']:>15,.2f}")
    print(f"Reconciles: {flow['reconciles']}   ({time.perf_counter() - started:.1f} s)")
    return 0 if flow["reconciles"] else 1


if __name__ == "__main__":
    sys.exit(main())
