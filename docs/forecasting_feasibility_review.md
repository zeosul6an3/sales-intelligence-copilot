# Forecasting feasibility review (Milestone 3, before any model training)

_Prepared 2026-10-24. No model has been trained. The numbers come from the cleaned built-in dataset and can be reproduced with `uv run python scripts/forecast_feasibility.py`, which writes [evaluation/forecast_feasibility/review.json](../evaluation/forecast_feasibility/review.json) and asserts the window dates below._

**Target:** weekly **net product revenue** (GBP) = product sales − product returns, in complete Monday–Sunday weeks. This is the same definition the dashboard uses.

## 1. Weeks available, gaps and zero sales

| Item | Finding |
|---|---|
| Data coverage | Tue 1 Dec 2009 07:45 → Fri 9 Dec 2011 12:50 |
| Complete weeks | **104**: weeks 1–104 = 7 Dec 2009 → 4 Dec 2011 |
| Partial weeks (excluded) | Week of 30 Nov 2009 (data starts Tuesday); week of 5 Dec 2011 (data ends Friday) |
| Weeks with **no records at all** | **2**: week 4 (28 Dec 2009) and week 56 (27 Dec 2010) |
| Short weeks | Week 3 (21 Dec 2009, 3 trading days). Four other weeks have 4 trading days (Easter and Christmas weeks) |
| Weekly total, other weeks | £49,895 (minimum) / £160,965 (median) / £370,687 (maximum) |

### Closure versus missing data
- **No missing data detected.** Every weekday without any transaction falls on a **UK public holiday** or the **Christmas closure** (24 Dec–3 Jan in both years):
  - 2010: Good Friday 2 Apr, Easter Monday 5 Apr, 3 May, 31 May, 30 Aug.
  - 2011: 22 Apr, 25 Apr, 29 Apr (the royal-wedding bank holiday), 2 May, 30 May, 29 Aug.
  - Saturdays almost never trade (one Saturday in two years).
- **The two zero weeks are closure weeks.** No line of *any* type (sales, returns, shipping, notes) was recorded in them, and they repeat at the same point in both years. This is an inference from the calendar pattern; the data itself never states that the business was closed.
- **Zero sales for a product** in a week when the business *was* trading (other lines were recorded that week) count as **confirmed zero sales** for that product.

| Week type | Total series | Product series |
|---|---|---|
| Trading week | Recorded value | Recorded value, or **confirmed zero** if no sales |
| Closure week (weeks 4, 56) | 0, flagged "closure" | 0, flagged "closure" (not counted as a sales zero) |
| Missing data | None detected | None detected |

**Proposed treatment:**
- Keep closure weeks as 0 in the target.
- Give the models a **trading-days-in-week** feature from a fixed calendar (UK bank holidays plus the observed Christmas closure). It is known in advance, so it involves no leakage.
- None of the validation, calibration or holdout target weeks contains a closure week.

## 2. Training, validation, calibration and holdout windows

All windows use complete-week numbers. The script **asserts** that:
- products are selected before any forecast window;
- no segments overlap;
- calibration targets end before the holdout starts;
- the holdout is at least as long as the horizon.

| Segment | Weeks | Dates | Used for |
|---|---|---|---|
| Product selection | 1–60 | 7 Dec 2009 → 30 Jan 2011 | Ranking top products only |
| **Validation targets** | 61–80 | 31 Jan 2011 → 19 Jun 2011 | Model selection |
| **Calibration targets** | 81–92 | 20 Jun 2011 → 11 Sep 2011 | Prediction-interval calibration |
| **Final holdout targets** | 93–104 | 12 Sep 2011 → 4 Dec 2011 | One final, untouched evaluation |

**How origins work:**
- Every forecast uses an **expanding window**: the model is fitted only on weeks before its forecast origin, then forecasts recursively (it feeds its own predictions back, never actuals).
- Model-selection forecasts only score targets in weeks 61–80, and calibration forecasts only weeks 81–92. Neither ever scores a holdout week.
- Hyperparameters and model choice are frozen before week 93.

