# Forecast evaluation: uci

- Target: **Adjusted net product revenue**. Weekly net product revenue (product sales minus product returns, GBP for the built-in data), with documented forecasting-only corrections applied. The dashboard's 'Net product revenue' is the same figure without those corrections.
- Weeks: Monday to Sunday; complete weeks only. Calendar features: `england_wales`.
- Config SHA-256: `297ac2910308b5ead78f6c38f04ba627315f14d1bb1cac4818cd0e529432207c`
- Selection stage: 2026-10-24 01:10:08 UTC, commit `685e1b4fcbebf5157b5fd320dcd924a5c2ed0c68`
- Holdout stage: 2026-10-24 01:19:37 UTC, commit `5f23e25e593404e7b7a7fc6105a9d5d59831b459`

> The holdout weeks are not completely unseen: aggregate weekly totals for them were inspected during the feasibility review (2026-10-24) before the candidates, selection rule, correction policy and windows were frozen. No model forecast for a holdout week existed before the model choice was fixed in selection.json.

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

## Final holdout

| Model | Business total, mean WAPE | Top products, mean WAPE |
|---|---:|---:|
| Naive (last week) | 22.7% | 54.0% |
| Moving average (4 weeks) | 24.1% | 50.4% |
| Seasonal naive (same week last year) | 9.5% | 52.9% |
| Ridge (pooled) | 14.9% | 58.0% |
| HistGradientBoosting (pooled) | 24.6% | 58.5% |
| HistGradientBoosting + 52-week lag (experiment) | 30.8% | 52.4% |

### Business total: holdout by horizon

