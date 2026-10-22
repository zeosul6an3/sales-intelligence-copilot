# Data dictionary

## Raw UCI columns (as downloaded)

| Column | Type | Meaning |
|---|---|---|
| `Invoice` | text | 6-digit invoice number. Prefix `C` = cancellation, `A` = bad-debt adjustment |
| `StockCode` | text | Product code (usually 5 digits plus optional letters); special codes for postage, fees, etc. |
| `Description` | text | Product description; sometimes a warehouse note or blank |
| `Quantity` | integer | Units on the line; negative on cancellations and stock notes |
| `InvoiceDate` | timestamp | Date and time of the invoice |
| `Price` | decimal | Unit price in GBP |
| `Customer ID` | number | 5-digit customer number; missing on about 23% of rows |
| `Country` | text | Customer's country |

## Cleaned table `lines` (one per dataset, in `warehouse.duckdb` and `lines.parquet`)

| Column | Type | Meaning |
|---|---|---|
| `line_id` | integer | Sequential ID within the dataset |
| `source_sheet` | text | UCI sheet name (empty for uploads) |
| `source_row` | integer | Row number in the original spreadsheet or CSV (header = row 1) |
| `invoice_id` | text | Invoice/order number, trimmed |
| `invoice_ts` | timestamp | Invoice date and time |
| `invoice_date` | date | Invoice date (used for all period filters) |
| `product_id` | text | Product code, trimmed and upper-cased |
| `raw_description` | text | Description exactly as given (trimmed) |
| `product_name` | text | Display name: most frequent description on the product's sale lines |
| `quantity` | decimal | Units |
| `unit_price` | decimal | Price per unit in the dataset's currency |
| `line_value` | decimal | `quantity × unit_price` |
| `customer_id` | text | Customer identifier, or empty |
| `country` | text | Country as recorded (`Unspecified` if an upload has none) |
| `line_type` | text | Classification; see [data_cleaning.md](data_cleaning.md) |
| `is_duplicate` | boolean | True for the second and later copies of an exactly identical row |
| `is_unusual` | boolean | Product line with an unusually large absolute value |

## Line types

| `line_type` | In product metrics? |
|---|---|
| `product_sale` | Yes: gross sales, units, orders, customers |
| `product_return` | Yes: returns |
| `shipping`, `fees_commission`, `discount`, `manual_adjustment`, `samples`, `gift_voucher`, `bad_debt_adjustment` | No: shown under "Other lines" |
| `test`, `zero_value_stock_note`, `zero_price_line`, `zero_quantity`, `negative_price`, `unclassified` | No: counted in the quality report |
| `invalid_row` (uploads only) | No: counted in the quality report, not stored |

## Files per dataset

| File | Contents |
|---|---|
| `metadata.json` | Name, kind, currency, date range, counts, attribution or source file |
| `quality_report.json` | Row flow, every rule with row counts and values, flags, coverage notes |
| `warehouse.duckdb` | The `lines` table, queried read-only by the app |
| `lines.parquet` | The same table for use in other tools |

The built-in dataset lives in `data/processed/uci/`, and each upload in `data/uploads/upload-<id>/`. Everything under `data/` except READMEs and templates is excluded from Git.

## Metrics

See [data_cleaning.md § 3](data_cleaning.md#3-business-metric-definitions). The definitions are also served by `GET /api/definitions` and shown on the Data quality page.
