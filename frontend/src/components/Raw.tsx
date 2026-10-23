// Scaffold helper: dump one endpoint's raw JSON for the current persona.

import { useApi } from '../hooks/useApi'

/** Render one endpoint's raw response under a heading. */
export function RawSection<T>({ title, fn }: { title: string; fn: () => Promise<T> }) {
  const state = useApi(fn)
  return (
    <section className="raw">
      <h2>{title}</h2>
      {state.status === 'loading' && <p className="muted">Loading...</p>}
      {state.status === 'error' && <p className="error">{state.error}</p>}
      {state.status === 'ok' && <pre>{JSON.stringify(state.data, null, 2)}</pre>}
    </section>
  )
}
