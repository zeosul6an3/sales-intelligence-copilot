"""Download the UCI Online Retail II dataset from its official source.

Saves the zip and the extracted workbook to data/raw/ (ignored by Git) and
writes data/raw/download_manifest.json with the source URL, file sizes and
SHA-256 checksums, so every computer can confirm it has the identical file.

Usage:
    uv run python scripts/download_data.py           # skips if already present
    uv run python scripts/download_data.py --force   # download again
"""

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/502/online+retail+ii"
ZIP_PATH = RAW_DIR / "online_retail_ii.zip"
MANIFEST_PATH = RAW_DIR / "download_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path) -> None:
    partial = target.with_suffix(".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    partial.replace(target)


def safe_extract(zip_path: Path, target_dir: Path) -> list[Path]:
    """Extract only plain files whose names cannot escape target_dir."""
    extracted = []
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if member.is_dir() or name.is_absolute() or ".." in name.parts:
                continue
            destination = target_dir / name.name
            with archive.open(member) as source, destination.open("wb") as handle:
                handle.write(source.read())
            extracted.append(destination)
    return extracted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="Download even if present")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists() and MANIFEST_PATH.exists() and not args.force:
        print(f"Already downloaded: {ZIP_PATH}. Use --force to download again.")
        return 0

    print(f"Downloading {SOURCE_URL} ...")
    download(SOURCE_URL, ZIP_PATH)
    files = safe_extract(ZIP_PATH, RAW_DIR)
    workbooks = [f for f in files if f.suffix.lower() == ".xlsx"]
    if not workbooks:
        print("The download did not contain an .xlsx workbook.")
        return 1

    manifest = {
        "dataset": "Online Retail II",
        "source_page": SOURCE_PAGE,
        "source_url": SOURCE_URL,
        "licence": "CC BY 4.0",
        "citation": (
            "Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. "
            "https://doi.org/10.24432/C5CG6D"
        ),
        "downloaded_at_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "files": [
            {"name": f.name, "bytes": f.stat().st_size, "sha256": sha256(f)}
            for f in [ZIP_PATH, *files]
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    for entry in manifest["files"]:
        print(f"  {entry['name']}: {entry['bytes']:,} bytes, sha256 {entry['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
