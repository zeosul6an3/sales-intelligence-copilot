# Project status

_Last updated: 2026-10-26 (Milestone 4 plan revision 2 proposed; not implemented)._
Read this first when resuming work on any computer.

## Current milestone
**Milestone 3 (forecasting): complete on macOS, awaiting review.** Milestone 4 (assistant) has **not** started.

## Completed: Milestone 3
- **Approved decisions implemented:**
  - Option A forecasting-only correction.
  - Dashboard note for the picnic basket.
  - Christmas closure weeks kept as £0 and flagged "inferred Christmas closure".
  - Holiday-calendar inputs from a published list.
  - Total + top 20 products, horizons 1–8.
- **Frozen design:** [configs/forecast.toml](configs/forecast.toml), committed (`685e1b4`) before any model ran on the data. The pipeline has a two-stage guard: the holdout stage refuses to run if the config or data changed after selection.
- **Code:**
  - [backend/sic/forecast/](backend/sic/forecast/): calendar, series and corrections, models, evaluation, pipeline, report.
  - [backend/sic/jobs.py](backend/sic/jobs.py): background job runner with progress.
  - [backend/sic/api/forecast.py](backend/sic/api/forecast.py).
  - [scripts/train_forecast.py](scripts/train_forecast.py).
- **Forecast page:**
  - Target explanation (adjusted vs reported).
  - Training with a progress bar.
  - Future forecast with 80% range and a seasonal-naive comparison line.
  - Holdout backtest by horizon.
  - Metric tables with n and n/a reasons.
  - Automatic warnings.
- **Dashboard:**
  - A visible picnic-basket note on Overview/Products when that week or product is in view, linking to full details (5 transactions) on Data quality.
  - Weekly zeros explained: "inferred Christmas closure" vs "business was trading; no recorded sales".
- **Uploads:** train on their own data with the same rules (minimum 70 complete weeks), month-only calendar, artifacts in the upload's ignored folder.
- **Write-up:** [docs/forecasting.md](docs/forecasting.md). Full metrics: [evaluation/forecast/uci/report.md](evaluation/forecast/uci/report.md).

### Operational override (2026-10-26, user decision)
- **What changed:** the built-in **business total** now uses **seasonal naive** as its operational default, recorded in [configs/forecast_overrides.toml](configs/forecast_overrides.toml) as **chosen after reviewing holdout results** (`independent_evaluation = false`).
- **What did not change:**
  - The frozen design: `configs/forecast.toml`, whose SHA-256 still matches the selection record (tested).
  - The frozen validation selection (HistGradientBoosting, kept on record and drawn as a comparison line).
  - The evaluation history in `evaluation/forecast/uci/`.
- **The 9.5% holdout WAPE is not an independent evaluation** of this decision.
- **Seasonal naive's own nominal 80% ranges:** calibrated on its own calibration-window residuals (n = 12 → 5). Holdout coverage was **58–71%**, so they are shown as too narrow, and that coverage is not independent either.
- **Products:** keep the frozen selection (4-week moving average).
- **Uploads:** cannot be overridden (enforced and tested); they use their own selection.
- **Where it shows:** the override is written to `operational.json` (tracked copy: [evaluation/forecast/uci/operational.json](evaluation/forecast/uci/operational.json)). The Forecast page and fresh forecasts use it, with a visible override notice.

### Results (built-in data)
| Group | Selected on validation | Validation mean WAPE | Holdout mean WAPE | Best on holdout |
|---|---|---:|---:|---|
| Business total | HistGradientBoosting | 19.3% | **24.6%** | Seasonal naive, 9.5% |
| Top 20 products | 4-week moving average (baseline) | 50.7% | 50.4% | Same model |

