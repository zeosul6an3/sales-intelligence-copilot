import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  getJson,
  type Evaluation,
  type ForecastOverview,
  type Job,
  type MetricCell,
  type NA,
  type Operational,
} from '../api'
import Chart, { type Tokens } from '../components/Chart'
import { money, moneyExact, shortDate } from '../format'
import { useApi } from '../hooks'

const MODEL_LABELS: Record<string, string> = {
  naive: 'Naive (last week)',
  moving_average_4: 'Moving average (4 weeks)',
  seasonal_naive: 'Seasonal naive (same week last year)',
  ridge: 'Ridge (pooled)',
  hist_gradient_boosting: 'HistGradientBoosting (pooled)',
  hist_gradient_boosting_lag52: 'HistGradientBoosting + 52-week lag (experiment)',
}
const label = (m: string) => MODEL_LABELS[m] ?? m
const pct = (c: NA | undefined, signed = false) =>
  !c || c.value === null ? 'n/a' : `${signed && c.value > 0 ? '+' : ''}${(c.value * 100).toFixed(1)}%`
const meanWape = (by: Record<string, MetricCell> | undefined) => {
  const values = Object.values(by ?? {}).map((m) => m.wape.value)
  return values.length && values.every((v) => v !== null)
    ? values.reduce((a, b) => a + (b as number), 0) / values.length
    : null
}

type Props = { datasetId: string; currency: string; onOpenIssue: () => void }

export default function Forecast({ datasetId, currency, onOpenIssue }: Props) {
  const overview = useApi<ForecastOverview>(`/api/datasets/${datasetId}/forecast`)
  const [job, setJob] = useState<Job | null>(null)
  const [seriesId, setSeriesId] = useState('total')
  const [horizon, setHorizon] = useState(1)

  useEffect(() => setJob(overview.data?.job ?? null), [overview.data])
  useEffect(() => setSeriesId('total'), [datasetId])

  // Poll a running job, then reload the results when it finishes.
  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return
    const timer = setInterval(async () => {
      try {
        const next = await getJson<Job>(`/api/jobs/${job.id}`)
        setJob(next)
        if (!['queued', 'running'].includes(next.status)) overview.reload()
      } catch {
        // keep polling; a transient error should not stop the progress display
      }
    }, 1000)
    return () => clearInterval(timer)
  }, [job, overview])

  const startTraining = async () => {
    const response = await fetch(`/api/datasets/${datasetId}/forecast/train`, { method: 'POST' })
    const body = await response.json()
    if (response.ok) setJob(body)
    else alert(body.detail ?? 'Could not start training')
  }

  if (overview.error) return <div className="notice notice-error">{overview.error}</div>
  if (!overview.data) return <p className="muted">Loading…</p>
  const { evaluation, operational, eligibility, target } = overview.data
  const running = job && ['queued', 'running'].includes(job.status)

  return (
    <div className="grid">
      <section className="card">
        <div className="card-header">
          <h2>Forecast target: {target.label} (weekly)</h2>
          <button className="button" disabled={Boolean(running) || !eligibility.eligible} onClick={startTraining}>
            {evaluation ? 'Retrain and re-evaluate' : 'Train and evaluate'}
          </button>
        </div>
        <p className="small">
          <strong>{target.label}</strong> is the dashboard's <strong>Net product revenue</strong> (product sales minus
          product returns, complete Monday–Sunday weeks) with documented forecasting-only corrections applied. The
          dashboard figures and the stored transactions are not changed.
        </p>
        {!eligibility.eligible && <div className="notice notice-warning">{eligibility.reason}</div>}
        {job && <JobStatus job={job} />}
        {!evaluation && eligibility.eligible && !running && (
          <p className="muted small">No evaluated model yet. Training runs in the background with progress shown here.</p>
        )}
      </section>
      {evaluation && operational && (
        <Results
          evaluation={evaluation}
          op={operational}
          currency={currency}
          seriesId={seriesId}
          setSeriesId={setSeriesId}
          horizon={horizon}
          setHorizon={setHorizon}
          onOpenIssue={onOpenIssue}
        />
      )}
    </div>
  )
}

