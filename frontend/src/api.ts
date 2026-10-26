// Typed access to the FastAPI backend. Every figure shown in the dashboard
// comes from these endpoints; the frontend never calculates business metrics.

export type DatasetMetadata = {
  id: string
  name: string
  kind: 'builtin' | 'upload'
  description: string
  currency: string
  currency_symbol: string
  first_date: string
  last_date: string
  lines: number
  products: number
  customers: number | null
  countries: number
  attribution?: string
  source_filename?: string
}

export type Preset = { label: string; start: string; end: string }

export type DatasetInfo = {
  metadata: DatasetMetadata
  coverage: { first_date: string; last_date: string }
  presets: Record<string, Preset>
  countries: string[]
}

export type Kpis = {
  gross_sales: number
  returns: number
  net_revenue: number
  orders: number
  customers: number
  units: number
  avg_order_value: number | null
}

export type Summary = {
  current: Kpis
  previous: Kpis
  previous_period: { start: string; end: string }
  previous_period_covered: boolean
}

export type SeriesPoint = {
  period_start: string
  period_end: string
  gross_sales: number
  returns: number
  net_revenue: number
  orders: number
  partial: boolean
  has_unusual: boolean
  no_business_transactions: boolean
  note: string | null
}

export type ProductRow = {
  product_id: string
  product_name: string
  net_revenue: number
  gross_sales: number
  returns: number
  units: number
  orders: number
}

export type CountryRow = {
  country: string
  net_revenue: number
  orders: number | null
  customers: number | null
}

export type OtherLine = { line_type: string; label: string; lines: number; value: number }

export type Issue = {
  code: string
  severity: 'error' | 'warning' | 'info'
  message: string
  rows: number | null
  examples: { row: number; value: string | null }[]
}

export type QualityRule = {
  line_type: string
  label: string
  condition: string
  treatment: string
  evidence: string
  rows: number
  value: number
}

export type QualityReport = {
  generated_at_utc: string
  source: {
    file: string
    sha256?: string
    sheets?: { name: string; rows: number; first_ts: string; last_ts: string }[]
  }
  row_flow: Record<string, number | boolean | string>
  rules: QualityRule[]
  flags?: Record<string, unknown>
  issues?: Issue[]
  coverage: { first_date: string; last_date: string; notes: string[] }
}

export type Definitions = {
  metrics: Record<string, { label: string; definition: string }>
  not_available: string
  line_types: Record<string, string>
}

export type StagedUpload = {
  upload_id: string
  filename: string
  columns: string[]
  sample_rows: Record<string, string>[]
  suggested_mapping: Record<string, string | null>
  fields: { required: string[]; optional: string[]; descriptions: Record<string, string> }
}

export type Validation = {
  rows_total: number
  rows_invalid: number
  rows_usable: number
  first_date: string | null
  last_date: string | null
  line_types: { line_type: string; rows: number; value: number }[]
  issues: Issue[]
  can_import: boolean
  preview: Record<string, string | number | null>[]
}

export type UploadOptions = {
  mapping: Record<string, string | null>
  currency: string
  day_first: boolean
  name?: string
}

export class ApiError extends Error {}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message =
      response.status >= 500
        ? 'The server hit an unexpected error. Details are in the terminal running `uv run sic serve`.'
        : `Request failed (HTTP ${response.status})`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      // keep the generic message
    }
    throw new ApiError(message)
  }
  return response.json() as Promise<T>
}

export function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  return fetch(url, { signal }).then((r) => parse<T>(r))
}

export function postJson<T>(url: string, body: unknown): Promise<T> {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then((r) => parse<T>(r))
}

export function uploadFile(file: File): Promise<StagedUpload> {
  const form = new FormData()
  form.append('file', file)
  return fetch('/api/uploads', { method: 'POST', body: form }).then((r) => parse<StagedUpload>(r))
}

export function deleteDataset(id: string): Promise<unknown> {
  return fetch(`/api/datasets/${encodeURIComponent(id)}`, { method: 'DELETE' }).then((r) => parse(r))
}

export type Query = { start: string; end: string; country: string }

