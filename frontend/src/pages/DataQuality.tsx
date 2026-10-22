import type { Definitions, Issue, QualityReport } from '../api'
import { moneyExact, number } from '../format'
import { useApi } from '../hooks'

const SEVERITY_LABEL = { error: '✕ Error', warning: '! Warning', info: 'i Info' }

export function IssueList({ issues }: { issues: Issue[] }) {
  if (issues.length === 0) return <p className="muted small">No issues found.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Severity</th>
            <th>Issue</th>
            <th className="num">Rows</th>
            <th>Examples (row: value)</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((i) => (
            <tr key={i.code}>
              <td className="severity">{SEVERITY_LABEL[i.severity]}</td>
              <td>{i.message}</td>
              <td className="num">{i.rows === null ? '–' : number(i.rows)}</td>
              <td className="small">
                {i.examples.map((e) => `${e.row}: ${e.value ?? ''}`).join(' · ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

type Flag = { rows?: number; value?: number; codes?: number; treatment?: string; rule?: string; lines?: unknown[] }

export default function DataQuality({ datasetId, currency }: { datasetId: string; currency: string }) {
  const report = useApi<QualityReport>(`/api/datasets/${datasetId}/quality`)
  const definitions = useApi<Definitions>('/api/definitions')
  if (report.error) return <div className="notice notice-error">{report.error}</div>
  if (!report.data) return <p className="muted">Loading…</p>
  const r = report.data
  const flags = (r.flags ?? {}) as Record<string, Flag | number>
  const unusual = (flags.unusual_lines as Flag | undefined)?.lines as
    | { invoice_id: string; product_id: string; description: string; quantity: number; line_value: number; invoice_ts: string }[]
    | undefined

  return (
    <div className="grid">
      <section className="card">
        <h2>How every row was handled</h2>
        <p className="card-sub">
          No row is dropped silently: each input row gets exactly one line type, and the counts below add up to the rows
          read. Generated {r.generated_at_utc} UTC.
        </p>
        <div className="table-wrap">
          <table>
            <tbody>
              {Object.entries(r.row_flow)
                .filter(([k]) => !k.endsWith('_note'))
                .map(([k, v]) => (
                  <tr key={k}>
                    <th>{k.replaceAll('_', ' ')}</th>
                    <td className="num">{typeof v === 'number' ? number(v) : v === true ? '✓ yes' : v === false ? '✕ no' : v}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {typeof r.row_flow.sheet_overlap_note === 'string' && (
          <p className="small muted">{r.row_flow.sheet_overlap_note}</p>
        )}
      </section>

      <section className="card">
        <h2>Classification rules</h2>
        <p className="card-sub">Rules apply in this order; the first match decides the line type.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Line type</th>
                <th className="num">Rows</th>
                <th className="num">Value</th>
                <th>Treatment</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {r.rules.map((rule) => (
                <tr key={rule.line_type}>
                  <td>
                    {rule.label}
                    <div className="mono muted">{rule.condition}</div>
                  </td>
                  <td className="num">{number(rule.rows)}</td>
                  <td className="num">{moneyExact(rule.value, currency)}</td>
                  <td className="small">{rule.treatment}</td>
                  <td className="small muted">{rule.evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {Object.keys(flags).length > 0 && (
        <section className="card">
          <h2>Flags</h2>
          <div className="table-wrap">
            <table>
              <tbody>
                {Object.entries(flags)
                  .filter(([k]) => k !== 'unusual_lines')
                  .map(([k, f]) => (
                    <tr key={k}>
                      <th>{k.replaceAll('_', ' ')}</th>
                      <td className="num">
                        {typeof f === 'number' ? number(f) : number(f.rows ?? f.codes ?? null)}
                      </td>
                      <td className="num">{typeof f === 'object' && f.value !== undefined ? moneyExact(f.value, currency) : ''}</td>
                      <td className="small">{typeof f === 'object' ? f.treatment : ''}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          {unusual && unusual.length > 0 && (
            <>
              <h3>Unusual lines</h3>
              <p className="card-sub">{(flags.unusual_lines as Flag).rule}. {(flags.unusual_lines as Flag).treatment}</p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Product</th>
                      <th className="num">Quantity</th>
                      <th className="num">Value</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unusual.map((u) => (
                      <tr key={`${u.invoice_id}-${u.product_id}`}>
                        <td className="mono">{u.invoice_id}</td>
                        <td>{u.description}</td>
                        <td className="num">{number(u.quantity)}</td>
                        <td className="num">{moneyExact(u.line_value, currency)}</td>
                        <td className="small">{u.invoice_ts}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {r.issues && r.issues.length > 0 && (
        <section className="card">
          <h2>Upload validation issues</h2>
          <IssueList issues={r.issues} />
        </section>
      )}

      <section className="card">
        <h2>Coverage and definitions</h2>
        <p className="small">
          Data from {r.coverage.first_date} to {r.coverage.last_date}.
        </p>
        <ul className="small">
          {r.coverage.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
        {definitions.data && (
          <>
            <div className="table-wrap">
              <table>
                <tbody>
                  {Object.entries(definitions.data.metrics).map(([k, m]) => (
                    <tr key={k}>
                      <th>{m.label}</th>
                      <td className="small">{m.definition}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="notice notice-info">{definitions.data.not_available}</p>
          </>
        )}
        {r.source.sha256 && (
          <p className="small muted">
            Source file {r.source.file}, SHA-256 <span className="mono">{r.source.sha256}</span>
          </p>
        )}
      </section>
    </div>
  )
}
