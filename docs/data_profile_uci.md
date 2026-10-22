# UCI Online Retail II: raw-data profile

Descriptions stored as numbers (read as text): 4

## Rows, dates and distinct values per sheet

| source_sheet | n_rows | first_ts | last_ts | invoices | stock_codes | customers | missing_customer | missing_description |
|---|---|---|---|---|---|---|---|---|
| Year 2009-2010 | 525461 | 2009-12-01 07:45:00 | 2010-12-09 20:01:00 | 28816 | 4632 | 4383 | 107927 | 2928 |
| Year 2010-2011 | 541910 | 2010-12-01 08:26:00 | 2011-12-09 12:50:00 | 25900 | 4070 | 4372 | 135080 | 1454 |

## Overlap between sheets: identical row groups? (0 differing = identical)

| sheet1_rows | sheet2_rows | differing_groups |
|---|---|---|
| 22523.0 | 22523.0 | 0 |

## Invoice prefixes

| prefix | n_rows | negative_qty | negative_price |
|---|---|---|---|
|  | 1025677 | 3393.0 | 0.0 |
| C | 19165 | 19164.0 | 0.0 |
| A | 6 | 0.0 | 5.0 |

## Negative quantity without a C/A invoice

| price_is_zero | no_customer | n_rows |
|---|---|---|
| True | True | 3393 |

## Most common descriptions on those rows

| description | n_rows |
|---|---|
| <blank> | 2633 |
| check | 121 |
| damages | 83 |
| ? | 81 |
| damaged | 78 |
| missing | 27 |
| sold as set on dotcom | 20 |
| Damaged | 17 |
| smashed | 9 |
| thrown away | 9 |
| Unsaleable, destroyed. | 9 |
| dotcom | 8 |

## Stock codes that are not 5 digits (+ optional letters)

| code | n_rows | c_rows | line_value | description |
|---|---|---|---|---|
| POST | 2086 | 228.0 | 110430.41 | POSTAGE |
| DOT | 1425 | 3.0 | 309844.1 | DOTCOM POSTAGE |
| M | 1403 | 535.0 | -82935.57 | Manual |
| C2 | 277 | 7.0 | 13136.0 | CARRIAGE |
| D | 173 | 168.0 | -12879.63 | Discount |
| S | 102 | 99.0 | -6000.85 | SAMPLES |
| BANK CHARGES | 100 | 66.0 | -35482.25 | Bank Charges |
| ADJUST | 67 | 31.0 | 6835.24 | Adjustment by john on 26/01/2010 16 |
| AMAZONFEE | 36 | 33.0 | -221520.5 | AMAZON FEE |
| DCGS0058 | 31 | 0.0 | 34.82 | MISO PRETTY  GUM |
| GIFT_0001_20 | 29 | 0.0 | 471.06 | Dotcomgiftshop Gift Voucher £20.00 |
| GIFT_0001_30 | 29 | 0.0 | 610.09 | Dotcomgiftshop Gift Voucher £30.00 |
| DCGSSGIRL | 25 | 0.0 | 295.63 | GIRLS PARTY BAG |
| DCGSSBOY | 23 | 0.0 | 251.35 | BOYS PARTY BAG |
| PADS | 19 | 1.0 | -36.58 | PADS TO MATCH ALL CUSHIONS |
| CRUK | 16 | 16.0 | -7933.43 | CRUK Commission |
| GIFT_0001_10 | 16 | 0.0 | 126.21 | Dotcomgiftshop Gift Voucher £10.00 |
| TEST001 | 15 | 4.0 | 202.5 | This is a test product. |
| DCGS0003 | 14 | 0.0 | 32.59 | BOXED GLASS ASHTRAY |
| DCGS0076 | 14 | 0.0 | 275.96 | SUNJAR LED NIGHT NIGHT LIGHT |
| GIFT_0001_50 | 8 | 0.0 | 253.59 | Dotcomgiftshop Gift Voucher £50.00 |
| GIFT_0001_40 | 7 | 0.0 | 166.09 | Dotcomgiftshop Gift Voucher £40.00 |
| DCGS0069 | 6 | 0.0 | 80.31 | OOH LA LA DOGS COLLAR |
| B | 6 | 0.0 | -147614.08 | Adjust bad debt |
| DCGS0004 | 5 | 0.0 | 67.94 | HAYNES CAMPER SHOULDER BAG |

