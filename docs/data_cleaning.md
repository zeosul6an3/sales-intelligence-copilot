# Data cleaning: UCI Online Retail II

This document records what the raw data contains, the rule applied to each case, the evidence behind each rule, and the decisions made by the project owner. Every figure below comes from the official file (SHA-256 `bcbe73b3…2df2e980`) and can be reproduced with:

```bash
uv run python scripts/download_data.py      # official zip + checksums
uv run python scripts/profile_raw_data.py   # evidence tables (saved in docs/data_profile_uci.md)
uv run python scripts/prepare_data.py       # applies the rules, prints row counts
```

The app's **Data quality** page shows the same counts, read from the generated `quality_report.json`.

## 1. What the raw file contains

`online_retail_II.xlsx` has two sheets with the same 8 columns: `Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country`.

| | Year 2009-2010 | Year 2010-2011 |
|---|---|---|
| Rows | 525,461 | 541,910 |
| First / last timestamp | 2009-12-01 07:45 / 2010-12-09 20:01 | 2010-12-01 08:26 / 2011-12-09 12:50 |
| Invoices | 28,816 | 25,900 |
| Stock codes | 4,632 | 4,070 |
| Customers | 4,383 | 4,372 |
| Missing Customer ID | 107,927 (20.5%) | 135,080 (24.9%) |
| Missing Description | 2,928 | 1,454 |

Prices are in **pounds sterling (GBP)**. No other column is ever missing.

## 2. Findings and rules

### Overlap between the sheets
- **Evidence:** 1–9 December 2010 appears in **both** sheets: 22,523 rows and 1,088 invoices in each. A null-safe, row-by-row comparison of all 8 columns finds **0 differences**.
- **Rule:** keep the second sheet's copy and drop the first sheet's 22,523 rows. The pipeline re-runs the comparison every time and **stops with an error** if the copies ever differ.
- **Result:** 1,067,371 rows read − 22,523 = **1,044,848 rows kept**. Every kept row gets exactly one line type, and the total reconciles (checked in code and tests).

### Line types (rules apply in this order; the first match wins)

| Line type | Rule | Rows | Value (£) | Treatment | Evidence |
|---|---|---:|---:|---|---|
| Bad-debt adjustment | invoice starts with `A` | 6 | −147,614.08 | Excluded from sales; reported separately | "Adjust bad debt", code `B`, no customer |
| Shipping | code `POST`, `DOT`, `C2`, `C3` | 3,789 | 433,410.51 | Excluded from product revenue | Postage and carriage descriptions |
| Fees and commission | `AMAZONFEE`, `BANK CHARGES`, `CRUK` | 152 | −264,936.18 | Excluded from product revenue | Fee and commission descriptions |
| Discount | code `D` | 173 | −12,879.63 | Excluded from product revenue | "Discount", nearly all on cancellation invoices |
| Manual adjustment | `M`, `ADJUST`, `ADJUST2` | 1,473 | −75,369.28 | Excluded from product revenue (**owner decision**) | See below |
| Samples | code `S` | 102 | −6,000.85 | Excluded from product revenue | "SAMPLES" |
| Gift voucher | code starts `GIFT` | 101 | 1,686.61 | Excluded from product revenue | Stored value, not merchandise |
| Test | code starts `TEST` | 17 | 203.50 | Excluded from everything | "This is a test product." |
| **Product return** | invoice starts `C` and quantity < 0 | 17,974 | −719,692.94 | **Returns** | UCI documents `C` as cancellation |
| Zero-value stock note | quantity < 0 and price = 0 | 3,391 | 0.00 | Excluded from sales and units | See below |
| Zero-price line | price = 0 | 2,582 | 0.00 | Excluded from sales and units | 98% without a customer |
| **Product sale** | quantity > 0 and price > 0 | 1,015,088 | 19,700,954.46 | **Gross sales, units, orders** | Ordinary lines |
| Unclassified | no rule matched | 0 | 0.00 | Excluded; reported | Kept as a safety net |

**Product codes such as `DCGS0058`** (dot-com gift-shop items), `SP1002` and `PADS` are genuine products, so they're treated as products.

### Cancellations versus returns
- `C`-prefixed invoices: 19,165 rows after removing the sheet overlap.
- 17,974 are product lines and become **product returns**. The rest carry non-product codes (manual, shipping, discount, fees, samples) and are classified by those codes.
- The data cannot tell a pre-shipment cancellation from a post-delivery return. Both are reported as **returns/cancellations**, dated by the cancellation's own date.
- Only one `C` line has a positive quantity: a `Manual` line, handled by the manual-adjustment rule.

### Negative quantities without a `C` invoice (not assumed to be stock adjustments)
- **Evidence:** all 3,393 such rows have **price £0 and no customer**. Their descriptions read like warehouse notes: blank (2,633), "check", "damages", "?", "damaged", "missing", "thrown away", "given away", "sold as set on dotcom".
- **Rule:** the stock-note rule requires *both* a negative quantity *and* a zero price. A negative quantity at a non-zero price would fall through to **Unclassified** and be reported, not silently absorbed. The tests include such a row.
- Two of the 3,393 rows carry non-product codes (`GIFT`, `C3`) and are classified by those codes first, which leaves 3,391 stock notes. All of them are £0, so no revenue figure changes.

