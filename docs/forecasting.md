# Forecasting: method, results and what they mean (Milestone 3)

The full numbers are in [evaluation/forecast/uci/report.md](../evaluation/forecast/uci/report.md), and the design review is in [forecasting_feasibility_review.md](forecasting_feasibility_review.md). To reproduce on any computer, after preparing the data:

```bash
uv run python scripts/train_forecast.py --stage selection
uv run python scripts/train_forecast.py --stage holdout
```

## 1. What is forecast

**Adjusted net product revenue, per complete Monday–Sunday week:**
- **Base figure:** the dashboard's **Net product revenue** (product sales − product returns).
- **One documented forecasting-only correction:**
  - **What:** the £38,970 picnic-basket sale reversed by a Manual credit (invoices 556444 / C556445, spreadsheet rows 222673 / 222683 of sheet "Year 2010-2011").
  - **Where it applies:** it lowers the **business total** for the week of 6 June 2011 from £212,228.43 to £173,258.43.
  - **Product 22502:** this product is not among the 20 forecast products; its own adjusted weekly figure (£39,981.52 → £1,011.52) is recorded with the correction.
  - **What stays unchanged:** the dashboard, the stored transactions and every other week.
- **Christmas closure weeks:** the two Christmas weeks with no transactions of any kind stay as £0 and are flagged **"inferred Christmas closure"**. The closure is inferred from the calendar pattern, not confirmed.

**Series forecast:** the business total, plus the top 20 products selected on weeks 1–60 only (834 eligible products).

## 2. Design, frozen before any result

Fixed in [configs/forecast.toml](../configs/forecast.toml) and committed (`685e1b4`) before any model ran on this data:

| Item | Setting |
|---|---|
| Windows | Selection 1–60 · validation 61–80 (31 Jan–19 Jun 2011) · calibration 81–92 (20 Jun–11 Sep 2011) · holdout 93–104 (12 Sep–4 Dec 2011) |
| Candidates | Naive, 4-week moving average, seasonal naive, Ridge (pooled), HistGradientBoosting (pooled) |
| Experiment (never selected) | HistGradientBoosting + 52-week lag |
| Features | Lags 1–4, rolling mean/std of lags 1–8 (scaled per series using training weeks only), month, England & Wales bank-holiday weekdays, days in 24 Dec–1 Jan. Calendar facts are known in advance and never force a zero. Uploads get month only, since their country is unknown |
| Forecasting | Recursive, 1–8 weeks; refitted at every origin on earlier weeks only |
| Selection | Lowest validation WAPE, averaged equally over h = 1–8. Products pooled (revenue-weighted). Ties within 0.5 points go to the simpler model. Total and products chosen separately |
| Intervals | 80% from calibration residual quantiles per horizon. h = 6–8 marked provisional (fewer than 8 calibration points per series) |

**Integrity timeline**

| Step | Commit |
|---|---|
| Design and code frozen | `685e1b4` |
| Validation and selection recorded | `d89d3a1` |
| Holdout results recorded | `f359395` (holdout run at `55b4553`) |
| Clean re-run with identical metrics | `14ab70a` (run at `5f23e25`) |

- **The holdout isn't fully unseen.** Its aggregate weekly totals were inspected in the feasibility review, before the design was frozen.
- **One failed run.** The first holdout run crashed while saving the model file (a pickling error), before any holdout metric was written or shown. Only the saving code was fixed.
- **Automated tests:** a future-data perturbation test for every model, plus window-boundary tests.

## 3. Results

### Which model won
| Group | Selected on validation (frozen rule) | Validation mean WAPE | Holdout mean WAPE | Best on holdout |
|---|---|---:|---:|---|
| Business total | **HistGradientBoosting** | 19.3% (vs 20.0% for the moving average) | **24.6%** | Seasonal naive, **9.5%** |
| Top 20 products | **4-week moving average** (a baseline) | 50.7% | **50.4%** | The same model |

### Business total, holdout by horizon (selected model vs seasonal naive)
| h | n | HGB WAPE | HGB bias | Seasonal naive WAPE | 80% interval coverage (HGB) |
|---:|---:|---:|---:|---:|---:|
| 1 | 12 | 17.6% | −1.6% | 14.9% | 33% |
| 2 | 11 | 18.8% | +5.7% | 14.0% | 36% |
| 3 | 10 | 16.1% | +11.7% | 12.6% | 40% |
| 4 | 9 | 24.5% | +19.1% | 10.3% | 44% |
| 5 | 8 | 24.4% | +23.9% | 9.7% | 38% |
| 6 (provisional) | 7 | 33.4% | +29.3% | 5.7% | 29% |
| 7 (provisional) | 6 | 29.3% | +26.3% | 5.1% | 33% |
| 8 (provisional) | 5 | 32.8% | +32.8% | 3.8% | 0% |

### Top products (pooled), selected moving average
- **WAPE:** 41.9% at h = 1, rising to 58.7% at h = 8.
- **80% interval coverage:** 75–80% at h = 1–3, falling to 57% at h = 8 (calibration n = 240 → 100).
- **Strongly seasonal products** are much better served by seasonal naive:
  - Paper chain kit 50's Christmas: 14.8% vs 62.6%.
  - The two hot water bottles: 26–29% vs 45–49%.

