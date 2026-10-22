import { useEffect, useState } from 'react'

type Health = {
  status: string
  app_version: string
  ollama: { reachable: boolean; version?: string; error?: string }
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ok'; health: Health }
  | { kind: 'error'; message: string }

function StatusRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <li className="status-row">
      <span className={ok ? 'dot dot-ok' : 'dot dot-bad'} aria-hidden="true" />
      <span className="status-label">{label}</span>
      <span className="status-detail">{detail}</span>
    </li>
  )
}

export default function App() {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })

  useEffect(() => {
    fetch('/api/health')
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<Health>
      })
      .then((health) => setState({ kind: 'ok', health }))
      .catch((error: Error) => setState({ kind: 'error', message: error.message }))
  }, [])

  return (
    <main className="page">
      <header>
        <h1>Sales Intelligence Copilot</h1>
        <p className="subtitle">Milestone 1: environment check</p>
      </header>

      <section className="card" aria-live="polite">
        <h2>System status</h2>
        {state.kind === 'loading' && <p>Checking…</p>}
        {state.kind === 'error' && (
          <ul className="status-list">
            <StatusRow label="API" ok={false} detail={`Not reachable (${state.message})`} />
          </ul>
        )}
        {state.kind === 'ok' && (
          <ul className="status-list">
            <StatusRow label="API" ok detail={`Running, version ${state.health.app_version}`} />
            <StatusRow
              label="Ollama"
              ok={state.health.ollama.reachable}
              detail={
                state.health.ollama.reachable
                  ? `Running, version ${state.health.ollama.version}`
                  : `Not reachable (${state.health.ollama.error}). Start the Ollama app.`
              }
            />
          </ul>
        )}
      </section>
    </main>
  )
}
