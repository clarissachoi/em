import { useEffect, useState } from 'react'
import { getInsights, getSuggestions, type Insight, type Suggestion, type Suggestions } from '../api/client'
import Icon from '../components/Icon'
import { usePersona } from '../hooks/usePersona'

type Load<T> = { persona: string; data?: T; error?: string }

const SECTIONS: { key: string; title: string; blurb: string; parts: (keyof Omit<Suggestions, 'headline'>)[] }[] = [
  { key: 'move', title: 'Move & Recover', blurb: 'Gentle on your body, built around your week.', parts: ['workouts', 'classes'] },
  { key: 'eat', title: 'Eat Well', blurb: 'Food first. Simple meals that fit your day.', parts: ['nutrition'] },
]
const ICON: Record<string, string> = { workouts: 'run', classes: 'lotus', nutrition: 'food' }

/** Fetch for the current persona; results from a previous persona read as loading. */
function usePersonaLoad<T>(fn: () => Promise<T>, persona: string, attempt: number): Load<T> | null {
  const [state, setState] = useState<Load<T> | null>(null)
  useEffect(() => {
    let cancelled = false
    fn()
      .then((data) => !cancelled && setState({ persona, data }))
      .catch((err: unknown) => !cancelled && setState({ persona, error: String(err) }))
    return () => {
      cancelled = true
    }
    // fn is a stable module-level API function
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persona, attempt])
  return state?.persona === persona ? state : null
}

/** One suggestion card. */
function Card({ s, part, added, onAdd, onAsk }: { s: Suggestion; part: string; added: boolean; onAdd: () => void; onAsk: () => void }) {
  return (
    <article className={`well-card ${part} ${s.source}`}>
      <div className={`well-art ${s.image ? 'photo' : ''}`}>
        {s.image ? <img src={s.image} alt="" loading="lazy" /> : <Icon name={ICON[part]} size={40} />}
        <span className="well-tag">{s.tag}</span>
        {s.duration_min != null && (
          <span className="well-dur"><Icon name="clock" size={12} /> {s.duration_min} min</span>
        )}
      </div>
      <div className="well-body">
        {s.where && (
          <span className="well-where">
            <Icon name="pin" size={12} /> {s.distance_mi != null && `${s.distance_mi} mi · `}{s.where}
          </span>
        )}
        {s.near_tag && <span className="near-tag"><Icon name="pin" size={11} /> {s.near_tag}</span>}
        <h3>{s.title}</h3>
        <p className="well-desc">{s.description}</p>
        <p className="well-why"><strong>{s.source === 'doctor' ? 'From your doctor:' : 'Why for you:'}</strong> {s.reason}</p>
      </div>
      <footer className="well-foot">
        <div>
          <span className="eyebrow">When</span>
          <span className="well-when">{s.when ?? 'Anytime'}</span>
        </div>
        <div className="well-actions">
          <button className="tag" onClick={onAsk}>Ask Em</button>
          <button className={`btn-dark small ${added ? 'added' : ''}`} onClick={onAdd} aria-pressed={added}>
            {s.source === 'doctor' ? (added ? 'Taken today' : 'Mark taken') : added ? 'Added' : 'Add to my day'}{' '}
            <Icon name={added ? 'check' : 'plus'} size={14} />
          </button>
        </div>
      </footer>
    </article>
  )
}

/** em.well: personalized move and eat ideas, plus a pattern Em noticed. */
export default function Wellness({ onAsk }: { onAsk: (prompt?: string) => void }) {
  const { persona } = usePersona()
  const [attempt, setAttempt] = useState(0)
  const [added, setAdded] = useState<Set<string>>(new Set())
  const suggestions = usePersonaLoad(getSuggestions, persona, attempt)
  const insights = usePersonaLoad<Insight[]>(getInsights, persona, 0)
  const top = insights?.data?.[0]

  const toggle = (title: string) =>
    setAdded((prev) => {
      const next = new Set(prev)
      if (next.has(title)) next.delete(title)
      else next.add(title)
      return next
    })

  return (
    <div className="well">
      <header className="well-hero">
        <div>
          <span className="pill small eyebrow-pill"><span className="dot coral" aria-hidden /> em.well · next steps</span>
          <h1 className="well-title">em.well</h1>
          <p className="well-sub">Ideas to move and eat well this week, shaped by your own data.</p>
        </div>
        <div className="well-focus glass">
          <span className="eyebrow">Your focus</span>
          <strong>{suggestions?.data?.headline ?? '...'}</strong>
        </div>
      </header>

      {suggestions?.error && (
        <div className="well-error glass">
          <p>Em could not put together suggestions right now.</p>
          <button className="btn-dark small" onClick={() => setAttempt((a) => a + 1)}>Try again</button>
        </div>
      )}

      {SECTIONS.map((sec) => {
        const items = sec.parts.flatMap((part) => (suggestions?.data?.[part] ?? []).map((s) => ({ s, part })))
        const loading = !suggestions
        if (!loading && items.length === 0) return null
        return (
          <section key={sec.key} className="well-section">
            <h2 className="well-h2"><span className="dot coral" aria-hidden /> {sec.title}</h2>
            <p className="muted well-blurb">{sec.blurb}</p>
            <div className="well-grid">
              {loading
                ? [0, 1, 2].map((i) => <div key={i} className="well-card skeleton" aria-hidden />)
                : items.map(({ s, part }) => (
                    <Card
                      key={s.title}
                      s={s}
                      part={part}
                      added={added.has(s.title)}
                      onAdd={() => toggle(s.title)}
                      onAsk={() =>
                        onAsk(
                          s.source === 'doctor'
                            ? `Can you remind me what my doctor said about "${s.title}"?`
                            : `Tell me more about "${s.title}". Is it a good fit for me this week?`,
                        )
                      }
                    />
                  ))}
            </div>
          </section>
        )
      })}
      {!suggestions && <p className="muted well-loading">Em is putting together ideas for you...</p>}

      <section className="well-noticed glass">
        <span className="noticed-icon"><Icon name="spark" size={20} /></span>
        <div className="noticed-text">
          <span className="eyebrow accent-text">Em noticed</span>
          <strong>{top?.text ?? 'Em is looking at your week...'}</strong>
          {top && <span className="muted">{top.evidence}</span>}
        </div>
        <div className="noticed-actions">
          <button className="tag" onClick={() => onAsk("I'm feeling good today. Can you log a quick check-in?")}>Feeling good</button>
          <button className="btn-coral" onClick={() => onAsk("I'd like to tell you how I'm feeling today.")}>
            Tell Em how you feel <Icon name="chat" size={14} />
          </button>
        </div>
      </section>
    </div>
  )
}