### Product codes
- 174 codes appear in more than one form: 173 differ only by letter case (e.g. `15056BL` / `15056bl`), and one has stray spaces. The case variants have **identical descriptions**.
- **Rule:** codes are trimmed and upper-cased.

### Descriptions
- 4,275 rows have no description; all of them are £0 lines without a customer. Four descriptions were stored as numbers and are read as text.
- Each product's **display name** is its most frequent description on sale lines.

### Missing Customer ID
- 226,882 product-sale rows (£2,576,013.46 of gross sales) have no customer ID.
- **Rule:** they are **kept in revenue**, because they are real sales, and excluded only from the "identified customers" count.

### Exact duplicate rows (**owner decision: keep and flag**)
- **Evidence:** 11,812 rows are exact copies of another row (all 8 columns identical), 11,731 of them product sales worth £57,093 (0.29% of gross sales). 86% of the copies are **not** on adjacent spreadsheet rows, and 70% have quantity 1, which looks more like the same item scanned again within one order than an export error. It cannot be proven either way.
- **Rule:** kept as genuine lines, flagged with `is_duplicate`, and the total is shown on the Data quality page.

### Manual adjustments (**owner decision: separate from product revenue**)
- **Evidence:** `M` (Manual) lines mix 900 manual charges (+£349k) with 565 manual credits on cancellation invoices (−£425k), and none can be tied to a product. Some clearly correct a product sale. For example, invoice 556444 sold 60 "PICNIC BASKET WICKER 60 PIECES" at £649.50 (£38,970), and three minutes later a Manual credit of exactly £38,970 reversed it.
- **Rule:** reported separately (net −£75,369). Product totals always equal the sum of products.
- **Known effect:** the week of 6 June 2011 overstates product revenue by £38,970. This line is flagged as unusual.

### Unusual transactions (**owner decision: keep and flag**)
- **Rule:** product lines with |value| ≥ £10,000, about 4 times the 99.99th percentile (£2,500). It flags exactly 6 lines:

| Invoice | Product | Quantity | Value (£) | When |
|---|---|---:|---:|---|
| 581483 | PAPER CRAFT, LITTLE BIRDIE | 80,995 | 168,469.60 | 2011-12-09 09:15 |
| C581484 | (its cancellation) | −80,995 | −168,469.60 | 2011-12-09 09:27 |
| 541431 | MEDIUM CERAMIC TOP STORAGE JAR | 74,215 | 77,183.60 | 2011-01-18 10:01 |
| C541433 | (its cancellation) | −74,215 | −77,183.60 | 2011-01-18 10:17 |
| 556444 | PICNIC BASKET WICKER 60 PIECES | 60 | 38,970.00 | 2011-06-10 15:28 |
| 530715 | ROTATING SILVER ANGELS T-LIGHT HLDR | 9,360 | 15,818.40 | 2010-11-04 11:36 |

- The two huge orders cancel out in net revenue but inflate gross sales and returns in their weeks. Charts mark those weeks, and the tooltip says so.

### Incomplete periods and gaps
- **December 2011 is partial:** the data ends on 9 December, so "last complete month" resolves to November 2011.
- **Partial periods in charts:** any week or month not fully covered by the data (or by the chosen filter) is drawn lighter and labelled "partial".
- **Christmas:** no trading is recorded from 24 Dec to 3 Jan in either year. These are closures, not missing data, and appear as zero weeks.
- **Saturdays:** almost no Saturday trading (402 rows in two years).

### Countries
Values are kept as recorded: "EIRE" means Ireland, and "Unspecified" (752 sale rows) and "European Community" (57) are kept as they are.

## 3. Business-metric definitions

These apply everywhere: dashboard, assistant (Milestone 4) and reports.

| Metric | Definition |
|---|---|
| Gross sales | Σ quantity × unit price over product-sale lines |
| Returns | Value of product-return lines, shown as a positive amount |
| Net revenue | Gross sales − returns (**products only**; **owner decision**) |
| Orders | Distinct invoices with at least one product-sale line |
| Units sold | Σ quantity over product-sale lines |
| Average order value | Gross sales ÷ orders |
| Identified customers | Distinct customer IDs on product-sale lines |

- **Reported separately, never mixed into net revenue:** shipping, fees and commission, discounts, manual adjustments, samples, gift vouchers, test lines, bad-debt adjustments.
- **Not available:** profit, margin and stock availability. The data has no cost or inventory information.

## 4. Uploaded CSVs

Uploads use a simpler, generic rule set, applied in this order:
1. Rows with a missing or unreadable invoice ID, date, product ID, quantity or price are **excluded and counted**.
2. Zero quantity → excluded.
3. Negative price → excluded from sales.
4. Zero price → excluded.
5. Negative quantity → **return**.
6. Positive quantity → **sale**.

Other behaviour:
- **Duplicates:** flagged and kept, as for the built-in data.
- **Unusual lines:** the same relative rule (4 × the 99.99th percentile of that dataset's line values).
- **Dates:** ISO dates are always read as ISO. For other formats, the user chooses day-first or month-first. Conflicting or ambiguous dates are reported with row numbers.
- **Currency:** each dataset has exactly one currency, declared by the user. A mixed currency column is rejected.
- **Isolation:** each upload is stored in its own folder and DuckDB file and never mixed with other data. The UCI forecasting model is **not** applied to uploads.
