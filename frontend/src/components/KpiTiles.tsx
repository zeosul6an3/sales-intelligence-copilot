import type { Kpis, Summary } from '../api'
import { money, number, percentChange, shortDate } from '../format'

type Tile = {
  key: keyof Kpis
  label: string
  kind: 'money' | 'count'
  /** Whether an increase is good news; drives the delta colour (always with an arrow + text). */
  upIsGood: boolean
}

const TILES: Tile[] = [
  { key: 'net_revenue', label: 'Net product revenue', kind: 'money', upIsGood: true },
  { key: 'gross_sales', label: 'Gross sales', kind: 'money', upIsGood: true },
  { key: 'returns', label: 'Returns', kind: 'money', upIsGood: false },
  { key: 'orders', label: 'Orders', kind: 'count', upIsGood: true },
  { key: 'avg_order_value', label: 'Avg order value', kind: 'money', upIsGood: true },
  { key: 'units', label: 'Units sold', kind: 'count', upIsGood: true },
  { key: 'customers', label: 'Identified customers', kind: 'count', upIsGood: true },
]

export default function KpiTiles({ summary, currency }: { summary: Summary; currency: string }) {
  const previousLabel = `${shortDate(summary.previous_period.start)} – ${shortDate(summary.previous_period.end)}`
  return (
    <section className="kpis" aria-label="Key figures">
      {TILES.map((tile) => {
        const current = summary.current[tile.key]
        const previous = summary.previous[tile.key]
        const change = summary.previous_period_covered ? percentChange(current, previous) : null
        const good = change !== null && (change > 0) === tile.upIsGood && change !== 0
        return (
          <div className="kpi" key={tile.key}>
            <div className="kpi-label">{tile.label}</div>
            <div className="kpi-value">
              {tile.kind === 'money' ? money(current, currency) : number(current)}
            </div>
            <div className="kpi-delta" title={`Compared with ${previousLabel}`}>
              {change === null ? (
                <span>{summary.previous_period_covered ? 'No comparison' : 'No earlier data to compare'}</span>
              ) : (
                <span className={good ? 'delta-good' : 'delta-bad'}>
                  {change > 0 ? '▲' : change < 0 ? '▼' : '■'} {Math.abs(change).toFixed(1)}%{' '}
                  <span className="muted">vs previous period</span>
                </span>
              )}
            </div>
          </div>
        )
      })}
    </section>
  )
}