### Usable training rows per series

| Forecast origin | Origin date | Short lags (1–4, rolling 8) | With 52-week lag | Pooled, short lags (21 series) | Pooled, with lag 52 (21 series) |
|---|---|---:|---:|---:|---:|
| First validation origin (week 61) | 31 Jan 2011 | 52 | **8** | 1,092 | 168 |
| First calibration origin (week 81) | 20 Jun 2011 | 72 | 28 | 1,512 | 588 |
| Holdout origin (week 93) | 12 Sep 2011 | 84 | 40 | 1,764 | 840 |
| Final refit (future forecast, week 105) | 5 Dec 2011 | 96 | 52 | 2,016 | 1,092 |

- The first trainable target is week 9 (1 Feb 2010) with short lags, and week 53 (6 Dec 2010) with a 52-week lag.
- "21 series" = the total plus the top 20 products.

### Evaluation points per series

| Segment | h = 1 | h = 4 | h = 8 |
|---|---:|---:|---:|
| Validation | 20 | 17 | 13 |
| Calibration | 12 | 9 | 5 |
| Holdout | 12 | 9 | 5 |

**What this means:**
- A **single-series** model with a 52-week lag would have only 8–40 rows: **not feasible**.
- 52-week information is only realistic through the **seasonal naive baseline**, or as an experimental feature in a **pooled** model.
- Intervals at h = 8 rest on 5 calibration points, so they will be **rough**, and the report must say so.

## 3. Supported baselines, models and horizons

| Type | Model | Available | Note |
|---|---|---|---|
| Baseline | Naive (last week) | All windows | |
| Baseline | Moving average, last 4 weeks | All windows | |
| Baseline | **Seasonal naive** (same week last year) | All evaluation windows (needs weeks ≥ 53) | Likely strong: holdout weeks are only +3.0% on the same weeks of 2010 |
| ML | Ridge regression, pooled over the 21 series | Yes | Short lags, rolling mean/std from lags only, month, trading days; each series scaled by its own training-window level |
| ML | HistGradientBoosting, pooled | Yes | Same features |
| ML (experiment) | HistGradientBoosting, pooled, **+ 52-week lag** | Yes, data-limited | Only 168–840 rows; reported as an experiment |
| Not supported | Any single-series ML for the total alone | No | 52–84 rows with short lags; too few with lag 52 |

**Horizon:** 1–8 weeks, recursive. Results are reported **per horizon**, and the h = 5–8 results rest on fewer points.

### Product series, selected using weeks 1–60 only
- **Eligibility rule:** net sales in ≥ 75% of the 58 trading weeks of the selection window, *and* sold in its first week. This keeps out products launched later, which would lack history.
- **Result:** 834 of 4,046 products qualify. The **top 20 by selection-window net product revenue** cover **9.7%** of total net product revenue in that window.

