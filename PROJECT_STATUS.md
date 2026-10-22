# Project status

_Last updated: 2026-10-22 (end of Milestone 1)._
Read this first when resuming work on any computer.

## Current milestone
**Milestone 1 (environment, repository, local-model feasibility): complete on macOS, awaiting review.**
Milestone 2 (data ingestion and dashboard) has **not** started.

## Completed
- **Tools installed** by the user from official sources and verified on the Mac. Exact steps: [docs/setup-macos.md](docs/setup-macos.md).
  - uv 0.13.5
  - Node.js v24.22.1 LTS (npm 11.19.1)
  - GitHub CLI 2.103.0
  - Ollama 0.40.8
- **Git**
  - Repository initialised on `main`.
  - Author `zeosul6an3` with the GitHub no-reply email, set **locally only** (no global Git config exists).
  - GitHub credentials come from `gh`, also configured locally.
- **GitHub**: private repository https://github.com/zeosul6an3/sales-intelligence-copilot. Visibility was checked as `PRIVATE`.
- **Backend skeleton**: FastAPI app (Python 3.13.17) with `/api/health`, which reports API and Ollama status.
  - `uv run sic serve` builds the dashboard if needed and serves it on 127.0.0.1:8000.
- **Dashboard skeleton**: React 19 + TypeScript 6 + Vite 8, based on the official template. It shows a status page, with colour tokens for light and dark mode.
- **Qwen models pulled**, with digests matching the official registry:
  - `qwen3:4b` (`359d7dd4bcda`)
  - `qwen3:4b-instruct-2507-q4_K_M` (`0edcdef34593`)
- **Feasibility benchmark**: [scripts/llm_feasibility.py](scripts/llm_feasibility.py), with results in [evaluation/llm_feasibility/](evaluation/llm_feasibility/2026-10-22_darwin-arm64.md).
- **Memory check**: [scripts/memory_check.py](scripts/memory_check.py) (one model plus the running app), with results in [evaluation/memory/](evaluation/memory/2026-10-22_darwin-arm64.md).

## Checks performed (actual results)
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
- Repository stays **private permanently** unless the user says otherwise. **No code licence** has been chosen yet.
- Git identity and credentials are configured per repository only.
- GitHub CLI was installed from the release's signed arm64 zip into `~/.local/bin`, because the universal `.pkg` was unsigned and Gatekeeper blocked it.
- TypeScript 6 (as pinned by the official Vite template) instead of TypeScript 7.
- DuckDB will be pinned below 2.0 (2.0.0 was released 2026-10-21) when it is added in Milestone 2.
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
2. **Comparison direction:** application code puts compared periods in chronological order, or presets such as "last two complete months" are used, so declines can't silently become increases.
3. **Forecast limits:** horizons beyond the evaluated maximum, and ineligible series, are rejected by validation with a clear explanation.
4. **Tool-based calculations:** every figure in an answer comes from a tool result, and the model does no arithmetic. Meaning-level checks confirm the metric, dataset, product, currency, filters and period.

**Evaluation requirement:**
- Measure these changes on **both** the existing 16 regression questions **and** a new set of **held-out questions** written separately and **not used to tune prompts or tools**.
- Report the actual accuracy on each set separately.
- Validation and grounding checks reduce errors but **do not guarantee correctness**. The reports must say so.

## Pending decisions (need the user)
1. **Code licence**: to be discussed separately.

## Known issues and limitations
### Open issues (must stay open until verified fixed)
- **Instruct model argument errors (open):** 81% correct arguments in the 16-question regression test. Seen errors:
  - swapped comparison periods in the main example request
  - `horizon_weeks: 20`, beyond the 8-week limit (validation caught it)
  - refused "what did returns cost us"

  To be fixed and re-measured under the Milestone 4 completion criteria above.
- **Memory pressure (open):**
  - **Benchmark:** after back-to-back model loads, with Chrome (~3.5 GB) and the Claude app (~1.8 GB) open, macOS reached "warning" pressure and swap grew from 0.5 to 2.3 GB.
  - **Retest:** one instruct model loaded, the app running and the dashboard open. Pressure stayed "normal" (one run, lighter background load).
  - **To do:** retest with `scripts/memory_check.py` once the real dashboard (Milestone 2) and the assistant (Milestone 4) exist.
  - **Mitigations:** keep `num_ctx` at 8192, load only one model, unload when idle (`keep_alive`), close heavy browser tabs when demoing.

### Other known issues
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
- **Regenerate on each machine:** `uv sync`, `npm ci --prefix frontend`. Data and trained models (from Milestone 2 on) are regenerated with the scripts, not copied.
- **Local Git settings are per clone.** On a new clone, repeat the `git config --local` steps in [docs/setup-macos.md](docs/setup-macos.md).

## Next task
After the user reviews Milestone 1: **Milestone 2**. That starts with downloading and inspecting both sheets of the UCI workbook, then proposing evidence-based transaction classification rules before building the pipeline and dashboard.
