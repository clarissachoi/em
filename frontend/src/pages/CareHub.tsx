import { useCallback, useEffect, useRef, useState } from 'react'
import {
  bookSlot,
  getAppointments,
  getScribeNotes,
  getSlots,
  prepAppointment,
  refreshSuggestions,
  scribeVisit,
  type Appointment,
  type AppointmentList,
  type ScribeNote,
  type Slot,
  type SuggestedAppointment,
} from '../api/client'
import Icon from '../components/Icon'
import { usePersona } from '../hooks/usePersona'

const BARS = 13
const MAX_RECORD_SEC = 60 * 60 // keeps uploads under the backend's size limit

// ---------- Helpers ----------

/** "Friday, Oct 23" */
const fmtDay = (iso: string) => new Date(iso).toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })
/** "5:15 PM" */
const fmtTime = (iso: string) => new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
/** "Tue Oct 27, 7:30 AM" for slot chips. */
const fmtShort = (iso: string) =>
  `${new Date(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}, ${fmtTime(iso)}`
/** "14:05" */
/** "Oct 16, 2026" */
const fmtDate = (iso: string) => new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
const fmtClock = (sec: number) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, '0')}`

const isToday = (iso: string) => new Date(iso).toDateString() === new Date().toDateString()

/** Download a one-hour .ics event for an appointment. Seed times are local, so they stay floating. */
function downloadIcs(a: Appointment) {
  const stamp = (d: Date) =>
    `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}T` +
    `${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}00`
  const start = new Date(a.datetime)
  const end = new Date(start.getTime() + 60 * 60 * 1000)
  const esc = (s: string) => s.replace(/([,;\\])/g, '\\$1')
  const ics = [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//em.care//EN', 'BEGIN:VEVENT',
    `UID:${a.id}@em.care`, `DTSTAMP:${stamp(new Date())}`, `DTSTART:${stamp(start)}`, `DTEND:${stamp(end)}`,
    `SUMMARY:${esc(`${a.specialty} with ${a.provider}`)}`, `LOCATION:${esc(a.location)}`,
    'END:VEVENT', 'END:VCALENDAR',
  ].join('\r\n')
  const url = URL.createObjectURL(new Blob([ics], { type: 'text/calendar' }))
  const link = Object.assign(document.createElement('a'), { href: url, download: `${a.id}.ics` })
  link.click()
  URL.revokeObjectURL(url)
}

/** First MediaRecorder audio type this browser supports. */
function pickMime() {
  return ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'].find((t) => MediaRecorder.isTypeSupported(t)) ?? ''
}

// ---------- Appointments ----------

/** One appointment with calendar and prep actions. The first upcoming one is featured. */
function AppointmentItem({ a, featured, onPrepped }: { a: Appointment; featured: boolean; onPrepped: (a: Appointment) => void }) {
  const [prepping, setPrepping] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const upcoming = a.status === 'upcoming'
  const badge = a.for_person !== 'self' ? `For ${a.for_person}` : upcoming ? (isToday(a.datetime) ? 'Today' : 'Confirmed') : 'Completed'

  const prep = () => {
    setPrepping(true)
    setError(null)
    prepAppointment(a.id)
      .then(onPrepped)
      .catch(() => setError('Could not get questions right now. Try again in a moment.'))
      .finally(() => setPrepping(false))
  }

  return (
    <li className={`appt ${featured ? 'featured' : ''}`}>
      <div className="appt-main">
        <span className="appt-icon"><Icon name="calendar" size={featured ? 22 : 18} /></span>
        <div className="appt-text">
          <div className="appt-title">
            <strong>{a.specialty}</strong>
            <span className={`badge ${upcoming ? 'coral' : ''}`}>{badge}</span>
          </div>
          <span className="muted">With {a.provider}</span>
          <div className="appt-meta">
            <span className="accent-text"><Icon name="clock" size={14} /> {fmtDay(a.datetime)} · {fmtTime(a.datetime)}</span>
            <span><Icon name="pin" size={14} /> {a.location}</span>
          </div>
        </div>
        {upcoming && (
          <div className="appt-actions">
            <button className="btn-pill" onClick={() => downloadIcs(a)}>
              <Icon name="calendar" /> Add to Calendar
            </button>
            <button className="btn-pill primary" onClick={prep} disabled={prepping}>
              <Icon name="sparkle" /> {prepping ? 'Preparing...' : a.prep_questions.length ? 'Refresh prep' : 'Prepare with Em'}
            </button>
          </div>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      {a.prep_questions.length > 0 && (
        <div className="prep">
          <span className="eyebrow">Questions to ask</span>
          <ol>{a.prep_questions.map((q) => <li key={q}>{q}</li>)}</ol>
        </div>
      )}
      {a.visit_summary && <p className="appt-summary">{a.visit_summary.summary}</p>}
    </li>
  )
}

/** Open slots as quick-book chips, with a confirm step before booking. */
function BookNext({ slots, booked, suggested, onBooked, onSuggested, onAsk }: {
  slots: Slot[]
  booked: string[]
  suggested: SuggestedAppointment[]
  onBooked: () => void
  onSuggested: (s: SuggestedAppointment[]) => void
  onAsk: (prompt?: string) => void
}) {
  const [picked, setPicked] = useState<Slot | null>(null)
  const [filter, setFilter] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Open times only for suggested categories, and never for care she already has booked
  const bookedSet = new Set(booked.map((b) => b.toLowerCase()))
  const suggestedSet = new Set(suggested.map((s) => s.specialty.toLowerCase()))
  const matches = (s: Slot) => {
    const specialty = s.specialty.toLowerCase()
    if (bookedSet.has(specialty)) return false
    return filter ? specialty === filter.toLowerCase() : suggestedSet.has(specialty)
  }
  const shown = slots.filter(matches).slice(0, 3)

  const book = () => {
    if (!picked) return
    setBusy(true)
    setError(null)
    bookSlot(picked.id)
      .then(() => {
        setPicked(null)
        setFilter(null)
        onBooked()
      })
      .catch(() => setError('That time was just taken. Pick another.'))
      .finally(() => setBusy(false))
  }

  const refresh = () => {
    setRefreshing(true)
    setError(null)
    refreshSuggestions()
      .then((next) => {
        onSuggested(next)
        setFilter(null)
      })
      .catch(() => setError('Could not refresh suggestions right now. Showing the saved ones.'))
      .finally(() => setRefreshing(false))
  }

  return (
    <div className="book-next" id="book-next">
      <div className="book-row">
        <div>
          <strong><Icon name="bolt" /> Book Next Session</strong>
          <span className="muted small">Visits Em suggests for your goals, and open times nearby</span>
        </div>
        <button className="btn-pill" onClick={refresh} disabled={refreshing}>
          <Icon name="refresh" /> {refreshing ? 'Refreshing...' : 'Refresh suggestions'}
        </button>
      </div>

      {suggested.length > 0 && (
        <div className="sug-row">
          <span className="eyebrow">Suggested for you</span>
          <div className="slot-chips">
            {suggested.map((sug, i) => (
              <span key={sug.specialty} className="sug">
                <button
                  className={`slot-chip sug-chip ${filter === sug.specialty ? 'on' : ''}`}
                  onClick={() => {
                    setPicked(null)
                    setFilter(filter === sug.specialty ? null : sug.specialty)
                  }}
                  aria-describedby={`sug-why-${i}`}
                  aria-pressed={filter === sug.specialty}
                >
                  {sug.urgency === 'soon' && <span className="dot coral" aria-hidden />}
                  {sug.specialty}
                </button>
                <span className="sug-pop" role="tooltip" id={`sug-why-${i}`}>
                  <span className="eyebrow">{sug.urgency === 'soon' ? 'Book soon' : 'Routine'} · why it helps</span>
                  {sug.reason || 'Refresh suggestions to see how this visit supports your goals.'}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="sug-row">
        <span className="eyebrow">{filter ? `Open times for ${filter}` : 'Open times for suggested visits'}</span>
        <div className="slot-chips">
          {shown.map((s) => (
            <button
              key={s.id}
              className={`slot-chip ${picked?.id === s.id ? 'on' : ''}`}
              onClick={() => setPicked(picked?.id === s.id ? null : s)}
              title={`${s.specialty} with ${s.provider}`}
            >
              {filter ? s.provider : s.specialty} · {fmtShort(s.datetime)}
            </button>
          ))}
          {shown.length === 0 && (
            <button
              className="slot-chip violet"
              onClick={() => onAsk(filter ? `Help me find a ${filter} appointment.` : 'Help me find times for my suggested visits.')}
            >
              No open times yet. Ask Em to find one
            </button>
          )}
          <button className="slot-chip violet" onClick={() => onAsk('Help me book a visit.')}>
            <Icon name="plus" size={14} /> Schedule Custom Visit
          </button>
        </div>
      </div>

      {picked && (
        <div className="book-confirm">
          <span>Book {picked.specialty}{picked.description ? ` (${picked.description})` : ''} with {picked.provider}, {fmtDay(picked.datetime)} at {fmtTime(picked.datetime)}?</span>
          <button className="btn-pill primary" onClick={book} disabled={busy}>{busy ? 'Booking...' : 'Confirm'}</button>
          <button className="btn-pill" onClick={() => setPicked(null)}>Cancel</button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  )
}

// ---------- Physician orders ----------

/** Pick a past visit (or one with a scribe note) and see its summary and the doctor's instructions. */
function PhysicianOrders({ notes, appointments, onBook }: { notes: ScribeNote[]; appointments: Appointment[]; onBook: () => void }) {
  const [picked, setPicked] = useState<string | null>(null)
  // notes arrive newest first, so find() gets the latest recording per visit
  const visits = appointments
    .filter((a) => a.status === 'completed' || notes.some((n) => n.appointment_id === a.id))
    .map((appt) => ({ appt, note: notes.find((n) => n.appointment_id === appt.id) }))
    .sort((x, y) => y.appt.datetime.localeCompare(x.appt.datetime))
  const visit =
    visits.find((v) => v.appt.id === picked) ?? visits.find((v) => v.appt.id === notes[0]?.appointment_id) ?? visits[0]

  const appt = visit?.appt
  const note = visit?.note
  const summary = note?.summary ?? appt?.visit_summary?.summary
  const orders = note ? note.doctor_instructions : appt?.doctor_notes?.plan ?? appt?.visit_summary?.action_items ?? []
  const followUps = note ? note.follow_ups : appt?.visit_summary?.follow_up ? [appt.visit_summary.follow_up] : []

  return (
    <section className="card glass hub-card">
      <header className="hub-head">
        <span className="hub-icon amber"><Icon name="clipboard" size={20} /></span>
        <div>
          <span className="eyebrow">Clinical care directives</span>
          <h2>Physician Orders</h2>
        </div>
      </header>
      {appt ? (
        <>
          <label className="field">
            <span className="eyebrow">Which visit?</span>
            <select value={appt.id} onChange={(e) => setPicked(e.target.value)}>
              {visits.map((v) => (
                <option key={v.appt.id} value={v.appt.id}>{v.appt.specialty} with {v.appt.provider} · {fmtDate(v.appt.datetime)}</option>
              ))}
            </select>
          </label>
          {summary && (
            <div className="visit-summary">
              <span className="eyebrow">Visit summary{note ? ' · from Em scribe' : ''}</span>
              <p>{summary}</p>
            </div>
          )}
          <Recommendations key={appt.id} items={orders} />
          <span className="eyebrow">Follow-ups</span>
          {followUps.length ? (
            <ul className="orders">{followUps.map((item) => <li key={item}><Icon name="calendar" /> {item}</li>)}</ul>
          ) : (
            <div className="no-follow">
              <span className="muted small">No follow-up available.</span>
              <button className="btn-pill" onClick={onBook}><Icon name="bolt" /> Book next session</button>
            </div>
          )}
          <p className="disclaimer">These are your doctor's words as recorded. Review anything about medication or treatment with {appt.provider} before acting on it.</p>
        </>
      ) : (
        <p className="empty">Your doctor's instructions show up here after a visit. Start the Ambient Scribe during your appointment and Em will pull them out for you.</p>
      )}
    </section>
  )
}

const PREVIEW = 2

/** The doctor's plan lines as a collapsible list that previews the first two. */
function Recommendations({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false)
  const extra = items.length - PREVIEW
  const shown = open ? items : items.slice(0, PREVIEW)

  return (
    <div className="recs">
      <button className="recs-head" onClick={() => setOpen(!open)} aria-expanded={open} disabled={extra <= 0}>
        <span className="eyebrow">Your doctor's recommendations ({items.length})</span>
        {extra > 0 && <span className="recs-toggle">{open ? 'Show less' : `Show ${extra} more`} <span className={`chev ${open ? 'up' : ''}`} aria-hidden>▾</span></span>}
      </button>
      {items.length ? (
        <ul className="orders">{shown.map((item) => <li key={item}><Icon name="check" /> {item}</li>)}</ul>
      ) : (
        <p className="muted small">No recommendations were recorded for this visit.</p>
      )}
    </div>
  )
}

// ---------- Ambient scribe ----------

type ScribeState = 'idle' | 'recording' | 'paused' | 'saving'

/** Records a visit in the browser, sends it to the backend for Gemini notes, and lists saved notes. */
function AmbientScribe({ appointments, notes, onSaved }: { appointments: Appointment[]; notes: ScribeNote[]; onSaved: (n: ScribeNote) => void }) {
  const [apptId, setApptId] = useState(appointments[0]?.id ?? '')
  const [consent, setConsent] = useState(false)
  const [state, setState] = useState<ScribeState>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [levels, setLevels] = useState<number[]>(() => Array(BARS).fill(0.15))
  const [error, setError] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const rec = useRef<{ recorder: MediaRecorder; stream: MediaStream; ctx: AudioContext; raf: number; timer: number } | null>(null)
  const elapsedRef = useRef(0)

  /** Stop the mic, meter, and timer. */
  const teardown = useCallback(() => {
    const r = rec.current
    if (!r) return
    cancelAnimationFrame(r.raf)
    clearInterval(r.timer)
    r.stream.getTracks().forEach((t) => t.stop())
    void r.ctx.close()
    rec.current = null
  }, [])

  // Leaving the page mid-visit discards the recording instead of uploading it
  useEffect(() => () => {
    const r = rec.current
    if (r) {
      r.recorder.onstop = null
      if (r.recorder.state !== 'inactive') r.recorder.stop()
    }
    teardown()
  }, [teardown])

  useEffect(() => {
    if (!appointments.some((a) => a.id === apptId)) setApptId(appointments[0]?.id ?? '')
  }, [appointments, apptId])

  const stop = useCallback(() => rec.current?.recorder.stop(), [])

  const start = async () => {
    setError(null)
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setError('Em needs microphone access to take notes. Allow it in your browser and try again.')
      return
    }
    const mimeType = pickMime()
    const recorder = new MediaRecorder(stream, { ...(mimeType && { mimeType }), audioBitsPerSecond: 32000 })
    const chunks: Blob[] = []
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data)
    recorder.onstop = () => {
      const duration = elapsedRef.current
      teardown()
      setLevels(Array(BARS).fill(0.15))
      if (!chunks.length) return setState('idle')
      setState('saving')
      scribeVisit(apptId, new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }), duration)
        .then((note) => {
          onSaved(note)
          setOpenId(note.id)
        })
        .catch(() => setError('Em could not process that recording. Please try again.'))
        .finally(() => setState('idle'))
    }

    const ctx = new AudioContext()
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 64
    ctx.createMediaStreamSource(stream).connect(analyser)
    const bins = new Uint8Array(analyser.frequencyBinCount)
    const draw = () => {
      analyser.getByteFrequencyData(bins)
      setLevels(Array.from({ length: BARS }, (_, i) => Math.max(0.12, bins[i + 1] / 255)))
      if (rec.current) rec.current.raf = requestAnimationFrame(draw)
    }

    elapsedRef.current = 0
    setElapsed(0)
    const timer = window.setInterval(() => {
      if (recorder.state !== 'recording') return
      elapsedRef.current += 1
      setElapsed(elapsedRef.current)
      if (elapsedRef.current >= MAX_RECORD_SEC) recorder.stop()
    }, 1000)
    rec.current = { recorder, stream, ctx, raf: requestAnimationFrame(draw), timer }
    recorder.start(1000)
    setState('recording')
  }

  const togglePause = () => {
    const r = rec.current?.recorder
    if (!r) return
    if (r.state === 'recording') {
      r.pause()
      setState('paused')
    } else {
      r.resume()
      setState('recording')
    }
  }

  const live = state === 'recording' || state === 'paused'
  const appt = appointments.find((a) => a.id === apptId)

  return (
    <section className="card glass hub-card">
      <header className="hub-head">
        <span className="hub-icon violet"><Icon name="ear" size={20} /></span>
        <div>
          <span className="eyebrow">Visit notetaker</span>
          <h2>Ambient Scribe</h2>
        </div>
        {live && <span className="badge violet"><span className="dot violet" /> {state === 'paused' ? 'Paused' : 'Listening'}</span>}
      </header>

      <div className={`scribe-stage ${state}`}>
        <div className="bars" aria-hidden>
          {levels.map((l, i) => <span key={i} className={`bar b${i % 3}`} style={{ height: `${Math.round(l * 100)}%` }} />)}
        </div>
        <div className="scribe-status">
          <span>
            {state === 'saving' ? 'Em is writing your notes...' : live ? (state === 'paused' ? 'Paused' : 'Listening') : 'Ready when you are'}
          </span>
          <span>{live || state === 'saving' ? fmtClock(elapsed) : ''}</span>
        </div>
      </div>

      {!live && state !== 'saving' && (
        <div className="scribe-setup">
          {appointments.length > 0 ? (
            <>
              <label className="field">
                <span className="eyebrow">Which visit?</span>
                <select value={apptId} onChange={(e) => setApptId(e.target.value)}>
                  {appointments.map((a) => (
                    <option key={a.id} value={a.id}>{a.specialty} with {a.provider} · {fmtShort(a.datetime)}</option>
                  ))}
                </select>
              </label>
              <label className="setting">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                <span>{appt ? appt.provider : 'My provider'} agreed to have this visit recorded.</span>
              </label>
              <button className="btn-dark" onClick={start} disabled={!consent || !apptId}>
                Start Scribe <span className="btn-dark-icon"><Icon name="mic" size={14} /></span>
              </button>
            </>
          ) : (
            <p className="muted small">Book a visit to use the scribe.</p>
          )}
        </div>
      )}
      {live && (
        <div className="scribe-controls">
          <button className="btn-pill" onClick={togglePause}>{state === 'paused' ? 'Resume' : 'Pause'}</button>
          <button className="btn-dark" onClick={stop}>
            Stop and save <span className="btn-dark-icon"><Icon name="stop" size={12} /></span>
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}

      <div className="notes">
        <span className="eyebrow">Saved visit notes</span>
        {notes.length === 0 && <p className="muted small">Notes from your visits are saved here so you can come back to them.</p>}
        {notes.map((n) => (
          <details key={n.id} className="scribe-note" open={openId === n.id} onToggle={(e) => e.currentTarget.open && setOpenId(n.id)}>
            <summary>
              <strong>{n.specialty} with {n.provider}</strong>
              <span className="muted small">
                {new Date(n.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                {n.duration_sec != null && ` · ${fmtClock(n.duration_sec)}`}
              </span>
            </summary>
            <p>{n.summary}</p>
            {n.key_points.length > 0 && <NoteList title="Key points" items={n.key_points} />}
            {n.doctor_instructions.length > 0 && <NoteList title="What your doctor said to do" items={n.doctor_instructions} />}
            {n.follow_ups.length > 0 && <NoteList title="Follow-ups" items={n.follow_ups} />}
            <details className="transcript-toggle">
              <summary>Transcript</summary>
              <pre>{n.transcript}</pre>
            </details>
            <p className="disclaimer">{n.disclaimer}</p>
          </details>
        ))}
      </div>
    </section>
  )
}

/** A titled bullet list inside a scribe note. */
function NoteList({ title, items }: { title: string; items: string[] }) {
  return (
    <>
      <span className="eyebrow">{title}</span>
      <ul>{items.map((i) => <li key={i}>{i}</li>)}</ul>
    </>
  )
}

// ---------- Page ----------

/** em.doc hub: appointments, booking, physician orders, and the ambient scribe. */
export default function CareHub({ onAsk }: { onAsk: (prompt?: string) => void }) {
  const { persona } = usePersona()
  const [data, setData] = useState<{ persona: string; appts: AppointmentList; slots: Slot[]; notes: ScribeNote[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'upcoming' | 'past'>('upcoming')

  /** Load appointments, open slots, and saved notes for the current persona. */
  const load = useCallback(() => {
    let cancelled = false
    Promise.all([getAppointments(), getSlots(), getScribeNotes()])
      .then(([appts, slots, notes]) => {
        if (cancelled) return
        setData({ persona, appts, slots, notes })
        setError(null)
      })
      .catch((err: unknown) => !cancelled && setError(String(err)))
    return () => {
      cancelled = true
    }
  }, [persona])

  useEffect(() => load(), [load])

  if (error) return <p className="error page-msg">Could not load em.doc. {error}</p>
  if (data?.persona !== persona) return <p className="muted page-msg">Loading...</p>
  const { appts, slots, notes } = data
  const upcoming = [...appts.upcoming].sort((a, b) => a.datetime.localeCompare(b.datetime))
  const past = [...appts.past].sort((a, b) => b.datetime.localeCompare(a.datetime))
  const shown = tab === 'upcoming' ? upcoming : past

  /** Switch to the Upcoming tab and scroll to Book Next Session. */
  const goToBooking = () => {
    setTab('upcoming')
    requestAnimationFrame(() => document.getElementById('book-next')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }
  const replaceAppt = (next: Appointment) =>
    setData((d) => d && {
      ...d,
      appts: { ...d.appts, upcoming: d.appts.upcoming.map((a) => (a.id === next.id ? next : a)) },
    })

  return (
    <div className="hub">
      <span className="pill live-pill"><span className="dot coral" /> Visits, prep and scribe</span>
      <h1 className="hub-title">em.doc</h1>
      <p className="hub-sub">Your visits, what to ask, and what your doctor said, all in one place.</p>

      <section className="card glass hub-card">
        <header className="hub-head">
          <span className="hub-icon violet"><Icon name="calendar" size={20} /></span>
          <div>
            <span className="eyebrow">Appointments and care visits</span>
            <h2>Appointments & Clinical Visits</h2>
          </div>
          <div className="seg" role="tablist">
            <button role="tab" aria-selected={tab === 'upcoming'} className={tab === 'upcoming' ? 'on' : ''} onClick={() => setTab('upcoming')}>
              Upcoming ({upcoming.length})
            </button>
            <button role="tab" aria-selected={tab === 'past'} className={tab === 'past' ? 'on' : ''} onClick={() => setTab('past')}>
              Past History
            </button>
          </div>
        </header>
        {shown.length ? (
          <ul className="appt-list">
            {shown.map((a, i) => <AppointmentItem key={a.id} a={a} featured={tab === 'upcoming' && i === 0} onPrepped={replaceAppt} />)}
          </ul>
        ) : (
          <p className="empty">{tab === 'upcoming' ? 'No upcoming visits. Book one below.' : 'No past visits yet.'}</p>
        )}
        {tab === 'upcoming' && (
          <BookNext
            slots={slots}
            booked={upcoming.map((a) => a.specialty)}
            suggested={appts.suggested}
            onBooked={load}
            onSuggested={(suggested) => setData((d) => d && { ...d, appts: { ...d.appts, suggested } })}
            onAsk={onAsk}
          />
        )}
      </section>

      <div className="hub-grid">
        <PhysicianOrders notes={notes} appointments={[...upcoming, ...past]} onBook={goToBooking} />
        <AmbientScribe
          appointments={[...upcoming, ...past]}
          notes={notes}
          onSaved={(n) => setData((d) => d && { ...d, notes: [n, ...d.notes] })}
        />
      </div>
    </div>
  )
}
