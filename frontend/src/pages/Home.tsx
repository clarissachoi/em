import { useEffect, useState, type FormEvent } from 'react'
import { getHome, type FocusItem, type HomeData } from '../api/client'
import Icon, { MoodFace } from '../components/Icon'
import TrendChart from '../components/TrendChart'
import { usePersona } from '../hooks/usePersona'

const FOCUS_ICON: Record<FocusItem['kind'], string> = {
  workout: 'run', nutrition: 'food', appointment: 'calendar', records: 'doc', lab: 'lab', checkin: 'chat',
}
const MOODS = ['Low', 'Okay', 'Good', 'Great']

/** 1-5 check-in mood to one of the 4 faces. */
const moodLevel = (mood: number) => (mood <= 2 ? 0 : mood - 2)

/** Initials for the care note avatar. */
function initials(name: string) {
  if (name === 'Em') return 'Em'
  return name.replace(/^Dr\.?\s+/, '').split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase()
}

/** Home dashboard matching the "Mock screen" design. onAsk opens Em with an optional question. */
export default function Home({
  onAsk,
  onOpenCare,
  onOpenWellness,
}: { onAsk: (prompt?: string) => void; onOpenCare: () => void; onOpenWellness: () => void }) {
  const { persona } = usePersona()
  const [home, setHome] = useState<{ persona: string; data: HomeData } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<Set<number>>(new Set())
  const [draft, setDraft] = useState('')
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    let cancelled = false
    getHome()
      .then((data) => {
        if (cancelled) return
        setHome({ persona, data })
        setDone(new Set())
        setError(null)
      })
      .catch((err: unknown) => !cancelled && setError(String(err)))
    return () => {
      cancelled = true
    }
  }, [persona])

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(id)
  }, [])

  if (error) return <p className="error page-msg">Could not load Home. {error}</p>
  if (home?.persona !== persona) return <p className="muted page-msg">Loading...</p>
  const d = home.data

  const ask = (e: FormEvent) => {
    e.preventDefault()
    onAsk(draft.trim() || undefined)
    setDraft('')
  }
  const toggle = (i: number) =>
    setDone((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  const remaining = d.focus.length - done.size
  // Viewer's own clock, not the server's (Vercel runs on UTC)
  const hour = now.getHours()
  const daypart = `Good ${hour < 12 ? 'Morning' : hour < 17 ? 'Afternoon' : 'Evening'}`

  return (
    <div className="home">
      <div className="status-row">
        <span className="pill">
          <Icon name="sun" size={14} /> {daypart} · {now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
        </span>
        {d.mood != null && (
          <span className="pill moods" role="img" aria-label={`Latest check-in mood: ${MOODS[moodLevel(d.mood)]}`}>
            {MOODS.map((label, i) => (
              <span key={label} className={`mood ${i === moodLevel(d.mood!) ? 'on' : ''}`} title={label}>
                <MoodFace level={i} />
              </span>
            ))}
          </span>
        )}
        {d.readiness && (
          <span className="pill">
            Readiness {d.readiness.score} · <span className="accent-text">{d.readiness.label}</span>
          </span>
        )}
      </div>

      <h1 className="greeting">{daypart}, {d.user_name}</h1>
      <p className="quote">{d.quote}</p>

      <form className="ask" onSubmit={ask}>
        <button type="button" className="ask-mic" onClick={() => onAsk()} aria-label="Talk to Em">
          <Icon name="mic" size={18} />
        </button>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask Em anything..."
          aria-label="Ask Em"
        />
        <div className="chips">
          {d.ask_suggestions.map((q) => (
            <button key={q} type="button" className="chip" onClick={() => onAsk(q)}>{q}</button>
          ))}
        </div>
        <button type="submit" className="ask-send" aria-label="Send to Em">
          <Icon name="arrow" size={16} />
        </button>
      </form>

      <div className="cards">
        <section className="card glass focus">
          <header className="card-head">
            <h2><span className="dot coral" aria-hidden /> Today's Focus</h2>
            <span className="eyebrow">{remaining} remaining</span>
          </header>
          <ul className="focus-list">
            {d.focus.map((f, i) => (
              <li key={i} className={`focus-item ${done.has(i) ? 'done' : ''}`}>
                <span className={`focus-icon ${f.kind}`}><Icon name={FOCUS_ICON[f.kind]} /></span>
                <div className="focus-text">
                  <strong>{f.title}</strong>
                  <span className="muted">{[f.time, f.detail].filter(Boolean).join(' · ')}</span>
                </div>
                {f.kind === 'checkin' ? (
                  <button className="tag" onClick={() => onAsk("I'd like to do my check-in.")}>Talk</button>
                ) : (
                  <button className="tag" onClick={() => toggle(i)} aria-pressed={done.has(i)}>
                    {done.has(i) ? 'Done' : 'Log'}
                  </button>
                )}
              </li>
            ))}
          </ul>
          <footer className="card-foot">
            <span className="muted small">
              <Icon name="check" size={14} />{' '}
              {d.care_checklist
                ? `${d.care_checklist.found} of ${d.care_checklist.total} care team found`
                : d.readiness?.summary ?? 'Synced today'}
            </span>
            <button className="btn-dark" onClick={() => onAsk('Help me reflect on my day.')}>
              Reflect Day <span className="btn-dark-icon"><Icon name="arrow" size={14} /></span>
            </button>
          </footer>
        </section>

        <section className="card glass pulse">
          <header className="card-head">
            <h2><span className="dot violet" aria-hidden /> Vital Pulse</h2>
            <span className="pill small">This Week</span>
          </header>
          <TrendChart points={d.trend} />
          <div className="metrics">
            {d.metrics.map((m) => (
              <div key={m.label} className="metric">
                <span className="eyebrow">{m.label}</span>
                <span className="metric-value">
                  {m.value}
                  {m.unit && <small>{m.unit}</small>}
                </span>
              </div>
            ))}
          </div>
          {d.care_note && (
            <div className="note">
              <span className={`avatar ${d.care_note.source}`}>{initials(d.care_note.author)}</span>
              <div>
                <strong>{d.care_note.author}</strong>
                <p>"{d.care_note.text}"</p>
              </div>
            </div>
          )}
        </section>
      </div>

      <nav className="shortcuts" aria-label="Other sections">
        <button className="shortcut link" onClick={onOpenCare}><Icon name="chat" /> em.doc</button>
        <span className="divider" aria-hidden />
        <button className="shortcut link" onClick={onOpenWellness}><Icon name="globe" /> em.well</button>
        <button className="ask-send coral" onClick={onOpenWellness} aria-label="Open em.well"><Icon name="arrow" size={16} /></button>
      </nav>
    </div>
  )
}
