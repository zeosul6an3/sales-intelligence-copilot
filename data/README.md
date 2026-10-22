# data/

Everything in this folder except this README is **ignored by Git**. Data is regenerated on each computer by scripts, never copied through GitHub.

| Folder | Contents | How to recreate |
|---|---|---|
| `raw/` | Official UCI download (zip, xlsx) and `download_manifest.json` with SHA-256 checksums | `uv run python scripts/download_data.py` |
| `processed/uci/` | Cleaned built-in dataset: `warehouse.duckdb`, `lines.parquet`, `metadata.json`, `quality_report.json` | `uv run python scripts/prepare_data.py` |
| `uploads/upload-<id>/` | One folder per uploaded CSV: the original file plus its own cleaned data and reports | Re-upload in the app |

The CSV upload template is available in the app (Datasets & upload → "Download the CSV template") and at `/api/uploads/template.csv`.