| # | Code | Product | Selection net (£) | Active weeks (selection) |
|---:|---|---|---:|---:|
| 1 | 85123A | WHITE HANGING HEART T-LIGHT HOLDER | 172,360.73 | 58 |
| 2 | 85099B | JUMBO BAG RED RETROSPOT | 95,031.39 | 58 |
| 3 | 84879 | ASSORTED COLOUR BIRD ORNAMENT | 73,151.63 | 58 |
| 4 | 22086 | PAPER CHAIN KIT 50'S CHRISTMAS | 56,374.64 | 46 |
| 5 | 47566 | PARTY BUNTING | 52,033.69 | 57 |
| 6 | 21843 | RED RETROSPOT CAKE STAND | 43,112.37 | 57 |
| 7 | 20685 | DOORMAT RED RETROSPOT | 42,455.48 | 57 |
| 8 | 21621 | VINTAGE UNION JACK BUNTING | 39,382.18 | 58 |
| 9 | 85099F | JUMBO BAG STRAWBERRY | 39,285.01 | 58 |
| 10 | 79321 | CHILLI LIGHTS | 38,987.59 | 50 |
| 11 | 20725 | LUNCH BAG RED RETROSPOT | 37,843.51 | 58 |
| 12 | 20914 | SET/5 RED RETROSPOT LID GLASS BOWLS | 35,915.81 | 58 |
| 13 | 15056N | EDWARDIAN PARASOL NATURAL | 35,249.52 | 58 |
| 14 | 21931 | JUMBO STORAGE BAG SUKI | 34,037.82 | 58 |
| 15 | 21232 | STRAWBERRY CERAMIC TRINKET BOX | 34,018.48 | 58 |
| 16 | 21212 | PACK OF 72 RETROSPOT CAKE CASES | 33,694.82 | 58 |
| 17 | 85099C | JUMBO BAG BAROQUE BLACK WHITE | 33,623.40 | 58 |
| 18 | 21754 | HOME BUILDING BLOCK WORD | 32,553.06 | 58 |
| 19 | 22114 | HOT WATER BOTTLE TEA AND SYMPATHY | 32,179.33 | 55 |
| 20 | 22112 | CHOCOLATE HOT WATER BOTTLE | 32,066.71 | 58 |

Two of these are **strongly seasonal**, which will be hard for short-lag models:
- *Paper chain kit 50's Christmas*: sold in only 11 of the 20 validation weeks.
- *Hot water bottle tea and sympathy*: 4 of 20.

The script reports activity in later windows for transparency only; it was **not** used for selection. The picnic-basket product (22502) is **not** among the selected products.

## 4. The £38,970 picnic-basket overstatement (week of 6 June 2011)

### The transactions
All five belong to customer 15098 on Friday 10 June 2011, within 17 minutes:

| Time | Invoice | Line | Value (£) | Line type under current rules |
|---|---|---|---:|---|
| 15:22 | 556442 | 60 × PICNIC BASKET WICKER SMALL @ £4.95 (code 22502) | 297.00 | product sale |
| 15:28 | 556444 | 60 × "PICNIC BASKET WICKER **60 PIECES**" @ £649.50 (code 22502) | 38,970.00 | product sale (flagged unusual) |
| 15:31 | C556445 | Manual credit, code `M`, quantity −1 @ £38,970.00 | −38,970.00 | manual adjustment |
| 15:33 | 556446 | **1** × "PICNIC BASKET WICKER 60 PIECES" @ £649.50 (code 22502) | 649.50 | product sale |
| 15:39 | C556448 | Return of the 60 small baskets @ £4.95 (code 22502) | −297.00 | product return |

### The accounting relationship
- **The error:** £649.50 is the price of **one pack of 60 baskets** (£10.83 each; the usual single-basket prices are £3.75–£10.79). Invoice 556444 entered the pack with quantity 60 instead of 1, charging 60 packs. Three minutes later the full £38,970 was reversed. The pack was then re-invoiced correctly as 1 × £649.50, and the earlier 60 small baskets were returned.
- **What the customer actually bought:** one pack, **£649.50** of product revenue.
- **Why it shows as an overstatement:** the reversal was booked with the non-product code `M` instead of as a return of product 22502. Under the approved policy (Manual lines are reported separately, outside net product revenue), product 22502's net that day is £297 + £38,970 + £649.50 − £297 = **£39,619.50**, and the matching −£38,970 sits under "Manual adjustments". The company-wide total of *all* lines is correct. Only the product-revenue view is overstated, by exactly £38,970.
- **Is it unique?** A systematic search found one match: Manual credits ≥ £1,000 on cancellation invoices that exactly equal one product-sale line of the same customer within 30 minutes. Smaller matches (£2–£20) are ambiguous because they fit several products at once. Other large Manual credits have no matching product sale, and most cancel out against a Manual charge of the same amount.

### Effect on the forecasting target and on the dashboard