- **Business total, 80% intervals:** covered 0–44% of holdout weeks (calibration n = 12 → 5). Far too narrow.
- **Products, 80% intervals:** 57–80% coverage (n = 240 → 100).
- **Integrity record:**
  - The holdout is **not completely unseen**: its aggregate weekly totals were inspected during the feasibility review.
  - The first holdout run crashed while saving the model file (pickling error), before any holdout metric was written or shown. Only the serialization was fixed (`55b4553`).
  - The final clean re-run (`14ab70a`) reproduced the metrics exactly.

## Milestone 3 feasibility review
- **Feasibility review:** [docs/forecasting_feasibility_review.md](docs/forecasting_feasibility_review.md). Reproducible with [scripts/forecast_feasibility.py](scripts/forecast_feasibility.py), which writes [evaluation/forecast_feasibility/review.json](evaluation/forecast_feasibility/review.json) and asserts the window dates.
- **Key findings:**
  - **Weeks:** 104 complete weeks (7 Dec 2009 → 4 Dec 2011). Two weeks have no records of any kind (the Christmas closures, weeks 4 and 56). No missing data was detected: every non-trading weekday matches a UK public holiday or the Christmas closure.
  - **Proposed windows:** product selection weeks 1–60; validation targets 61–80 (31 Jan–19 Jun 2011); calibration targets 81–92 (20 Jun–11 Sep 2011); final holdout 93–104 (12 Sep–4 Dec 2011).
  - **Training rows per series:** 52 → 84 with short lags; only 8 → 40 with a 52-week lag. So 52-week information comes from the seasonal-naive baseline, plus one pooled experiment.
  - **Top 20 products,** selected on weeks 1–60 only: 834 of 4,046 products are eligible; the top 20 cover 9.7% of net product revenue.
  - **Picnic-basket case:** quantity 60 was keyed for one £649.50 pack; the £38,970 reversal was booked as a Manual credit, not a product return. It inflates week 79 (in validation) by 18.4%, and lifts product 22502 to #9 in the dashboard's last-12-months top 10 (#158 without it). It is the only large exact match.
- **Wording fix:** every dashboard label now says **"Net product revenue"** (10 places plus the metric definition). The calculation is unchanged; the API field is still `net_revenue`.

## Completed: Milestone 2
- **Data acquisition:** [scripts/download_data.py](scripts/download_data.py) downloads the official UCI zip and records checksums.
  - zip `572e3627…7bfb`
  - workbook `bcbe73b3…2df2e980`
- **Inspection:** both sheets were inspected. The evidence is reproducible with [scripts/profile_raw_data.py](scripts/profile_raw_data.py), and the output is saved in [docs/data_profile_uci.md](docs/data_profile_uci.md).
- **Cleaning pipeline:** [backend/sic/data/uci.py](backend/sic/data/uci.py), run with [scripts/prepare_data.py](scripts/prepare_data.py) in ~7 s.
  - 1,067,371 rows read; 22,523 identical sheet-overlap rows removed after a null-safe comparison.
  - 1,044,848 rows kept, each with exactly one line type; 0 unclassified; the counts reconcile.
  - Rules, evidence and counts: [docs/data_cleaning.md](docs/data_cleaning.md). Columns: [docs/data_dictionary.md](docs/data_dictionary.md).
- **Storage:** one folder and DuckDB file per dataset, opened read-only by the API. Dataset IDs are validated against a strict pattern ([backend/sic/data/storage.py](backend/sic/data/storage.py)).
- **Metrics layer:** [backend/sic/metrics/](backend/sic/metrics/). Parametrised SQL provides KPIs, period comparison, weekly/monthly series with partial-period flags, product ranking and search, countries, and "other lines". Named periods (last complete month/week, etc.) are resolved in code.
- **API:** dataset, metrics, quality, definitions and upload endpoints ([backend/sic/api/](backend/sic/api/)).
- **Dashboard** (React + ECharts, light/dark):
  - Overview: KPI tiles with comparison, trend chart with table view, top products, countries, other lines.
  - Products: search, sort, per-product trend.
  - Data quality: row flow, rules, flags, unusual lines, definitions.
  - Datasets & upload.
  - Screenshots: [docs/screenshots/](docs/screenshots/).