export function withQuery(path: string, params: Record<string, string | number | undefined | null>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `${path}?${text}` : path
}

export type KnownIssue = {
  id: string
  week_start: string
  week_end: string
  product_id: string
  product_name: string
  amount: number
  summary: string
  forecasting_treatment: string
  transactions: {
    invoice_id: string
    invoice_ts: string
    product_id: string
    description: string | null
    quantity: number
    unit_price: number
    line_value: number
    line_type: string
  }[]
}

export type NA = { value: number | null; reason?: string }
export type MetricCell = {
  n: number
  mae: NA
  rmse: NA
  wape: NA
  bias: NA
  skill_vs_naive: NA
  skill_vs_seasonal_naive: NA
}
export type MetricTable = Record<string, Record<string, Record<string, MetricCell>>>

export type FuturePoint = {
  week_start: string
  h: number
  forecast: number
  lower: number | null
  upper: number | null
  provisional: boolean
}

export type Evaluation = {
  dataset_id: string
  target: { label: string; description: string; week: string }
  calendar: string
  windows: Record<string, { weeks: string; count: number; from: string; to: string }>
  horizons: Record<
    string,
    {
      supported: boolean
      provisional: boolean
      validation_points_per_series: number
      calibration_points_per_series: number
      holdout_points_per_series: number
    }
  >
  series: { id: string; name: string }[]
  product_selection: { rule: string; eligible: number; products_with_sales: number }
  corrections: {
    id: string
    amount: number
    week_start: string
    product_id: string
    product_name: string
    applied_to: string[]
    product_in_forecast_set: boolean
    total_week_reported: number
    total_week_adjusted: number
    product_week_reported: number
    product_week_adjusted: number
    rationale: string
    rule: string
  }[]
  decision: Record<
    string,
    { selected: string; mean_validation_wape: Record<string, number>; tie_rule_applied: boolean }
  >
  selection_rule: { metric: string; candidates: string[]; experiments: string[]; tie_tolerance: number }
  validation_metrics: MetricTable
  holdout_metrics: MetricTable
  holdout_metrics_by_series: MetricTable
  holdout_coverage: Record<string, Record<string, { coverage: number; n: number }>>
  calibration_quantiles: Record<string, Record<string, { n: number }>>
  holdout_note: string
  selection_created_at_utc: string
  holdout_created_at_utc: string
  history: {
    weeks: string[]
    week_flags: (string | null)[]
    adjusted: Record<string, number[]>
    reported: Record<string, number[]>
    zero_kind: Record<string, (string | null)[]>
  }
  holdout_predictions: {
    model: string
    series: string
    h: number
    week_start: string
    actual: number
    forecast: number
    lower: number | null
    upper: number | null
  }[]
  future_forecast: {
    origin_week: string
    series: Record<
      string,
      { model: string; points: FuturePoint[]; comparison?: { model: string; points: { week_start: string; forecast: number }[] } }
    >
  }
}

export type Job = {
  id: string
  dataset_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'not_eligible' | 'interrupted'
  progress: number
  message: string
  error: string | null
  created_at_utc: string
  finished_at_utc: string | null
}

export type OperationalGroup = {
  model: string
  source: string
  frozen_selection: string
  override: {
    model: string
    replaces: string
    decided_on: string
    decided_by: string
    reason: string
    evidence: string
  } | null
  evaluation_note: string | null
  interval_calibration_n: Record<string, number>
  interval_holdout_coverage: Record<string, { coverage: number; n: number }>
  interval_mean_holdout_coverage: number | null
  interval_note: string
}

export type Operational = {
  groups: Record<string, OperationalGroup>
  future_forecast: {
    origin_week: string
    series: Record<
      string,
      {
        model: string
        points: FuturePoint[]
        comparison?: { model: string; role: string; points: { week_start: string; forecast: number }[] }
      }
    >
  }
}

export type ForecastOverview = {
  target: { label: string; description: string }
  eligibility: { eligible: boolean; reason: string | null }
  evaluation: Evaluation | null
  operational: Operational | null
  job: Job | null
}
