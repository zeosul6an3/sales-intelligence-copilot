import type { KnownIssue } from '../api'
import { moneyExact, shortDate } from '../format'
import { useApi } from '../hooks'

export function useKnownIssues(datasetId: string): KnownIssue[] {
  return useApi<{ issues: KnownIssue[] }>(`/api/datasets/${datasetId}/known-issues`).data?.issues ?? []
}

type NoteProps = {
  issues: KnownIssue[]
  currency: string
  onOpenIssue: () => void
  period?: { start: string; end: string }
  productId?: string | null
}

/** A short, visible note for documented issues that touch the current view. */
export function KnownIssueNotes({ issues, currency, onOpenIssue, period, productId }: NoteProps) {
  const relevant = issues.filter((i) => {
    const inPeriod = !period || (i.week_start <= period.end && i.week_end >= period.start)
    const forProduct = productId === undefined || i.product_id === productId
    return inPeriod && forProduct
  })
  return (
    <>
      {relevant.map((i) => (
        <div className="notice notice-info" key={i.id} role="note">
          i <strong>Known discrepancy:</strong> net product revenue for the week of {shortDate(i.week_start)} and for{' '}
          {i.product_name} ({i.product_id}) includes a {moneyExact(i.amount, currency)} sale that was reversed by a Manual
          credit, so both are {moneyExact(i.amount, currency)} higher than the customer's actual purchase and the
          product can rank higher than it otherwise would.{' '}
          <button className="link-button" onClick={onOpenIssue}>
            Details
          </button>
        </div>
      ))}
    </>
  )
}

/** Full explanation, shown on the Data quality page. */
export function KnownIssueDetails({ issues, currency }: { issues: KnownIssue[]; currency: string }) {
  if (issues.length === 0) return null
  return (
    <section className="card" id="known-issues">
      <h2>Known discrepancies</h2>
      {issues.map((i) => (
        <div key={i.id}>
          <h3>
            {i.product_name} ({i.product_id}), week of {shortDate(i.week_start)}
          </h3>
          <p className="small">{i.summary}</p>
          <p className="small">
            <strong>Forecasting:</strong> {i.forecasting_treatment} <strong>Dashboard:</strong> unchanged; the agreed
            product-only policy keeps Manual lines outside net product revenue, and no transaction is removed.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Invoice</th>
                  <th>Line</th>
                  <th className="num">Qty</th>
                  <th className="num">Unit price</th>
                  <th className="num">Value</th>
                  <th>Line type</th>
                </tr>
              </thead>
              <tbody>
                {i.transactions.map((t) => (
                  <tr key={`${t.invoice_id}-${t.invoice_ts}-${t.product_id}`}>
                    <td className="small">{t.invoice_ts.slice(11, 16)}</td>
                    <td className="mono">{t.invoice_id}</td>
                    <td>
                      {t.description} <span className="mono muted">{t.product_id}</span>
                    </td>
                    <td className="num">{t.quantity}</td>
                    <td className="num">{moneyExact(t.unit_price, currency)}</td>
                    <td className="num">{moneyExact(t.line_value, currency)}</td>
                    <td className="small">{t.line_type.replaceAll('_', ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </section>
  )
}