| Model | h | n | MAE | RMSE | WAPE | Bias | Skill vs naive | Skill vs seasonal naive |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Naive (last week) | 1 | 12 | £62,571 | £71,134 | 22.4% | -3.6% | +0.0% | -50.1% |
| Naive (last week) | 2 | 11 | £53,859 | £67,084 | 18.9% | -6.2% | +0.0% | -35.0% |
| Naive (last week) | 3 | 10 | £70,083 | £80,119 | 24.9% | -8.7% | +0.0% | -97.2% |
| Naive (last week) | 4 | 9 | £64,244 | £79,554 | 22.1% | -15.1% | +0.0% | -114.1% |
| Naive (last week) | 5 | 8 | £69,056 | £81,949 | 23.9% | -16.5% | +0.0% | -147.0% |
| Naive (last week) | 6 (provisional) | 7 | £67,983 | £79,691 | 22.6% | -19.7% | +0.0% | -296.1% |
| Naive (last week) | 7 (provisional) | 6 | £70,662 | £88,505 | 22.9% | -22.4% | +0.0% | -351.7% |
| Naive (last week) | 8 (provisional) | 5 | £76,435 | £87,870 | 23.7% | -23.7% | +0.0% | -519.2% |
| Moving average (4 weeks) | 1 | 12 | £51,726 | £66,691 | 18.5% | -11.7% | +17.3% | -24.1% |
| Moving average (4 weeks) | 2 | 11 | £55,709 | £75,136 | 19.5% | -15.8% | -3.4% | -39.6% |
| Moving average (4 weeks) | 3 | 10 | £56,858 | £70,422 | 20.2% | -17.3% | +18.9% | -60.0% |
| Moving average (4 weeks) | 4 | 9 | £63,182 | £77,367 | 21.8% | -21.8% | +1.7% | -110.6% |
| Moving average (4 weeks) | 5 | 8 | £64,273 | £70,202 | 22.2% | -22.2% | +6.9% | -129.9% |
| Moving average (4 weeks) | 6 (provisional) | 7 | £80,172 | £84,420 | 26.6% | -26.6% | -17.9% | -367.1% |
| Moving average (4 weeks) | 7 (provisional) | 6 | £90,507 | £99,077 | 29.4% | -29.4% | -28.1% | -478.6% |
| Moving average (4 weeks) | 8 (provisional) | 5 | £112,928 | £123,686 | 35.0% | -35.0% | -47.7% | -814.8% |
| Seasonal naive (same week last year) | 1 | 12 | £41,690 | £52,980 | 14.9% | -2.9% | +33.4% | +0.0% |
| Seasonal naive (same week last year) | 2 | 11 | £39,903 | £52,152 | 14.0% | -1.1% | +25.9% | +0.0% |
| Seasonal naive (same week last year) | 3 | 10 | £35,544 | £47,904 | 12.6% | +1.7% | +49.3% | +0.0% |
| Seasonal naive (same week last year) | 4 | 9 | £30,008 | £41,714 | 10.3% | -1.4% | +53.3% | +0.0% |
| Seasonal naive (same week last year) | 5 | 8 | £27,956 | £41,088 | 9.7% | +0.4% | +59.5% | +0.0% |
| Seasonal naive (same week last year) | 6 (provisional) | 7 | £17,164 | £19,974 | 5.7% | -4.5% | +74.8% | +0.0% |
| Seasonal naive (same week last year) | 7 (provisional) | 6 | £15,644 | £18,716 | 5.1% | -3.7% | +77.9% | +0.0% |
| Seasonal naive (same week last year) | 8 (provisional) | 5 | £12,344 | £14,620 | 3.8% | -2.3% | +83.8% | +0.0% |
| Ridge (pooled) | 1 | 12 | £40,439 | £53,153 | 14.4% | +3.2% | +35.4% | +3.0% |
| Ridge (pooled) | 2 | 11 | £38,884 | £50,015 | 13.6% | +4.6% | +27.8% | +2.6% |
| Ridge (pooled) | 3 | 10 | £39,598 | £45,454 | 14.1% | +9.1% | +43.5% | -11.4% |
| Ridge (pooled) | 4 | 9 | £40,803 | £51,457 | 14.1% | +9.5% | +36.5% | -36.0% |
| Ridge (pooled) | 5 | 8 | £42,487 | £51,771 | 14.7% | +14.2% | +38.5% | -52.0% |
| Ridge (pooled) | 6 (provisional) | 7 | £43,212 | £53,295 | 14.3% | +13.8% | +36.4% | -151.8% |
| Ridge (pooled) | 7 (provisional) | 6 | £50,392 | £61,828 | 16.3% | +16.3% | +28.7% | -222.1% |
| Ridge (pooled) | 8 (provisional) | 5 | £56,904 | £63,985 | 17.6% | +17.6% | +25.6% | -361.0% |
| HistGradientBoosting (pooled) | 1 | 12 | £49,364 | £60,130 | 17.6% | -1.6% | +21.1% | -18.4% |
| HistGradientBoosting (pooled) | 2 | 11 | £53,579 | £66,311 | 18.8% | +5.7% | +0.5% | -34.3% |
| HistGradientBoosting (pooled) | 3 | 10 | £45,259 | £58,332 | 16.1% | +11.7% | +35.4% | -27.3% |
| HistGradientBoosting (pooled) | 4 | 9 | £71,263 | £89,341 | 24.5% | +19.1% | -10.9% | -137.5% |
| HistGradientBoosting (pooled) | 5 | 8 | £70,543 | £92,408 | 24.4% | +23.9% | -2.2% | -152.3% |
| HistGradientBoosting (pooled) | 6 (provisional) | 7 | £100,678 | £120,268 | 33.4% | +29.3% | -48.1% | -486.6% |
| HistGradientBoosting (pooled) | 7 (provisional) | 6 | £90,299 | £117,973 | 29.3% | +26.3% | -27.8% | -477.2% |
| HistGradientBoosting (pooled) | 8 (provisional) | 5 | £105,919 | £110,653 | 32.8% | +32.8% | -38.6% | -758.0% |
| HistGradientBoosting + 52-week lag (experiment) | 1 | 12 | £63,131 | £80,147 | 22.6% | -2.8% | -0.9% | -51.4% |
| HistGradientBoosting + 52-week lag (experiment) | 2 | 11 | £63,767 | £81,888 | 22.4% | -13.6% | -18.4% | -59.8% |
| HistGradientBoosting + 52-week lag (experiment) | 3 | 10 | £61,553 | £72,885 | 21.9% | -13.5% | +12.2% | -73.2% |
| HistGradientBoosting + 52-week lag (experiment) | 4 | 9 | £79,333 | £96,046 | 27.3% | -27.3% | -23.5% | -164.4% |
| HistGradientBoosting + 52-week lag (experiment) | 5 | 8 | £81,162 | £94,411 | 28.1% | -28.1% | -17.5% | -190.3% |
| HistGradientBoosting + 52-week lag (experiment) | 6 (provisional) | 7 | £106,552 | £115,171 | 35.4% | -35.4% | -56.7% | -520.8% |
| HistGradientBoosting + 52-week lag (experiment) | 7 (provisional) | 6 | £127,962 | £132,360 | 41.5% | -41.5% | -81.1% | -718.0% |
| HistGradientBoosting + 52-week lag (experiment) | 8 (provisional) | 5 | £153,731 | £156,479 | 47.6% | -47.6% | -101.1% | -1145.4% |

