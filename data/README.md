# data/

Everything in this folder except this README and `templates/` is **ignored by Git**. Data is regenerated on each computer by scripts, never copied through GitHub.

| Folder | Contents | How to recreate |
|---|---|---|
| `raw/` | Original UCI download (zip/xlsx) | `scripts/download_data.py` (Milestone 2) |
| `processed/` | Cleaned data, DuckDB files, quality reports | `scripts/prepare_data.py` (Milestone 2) |
| `uploads/<dataset_id>/` | Each uploaded CSV, isolated, with its own reports and models | Re-upload in the app |
