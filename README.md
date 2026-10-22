# Sales Intelligence Copilot

A local sales analytics application: an interactive dashboard, a forecasting model trained and evaluated on historical sales, and an AI assistant that answers business questions by calling validated analysis tools.

> **Status: Milestone 1 (environment, repository, local-model feasibility).** The dashboard, data pipeline, forecasting and assistant are not built yet. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for what is done and what is verified.

## What it will do
- Built-in example data: the UCI *Online Retail II* dataset (historical UK online retail transactions, GBP). See [DATA_LICENSE.md](DATA_LICENSE.md).
- Upload your own sales CSV, with column mapping, validation and isolated storage.
- Dashboard: gross sales, returns, net revenue, products, countries, data-quality report.
- Weekly net-revenue forecasting, comparing simple baselines against machine-learning models with time-based backtests.
- An assistant powered by **Qwen3 4B running locally in Ollama**. The model chooses tools, and the application code does every calculation. It can also produce downloadable HTML + CSV reports.

## Architecture (planned)
| Layer | Technology |
|---|---|
| Dashboard | React 19 + TypeScript, built with Vite; Apache ECharts |
| API | Python 3.13, FastAPI, served on `127.0.0.1` only |
| Data | pandas + DuckDB (one database file per dataset) |
| Forecasting | scikit-learn |
| Assistant | Ollama (local) running Qwen3 4B Instruct (`qwen3:4b-instruct-2507-q4_K_M`), with tool calling |

## Run it (macOS)
Prerequisites: uv, Node.js 24 LTS, Ollama. See [docs/setup-macos.md](docs/setup-macos.md) for verified install steps.

```bash
uv sync
npm ci --prefix frontend
uv run sic serve
```

`uv run sic serve` builds the dashboard if needed and opens `http://127.0.0.1:8000`. The page currently shows a health check for the API and the local Ollama server.

Run the tests:
```bash
uv run pytest
```

## Windows
Windows support is planned but **not yet verified**.

## AI-assisted development
This project is developed with Claude Code acting as a coding assistant under my direction. I set the requirements, reviewed the decisions and verified the results. The development history in Git reflects this honestly.