## Codes differing only by letter case or spaces

| codes |
|---|
| 174 |

## Exact duplicate copies and how often copies sit on adjacent rows

| extra_copies | pct_adjacent |
|---|---|
| 11812 | 14.3 |

## Largest lines by absolute value

| Invoice | StockCode | Description | Quantity | Price | line_value | InvoiceDate |
|---|---|---|---|---|---|---|
| 581483 | 23843 | PAPER CRAFT , LITTLE BIRDIE | 80995 | 2.08 | 168469.6 | 2011-12-09 09:15:00 |
| C581484 | 23843 | PAPER CRAFT , LITTLE BIRDIE | -80995 | 2.08 | -168469.6 | 2011-12-09 09:27:00 |
| 541431 | 23166 | MEDIUM CERAMIC TOP STORAGE JAR | 74215 | 1.04 | 77183.6 | 2011-01-18 10:01:00 |
| C541433 | 23166 | MEDIUM CERAMIC TOP STORAGE JAR | -74215 | 1.04 | -77183.6 | 2011-01-18 10:17:00 |
| A506401 | B | Adjust bad debt | 1 | -53594.36 | -53594.36 | 2010-04-29 13:36:00 |
| A516228 | B | Adjust bad debt | 1 | -44031.79 | -44031.79 | 2010-07-19 11:24:00 |
| 556444 | 22502 | PICNIC BASKET WICKER 60 PIECES | 60 | 649.5 | 38970.0 | 2011-06-10 15:28:00 |
| C556445 | M | Manual | -1 | 38970.0 | -38970.0 | 2011-06-10 15:31:00 |
| A528059 | B | Adjust bad debt | 1 | -38925.87 | -38925.87 | 2010-10-20 12:04:00 |
| 512771 | M | Manual | 1 | 25111.09 | 25111.09 | 2010-06-17 16:53:00 |

## Rows and trading days per month

| ym | n_rows | trading_days | last_day |
|---|---|---|---|
| 2009-12 | 45228 | 21 | 2009-12-23 00:00:00 |
| 2010-01 | 31555 | 24 | 2010-01-31 00:00:00 |
| 2010-02 | 29388 | 24 | 2010-02-28 00:00:00 |
| 2010-03 | 41511 | 27 | 2010-03-31 00:00:00 |
| 2010-04 | 34057 | 23 | 2010-04-30 00:00:00 |
| 2010-05 | 35323 | 24 | 2010-05-30 00:00:00 |
| 2010-06 | 39983 | 26 | 2010-06-30 00:00:00 |
| 2010-07 | 33383 | 26 | 2010-07-30 00:00:00 |
| 2010-08 | 33306 | 26 | 2010-08-31 00:00:00 |
| 2010-09 | 42091 | 26 | 2010-09-30 00:00:00 |
| 2010-10 | 59098 | 26 | 2010-10-31 00:00:00 |
| 2010-11 | 78015 | 26 | 2010-11-30 00:00:00 |
| 2010-12 | 42481 | 20 | 2010-12-23 00:00:00 |
| 2011-01 | 35147 | 24 | 2011-01-31 00:00:00 |
| 2011-02 | 27707 | 24 | 2011-02-28 00:00:00 |
| 2011-03 | 36748 | 27 | 2011-03-31 00:00:00 |
| 2011-04 | 29916 | 21 | 2011-04-28 00:00:00 |
| 2011-05 | 37030 | 25 | 2011-05-31 00:00:00 |
| 2011-06 | 36874 | 26 | 2011-06-30 00:00:00 |
| 2011-07 | 39518 | 26 | 2011-07-31 00:00:00 |
| 2011-08 | 35284 | 26 | 2011-08-31 00:00:00 |
| 2011-09 | 50226 | 26 | 2011-09-30 00:00:00 |
| 2011-10 | 60742 | 26 | 2011-10-31 00:00:00 |
| 2011-11 | 84711 | 26 | 2011-11-30 00:00:00 |
| 2011-12 | 25526 | 8 | 2011-12-09 00:00:00 |

