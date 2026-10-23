// Calendar icon in the header: month view of the persona's events, cycle, and pregnancy timeline.

import { useEffect, useMemo, useRef, useState } from 'react'
import { getCalendar, type CalendarEvent } from '../api/client'
import { usePersona } from '../hooks/usePersona'
import Icon from './Icon'

type Group = 'appointments' | 'travel' | 'plan' | 'cycle' | 'pregnancy' | 'routine'

const GROUP_OF: Record<CalendarEvent['kind'], Group> = {
  appointment: 'appointments', travel: 'travel', work: 'travel', plan: 'plan', period: 'cycle', ovulation: 'cycle',
  pregnancy: 'pregnancy', prenatal: 'pregnancy', routine: 'routine', family: 'routine',
}
const GROUPS: { key: Group; label: string }[] = [
  { key: 'appointments', label: 'Appointments' },
  { key: 'travel', label: 'Travel & work' },
  { key: 'plan', label: 'Plan' },
  { key: 'cycle', label: 'Cycle' },
  { key: 'pregnancy', label: 'Pregnancy' },
  { key: 'routine', label: 'Routine' },
]
const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

/** Local YYYY-MM-DD for a Date. */
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Date at local noon (avoids DST edge cases) from YYYY-MM-DD. */
const parse = (s: string) => new Date(`${s}T12:00:00`)

/** '18:00' -> '6:00 PM'. */
function clock(t: string | null) {
  if (!t) return null
  const [h, m] = t.split(':').map(Number)
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`
}

/** The 6-week grid (Sunday start) that covers a month. */
function gridDays(month: Date) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1, 12)
  const start = new Date(first)
  start.setDate(1 - first.getDay())
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    return d
  })
}

/** Header button that opens the calendar popover. */
export default function CalendarMenu() {
  const { persona } = usePersona()
  const [open, setOpen] = useState(false)
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1, 12))
  const [selected, setSelected] = useState(() => iso(new Date()))
  const [hidden, setHidden] = useState<Set<Group>>(new Set(['routine']))
  const [result, setResult] = useState<{ key: string; events: CalendarEvent[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const root = useRef<HTMLDivElement>(null)

  const days = useMemo(() => gridDays(month), [month])
  const range = { start: iso(days[0]), end: iso(days[41]) }
  const key = `${persona}:${range.start}`

  useEffect(() => {
    if (!open) return
    let cancelled = false
    getCalendar(range.start, range.end)
      .then((events) => {
        if (cancelled) return
        setResult({ key, events })
        setError(null)
      })
      .catch(() => !cancelled && setError('Could not load your calendar.'))
    return () => {
      cancelled = true
    }
    // range is derived from key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, key])

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

  const events = result?.key === key ? result.events : null
  const present = new Set((events ?? []).map((e) => GROUP_OF[e.kind]))
  const visible = (events ?? []).filter((e) => !hidden.has(GROUP_OF[e.kind]))
  const on = (day: string) => visible.filter((e) => e.start_date <= day && e.end_date >= day)
  const today = iso(new Date())
  const agenda = on(selected).sort((a, b) => (a.start_time ?? '').localeCompare(b.start_time ?? ''))

  const shift = (delta: number) => {
    const next = new Date(month.getFullYear(), month.getMonth() + delta, 1, 12)
    setMonth(next)
    setSelected(iso(next.getMonth() === new Date().getMonth() && next.getFullYear() === new Date().getFullYear() ? new Date() : next))
  }
  const toggle = (g: Group) =>
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(g)) next.delete(g)
      else next.add(g)
      return next
    })

  return (
    <div className="data-menu cal-menu" ref={root}>
      <button type="button" className="icon-btn" aria-haspopup="dialog" aria-expanded={open} aria-label="Calendar"
        onClick={() => setOpen((o) => !o)}>
        <Icon name="calendar" size={16} />
      </button>
      {open && (
        <div className="data-pop cal-pop" role="dialog" aria-label="Calendar">
          <header className="cal-head">
            <button type="button" className="cal-nav" onClick={() => shift(-1)} aria-label="Previous month">‹</button>
            <strong>{month.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</strong>
            <button type="button" className="cal-nav" onClick={() => shift(1)} aria-label="Next month">›</button>
          </header>

          <div className="cal-filters">
            {GROUPS.filter((g) => present.has(g.key)).map((g) => (
              <button key={g.key} type="button" className={`cal-filter ${g.key} ${hidden.has(g.key) ? 'off' : ''}`}
                aria-pressed={!hidden.has(g.key)} onClick={() => toggle(g.key)}>
                <span className="cal-dot" aria-hidden /> {g.label}
              </button>
            ))}
          </div>

          <div className="cal-grid" role="grid" aria-label="Month">
            {WEEKDAYS.map((w, i) => <span key={i} className="cal-wd" aria-hidden>{w}</span>)}
            {days.map((d) => {
              const day = iso(d)
              const groups = [...new Set(on(day).map((e) => GROUP_OF[e.kind]))]
              const period = on(day).some((e) => e.kind === 'period')
              return (
                <button key={day} type="button" role="gridcell"
                  className={`cal-day ${d.getMonth() !== month.getMonth() ? 'other' : ''} ${day === today ? 'today' : ''} ${day === selected ? 'sel' : ''} ${period ? 'period' : ''}`}
                  aria-label={`${d.toDateString()}, ${on(day).length} events`} aria-selected={day === selected}
                  onClick={() => setSelected(day)}>
                  <span>{d.getDate()}</span>
                  <span className="cal-dots">{groups.slice(0, 4).map((g) => <i key={g} className={`cal-dot ${g}`} />)}</span>
                </button>
              )
            })}
          </div>

          <div className="cal-agenda">
            <span className="eyebrow">{parse(selected).toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}</span>
            {error && <p className="error">{error}</p>}
            {!events && !error && <p className="muted small">Loading...</p>}
            {events && agenda.length === 0 && <p className="muted small">Nothing on this day.</p>}
            <ul>
              {agenda.map((e) => (
                <li key={e.id} className={GROUP_OF[e.kind]}>
                  <span className="cal-time">
                    {clock(e.start_time) ?? 'All day'}
                  </span>
                  <div>
                    <strong>{e.title}</strong>
                    {(e.detail || e.location) && <span className="muted small">{[e.detail, e.location].filter(Boolean).join(' · ')}</span>}
                    {e.end_date !== e.start_date && (
                      <span className="muted small">
                        {parse(e.start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} to{' '}
                        {parse(e.end_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </span>
                    )}
                  </div>
                  {e.predicted && <span className="cal-pred">Estimated</span>}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
