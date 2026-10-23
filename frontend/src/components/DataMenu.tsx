// Profile icon menu with the "Your data" choices. Both are opt in; the demo saves the choice and shares nothing.

import { useEffect, useRef, useState } from 'react'
import { getDataSettings, putDataSettings, type DataSettings } from '../api/client'
import { usePersona } from '../hooks/usePersona'
import Icon from './Icon'

type Choice = 'model_training' | 'third_party_sharing'

const CHOICES: { key: Choice; title: string; detail: string }[] = [
  {
    key: 'model_training',
    title: 'Help improve em.care AI',
    detail: 'Use my check-ins and health data to train and improve em.care models.',
  },
  {
    key: 'third_party_sharing',
    title: 'Share with partners for tailored offers',
    detail: 'Share or sell my data to vetted third parties, like wellness brands, so they can suggest products and programs.',
  },
]

/** One labeled on/off switch. */
function Switch({ on, label, disabled, onChange }: { on: boolean; label: string; disabled: boolean; onChange: (on: boolean) => void }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled}
      className={`switch ${on ? 'on' : ''}`} onClick={() => onChange(!on)}>
      <span className="switch-thumb" />
    </button>
  )
}

/** Avatar button that opens the data settings popover. */
export default function DataMenu() {
  const { persona } = usePersona()
  const [open, setOpen] = useState(false)
  const [settings, setSettings] = useState<{ persona: string; data: DataSettings } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    getDataSettings()
      .then((data) => {
        if (cancelled) return
        setSettings({ persona, data })
        setError(null)
      })
      .catch(() => !cancelled && setError('Could not load your settings.'))
    return () => {
      cancelled = true
    }
  }, [open, persona])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onClick = (e: MouseEvent) => root.current && !root.current.contains(e.target as Node) && setOpen(false)
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onClick)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onClick)
    }
  }, [open])

  const current = settings?.persona === persona ? settings.data : null

  const change = (key: Choice, on: boolean) => {
    if (!current) return
    const before = current
    const next = { ...current, [key]: on }
    setSettings({ persona, data: next })
    setSaving(true)
    setError(null)
    putDataSettings({ model_training: next.model_training, third_party_sharing: next.third_party_sharing })
      .then((data) => setSettings({ persona, data }))
      .catch(() => {
        setSettings({ persona, data: before })
        setError('Could not save. Your choice was not changed.')
      })
      .finally(() => setSaving(false))
  }

  return (
    <div className="data-menu" ref={root}>
      <button type="button" className="avatar-btn" aria-haspopup="dialog" aria-expanded={open} aria-label="Your data settings"
        onClick={() => setOpen((o) => !o)}>
        <Icon name="user" size={16} />
      </button>
      {open && (
        <div className="data-pop" role="dialog" aria-label="Your data">
          <header className="data-pop-head">
            <span className="data-pop-icon"><Icon name="shield" size={18} /></span>
            <div>
              <strong>Your data</strong>
              <span className="muted small">You choose how your data is used. Both are off unless you turn them on.</span>
            </div>
          </header>

          {!current && !error && <p className="muted small">Loading...</p>}
          {current && (
            <ul className="data-choices">
              {CHOICES.map((c) => (
                <li key={c.key}>
                  <div>
                    <strong>{c.title}</strong>
                    <span className="muted small">{c.detail}</span>
                  </div>
                  <Switch on={current[c.key]} label={c.title} disabled={saving} onChange={(on) => change(c.key, on)} />
                </li>
              ))}
            </ul>
          )}
          {error && <p className="error">{error}</p>}

          <p className="data-note">
            Turning these on may help tailor recommendations over time. Em works fully with both off.
          </p>
          <p className="data-note muted">
            Demo: nothing is trained on or shared. To reply to you, Em sends what you share to Google Gemini; that is
            needed for Em to work and is separate from these choices.
            {current?.updated_at && ` Last changed ${new Date(current.updated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}.`}
          </p>
        </div>
      )}
    </div>
  )
}
