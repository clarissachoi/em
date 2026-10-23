import { useEffect, useState } from 'react'
import Icon from './components/Icon'
import PersonaProvider from './components/PersonaProvider'
import PersonaSwitcher from './components/PersonaSwitcher'
import VoicePanel from './components/VoicePanel'
import { usePersona } from './hooks/usePersona'
import AppointmentsDebug from './pages/AppointmentsDebug'
import CareHub from './pages/CareHub'
import Home from './pages/Home'
import Wellness from './pages/Wellness'

/** Slide-over drawer holding the live Em voice panel. */
function EmDrawer({ open, prompt, session, onClose }: { open: boolean; prompt?: string; session: number; onClose: () => void }) {
  const { persona } = usePersona()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-label="Talk to Em" onClick={(e) => e.stopPropagation()}>
        <button className="drawer-close" onClick={onClose} aria-label="Close">
          <Icon name="close" />
        </button>
        {/* key starts a fresh session per open and per persona */}
        <VoicePanel key={`${persona}-${session}`} autoStart prompt={prompt} />
      </aside>
    </div>
  )
}

/** App shell: header with nav and persona switcher, the page, Em drawer, footer. */
function Shell() {
  const [em, setEm] = useState<{ open: boolean; prompt?: string; session: number }>({ open: false, session: 0 })
  const [page, setPage] = useState<'home' | 'care' | 'wellness' | 'appointments-debug'>('home')
  const openEm = (prompt?: string) => setEm((s) => ({ open: true, prompt, session: s.session + 1 }))
  const closeEm = () => setEm((s) => ({ ...s, open: false }))

  return (
    <div className="shell">
      <header className="topbar">
        <span className="logo">em.care</span>
        <nav className="tabs" aria-label="Main">
          <a
            className={`tab ${page === 'home' ? 'active' : ''}`}
            aria-current={page === 'home' ? 'page' : undefined}
            href="/"
            onClick={(e) => {
              e.preventDefault()
              setPage('home')
            }}
          >
            Home
          </a>
          <a
            className={`tab ${page === 'care' ? 'active' : ''}`}
            aria-current={page === 'care' ? 'page' : undefined}
            href="/care"
            onClick={(e) => {
              e.preventDefault()
              setPage('care')
            }}
          >
            em.doc
          </a>
          <a
            className={`tab ${page === 'wellness' ? 'active' : ''}`}
            aria-current={page === 'wellness' ? 'page' : undefined}
            href="#em-well"
            onClick={(e) => {
              e.preventDefault()
              setPage('wellness')
            }}
          >
            em.well
          </a>
        </nav>
        <div className="profile-chip">
          <PersonaSwitcher />
          <span className="avatar-btn" aria-hidden><Icon name="user" size={16} /></span>
        </div>
      </header>

      <main className="page">
        {page === 'home' && <Home onAsk={openEm} onOpenCare={() => setPage('care')} onOpenWellness={() => setPage('wellness')} />}
        {page === 'care' && <CareHub onAsk={openEm} />}
        {page === 'wellness' && <Wellness onAsk={openEm} />}
        {page === 'appointments-debug' && <AppointmentsDebug />}
      </main>

      <footer className="site-footer">
        <span><span className="logo small">em.care</span> · Mindful Clinical Synthesis</span>
        <span>
          {/* Temporary: the appointments test page stays reachable until it has a real screen */}
          <button className="link-btn" onClick={() => setPage('appointments-debug')}>Appointments (test)</button>
          {' · '}© 2026 em.care Health. Ethereal, compassionate care.
        </span>
      </footer>

      <EmDrawer open={em.open} prompt={em.prompt} session={em.session} onClose={closeEm} />
    </div>
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