### Top products (pooled): holdout by horizon

| Model | h | n | MAE | RMSE | WAPE | Bias | Skill vs naive | Skill vs seasonal naive |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Naive (last week) | 1 | 240 | £520 | £872 | 50.6% | -4.2% | +0.0% | +12.2% |
| Naive (last week) | 2 | 220 | £515 | £915 | 49.2% | -9.0% | +0.0% | +14.5% |
| Naive (last week) | 3 | 200 | £549 | £1,034 | 52.1% | -16.7% | +0.0% | +11.2% |
| Naive (last week) | 4 | 180 | £592 | £1,114 | 53.9% | -25.4% | +0.0% | +2.4% |
| Naive (last week) | 5 | 160 | £616 | £1,139 | 54.7% | -30.8% | +0.0% | -4.9% |
| Naive (last week) | 6 (provisional) | 140 | £671 | £1,201 | 56.4% | -34.5% | +0.0% | -15.4% |
| Naive (last week) | 7 (provisional) | 120 | £714 | £1,358 | 56.6% | -37.9% | +0.0% | -21.8% |
| Naive (last week) | 8 (provisional) | 100 | £793 | £1,441 | 58.3% | -40.7% | +0.0% | -25.8% |
| Moving average (4 weeks) | 1 | 240 | £430 | £794 | 41.9% | -14.0% | +17.3% | +27.4% |
| Moving average (4 weeks) | 2 | 220 | £458 | £885 | 43.8% | -20.0% | +11.0% | +23.9% |
| Moving average (4 weeks) | 3 | 200 | £487 | £966 | 46.3% | -24.6% | +11.2% | +21.2% |
| Moving average (4 weeks) | 4 | 180 | £547 | £1,062 | 49.8% | -29.9% | +7.6% | +9.8% |
| Moving average (4 weeks) | 5 | 160 | £584 | £1,120 | 52.0% | -32.3% | +5.1% | +0.4% |
| Moving average (4 weeks) | 6 (provisional) | 140 | £642 | £1,225 | 54.0% | -36.1% | +4.3% | -10.4% |
| Moving average (4 weeks) | 7 (provisional) | 120 | £720 | £1,349 | 57.1% | -39.5% | -0.9% | -22.8% |
| Moving average (4 weeks) | 8 (provisional) | 100 | £799 | £1,500 | 58.7% | -44.3% | -0.7% | -26.7% |
| Seasonal naive (same week last year) | 1 | 240 | £592 | £942 | 57.7% | +21.8% | -13.9% | +0.0% |
| Seasonal naive (same week last year) | 2 | 220 | £602 | £964 | 57.6% | +24.4% | -16.9% | +0.0% |
| Seasonal naive (same week last year) | 3 | 200 | £618 | £987 | 58.7% | +26.2% | -12.7% | +0.0% |
| Seasonal naive (same week last year) | 4 | 180 | £607 | £958 | 55.3% | +20.8% | -2.5% | +0.0% |
| Seasonal naive (same week last year) | 5 | 160 | £587 | £943 | 52.2% | +19.5% | +4.7% | +0.0% |
| Seasonal naive (same week last year) | 6 (provisional) | 140 | £581 | £949 | 48.9% | +14.6% | +13.3% | +0.0% |
| Seasonal naive (same week last year) | 7 (provisional) | 120 | £586 | £984 | 46.5% | +12.8% | +17.9% | +0.0% |
| Seasonal naive (same week last year) | 8 (provisional) | 100 | £630 | £1,043 | 46.4% | +13.4% | +20.5% | +0.0% |
| Ridge (pooled) | 1 | 240 | £457 | £770 | 44.5% | +1.5% | +12.2% | +22.9% |
| Ridge (pooled) | 2 | 220 | £508 | £857 | 48.6% | +3.5% | +1.4% | +15.6% |
| Ridge (pooled) | 3 | 200 | £566 | £935 | 53.8% | +7.1% | -3.2% | +8.4% |
| Ridge (pooled) | 4 | 180 | £644 | £1,020 | 58.6% | +8.1% | -8.8% | -6.1% |
| Ridge (pooled) | 5 | 160 | £682 | £1,079 | 60.6% | +11.6% | -10.8% | -16.2% |
| Ridge (pooled) | 6 (provisional) | 140 | £754 | £1,171 | 63.3% | +11.7% | -12.4% | -29.6% |
| Ridge (pooled) | 7 (provisional) | 120 | £833 | £1,285 | 66.0% | +12.4% | -16.7% | -42.1% |
| Ridge (pooled) | 8 (provisional) | 100 | £932 | £1,400 | 68.5% | +13.0% | -17.5% | -47.8% |
| HistGradientBoosting (pooled) | 1 | 240 | £457 | £758 | 44.5% | -2.0% | +12.1% | +22.9% |
| HistGradientBoosting (pooled) | 2 | 220 | £495 | £838 | 47.4% | -0.3% | +3.8% | +17.7% |
| HistGradientBoosting (pooled) | 3 | 200 | £568 | £923 | 54.0% | +5.8% | -3.5% | +8.1% |
| HistGradientBoosting (pooled) | 4 | 180 | £635 | £995 | 57.8% | +6.2% | -7.2% | -4.6% |
| HistGradientBoosting (pooled) | 5 | 160 | £673 | £1,019 | 59.9% | +11.2% | -9.4% | -14.8% |
| HistGradientBoosting (pooled) | 6 (provisional) | 140 | £748 | £1,180 | 62.9% | +15.2% | -11.6% | -28.7% |
| HistGradientBoosting (pooled) | 7 (provisional) | 120 | £851 | £1,346 | 67.5% | +18.4% | -19.3% | -45.3% |
| HistGradientBoosting (pooled) | 8 (provisional) | 100 | £1,002 | £1,496 | 73.7% | +18.3% | -26.4% | -59.0% |
| HistGradientBoosting + 52-week lag (experiment) | 1 | 240 | £476 | £854 | 46.4% | -7.5% | +8.4% | +19.6% |
| HistGradientBoosting + 52-week lag (experiment) | 2 | 220 | £521 | £922 | 49.9% | -10.3% | -1.3% | +13.4% |
| HistGradientBoosting + 52-week lag (experiment) | 3 | 200 | £517 | £977 | 49.1% | -14.7% | +5.7% | +16.3% |
| HistGradientBoosting + 52-week lag (experiment) | 4 | 180 | £564 | £1,045 | 51.4% | -22.2% | +4.7% | +7.0% |
| HistGradientBoosting + 52-week lag (experiment) | 5 | 160 | £610 | £1,117 | 54.3% | -25.0% | +0.9% | -4.0% |
| HistGradientBoosting + 52-week lag (experiment) | 6 (provisional) | 140 | £647 | £1,188 | 54.4% | -28.5% | +3.5% | -11.3% |
| HistGradientBoosting + 52-week lag (experiment) | 7 (provisional) | 120 | £716 | £1,319 | 56.8% | -32.9% | -0.3% | -22.2% |
| HistGradientBoosting + 52-week lag (experiment) | 8 (provisional) | 100 | £772 | £1,440 | 56.8% | -40.1% | +2.6% | -22.5% |

