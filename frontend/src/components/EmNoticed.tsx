import { useEffect, useState } from 'react'
import { getInsights, type Insight } from '../api/client'
import { usePersona } from '../hooks/usePersona'
import Icon from './Icon'

/** "Em noticed" banner: the top cross-data pattern plus quick check-in actions. Used on Home and em.well. */
export default function EmNoticed({ onAsk }: { onAsk: (prompt?: string) => void }) {
  const { persona } = usePersona()
  const [insight, setInsight] = useState<{ persona: string; top?: Insight } | null>(null)

  useEffect(() => {
    let cancelled = false
    getInsights()
      .then((list) => !cancelled && setInsight({ persona, top: list[0] }))
      .catch(() => !cancelled && setInsight({ persona }))
    return () => {
      cancelled = true
    }
  }, [persona])

  // Results from a previous persona read as loading
  const top = insight?.persona === persona ? insight.top : undefined

  return (
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
  )
}
