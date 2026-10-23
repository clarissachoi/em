import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api'

/** Root component. Shows whether the backend is reachable. */
export default function App() {
  const [backend, setBackend] = useState('checking...')

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((res) => res.json())
      .then((data: { ok: boolean }) => setBackend(data.ok ? 'ok' : 'not ok'))
      .catch(() => setBackend('unreachable'))
  }, [])

  return (
    <main className="app">
      <h1>EmCare</h1>
      <p>Backend: {backend}</p>
    </main>
  )
}
