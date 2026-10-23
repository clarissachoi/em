import { useEffect, useState } from 'react'
import { getHealth, getMe, type UserProfile } from './api/client'
import PersonaProvider from './components/PersonaProvider'
import PersonaSwitcher from './components/PersonaSwitcher'
import { usePersona } from './hooks/usePersona'

/** Current persona's profile, re-fetched when the persona changes. */
function Profile() {
  const { persona } = usePersona()
  const [me, setMe] = useState<{ persona: string; profile: UserProfile } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getMe()
      .then((profile) => !cancelled && setMe({ persona, profile }))
      .catch((err: unknown) => !cancelled && setError(String(err)))
    return () => {
      cancelled = true
    }
  }, [persona])

  if (error) return <p className="error">{error}</p>
  if (me?.persona !== persona) return <p className="muted">Loading...</p>
  const { profile } = me
  return (
    <section>
      <h1>Hi, {profile.name}</h1>
      <p>{profile.primary_goal}</p>
      {profile.pregnancy && <p>Week {profile.pregnancy.week} of pregnancy</p>}
    </section>
  )
}

/** App shell: header with persona switcher, then the page. */
function Shell() {
  const [backend, setBackend] = useState('checking...')

  useEffect(() => {
    getHealth()
      .then((data) => setBackend(data.ok ? 'ok' : 'not ok'))
      .catch(() => setBackend('unreachable'))
  }, [])

  return (
    <>
      <header className="header">
        <strong>EmCare</strong>
        <PersonaSwitcher />
      </header>
      <main className="app">
        <Profile />
        <p className="muted">Backend: {backend}</p>
      </main>
    </>
  )
}

/** Root component. */
export default function App() {
  return (
    <PersonaProvider>
      <Shell />
    </PersonaProvider>
  )
}
