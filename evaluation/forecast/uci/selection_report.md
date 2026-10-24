# Forecast evaluation: uci

- Target: **Adjusted net product revenue**. Weekly net product revenue (product sales minus product returns, GBP for the built-in data), with documented forecasting-only corrections applied. The dashboard's 'Net product revenue' is the same figure without those corrections.
- Weeks: Monday to Sunday; complete weeks only. Calendar features: `england_wales`.
- Config SHA-256: `297ac2910308b5ead78f6c38f04ba627315f14d1bb1cac4818cd0e529432207c`
- Selection stage: 2026-10-24 01:10:08 UTC, commit `685e1b4fcbebf5157b5fd320dcd924a5c2ed0c68`

## Windows

| Window | Weeks | From | To |
|---|---|---|---|
| selection | 1-60 (60) | 2009-12-07 | 2011-01-30 |
| validation | 61-80 (20) | 2011-01-31 | 2011-06-19 |
| calibration | 81-92 (12) | 2011-06-20 | 2011-09-11 |
| holdout | 93-104 (12) | 2011-09-12 | 2011-12-04 |

## Forecasting-only corrections

- **manual-reversal-C556445**: −£38,970.00 in the week of 2011-06-06 (product 22502, PICNIC BASKET WICKER 60 PIECES). Applied to: total. Business total that week: £212,228.43 reported → £173,258.43 adjusted. Source rows: sale 556444 (row 222673), reversal C556445 (row 222683).

## Model selection (validation)

Rule: lowest WAPE averaged with equal weight over horizons 1–8; products pooled (revenue-weighted). Ties within 0.5 percentage points go to the simpler model. The 52-week-lag model is an experiment and is never eligible.

| Model | Business total | Top products |
|---|---:|---:|
| Naive (last week) | 24.2% | 55.6% |
| Moving average (4 weeks) | 20.0% | 50.7% |
| Seasonal naive (same week last year) | 21.6% | 67.0% |
| Ridge (pooled) | 24.1% | 56.7% |
| HistGradientBoosting (pooled) | 19.3% | 54.3% |
| HistGradientBoosting + 52-week lag (experiment) | 22.0% | 54.8% |

- **Business total: HistGradientBoosting (pooled)**
- **Top products (pooled): Moving average (4 weeks)**