### 80% interval coverage on the holdout (selected models)

| Group | h | Calibration n | Holdout n | Coverage |
|---|---:|---:|---:|---:|
| Business total | 1 | 12 | 12 | 33% |
| Business total | 2 | 11 | 11 | 36% |
| Business total | 3 | 10 | 10 | 40% |
| Business total | 4 | 9 | 9 | 44% |
| Business total | 5 | 8 | 8 | 38% |
| Business total | 6 (provisional) | 7 | 7 | 29% |
| Business total | 7 (provisional) | 6 | 6 | 33% |
| Business total | 8 (provisional) | 5 | 5 | 0% |
| Top products (pooled) | 1 | 240 | 240 | 75% |
| Top products (pooled) | 2 | 220 | 220 | 80% |
| Top products (pooled) | 3 | 200 | 200 | 80% |
| Top products (pooled) | 4 | 180 | 180 | 72% |
| Top products (pooled) | 5 | 160 | 160 | 72% |
| Top products (pooled) | 6 (provisional) | 140 | 140 | 68% |
| Top products (pooled) | 7 (provisional) | 120 | 120 | 63% |
| Top products (pooled) | 8 (provisional) | 100 | 100 | 57% |

### Individual products: holdout WAPE (mean over horizons)

| Product | Selected model | Seasonal naive | Naive |
|---|---:|---:|---:|
| 85123A WHITE HANGING HEART T-LIGHT HOLDER | 51.2% | 84.8% | 62.5% |
| 85099B JUMBO BAG RED RETROSPOT | 37.6% | 34.2% | 52.2% |
| 84879 ASSORTED COLOUR BIRD ORNAMENT | 37.5% | 73.1% | 36.8% |
| 22086 PAPER CHAIN KIT 50'S CHRISTMAS | 62.6% | 14.8% | 56.2% |
| 47566 PARTY BUNTING | 67.1% | 62.3% | 57.9% |
| 21843 RED RETROSPOT CAKE STAND | 56.9% | 95.3% | 60.7% |
| 20685 DOORMAT RED RETROSPOT | 49.7% | 79.3% | 59.2% |
| 21621 VINTAGE UNION JACK BUNTING | 33.7% | 116.6% | 47.1% |
| 85099F JUMBO BAG STRAWBERRY | 81.0% | 99.2% | 107.5% |
| 79321 CHILLI LIGHTS | 61.8% | 62.8% | 66.3% |
| 20725 LUNCH BAG RED RETROSPOT | 23.5% | 27.3% | 27.2% |
| 20914 SET/5 RED RETROSPOT LID GLASS BOWLS | 39.0% | 64.9% | 47.3% |
| 15056N EDWARDIAN PARASOL NATURAL | 82.6% | 157.2% | 90.1% |
| 21931 JUMBO STORAGE BAG SUKI | 32.2% | 68.8% | 35.0% |
| 21232 STRAWBERRY CERAMIC TRINKET BOX | 39.9% | 126.3% | 47.0% |
| 21212 PACK OF 72 RETROSPOT CAKE CASES | 28.4% | 116.4% | 36.9% |
| 85099C JUMBO  BAG BAROQUE BLACK WHITE | 41.4% | 52.0% | 55.1% |
| 21754 HOME BUILDING BLOCK WORD | 31.5% | 141.0% | 39.5% |
| 22114 HOT WATER BOTTLE TEA AND SYMPATHY | 44.6% | 28.9% | 46.3% |
| 22112 CHOCOLATE HOT WATER BOTTLE | 48.8% | 25.6% | 47.3% |