| View | As reported (policy) | If the reversal were applied | Difference |
|---|---:|---:|---:|
| Total weekly target, week 79 (6–12 Jun 2011) | £212,228.43 | £173,258.43 | 18.4% of the reported week |
| Product 22502, week 79 | £39,981.52 | £1,011.52 | about 40× |
| Product 22502, last 12 complete months (dashboard) | £51,041.37, **rank #9** | £12,071.37, rank #158 | Appears in the dashboard's top 10 only because of the error |

**Effect on forecasting:**
- Week 79 is inside the **validation** window. It would penalise every model in model selection for one week it could never predict.
- Through the lag features, it would also distort the forecasts made for weeks 80–87, which include calibration weeks 81–87.

### Proposed treatment (policy unchanged, nothing removed)
- **Option A (recommended): a documented forecasting-target correction.**
  - **The rule:** a Manual credit ≥ £1,000 on a C-invoice that exactly reverses one, and only one, product-sale line of the same customer within 30 minutes. The rule is reproducible and today matches only this case.
  - **Where it applies:** **only to the forecasting series**, through an explicit corrections table stored with each training run and shown in the model card. Raw and corrected series are both kept.
  - **Dashboard and reports:** they keep the approved revenue policy unchanged, and gain a visible **annotation** on product 22502 and on that week.
- **Option B:** no correction. Keep the spike in training and evaluation, and only report it. The cost is that model selection is skewed by one artificial week.
- **Option C:** keep the target as is, but leave week 79 out of the validation *scoring*. The cost is that the lag features would still carry the spike into weeks 80–87.

## 5. Recommended first scope and how performance will be measured

**Scope:**
- **Series:** total business plus the top 20 products (21 series), weekly net product revenue.
- **Horizon:** 1–8 weeks.
- **Built-in dataset first:** the train-and-evaluate job for **uploaded** datasets follows in this milestone, with the same pipeline and its own eligibility check. The UCI model is never applied to uploads.

**Models:** the 3 baselines; pooled Ridge and HistGradientBoosting on short-lag and calendar features; and the pooled HistGradientBoosting + lag-52 variant as an experiment.

**Selection:**
- Separately for the total and for the product set, the model with the lowest **mean validation WAPE over h = 1–8** wins.
- Ties go to the simpler model.
- **If a baseline wins, it is reported and used.**

**Metrics:** reported per model, per series group and **per horizon**.

| Metric | Meaning | When undefined |
|---|---|---|
| MAE (£) | Average absolute error | — |
| RMSE (£) | Penalises large misses | — |
| WAPE | Σ\|error\| ÷ Σ\|actual\| | n/a if Σ\|actual\| = 0 (reason given) |
| Bias | Σ error ÷ Σ actual (over- vs under-forecasting) | n/a if Σ actual = 0 |
| Skill vs seasonal naive | 1 − MAE_model ÷ MAE_seasonal naive | n/a if the baseline's MAE = 0 |
| Skill vs naive | 1 − MAE_model ÷ MAE_naive | n/a if the baseline's MAE = 0 |
| 80% interval coverage (holdout) | Share of actuals inside the calibrated interval | Reported with the number of points |

**Leakage controls, tested automatically:**
- A perturbation test: changing any value after the forecast origin must leave the forecast unchanged.
- The window-date assertions above.
- An assertion that product selection uses weeks ≤ 60 only.
- Scalers fitted on training rows only.

**Honest expectation:** the holdout covers the September–November peak, which runs only 3% above the previous year. Seasonal naive will probably be **hard to beat**, especially at longer horizons and for seasonal products. Nothing is promised before measuring.

## Decisions needed
1. **Picnic-basket treatment for the forecasting target:** Option A (recommended), B or C.
2. **Dashboard annotation** for product 22502 and the week of 6 June 2011 (recommended), with no change to the revenue policy.
3. **Closure weeks:** keep them as zeros and add a calendar trading-days feature (recommended).
4. **First scope:** total + top 20 products (recommended), or the total series only.