- **CSV upload:**
  - Downloadable template and automatic column-mapping suggestions.
  - Validation with row-numbered examples: unreadable dates, non-numeric values, missing IDs, ambiguous or conflicting day/month order, mixed currency.
  - 50-row preview; each upload is stored in its own folder; delete option.

## Completed: Milestone 1
- **Tools installed** by the user from official sources and verified on the Mac. Exact steps: [docs/setup-macos.md](docs/setup-macos.md).
  - uv 0.13.5
  - Node.js v24.22.1 LTS (npm 11.19.1)
  - GitHub CLI 2.103.0
  - Ollama 0.40.8
- **Git**
  - Repository initialised on `main`.
  - Author `zeosul6an3` with the GitHub no-reply email, set **locally only** (no global Git config exists).
  - GitHub credentials come from `gh`, also configured locally.
- **GitHub**: repository https://github.com/zeosul6an3/sales-intelligence-copilot. It was created private; it has been **public since 2026-10-26** by the owner's own choice (see Decisions).
- **Backend skeleton**: FastAPI app (Python 3.13.17) with `/api/health`, which reports API and Ollama status.
  - `uv run sic serve` builds the dashboard if needed and serves it on 127.0.0.1:8000.
- **Dashboard skeleton**: React 19 + TypeScript 6 + Vite 8, based on the official template. It shows a status page, with colour tokens for light and dark mode.
- **Qwen models pulled**, with digests matching the official registry:
  - `qwen3:4b` (`359d7dd4bcda`)
  - `qwen3:4b-instruct-2507-q4_K_M` (`0edcdef34593`)
- **Feasibility benchmark**: [scripts/llm_feasibility.py](scripts/llm_feasibility.py), with results in [evaluation/llm_feasibility/](evaluation/llm_feasibility/2026-10-22_darwin-arm64.md).
- **Memory check**: [scripts/memory_check.py](scripts/memory_check.py) (one model plus the running app), with results in [evaluation/memory/](evaluation/memory/2026-10-22_darwin-arm64.md).

## Checks performed (actual results)
### Milestone 3
| Check | Result |
|---|---|
| `uv run pytest` (after override) | **72 passed**. New tests cover: the override applies only to built-in data; invalid overrides are rejected; the frozen config SHA is unchanged; seasonal naive's own intervals differ from HGB's; the fresh total forecast equals the same week last year; uploads use their own frozen selection |
| `uv run pytest` (before override) | **64 passed**. They cover: future-data perturbation for all 6 models; window boundaries; horizon/provisional rules; metrics including n/a; the selection rule (a baseline can win, ties go to the simpler model, the experiment is never selected); calendar; exact/unique/too-late correction matching; the real-data correction touching one week only; closure flags; model save/reload; upload training through the job API; ineligible short uploads |
| Selection recorded before the holdout | Selection commit `685e1b4` (clean); selection results committed (`d89d3a1`) before any holdout run |
| Holdout re-run reproducibility | `report.md` identical apart from the run timestamp and commit |
| Browser: upload → Forecast → Train | Progress bar shown; finished; upload selected Ridge for its total on its own validation; month-only calendar; no page errors; deleted with no leftovers |
| Browser: picnic note | Shown for periods including 6 Jun 2011, hidden for November 2011; "Details" opens 5 transactions |
| Bank-holiday list consistency | All 17 weekday bank holidays in the data range had no trading; every non-trading weekday is a bank holiday or 24 Dec–3 Jan |
| Upload e2e (`scripts/e2e_upload_check.py`) and screenshots | Pass; light/dark screenshots retaken, including Forecast |

