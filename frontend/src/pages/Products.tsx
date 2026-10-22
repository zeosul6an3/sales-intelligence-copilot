import { useEffect, useState } from 'react'
import { withQuery, type ProductRow, type Query, type SeriesPoint, type Summary } from '../api'
import TrendChart from '../components/TrendChart'
import { moneyExact, number } from '../format'
import { useApi } from '../hooks'

type SortKey = 'net_revenue' | 'gross_sales' | 'returns' | 'units' | 'orders'
const COLUMNS: { key: SortKey; label: string; money: boolean }[] = [
  { key: 'net_revenue', label: 'Net revenue', money: true },
  { key: 'gross_sales', label: 'Gross sales', money: true },
  { key: 'returns', label: 'Returns', money: true },
  { key: 'units', label: 'Units', money: false },
  { key: 'orders', label: 'Orders', money: false },
]

type Props = { datasetId: string; query: Query; currency: string; productId: string | null; onSelect: (id: string | null) => void }

export default function Products({ datasetId, query, currency, productId, onSelect }: Props) {
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [sortBy, setSortBy] = useState<SortKey>('net_revenue')
  const [order, setOrder] = useState<'desc' | 'asc'>('desc')
  const [freq, setFreq] = useState<'week' | 'month'>('week')

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300)
    return () => clearTimeout(timer)
  }, [search])

  const base = `/api/datasets/${datasetId}`
  const table = useApi<{ total_matches: number; products: ProductRow[] }>(
    withQuery(`${base}/products`, { ...query, sort_by: sortBy, order, limit: 50, search: debounced }),
  )
  const detailQuery = { ...query, product_id: productId }
  const series = useApi<{ points: SeriesPoint[] }>(
    productId ? withQuery(`${base}/timeseries`, { ...detailQuery, freq }) : null,
  )
  const summary = useApi<Summary>(productId ? withQuery(`${base}/summary`, detailQuery) : null)
  const selected = table.data?.products.find((p) => p.product_id === productId)

  const sortOn = (key: SortKey) => {
    if (key === sortBy) setOrder(order === 'desc' ? 'asc' : 'desc')
    else {
      setSortBy(key)
      setOrder('desc')
    }
  }

  return (
    <div className="grid">
      {productId && (
        <section className={`card ${series.loading ? 'loading' : ''}`}>
          <div className="card-header">
            <h2>
              {selected?.product_name ?? productId} <span className="muted small">({productId})</span>
            </h2>
            <button className="link-button" onClick={() => onSelect(null)}>
              Close
            </button>
          </div>
          {summary.data && (
            <p className="card-sub">
              Net revenue {moneyExact(summary.data.current.net_revenue, currency)} · gross sales{' '}
              {moneyExact(summary.data.current.gross_sales, currency)} · returns{' '}
              {moneyExact(summary.data.current.returns, currency)} · {number(summary.data.current.units)} units ·{' '}
              {number(summary.data.current.orders)} orders
            </p>
          )}
          {series.error && <div className="notice notice-error">{series.error}</div>}
          {series.data && (
            <TrendChart points={series.data.points} freq={freq} currency={currency} onFreqChange={setFreq} />
          )}
        </section>
      )}

      <section className={`card ${table.loading ? 'loading' : ''}`}>
        <div className="card-header">
          <h2>Products</h2>
          <label className="field" style={{ flexDirection: 'row', alignItems: 'center' }}>
            <span>Search</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Name or code"
              maxLength={60}
            />
          </label>
        </div>
        <p className="card-sub">
          {table.data ? `${number(table.data.total_matches)} products with sales or returns in this period` : ''}
          {table.data && table.data.total_matches > 50 ? ' · showing the first 50' : ''}. Click a column to
          sort, a row to see its trend.
        </p>
        {table.error && <div className="notice notice-error">{table.error}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Product</th>
                {COLUMNS.map((c) => (
                  <th key={c.key} className="num">
                    <button className="link-button" onClick={() => sortOn(c.key)} aria-label={`Sort by ${c.label}`}>
                      {c.label} {sortBy === c.key ? (order === 'desc' ? '▼' : '▲') : ''}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.data?.products.map((p) => (
                <tr
                  key={p.product_id}
                  className={`clickable ${p.product_id === productId ? 'selected' : ''}`}
                  onClick={() => onSelect(p.product_id)}
                >
                  <td className="mono">{p.product_id}</td>
                  <td>{p.product_name}</td>
                  {COLUMNS.map((c) => (
                    <td key={c.key} className="num">
                      {c.money ? moneyExact(p[c.key], currency) : number(p[c.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
