import { useState } from 'react'
import { withQuery, type CountryRow, type OtherLine, type ProductRow, type Query, type SeriesPoint, type Summary } from '../api'
import HBarChart from '../components/HBarChart'
import { KnownIssueNotes, useKnownIssues } from '../components/KnownIssues'
import KpiTiles from '../components/KpiTiles'
import TrendChart from '../components/TrendChart'
import { moneyExact, number } from '../format'
import { useApi } from '../hooks'

type Props = {
  datasetId: string
  query: Query
  currency: string
  onOpenProduct: (id: string) => void
  onOpenIssue: () => void
}

export default function Overview({ datasetId, query, currency, onOpenProduct, onOpenIssue }: Props) {
  const issues = useKnownIssues(datasetId)
  const [freq, setFreq] = useState<'week' | 'month'>('week')
  const base = `/api/datasets/${datasetId}`
  const summary = useApi<Summary>(withQuery(`${base}/summary`, query))
  const series = useApi<{ points: SeriesPoint[] }>(withQuery(`${base}/timeseries`, { ...query, freq }))
  const products = useApi<{ products: ProductRow[] }>(
    withQuery(`${base}/products`, { ...query, limit: 10, sort_by: 'net_revenue' }),
  )
  const countries = useApi<{ countries: CountryRow[] }>(
    withQuery(`${base}/countries`, { start: query.start, end: query.end, limit: 8 }),
  )
  const other = useApi<{ lines: OtherLine[] }>(withQuery(`${base}/other-lines`, query))

  const error = summary.error || series.error || products.error || countries.error || other.error
  return (
    <>
      {error && <div className="notice notice-error">{error}</div>}
      <KnownIssueNotes issues={issues} currency={currency} onOpenIssue={onOpenIssue} period={query} />
      {summary.data && (
        <div className={summary.loading ? 'loading' : ''}>
          <KpiTiles summary={summary.data} currency={currency} />
        </div>
      )}

      <section className={`card ${series.loading ? 'loading' : ''}`} style={{ marginBottom: 16 }}>
        {series.data && (
          <TrendChart points={series.data.points} freq={freq} currency={currency} onFreqChange={setFreq} />
        )}
      </section>

      <div className="grid grid-2">
        <section className={`card ${products.loading ? 'loading' : ''}`}>
          <div className="card-header">
            <h2>Top 10 products by net product revenue</h2>
          </div>
          <p className="card-sub">Click a bar to open the product.</p>
          {products.data && products.data.products.length > 0 ? (
            <HBarChart
              rows={products.data.products.map((p) => ({ label: p.product_name, value: p.net_revenue }))}
              currency={currency}
              ariaLabel="Top 10 products by net product revenue"
              onSelect={(i) => onOpenProduct(products.data!.products[i].product_id)}
            />
          ) : (
            <p className="muted small">No product sales in this period.</p>
          )}
        </section>

        <section className={`card ${countries.loading ? 'loading' : ''}`}>
          <div className="card-header">
            <h2>Net product revenue by country</h2>
          </div>
          <p className="card-sub">Ignores the country filter so the whole picture stays visible.</p>
          {countries.data && countries.data.countries.length > 0 ? (
            <HBarChart
              rows={countries.data.countries.map((c) => ({ label: c.country, value: c.net_revenue }))}
              currency={currency}
              ariaLabel="Net product revenue by country"
            />
          ) : (
            <p className="muted small">No sales in this period.</p>
          )}
        </section>
      </div>

      <section className={`card ${other.loading ? 'loading' : ''}`} style={{ marginTop: 16 }}>
        <div className="card-header">
          <h2>Other lines (not in net product revenue)</h2>
        </div>
        <p className="card-sub">
          Shipping, fees, discounts, manual adjustments and similar lines are reported here instead of
          being mixed into net product revenue.
        </p>
        {other.data && other.data.lines.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Line type</th>
                  <th className="num">Lines</th>
                  <th className="num">Value</th>
                </tr>
              </thead>
              <tbody>
                {other.data.lines.map((l) => (
                  <tr key={l.line_type}>
                    <td>{l.label}</td>
                    <td className="num">{number(l.lines)}</td>
                    <td className="num">{moneyExact(l.value, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted small">None in this period.</p>
        )}
      </section>
    </>
  )
}