function JobStatus({ job }: { job: Job }) {
  const labels: Record<Job['status'], string> = {
    queued: 'Queued',
    running: 'Running',
    succeeded: '✓ Finished',
    failed: '✕ Failed',
    not_eligible: '! Not eligible',
    interrupted: '! Interrupted',
  }
  return (
    <div className="small" aria-live="polite">
      <strong>{labels[job.status]}</strong> · {job.message}
      {['queued', 'running'].includes(job.status) && (
        <div className="progress" role="progressbar" aria-valuenow={Math.round(job.progress * 100)}>
          <div style={{ width: `${Math.round(job.progress * 100)}%` }} />
        </div>
      )}
      {job.error && job.status === 'failed' && <div className="notice notice-error">{job.error}</div>}
    </div>
  )
}

type ResultsProps = {
  evaluation: Evaluation
  op: Operational
  currency: string
  seriesId: string
  setSeriesId: (s: string) => void
  horizon: number
  setHorizon: (h: number) => void
  onOpenIssue: () => void
}

function Results({ evaluation: ev, op, currency, seriesId, setSeriesId, horizon, setHorizon, onOpenIssue }: ResultsProps) {
  const group = seriesId === 'total' ? 'total' : 'products'
  const g = op.groups[group]
  const frozen = ev.decision[group]?.selected
  const horizons = Object.entries(ev.horizons)
    .filter(([, v]) => v.supported)
    .map(([h]) => Number(h))
  const provisional = horizons.filter((h) => ev.horizons[h].provisional)
  const future = op.future_forecast.series[seriesId]
  const name = ev.series.find((s) => s.id === seriesId)?.name ?? seriesId
  const comparisonModel = future?.comparison?.model ?? (g.model === 'seasonal_naive' ? frozen : 'seasonal_naive')

  // Without an override: warn when the frozen selection lost to seasonal naive on the holdout.
  const selHold = meanWape(ev.holdout_metrics[frozen]?.[group])
  const snHold = meanWape(ev.holdout_metrics.seasonal_naive?.[group])

  return (
    <>
      <section className="card">
        <div className="card-header">
          <h2>Series</h2>
          <label className="field" style={{ flexDirection: 'row', alignItems: 'center' }}>
            <span>Show</span>
            <select value={seriesId} onChange={(e) => setSeriesId(e.target.value)}>
              {ev.series.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id === 'total' ? s.name : `${s.name} (${s.id})`}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="small">
          Model used for {group === 'total' ? 'the business total' : 'products'}: <strong>{label(g.model)}</strong> ({g.source}).
          {!g.override &&
            ` Chosen by the frozen rule (lowest validation WAPE averaged over horizons 1–${Math.max(...horizons)}).`}
          {provisional.length > 0 && ` Horizons ${provisional.join(', ')} are provisional: their calibration samples are small.`}
        </p>
        {g.override && (
          <div className="notice notice-warning" role="note">
            <strong>! Operational override, chosen after reviewing holdout results ({g.override.decided_on}).</strong>{' '}
            {label(g.model)} replaces the frozen validation selection, {label(g.override.replaces)}, which stays on record
            and is shown as a comparison line. {g.evaluation_note} Its holdout WAPE below is therefore shown for reference
            only, not as evidence that this choice is accurate.
          </div>
        )}
        {!g.override && selHold !== null && snHold !== null && selHold > snHold && (
          <div className="notice notice-warning">
            ! On the final holdout the selected model was less accurate than seasonal naive ({(selHold * 100).toFixed(1)}%
            vs {(snHold * 100).toFixed(1)}% mean WAPE). The selection is kept because it was fixed before the holdout was
            evaluated.
          </div>
        )}
        <div className={`notice ${(g.interval_mean_holdout_coverage ?? 1) < 0.75 ? 'notice-warning' : 'notice-info'}`}>
          {(g.interval_mean_holdout_coverage ?? 1) < 0.75 ? '! ' : 'i '}Ranges: {g.interval_note}
        </div>
        {ev.corrections
          .filter((c) => c.applied_to.includes(seriesId))
          .map((c) => (
            <div className="notice notice-info" key={c.id}>
              i Week of {shortDate(c.week_start)}: adjusted by −{moneyExact(c.amount, currency)} (
              {seriesId === 'total' ? 'business total' : 'this product'} reported{' '}
              {moneyExact(seriesId === 'total' ? c.total_week_reported : c.product_week_reported, currency)}, adjusted{' '}
              {moneyExact(seriesId === 'total' ? c.total_week_adjusted : c.product_week_adjusted, currency)}).{' '}
              <button className="link-button" onClick={onOpenIssue}>
                Why?
              </button>
            </div>
          ))}
        {future && <FutureChart ev={ev} op={op} seriesId={seriesId} currency={currency} name={name} />}
        {future && <FutureTable op={op} seriesId={seriesId} currency={currency} />}
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Historical backtest: final holdout ({ev.windows.holdout.from} → {ev.windows.holdout.to})</h2>
          <label className="field" style={{ flexDirection: 'row', alignItems: 'center' }}>
            <span>Weeks ahead</span>
            <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
              {horizons.map((h) => (
                <option key={h} value={h}>
                  {h}
                  {ev.horizons[h].provisional ? ' (provisional)' : ''}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="card-sub">
          Forecasts made {horizon} week{horizon > 1 ? 's' : ''} before each holdout week, using only earlier data.
          These are past tests, not future forecasts. {ev.holdout_note}
        </p>
        <BacktestChart
          ev={ev}
          seriesId={seriesId}
          horizon={horizon}
          currency={currency}
          model={g.model}
          comparison={comparisonModel}
        />
      </section>

      <MetricsCard ev={ev} op={op} group={group} />
      {group === 'products' && <ProductTable ev={ev} model={g.model} seriesId={seriesId} />}
      <WindowsCard ev={ev} />
    </>
  )
}

type FutureProps = { ev: Evaluation; op: Operational; seriesId: string; currency: string; name: string }

function FutureChart({ ev, op, seriesId, currency, name }: FutureProps) {
  const future = op.future_forecast.series[seriesId]
  const compName = future.comparison
    ? `${label(future.comparison.model)} (${future.comparison.role})`
    : ''
  const build = useCallback(
    (t: Tokens) => {
      const histWeeks = ev.history.weeks.slice(-52)
      const actual = ev.history.adjusted[seriesId].slice(-52)
      const reported = ev.history.reported[seriesId].slice(-52)
      const flags = ev.history.week_flags.slice(-52)
      const kinds = ev.history.zero_kind[seriesId].slice(-52)
      const weeks = [...histWeeks, ...future.points.map((p) => p.week_start)]
      const pad = (n: number) => Array(n).fill(null)
      const last = actual[actual.length - 1]
      const lower = future.points.map((p) => p.lower)
      const width = future.points.map((p) => (p.lower !== null && p.upper !== null ? p.upper - p.lower : null))
      return {
        animation: false,
        grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
        legend: { top: 0, textStyle: { color: t.textSecondary, fontSize: 11 }, data: ['Actual (adjusted)', 'Forecast', ...(compName ? [compName] : []), '80% range'] },
        tooltip: {
          trigger: 'axis',
          backgroundColor: t.surface,
          borderColor: t.axis,
          textStyle: { color: t.text, fontSize: 12 },
          formatter: (items: { dataIndex: number }[]) => {
            const i = items[0].dataIndex
            const lines = [`<strong>Week of ${shortDate(weeks[i])}</strong>`]
            if (i < histWeeks.length) {
              lines.push(`Adjusted actual: ${moneyExact(actual[i], currency)}`)
              if (reported[i] !== actual[i]) lines.push(`Reported (dashboard): ${moneyExact(reported[i], currency)}`)
              if (flags[i]) lines.push(`<span style="opacity:.75">${flags[i]}</span>`)
              else if (kinds[i]) lines.push(`<span style="opacity:.75">${kinds[i]}</span>`)
            } else {
              const p = future.points[i - histWeeks.length]
              lines.push(`Forecast (${label(future.model)}): <strong>${moneyExact(p.forecast, currency)}</strong>`)
              if (p.lower !== null && p.upper !== null)
                lines.push(`80% range: ${moneyExact(p.lower, currency)} – ${moneyExact(p.upper, currency)}`)
              const c = future.comparison?.points[i - histWeeks.length]
              if (c) lines.push(`${compName}: ${moneyExact(c.forecast, currency)}`)
              if (p.provisional) lines.push('<span style="opacity:.75">Provisional horizon</span>')
            }
            return lines.join('<br/>')
          },
        },
        xAxis: {
          type: 'category',
          data: weeks.map((w) => shortDate(w)),
          axisLine: { lineStyle: { color: t.axis } },
          axisTick: { show: false },
          axisLabel: { color: t.muted, fontSize: 11, hideOverlap: true },
        },
        yAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: t.grid } },
          axisLabel: { color: t.muted, fontSize: 11, formatter: (v: number) => money(v, currency, true) },
        },
        series: [
          { name: '80% range', type: 'line', stack: 'band', data: [...pad(histWeeks.length), ...lower], lineStyle: { opacity: 0 }, symbol: 'none', itemStyle: { color: t.band } },
          { name: '80% range', type: 'line', stack: 'band', data: [...pad(histWeeks.length), ...width], lineStyle: { opacity: 0 }, symbol: 'none', areaStyle: { color: t.band }, itemStyle: { color: t.band } },
          { name: 'Actual (adjusted)', type: 'line', data: [...actual, ...pad(future.points.length)], lineStyle: { width: 2, color: t.series }, itemStyle: { color: t.series }, symbol: 'none' },
          {
            name: 'Forecast',
            type: 'line',
            data: [...pad(histWeeks.length - 1), last, ...future.points.map((p) => p.forecast)],
            lineStyle: { width: 2, color: t.series2 },
            itemStyle: { color: t.series2 },
            symbolSize: 6,
          },
          ...(future.comparison
            ? [
                {
                  name: compName,
                  type: 'line',
                  data: [...pad(histWeeks.length - 1), last, ...future.comparison.points.map((p) => p.forecast)],
                  lineStyle: { width: 2, color: t.series3 },
                  itemStyle: { color: t.series3 },
                  symbolSize: 6,
                },
              ]
            : []),
        ],
      }
    },
    [ev, seriesId, currency, future, compName],
  )
  return (
    <>
      <h3>
        {name}: last 52 weeks and the next {future.points.length} weeks (future forecast, not yet observed)
      </h3>
      <Chart build={build} height={320} ariaLabel={`${name}: history and future forecast; table below`} />
    </>
  )
}