### Experiment (52-week lag)
- **Business total:** 30.8%, worse than every candidate.
- **Products:** 52.4%, between seasonal naive and the moving average.

With only 8–40 training rows per series for this feature, the experiment wasn't expected to be reliable.

## 4. What the results mean

1. **The selection rule was sound in principle but used an unrepresentative window.**
   - Validation covered February–June 2011. There, the year-ago pattern repeated only moderately well: seasonal naive came 3rd of 5 for the total (21.6% mean WAPE) and was worse than the 4-week moving average at 7 of 8 horizons.
   - The holdout covers September–November, where the pre-Christmas peak repeats strongly from 2010. The ranking flipped.
   - With only two years of data, no validation window before the holdout contains a peak season. This is a limit of the data, not of the code.
2. **The selected business-total model is not trustworthy for this season.**
   - HistGradientBoosting over-forecasts more as the horizon grows (bias +6% to +33%).
   - It forecasts **−£8,036 for the week of 26 Dec 2011**. It learned from the calendar input that Christmas weeks are near zero and overshot below zero. Nothing forces a zero, as required. A negative week is implausible, and this was left visible rather than clipped.
   - Its 80% ranges covered 0–44% of holdout weeks. They were calibrated on 5–12 quiet summer weeks, so they are far too narrow.
3. **The product forecasts are honest but basic.**
   - A baseline won, and it held up on the holdout.
   - Its forecasts are flat: the same value for all 8 weeks. So it cannot anticipate seasonal turns, such as Christmas products after December.
4. **Error levels.** About 15–25% weekly error for the total and about 40–60% for single products. Weekly product sales are volatile, so treat product forecasts as rough guides.

After reviewing these results, the project owner chose an operational override for the business total (section 7).

## 5. Operational override (business total, built-in data only)

On 2026-10-26 the project owner chose **seasonal naive** as the **operational default** for the built-in business-total forecast, replacing the frozen validation selection (HistGradientBoosting) **after reviewing the holdout results**.

**How it is recorded:**
- The override lives in its own file, [configs/forecast_overrides.toml](../configs/forecast_overrides.toml), which states `independent_evaluation = false` and the reason.
- The frozen design ([configs/forecast.toml](../configs/forecast.toml), unchanged; a test checks that its SHA-256 still matches the recorded selection), the validation selection and the evaluation history in `evaluation/forecast/uci/` (`selection.json`, `evaluation.json`, `report.md`) are **unchanged**.
- The model the app uses is written separately to `operational.json` by `uv run python scripts/train_forecast.py --stage operational`.

**What the 9.5% means now:** the holdout WAPE of seasonal naive (9.5%) is **not an independent evaluation** of this decision, because the decision was made after seeing it. No untouched data remains to provide one.

**The override model's own ranges:** calibrated on seasonal naive's own calibration-window residuals, not HGB's.

| h | Calibration n | Nominal 80% range around the forecast | Holdout coverage (n) |
|---:|---:|---|---:|
| 1 | 12 | −£20,051 to +£40,672 | 58% (12) |
| 2 | 11 | −£21,968 to +£40,787 | 64% (11) |
| 3 | 10 | −£4,715 to +£42,490 | 60% (10) |
| 4 | 9 | −£6,632 to +£44,194 | 67% (9) |
| 5 | 8 | −£1,072 to +£45,897 | 62% (8) |
| 6 (provisional) | 7 | −£1,319 to +£46,910 | 71% (7) |
| 7 (provisional) | 6 | −£1,565 to +£48,728 | 67% (6) |
| 8 (provisional) | 5 | −£1,812 to +£41,450 | 60% (5) |

- **Too narrow:** measured coverage is 58–71%, below the nominal 80%, on very small samples. The ranges are shown as "nominal 80%" with this warning, not as reliable 80% ranges.
- **Not independent:** this coverage was also measured on the holdout that influenced the decision.
- **Skewed upward:** in the summer calibration weeks, actuals mostly exceeded last year's values.

**Unchanged:**
- **Products:** still use their frozen validation selection, the 4-week moving average.
- **Uploads:** cannot be overridden (enforced in code and tested). They always use their own validation-based selection.

## 6. Uploads
- **Same pipeline, own data:** an upload uses the same pipeline and frozen rules on its own data, through the **Train and evaluate** button, which runs as a background job with progress.
- **Minimum history:** **70 complete weeks** (26 history + 20 validation + 12 calibration + 12 holdout). Shorter uploads are refused with that explanation.
- **Calendar:** no UK holidays are assumed; month is the only calendar input.
- **Storage:** models and results are stored in the upload's own folder under `data/uploads/` (ignored by Git) and are deleted with the upload. The built-in model is never applied to uploads.
- **Complete weeks:** a business that never trades on weekends has its final week counted as partial if the data ends on a Friday.

## 7. Limitations
- Two years of data; only 12 holdout weeks; h = 6–8 are provisional.
- Intervals for the business total are unreliable (see above).
- Fixed hyperparameters (no tuning), to keep the comparison simple and honest.
- The bank-holiday list was transcribed from gov.uk. It was checked for consistency against the dataset (all 17 weekday bank holidays in range had no trading), but it is not an operating schedule.
- **Windows: unverified.**
