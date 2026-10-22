import { useCallback, useState } from 'react'
import type { SeriesPoint } from '../api'
import { money, moneyExact, monthLabel, number, shortDate } from '../format'
import Chart, { type Tokens } from './Chart'

type Metric = 'net_revenue' | 'gross_sales' | 'returns' | 'orders'
const METRIC_LABELS: Record<Metric, string> = {
  net_revenue: 'Net revenue',
  gross_sales: 'Gross sales',
  returns: 'Returns',
  orders: 'Orders',
}

type Props = {
  points: SeriesPoint[]
  freq: 'week' | 'month'
  currency: string
  onFreqChange?: (freq: 'week' | 'month') => void
  title?: string
}

/** One metric over time as bars. Partial periods use a lighter fill and say so
 *  in the tooltip and the table, so a cut-off week never reads as a slump. */
export default function TrendChart({ points, freq, currency, onFreqChange, title }: Props) {
  const [metric, setMetric] = useState<Metric>('net_revenue')
  const [showTable, setShowTable] = useState(false)
  const isMoney = metric !== 'orders'
  const label = (p: SeriesPoint) => (freq === 'month' ? monthLabel(p.period_start) : shortDate(p.period_start))
  const partialCount = points.filter((p) => p.partial).length

  const build = useCallback(
    (t: Tokens) => ({
      animation: false,
      grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow', shadowStyle: { color: t.grid, opacity: 0.5 } },
        backgroundColor: t.surface,
        borderColor: t.axis,
        textStyle: { color: t.text, fontSize: 12 },
        formatter: (items: { dataIndex: number }[]) => {
          const p = points[items[0].dataIndex]
          const value = isMoney ? moneyExact(p[metric], currency) : number(p[metric])
          const notes = [
            p.partial ? 'Partial period (not fully covered by the data or the filter)' : '',
            p.has_unusual ? 'Contains an unusually large line (see Data quality)' : '',
          ].filter(Boolean)
          return `<strong>${shortDate(p.period_start)} – ${shortDate(p.period_end)}</strong><br/>${
            METRIC_LABELS[metric]
          }: <strong>${value}</strong>${notes.map((n) => `<br/><span style="opacity:.75">${n}</span>`).join('')}`
        },
      },
      xAxis: {
        type: 'category',
        data: points.map(label),
        axisLine: { lineStyle: { color: t.axis } },
        axisTick: { show: false },
        axisLabel: { color: t.muted, fontSize: 11, hideOverlap: true },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: t.grid } },
        axisLabel: {
          color: t.muted,
          fontSize: 11,
          formatter: (v: number) => (isMoney ? money(v, currency, true) : number(v, true)),
        },
      },
      series: [
        {
          type: 'bar',
          name: METRIC_LABELS[metric],
          barMaxWidth: 28,
          barCategoryGap: '20%',
          data: points.map((p) => ({
            value: p[metric],
            itemStyle: {
              color: p.partial ? t.seriesSoft : t.series,
              borderRadius: [4, 4, 0, 0],
            },
          })),
        },
      ],
    }),
    [points, metric, freq, currency],
  )

  return (
    <div>
      <div className="card-header">
        <h2>{title ?? `${METRIC_LABELS[metric]} by ${freq}`}</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <div className="segmented" role="group" aria-label="Metric">
            {(Object.keys(METRIC_LABELS) as Metric[]).map((m) => (
              <button key={m} aria-pressed={metric === m} onClick={() => setMetric(m)}>
                {METRIC_LABELS[m]}
              </button>
            ))}
          </div>
          {onFreqChange && (
            <div className="segmented" role="group" aria-label="Interval">
              {(['week', 'month'] as const).map((f) => (
                <button key={f} aria-pressed={freq === f} onClick={() => onFreqChange(f)}>
                  {f === 'week' ? 'Weekly' : 'Monthly'}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      {partialCount > 0 && (
        <p className="card-sub">
          Lighter bars ({partialCount}) are partial periods, cut off by the data range or the filter.
        </p>
      )}
      <Chart build={build} ariaLabel={`${METRIC_LABELS[metric]} by ${freq}; table view available`} />
      <button className="link-button" onClick={() => setShowTable((s) => !s)}>
        {showTable ? 'Hide table' : 'Show as table'}
      </button>
      {showTable && (
        <div className="table-wrap" style={{ maxHeight: 280, overflowY: 'auto', marginTop: 8 }}>
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th className="num">Net revenue</th>
                <th className="num">Gross sales</th>
                <th className="num">Returns</th>
                <th className="num">Orders</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.period_start}>
                  <td>
                    {shortDate(p.period_start)} – {shortDate(p.period_end)}
                  </td>
                  <td className="num">{moneyExact(p.net_revenue, currency)}</td>
                  <td className="num">{moneyExact(p.gross_sales, currency)}</td>
                  <td className="num">{moneyExact(p.returns, currency)}</td>
                  <td className="num">{number(p.orders)}</td>
                  <td className="small muted">
                    {[p.partial && 'partial', p.has_unusual && 'unusual line'].filter(Boolean).join(', ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