function FutureTable({ op, seriesId, currency }: { op: Operational; seriesId: string; currency: string }) {
  const future = op.future_forecast.series[seriesId]
  return (
    <div className="table-wrap" style={{ marginTop: 8 }}>
      <table>
        <thead>
          <tr>
            <th>Week of</th>
            <th className="num">Forecast</th>
            <th className="num">Nominal 80% range</th>
            <th className="num">{future.comparison ? label(future.comparison.model) : 'Comparison'}</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {future.points.map((p, i) => (
            <tr key={p.week_start}>
              <td>{shortDate(p.week_start)}</td>
              <td className="num">{moneyExact(p.forecast, currency)}</td>
              <td className="num">
                {p.lower !== null && p.upper !== null
                  ? `${moneyExact(p.lower, currency)} – ${moneyExact(p.upper, currency)}`
                  : 'n/a'}
              </td>
              <td className="num">{future.comparison ? moneyExact(future.comparison.points[i].forecast, currency) : 'n/a'}</td>
              <td className="small muted">{p.provisional ? 'provisional horizon' : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

type BacktestProps = { ev: Evaluation; seriesId: string; horizon: number; currency: string; model: string; comparison: string }

function BacktestChart({ ev, seriesId, horizon, currency, model, comparison }: BacktestProps) {
  const rows = useMemo(
    () => ev.holdout_predictions.filter((r) => r.series === seriesId && r.h === horizon),
    [ev, seriesId, horizon],
  )
  const weeks = [...new Set(rows.map((r) => r.week_start))].sort()
  const pick = (model: string) => weeks.map((w) => rows.find((r) => r.model === model && r.week_start === w))
  const sel = pick(model)
  const sn = comparison === model ? [] : pick(comparison)
  const build = useCallback(
    (t: Tokens) => ({
      animation: false,
      grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
      legend: { top: 0, textStyle: { color: t.textSecondary, fontSize: 11 } },
      tooltip: {
        trigger: 'axis',
        backgroundColor: t.surface,
        borderColor: t.axis,
        textStyle: { color: t.text, fontSize: 12 },
        valueFormatter: (v: number) => moneyExact(v, currency),
      },
      xAxis: {
        type: 'category',
        data: weeks.map((w) => shortDate(w)),
        axisLine: { lineStyle: { color: t.axis } },
        axisTick: { show: false },
        axisLabel: { color: t.muted, fontSize: 11, hideOverlap: true },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: t.grid } },
        axisLabel: { color: t.muted, fontSize: 11, formatter: (v: number) => money(v, currency, true) },
      },
      series: [
        { name: 'Actual (adjusted)', type: 'line', data: sel.map((r) => r?.actual ?? null), lineStyle: { width: 2, color: t.series }, itemStyle: { color: t.series }, symbolSize: 6 },
        { name: `${label(model)} (in use)`, type: 'line', data: sel.map((r) => r?.forecast ?? null), lineStyle: { width: 2, color: t.series2 }, itemStyle: { color: t.series2 }, symbolSize: 6 },
        ...(sn.length
          ? [{ name: label(comparison), type: 'line', data: sn.map((r) => r?.forecast ?? null), lineStyle: { width: 2, color: t.series3 }, itemStyle: { color: t.series3 }, symbolSize: 6 }]
          : []),
      ],
    }),
    [weeks, sel, sn, model, comparison, currency],
  )
  if (!rows.length) return <p className="muted small">No holdout forecasts at this horizon.</p>
  return <Chart build={build} height={280} ariaLabel="Holdout backtest: actual versus forecasts; metrics table below" />
}

function MetricsCard({ ev, op, group }: { ev: Evaluation; op: Operational; group: string }) {
  const models = [...ev.selection_rule.candidates, ...ev.selection_rule.experiments]
  const g = op.groups[group]
  const selected = g.model
  const frozen = ev.decision[group]?.selected
  const horizons = Object.keys(ev.holdout_metrics[selected]?.[group] ?? {})
  return (
    <section className="card">
      <h2>How well each model did ({group === 'total' ? 'business total' : 'top products, pooled'})</h2>
      <p className="card-sub">
        Selection used validation weeks {ev.windows.validation.from} → {ev.windows.validation.to} only. WAPE = total
        absolute error ÷ total actual sales (lower is better). Bias &gt; 0 means over-forecasting. Skill = improvement in
        average error over a baseline (higher is better). Hover an "n/a" to see why it is undefined.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th className="num">Validation WAPE</th>
              <th className="num">Holdout WAPE</th>
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m} className={m === selected ? 'highlight' : ''}>
                <td>
                  {label(m)}
                  {m === frozen ? ' · frozen validation selection' : ''}
                  {m === selected ? (g.override ? ' · ✓ in use (override)' : ' · ✓ in use') : ''}
                </td>
                <td className="num">{pct({ value: meanWape(ev.validation_metrics[m]?.[group]) })}</td>
                <td className="num">{pct({ value: meanWape(ev.holdout_metrics[m]?.[group]) })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Model in use ({label(selected)}) on the holdout, by horizon</h3>
      {g.override && <p className="small">{g.evaluation_note}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Weeks ahead</th>
              <th className="num">n</th>
              <th className="num">MAE</th>
              <th className="num">RMSE</th>
              <th className="num">WAPE</th>
              <th className="num">Bias</th>
              <th className="num">vs naive</th>
              <th className="num">vs seasonal naive</th>
              <th className="num">80% coverage</th>
              <th className="num">Calibration n</th>
            </tr>
          </thead>
          <tbody>
            {horizons.map((h) => {
              const m = ev.holdout_metrics[selected][group][h]
              const cov = g.interval_holdout_coverage[h]
              const cell = (c: NA, f: (c: NA) => string) => <span title={c.reason ?? ''}>{f(c)}</span>
              return (
                <tr key={h}>
                  <td>
                    {h}
                    {ev.horizons[h]?.provisional ? ' (provisional)' : ''}
                  </td>
                  <td className="num">{m.n}</td>
                  <td className="num">{cell(m.mae, (c) => (c.value === null ? 'n/a' : `${Math.round(c.value).toLocaleString('en-GB')}`))}</td>
                  <td className="num">{cell(m.rmse, (c) => (c.value === null ? 'n/a' : `${Math.round(c.value).toLocaleString('en-GB')}`))}</td>
                  <td className="num">{cell(m.wape, (c) => pct(c))}</td>
                  <td className="num">{cell(m.bias, (c) => pct(c, true))}</td>
                  <td className="num">{cell(m.skill_vs_naive, (c) => pct(c, true))}</td>
                  <td className="num">{cell(m.skill_vs_seasonal_naive, (c) => pct(c, true))}</td>
                  <td className="num">{cov ? `${(cov.coverage * 100).toFixed(0)}% (n=${cov.n})` : 'n/a'}</td>
                  <td className="num">{g.interval_calibration_n[h] ?? 'n/a'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function ProductTable({ ev, model, seriesId }: { ev: Evaluation; model: string; seriesId: string }) {
  const selected = model
  const models = [selected, 'seasonal_naive', 'naive'].filter((m, i, a) => a.indexOf(m) === i)
  return (
    <section className="card">
      <h2>Individual products on the holdout (mean WAPE over horizons)</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              {models.map((m) => (
                <th key={m} className="num">
                  {label(m)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ev.series
              .filter((s) => s.id !== 'total')
              .map((s) => (
                <tr key={s.id} className={s.id === seriesId ? 'selected' : ''}>
                  <td>
                    {s.name} <span className="mono muted">{s.id}</span>
                  </td>
                  {models.map((m) => (
                    <td key={m} className="num">
                      {pct({ value: meanWape(ev.holdout_metrics_by_series[m]?.[s.id]) })}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function WindowsCard({ ev }: { ev: Evaluation }) {
  return (
    <section className="card">
      <h2>Evaluation design (frozen before the holdout was evaluated)</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Window</th>
              <th>Weeks</th>
              <th>Dates</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(ev.windows).map(([k, w]) => (
              <tr key={k}>
                <td>{k}</td>
                <td>
                  {w.weeks} ({w.count})
                </td>
                <td>
                  {w.from} → {w.to}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small">
        Products: {ev.product_selection.rule} ({ev.product_selection.eligible} eligible). Calendar inputs:{' '}
        {ev.calendar === 'none'
          ? 'month only (country unknown, so no holiday calendar)'
          : 'month, England & Wales bank holidays, days in 24 Dec–1 Jan (known in advance; never forces a zero forecast)'}
        . Selection run {ev.selection_created_at_utc} UTC; holdout run {ev.holdout_created_at_utc} UTC.
      </p>
    </section>
  )
}
