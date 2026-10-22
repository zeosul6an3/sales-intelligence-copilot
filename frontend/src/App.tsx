import { useEffect, useMemo, useState } from 'react'
import type { DatasetInfo, DatasetMetadata, Query } from './api'
import { shortDate } from './format'
import { useApi } from './hooks'
import DataQuality from './pages/DataQuality'
import Datasets from './pages/Datasets'
import Overview from './pages/Overview'
import Products from './pages/Products'

type Tab = 'overview' | 'products' | 'quality' | 'datasets'
const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'products', label: 'Products' },
  { id: 'quality', label: 'Data quality' },
  { id: 'datasets', label: 'Datasets & upload' },
]

type Health = { ollama: { reachable: boolean; version?: string } }

export default function App() {
  const [datasetId, setDatasetId] = useState('uci')
  const [tab, setTab] = useState<Tab>('overview')
  const [preset, setPreset] = useState('last_12_complete_months')
  const [custom, setCustom] = useState({ start: '', end: '' })
  const [country, setCountry] = useState('')
  const [productId, setProductId] = useState<string | null>(null)

  const datasets = useApi<DatasetMetadata[]>('/api/datasets')
  const info = useApi<DatasetInfo>(`/api/datasets/${datasetId}`)
  const health = useApi<Health>('/api/health')

  // Reset filters when switching dataset; fall back to "all data" if a preset doesn't exist.
  useEffect(() => {
    setCountry('')
    setProductId(null)
    setCustom({ start: '', end: '' })
  }, [datasetId])
  useEffect(() => {
    if (info.data && preset !== 'custom' && !info.data.presets[preset]) setPreset('all_data')
  }, [info.data, preset])

  const query: Query | null = useMemo(() => {
    if (!info.data) return null
    if (preset === 'custom') {
      return {
        start: custom.start || info.data.coverage.first_date,
        end: custom.end || info.data.coverage.last_date,
        country,
      }
    }
    const p = info.data.presets[preset] ?? info.data.presets.all_data
    return { start: p.start, end: p.end, country }
  }, [info.data, preset, custom, country])

  const metadata = info.data?.metadata
  const currency = metadata?.currency ?? 'GBP'
  const showFilters = tab === 'overview' || tab === 'products'

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">
          <h1>Sales Intelligence Copilot</h1>
          <p>{metadata ? `${metadata.name} · ${metadata.currency}` : 'Loading…'}</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <label className="field">
            <span>Dataset</span>
            <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
              {(datasets.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <span className="status-pill" title="Local language model server (used from Milestone 4)">
            <span className={`dot ${health.data?.ollama.reachable ? 'dot-ok' : 'dot-bad'}`} />
            Ollama {health.data?.ollama.reachable ? 'running' : 'not reachable'}
          </span>
        </div>
      </header>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" className="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      {info.error && <div className="notice notice-error">{info.error}</div>}
      {datasets.data && datasets.data.length === 0 && (
        <div className="notice notice-warning">
          No datasets yet. Run <code>uv run python scripts/download_data.py</code> and{' '}
          <code>uv run python scripts/prepare_data.py</code>, then reload.
        </div>
      )}

      {showFilters && info.data && query && (
        <div className="filter-bar" role="group" aria-label="Filters">
          <label className="field">
            <span>Period</span>
            <select value={preset} onChange={(e) => setPreset(e.target.value)}>
              {Object.entries(info.data.presets).map(([key, p]) => (
                <option key={key} value={key}>
                  {p.label}
                </option>
              ))}
              <option value="custom">Custom range…</option>
            </select>
          </label>
          {preset === 'custom' && (
            <>
              <label className="field">
                <span>From</span>
                <input
                  type="date"
                  value={custom.start || info.data.coverage.first_date}
                  min={info.data.coverage.first_date}
                  max={info.data.coverage.last_date}
                  onChange={(e) => setCustom({ ...custom, start: e.target.value })}
                />
              </label>
              <label className="field">
                <span>To</span>
                <input
                  type="date"
                  value={custom.end || info.data.coverage.last_date}
                  min={info.data.coverage.first_date}
                  max={info.data.coverage.last_date}
                  onChange={(e) => setCustom({ ...custom, end: e.target.value })}
                />
              </label>
            </>
          )}
          <label className="field">
            <span>Country</span>
            <select value={country} onChange={(e) => setCountry(e.target.value)}>
              <option value="">All countries</option>
              {info.data.countries.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <span className="filter-note">
            {shortDate(query.start)} – {shortDate(query.end)} · data covers {shortDate(info.data.coverage.first_date)} –{' '}
            {shortDate(info.data.coverage.last_date)}
          </span>
        </div>
      )}

      {query && tab === 'overview' && (
        <Overview
          datasetId={datasetId}
          query={query}
          currency={currency}
          onOpenProduct={(id) => {
            setProductId(id)
            setTab('products')
          }}
        />
      )}
      {query && tab === 'products' && (
        <Products
          datasetId={datasetId}
          query={query}
          currency={currency}
          productId={productId}
          onSelect={setProductId}
        />
      )}
      {tab === 'quality' && <DataQuality datasetId={datasetId} currency={currency} />}
      {tab === 'datasets' && (
        <Datasets
          datasets={datasets.data ?? []}
          activeId={datasetId}
          onSelect={(id) => {
            setDatasetId(id)
            setTab('overview')
          }}
          onChanged={datasets.reload}
        />
      )}

      <footer className="footer">
        {metadata?.attribution ? (
          <p>
            Data: {metadata.attribution}{' '}
            <a href="https://archive.ics.uci.edu/dataset/502/online+retail+ii" target="_blank" rel="noreferrer">
              Source
            </a>
            . Amounts in {metadata.currency} as recorded; profit and stock levels are not available in this data.
          </p>
        ) : (
          metadata && <p>Uploaded dataset · amounts in {metadata.currency}.</p>
        )}
      </footer>
    </div>
  )
}