### Milestone 3 (review stage)
| Check | Result |
|---|---|
| Window assertions in `forecast_feasibility.py` | Pass: selection before validation; segments disjoint; calibration ends before holdout; holdout ≥ horizon |
| After the label change | `uv run pytest` 44 passed; browser upload check passed (tile labelled "Net product revenue" shows £45); screenshots retaken |

### Milestone 2
| Check | Result |
|---|---|
| `uv run pytest` | **44 passed**, including the two real-data tests (not skipped) |
| Metrics vs hand calculation | Synthetic dataset: KPIs, filters, weekly series (with empty and partial weeks), rankings and comparison all match hand-calculated values |
| Metrics vs independent pandas (real UCI data) | Match for all data, Germany only, last complete month, previous complete month and last complete week |
| Pinned UCI totals | Gross £19,700,954.46 · returns £719,692.94 · net £18,981,261.52 · 1,044,848 rows (tied to the file's SHA-256) |
| Cleaning rules | One synthetic row per rule; a negative quantity at a non-zero price stays unclassified (not assumed a stock note); a changed overlap row stops the pipeline |
| Dataset isolation | Two uploads + built-in: each returns only its own totals; the built-in file is byte-identical after uploads; malformed IDs (`../`, upper case, wrong length) rejected; deleting one upload leaves the others intact |
| Upload validation | Bad dates, non-numeric values (decimal comma rejected, not guessed), missing IDs, thousands separators, date-order conflict, mixed/mismatched currency, empty and Windows-encoded files, formula/SQL-like text stored as plain data |
| Browser upload journey (Playwright, [scripts/e2e_upload_check.py](scripts/e2e_upload_check.py)) | Pass: non-standard headers auto-mapped; 1 unreadable date reported (4 of 5 rows usable); import opens the new dataset with net revenue £45 (hand-calculated); delete leaves no files |
| Dashboard review | Screenshots of all four pages in light and dark mode at 1280 px checked by eye; no page errors |
| Memory with real dashboard data + instruct model loaded | Pressure **normal** (free 84% → 58%; app process 291 MB). Single run: [report](evaluation/memory/2026-10-22_darwin-arm64_m2-dashboard.md) |

### Milestone 1
| Check | Result |
|---|---|
| `uv run pytest` | 3 passed (health endpoint, Ollama-down handling, localhost defaults) |
| `uv run ruff check` / `ruff format --check` | Clean |
| `npm ci` + `npm run build` | Succeeded; 0 vulnerabilities reported by `npm audit --omit=dev` |
| Server binding | Listens on `127.0.0.1:8000` only; a request to the Mac's network address was refused |
| Dashboard rendering | Checked in the browser in both light and dark mode |
| Qwen speed (M3, 8k context, medians of 5 runs) | ~29 tokens/s generation, ~320 tokens/s prompt processing, under 2.1 s cold load, **100% GPU** |
| Qwen memory | Model uses 3.2 GB at 4k context and 3.9 GB at 8k. macOS memory pressure reached **"warning"** after runs (FAIL against the proposed bar; see known issues) |
| Tool calling, 16 questions with mock tools | Instruct: 88% tool choice, 81% correct arguments, median 4.5 s per question. Thinking (`think=true`): 94% / 94%, median 34 s, max 161 s |
| `think=false` on `qwen3:4b` | **Does not suppress reasoning**: the reasoning moves into the visible answer (16 of 16 answers). Not usable |
| Memory retest: app running, dashboard open, only the instruct model loaded (8k context, 5 requests) | Pressure stayed **normal** (free memory 83% → 60%, swap unchanged). Model 3.88 GB, 100% GPU, 28.1–28.3 tok/s. This is a single run with lighter background load than the benchmark (Chrome ~2.1 GB vs ~3.5 GB), so it does not close the memory issue. Report: [evaluation/memory/](evaluation/memory/2026-10-22_darwin-arm64.md) |

## Decisions
- Architecture, data policies, forecasting and agent design: see the approved plan, summarised in the README.
- **Repository visibility: public, explicitly authorized by the owner on 2026-10-26.**
  - The owner made it public themself, and it must **not** be switched back to private.
  - This supersedes the earlier "private permanently" requirement.
  - Credentials, uploaded datasets and their reports/models, downloaded and processed data, and local runtime artifacts stay outside Git (enforced by `.gitignore`).
- **No code licence** has been chosen yet. A public repository without a licence can be viewed, but others have no right to reuse the code. To be discussed separately.
- Git identity and credentials are configured per repository only.
- GitHub CLI was installed from the release's signed arm64 zip into `~/.local/bin`, because the universal `.pkg` was unsigned and Gatekeeper blocked it.
- TypeScript 6 (as pinned by the official Vite template) instead of TypeScript 7.
- DuckDB pinned below 2.0 (`>=1.5.6,<2`; 2.0.0 was released 2026-10-21). Installed: 1.5.6.
- **Data decisions by the user (Milestone 2):**
  - **Exact duplicates:** kept as genuine lines and flagged (11,812 copies, £54,228 net).
  - **Manual (`M`) lines:** reported separately, not in product revenue.
  - **Net revenue:** products only (product sales − product returns). Shipping, fees, discounts and adjustments are shown as "other lines".
  - **Huge cancelled orders:** kept and flagged (|line value| ≥ £10,000 rule).
- **Unusual-line rule:** |value| ≥ £10,000 for UCI (about 4× its 99.99th percentile). Uploads use the same relative rule.
- **Previous period for comparisons:** whole calendar months compare with the preceding months; other ranges with the same number of days before them.
- **Charts:** ECharts with the validated reference palette (single-series charts, table views, partial periods drawn lighter). Playwright (Python) for browser checks and screenshots.
### Default assistant model (decided by the user, 2026-10-22)
**`qwen3:4b-instruct-2507-q4_K_M`**, the tested instruct (non-thinking) variant.

| Property | Value |
|---|---|
| Ollama tag | `qwen3:4b-instruct-2507-q4_K_M` (same model as `qwen3:4b-instruct`) |
| Digest | `0edcdef34593` (matches the official Ollama registry) |
| Parameters / quantization | 4.0B / Q4_K_M; 2.5 GB download |
| Loaded size | 3.18 GB at 4k context, 3.88 GB at 8k; 100% GPU (Metal) |
| Speed (8k context, medians of 5 runs) | 28.3 tok/s generation, 318.3 tok/s prompt, 0.8 s warm load (1.9 s cold at 4k) |
| Tool test, 16 regression questions with mock tools | 88% tool choice, 81% correct arguments, 94% valid arguments, median 4.5 s and max 10.2 s per question, 0 of 16 answers showed reasoning |
| Licence | Apache 2.0 |

- **Where it's set:** `backend/sic/config.py` (`SIC_OLLAMA_MODEL` overrides it).
- **Full benchmark:** [evaluation/llm_feasibility/2026-10-22_darwin-arm64.md](evaluation/llm_feasibility/2026-10-22_darwin-arm64.md)

**Evaluated alternative, kept for later consideration:** `qwen3:4b` (thinking, digest `359d7dd4bcda`) with `think=true`.
- Results: 94% tool choice, 94% arguments, but a median of 34 s and a maximum of 161 s per question.
- It stays installed. Whether to offer it (for example as a slower "deep analysis" mode) is **not decided**.
- `qwen3:4b` with `think=false` is **rejected**, because its reasoning leaks into the visible answer.

### Completion criteria for the assistant (Milestone 4)
The assistant is **not complete** until each of these is implemented **and verified**:
1. **Business definitions:** gross sales, returns (a £ value) and net revenue are defined explicitly for the model and match the metrics layer. Questions like "what did returns cost us" are answered with the returns metric, not refused.
2. **Comparison intent:**
   - Presets such as "last two complete months" resolve chronologically.
   - An **explicitly requested baseline is never reordered** ("October relative to November" ≠ "November relative to October").
   - Results state baseline and comparison dates.
   - Both directions are tested.
3. **Dataset-specific forecast limits:**
   - Only the active dataset's evaluated series and supported horizons are accepted, otherwise the request is rejected with a clear explanation.
   - No built-in top-20 restriction is hard-coded for uploads.
   - Only limitations that apply to that dataset and series are returned: the UCI correction and override never appear for uploads or product forecasts.
4. **Tool-based calculations:** every figure in an answer comes from a tool result, and the model does no arithmetic. Meaning-level checks confirm the metric, dataset, product, currency, filters and period.

**Evaluation requirement:**
- Measure these changes on the 16 regression questions, an AI-written held-out set frozen before tuning, and **5 private questions written by the user**, given to Claude only after prompts, tools and settings are frozen.
- Report each set separately.
- **Seeds:** the three seeds are **repeated measurements**. Report per-seed accuracy over unique questions and repeat consistency; never treat repeats as independent questions.
- **Reviews:** Claude's review is labelled **AI-assisted**, and a sample of answers is provided for the user's own review.
- Validation and grounding checks reduce errors but **do not guarantee correctness**. The reports must say so.

## Pending decisions (need the user)
1. **Code licence:** to be discussed separately.

### Decided (Milestone 3)
- Business total: seasonal naive as the operational default (override chosen after the holdout; documented, not independently evaluated). Products keep the moving average.
- Picnic basket: Option A (forecasting-only correction); dashboard note approved.
- Closure weeks: £0, flagged "inferred Christmas closure"; published holiday calendar as inputs only.
- Scope: total + top 20 products (selected on weeks 1–60); horizons 1–8 (6–8 provisional).

## Known issues and limitations
### Open issues (must stay open until verified fixed)
- **Business-total forecast (open, partly addressed):**
  - **Now in use:** seasonal naive, by override.
  - **Not independently tested:** its accuracy and its nominal 80% ranges (holdout coverage 58–71%, too narrow) have no independent test; the 9.5% WAPE was seen before the decision.
  - **Frozen selection (HGB), on record:** 24.6% WAPE, bias up to +33%, a −£8,036 forecast for the week of 26 Dec 2011.
  - **Cause:** with two years of data, validation (Feb–Jun) contains no peak season.
  - **Closes when:** the choice is evaluated on new data the decision never saw.
- **Flat product forecasts (open):** the selected 4-week moving average repeats one value for 8 weeks and cannot anticipate seasonal turns (e.g. Christmas products in January).
- **Instruct model argument errors (open):** 81% correct arguments in the 16-question regression test. Seen errors:
  - swapped comparison periods in the main example request
  - `horizon_weeks: 20`, beyond the 8-week limit (validation caught it)
  - refused "what did returns cost us"

  To be fixed and re-measured under the Milestone 4 completion criteria above.
- **Memory pressure (open):**
  - **Benchmark:** after back-to-back model loads, with Chrome (~3.5 GB) and the Claude app (~1.8 GB) open, macOS reached "warning" pressure and swap grew from 0.5 to 2.3 GB.
  - **Retest:** one instruct model loaded, the app running and the dashboard open. Pressure stayed "normal" (one run, lighter background load).
  - **Retest with the real dashboard data (Milestone 2):** pressure "normal", free 84% → 58% (single run).
  - **To do:** retest when the assistant exists (Milestone 4), with realistic agent prompts.
  - **Mitigations:** keep `num_ctx` at 8192, load only one model, unload when idle (`keep_alive`), close heavy browser tabs when demoing.

### Other known issues
- **Bugs found by tests and fixed during Milestone 2:**
  - An upload without the optional product-name column failed on import (an empty column was typed as a number).
  - The upload check called ISO dates ambiguous, and "day first" would have misread them.
  - A file could silently mix day/month orders (05/02 read as 2 May, 25/02 as 25 Feb); this is now reported as a conflict.
  - Each bug has a test.
- **Manual-adjustment effect:** the week of 6 June 2011 overstates net product revenue by £38,970. A sale keyed as 60 packs instead of 1 was reversed by a Manual credit, which sits outside product revenue by decision. It also puts PICNIC BASKET WICKER SMALL (22502) at #9 in the dashboard's last-12-months top 10 (#158 without it). Full analysis in the feasibility review; treatment awaits decision 1.
- **Not handled in uploads:** decimal commas such as `2,50` are rejected rather than guessed. Files over 50 MB or 2 million rows are rejected.
- **Bundle size:** the dashboard's JavaScript bundle is 786 kB (mostly ECharts). Fine locally; Vite warns about it.
- **Server restarts:** `uv run sic serve` does not reload code automatically. Restart it after pulling changes.
- **Benchmark scoring bugs found and fixed after the run**, then re-scored from the saved raw responses (no results were re-run or edited by hand):
  - The `think=false` check looked only for a separate thinking field, so it missed reasoning written into the answer.
  - Omitted arguments were not given their documented defaults before comparison.
  - Reasoning leaking into answers is now measured with a labelled heuristic.
- **Failures seen in the tool test** (details of the open argument-error issue above):
  - "How much did returns cost us?" was refused by all three setups. The models read "cost" as cost data, so the system prompt must define returns as a £ value.
  - The instruct model swapped the period order in the main example request. Tools should order periods in code, or offer a "last two complete months" preset.
  - The instruct model passed `horizon_weeks: 20`. Validation rejected it and the model then explained the 8-week limit.
- The instruct model answered 17 × 23 = 401 (wrong). This confirms the design rule that the application computes every number, not the model.
- The tool-calling test is small (16 questions, one run each), so its percentages are indicative, not precise.
- Starlette shows a deprecation warning about `httpx` in the test client. Harmless for now; to revisit when dependencies are updated.
- `gh` was installed from a zip, so it does not update automatically.
- **Windows: unverified.** Nothing has been run on the Windows PC yet.

## Switching computers
- **Before leaving a computer:** `git status` → `git diff` → `git add …` → `git commit` → `git push`.
- **On arrival:** `git fetch` → `git status` → `git pull --ff-only`.
- **Install separately on each machine** (not in Git): uv, Node.js LTS, gh (then `gh auth login`), Ollama and the Qwen models.
- **Regenerate on each machine:**
  - `uv sync`
  - `npm ci --prefix frontend`
  - `uv run python scripts/download_data.py`
  - `uv run python scripts/prepare_data.py` (the pinned-totals test confirms the result matches)
  - `uv run playwright install chromium` (only needed for screenshots and browser checks)
  - `uv run python scripts/train_forecast.py --stage selection`, then `--stage holdout`, then `--stage operational`. This regenerates the local model files; the tracked metrics in `evaluation/forecast/uci/` should reproduce. Uploads' models are retrained in the app.
- **Never copied between computers:** uploaded datasets live only on the computer where they were uploaded; re-upload them if needed.
- **Local Git settings are per clone.** On a new clone, repeat the `git config --local` steps in [docs/setup-macos.md](docs/setup-macos.md).
  - These include `http.postBuffer`: pushing the screenshots failed with `HTTP 400` until it was raised for this repository.

## Next task
**Milestone 4 plan, revision 2, awaiting approval:** [docs/milestone4_plan.md](docs/milestone4_plan.md).
- **Decisions recorded:**
  - 5 private user questions
  - a dedicated Assistant tab
  - individual CSVs plus a ZIP
  - one built-in-data sample report in `docs/examples/`
- **Revised for:**
  - preserved comparison intent
  - dataset-specific forecasts and limitations
  - the example request in 4 tool calls (batched trends, combined chart)
  - preserved trend frequency
  - seed handling and AI-assisted review labelling
- **Not yet implemented:** nothing in Milestone 4.
