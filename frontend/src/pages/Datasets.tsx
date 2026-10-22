import { useState } from 'react'
import {
  deleteDataset,
  postJson,
  uploadFile,
  type DatasetMetadata,
  type StagedUpload,
  type UploadOptions,
  type Validation,
} from '../api'
import { moneyExact, number, shortDate } from '../format'
import { IssueList } from './DataQuality'

type Props = {
  datasets: DatasetMetadata[]
  activeId: string
  onSelect: (id: string) => void
  onChanged: () => void
}

export default function Datasets({ datasets, activeId, onSelect, onChanged }: Props) {
  const [error, setError] = useState<string | null>(null)

  const remove = async (d: DatasetMetadata) => {
    if (!window.confirm(`Delete the uploaded dataset "${d.name}" and everything generated from it?`)) return
    try {
      await deleteDataset(d.id)
      if (d.id === activeId) onSelect('uci')
      onChanged()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="grid">
      <section className="card">
        <h2>Datasets</h2>
        <p className="card-sub">
          Each dataset is stored and queried separately; an upload can never change or read the built-in data or
          another upload.
        </p>
        {error && <div className="notice notice-error">{error}</div>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Dates</th>
                <th className="num">Lines</th>
                <th className="num">Products</th>
                <th>Currency</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.id} className={d.id === activeId ? 'selected' : ''}>
                  <td>{d.name}</td>
                  <td>{d.kind === 'builtin' ? 'Built-in example' : 'Upload'}</td>
                  <td className="small">
                    {shortDate(d.first_date)} – {shortDate(d.last_date)}
                  </td>
                  <td className="num">{number(d.lines)}</td>
                  <td className="num">{number(d.products)}</td>
                  <td>{d.currency}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    {d.id !== activeId && (
                      <button className="button" onClick={() => onSelect(d.id)}>
                        Open
                      </button>
                    )}{' '}
                    {d.kind === 'upload' && (
                      <button className="button" onClick={() => remove(d)}>
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <UploadWizard
        onImported={(id) => {
          onChanged()
          onSelect(id)
        }}
      />
    </div>
  )
}

function UploadWizard({ onImported }: { onImported: (id: string) => void }) {
  const [staged, setStaged] = useState<StagedUpload | null>(null)
  const [mapping, setMapping] = useState<Record<string, string | null>>({})
  const [currency, setCurrency] = useState('GBP')
  const [dayFirst, setDayFirst] = useState(false)
  const [name, setName] = useState('')
  const [validation, setValidation] = useState<Validation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const step = !staged ? 1 : !validation ? 2 : 3
  const options = (): UploadOptions => ({ mapping, currency, day_first: dayFirst, name: name || undefined })

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const choose = (file: File | undefined) =>
    file &&
    run(async () => {
      const result = await uploadFile(file)
      setStaged(result)
      setMapping(result.suggested_mapping)
      setName(result.filename.replace(/\.csv$/i, ''))
      setValidation(null)
    })

  const validate = () =>
    staged && run(async () => setValidation(await postJson<Validation>(`/api/uploads/${staged.upload_id}/validate`, options())))

  const importNow = () =>
    staged &&
    run(async () => {
      const metadata = await postJson<DatasetMetadata>(`/api/uploads/${staged.upload_id}/import`, options())
      setStaged(null)
      setValidation(null)
      onImported(metadata.id)
    })

  return (
    <section className="card">
      <h2>Upload a sales CSV</h2>
      <div className="steps" aria-label="Upload steps">
        <span className={step === 1 ? 'current' : ''}>1. Choose file</span>›
        <span className={step === 2 ? 'current' : ''}>2. Map columns</span>›
        <span className={step === 3 ? 'current' : ''}>3. Check and import</span>
      </div>
      {error && <div className="notice notice-error">{error}</div>}

      {step === 1 && (
        <>
          <p className="small">
            One row per order line. Required columns: <strong>invoice ID, invoice date, product ID, quantity, unit
            price</strong>. Optional: product name, customer ID, country, currency. Negative quantities are treated as
            returns. Maximum 50 MB.
          </p>
          <p className="small">
            <a href="/api/uploads/template.csv" download>
              Download the CSV template
            </a>
          </p>
          <input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => choose(e.target.files?.[0])} />
        </>
      )}

      {staged && step >= 2 && (
        <>
          <p className="small">
            File <strong>{staged.filename}</strong>: {staged.columns.length} columns. Suggested matches are filled in;
            check each one.
          </p>
          <div className="mapping-grid">
            {[...staged.fields.required, ...staged.fields.optional].map((field) => (
              <label className="field" key={field}>
                <span>
                  {field.replaceAll('_', ' ')}
                  {staged.fields.required.includes(field) ? ' *' : ' (optional)'}
                </span>
                <select
                  value={mapping[field] ?? ''}
                  onChange={(e) => {
                    setMapping({ ...mapping, [field]: e.target.value || null })
                    setValidation(null)
                  }}
                >
                  <option value="">— not in file —</option>
                  {staged.columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <span className="muted" style={{ fontSize: '0.72rem' }}>
                  {staged.fields.descriptions[field]}
                </span>
              </label>
            ))}
            <label className="field">
              <span>Currency of the prices *</span>
              <input
                value={currency}
                maxLength={3}
                onChange={(e) => {
                  setCurrency(e.target.value.toUpperCase())
                  setValidation(null)
                }}
              />
              <span className="muted" style={{ fontSize: '0.72rem' }}>3-letter code, e.g. GBP, EUR, USD.</span>
            </label>
            <label className="field">
              <span>Date order for dates like 05/02/2024</span>
              <select
                value={dayFirst ? 'day' : 'month'}
                onChange={(e) => {
                  setDayFirst(e.target.value === 'day')
                  setValidation(null)
                }}
              >
                <option value="month">Month first (02 May)</option>
                <option value="day">Day first (5 February)</option>
              </select>
              <span className="muted" style={{ fontSize: '0.72rem' }}>ISO dates (2024-02-05) are always read correctly.</span>
            </label>
            <label className="field">
              <span>Dataset name</span>
              <input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
            </label>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="button button-primary" disabled={busy} onClick={validate}>
              {busy && step === 2 ? 'Checking…' : 'Check file'}
            </button>
            <button
              className="button"
              disabled={busy}
              onClick={() => {
                setStaged(null)
                setValidation(null)
                setError(null)
              }}
            >
              Start again
            </button>
          </div>
        </>
      )}

      {validation && (
        <>
          <h3>Check results</h3>
          <p className="small">
            {number(validation.rows_total)} rows read · {number(validation.rows_usable)} usable ·{' '}
            {number(validation.rows_invalid)} excluded
            {validation.first_date && ` · ${shortDate(validation.first_date)} – ${shortDate(validation.last_date!)}`}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Line type</th>
                  <th className="num">Rows</th>
                  <th className="num">Value</th>
                </tr>
              </thead>
              <tbody>
                {validation.line_types.map((l) => (
                  <tr key={l.line_type}>
                    <td>{l.line_type.replaceAll('_', ' ')}</td>
                    <td className="num">{number(l.rows)}</td>
                    <td className="num">{l.line_type === 'invalid_row' ? '–' : moneyExact(l.value, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>Issues</h3>
          <IssueList issues={validation.issues} />
          <h3>Preview (first {validation.preview.length} rows, as they will be read)</h3>
          <div className="table-wrap" style={{ maxHeight: 260, overflowY: 'auto' }}>
            <table>
              <thead>
                <tr>
                  {validation.preview[0] && Object.keys(validation.preview[0]).map((k) => <th key={k}>{k}</th>)}
                </tr>
              </thead>
              <tbody>
                {validation.preview.map((row) => (
                  <tr key={String(row.source_row)}>
                    {Object.entries(row).map(([k, v]) => (
                      <td key={k} className="small">
                        {v === null ? '' : String(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="small muted">
            Forecasting is not applied to uploads automatically: a model will be trained and evaluated on this dataset
            separately (Milestone 3).
          </p>
          <button className="button button-primary" disabled={busy || !validation.can_import} onClick={importNow}>
            {busy ? 'Importing…' : 'Import dataset'}
          </button>
        </>
      )}
    </section>
  )
}
