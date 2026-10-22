import { useEffect, useState } from 'react'
import { getJson } from './api'

type State<T> = { data: T | null; error: string | null; loading: boolean }

/** Fetch JSON for a URL. Keeps the previous data while refetching, so charts
 *  dim instead of flashing empty. Pass null to skip fetching. */
export function useApi<T>(url: string | null): State<T> & { reload: () => void } {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: Boolean(url) })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    if (!url) return
    const controller = new AbortController()
    setState((s) => ({ ...s, loading: true, error: null }))
    getJson<T>(url, controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setState((s) => ({ ...s, error: error.message, loading: false }))
      })
    return () => controller.abort()
  }, [url, version])

  return { ...state, reload: () => setVersion((v) => v + 1) }
}

/** True while the operating system is in dark mode; updates live. */
export function usePrefersDark(): boolean {
  const query = '(prefers-color-scheme: dark)'
  const [dark, setDark] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const media = window.matchMedia(query)
    const onChange = () => setDark(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return dark
}
