// Temporary test page for the appointments endpoints. Replace once the mockup lands.
// Types live here (not in api/client.ts) so this page can be deleted without touching shared files.

import { useCallback, useEffect, useState } from 'react'
import { request } from '../api/client'
import { usePersona } from '../hooks/usePersona'

// ---------- Types (mirror API.md) ----------

interface VisitSummary { summary: string; action_items: string[]; follow_up: string | null }
interface Appointment {
  id: string
  for_person: string
  provider: string
  specialty: string
  datetime: string
  location: string
  status: 'upcoming' | 'completed'
  prep_questions: string[]
  visit_summary: VisitSummary | null
}
interface SuggestedAppointment { specialty: string; reason: string; urgency: 'soon' | 'routine' }
interface AppointmentList { upcoming: Appointment[]; past: Appointment[]; suggested: SuggestedAppointment[] }
interface Slot { id: string; provider: string; specialty: string; datetime: string; description: string | null }

// ---------- Calls ----------

const getAppointments = () => request<AppointmentList>('/appointments')
const getSlots = () => request<Slot[]>('/appointments/slots')
const bookSlot = (slot_id: string) =>
  request<Appointment>('/appointments/book', { method: 'POST', body: JSON.stringify({ slot_id }) })
const refreshSuggestions = () => request<SuggestedAppointment[]>('/appointments/suggestions', { method: 'POST' })

// ---------- Helpers ----------

/** Format an ISO datetime for display. */
const fmt = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

/** Local YYYY-MM-DD for a date offset from today. Uses the browser clock (seed as_of matches it for the demo). */
function dayKey(offsetDays = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const sameSpecialty = (a: string, b: string) => a.toLowerCase() === b.toLowerCase()

/** One appointment row. */
function AppointmentRow({ a }: { a: Appointment }) {
  return (
    <li>
      <strong>{a.specialty}</strong> with {a.provider} · {fmt(a.datetime)} · {a.location}
      {a.for_person !== 'self' && <> · for {a.for_person}</>}
      {a.visit_summary && <div className="muted">{a.visit_summary.summary}</div>}
    </li>
  )
}

/** A list of appointments under a heading, or "None". */
function AppointmentSection({ title, items }: { title: string; items: Appointment[] }) {
  return (
    <>
      <h2>{title}</h2>
      {items.length ? <ul>{items.map((a) => <AppointmentRow key={a.id} a={a} />)}</ul> : <p className="muted">None</p>}
    </>
  )
}

/** Debug view: today, this week, suggestions with bookable slots, and past visits for the current persona. */
export default function AppointmentsDebug() {
  const { persona } = usePersona()
  const [list, setList] = useState<AppointmentList | null>(null)
  const [slots, setSlots] = useState<Slot[]>([])
  const [error, setError] = useState<string | null>(null)
  const [booking, setBooking] = useState<string | null>(null)
  const [thinking, setThinking] = useState(false)

  /** Reload appointments and open slots. */
  const loadAll = useCallback(() => {
    setError(null)
    return Promise.all([getAppointments(), getSlots()])
      .then(([a, s]) => {
        setList(a)
        setSlots(s)
      })
      .catch((err: unknown) => setError(String(err)))
  }, [])

  useEffect(() => {
    setList(null)
    loadAll()
  }, [persona, loadAll])

  /** Book a slot, then refresh everything. */
  const onBook = async (id: string) => {
    setBooking(id)
    try {
      await bookSlot(id)
      await loadAll()
    } catch (err) {
      setError(String(err))
    } finally {
      setBooking(null)
    }
  }

  /** Ask Gemini for new suggestions, then refresh. */
  const onRefresh = async () => {
    setThinking(true)
    setError(null)
    try {
      await refreshSuggestions()
      await loadAll()
    } catch (err) {
      setError(String(err))
    } finally {
      setThinking(false)
    }
  }

  /** Book button for one slot. */
  const bookButton = (s: Slot) => (
    <button disabled={booking !== null} onClick={() => onBook(s.id)}>
      {booking === s.id ? 'Booking...' : 'Book'}
    </button>
  )

  if (!list) return error ? <p className="error">{error}</p> : <p className="muted">Loading...</p>

  const today = dayKey()
  const weekEnd = dayKey(7)
  const day = (a: Appointment) => a.datetime.slice(0, 10)
  const todays = list.upcoming.filter((a) => day(a) === today)
  const thisWeek = list.upcoming.filter((a) => day(a) > today && day(a) <= weekEnd)
  const later = list.upcoming.filter((a) => day(a) > weekEnd)

  return (
    <section>
      <h1>Appointments (debug)</h1>
      {error && <p className="error">{error}</p>}

      {todays.length > 0 && <AppointmentSection title="Today" items={todays} />}
      <AppointmentSection title="This week" items={thisWeek} />
      {later.length > 0 && <AppointmentSection title="Later" items={later} />}

      <h2>Suggested</h2>
      <button disabled={thinking} onClick={onRefresh}>
        {thinking ? 'Asking Em...' : 'Refresh with Gemini'}
      </button>
      {list.suggested.length ? (
        <ul>
          {list.suggested.map((sug) => {
            const matching = slots.filter((s) => sameSpecialty(s.specialty, sug.specialty))
            return (
              <li key={sug.specialty}>
                <strong>{sug.specialty}</strong> ({sug.urgency}){sug.reason && <>: {sug.reason}</>}
                {matching.length ? (
                  <ul>
                    {matching.map((s) => (
                      <li key={s.id}>
                        {fmt(s.datetime)} with {s.provider}
                        {s.description && <> · {s.description}</>} {bookButton(s)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="muted">No open slots for this specialty</div>
                )}
              </li>
            )
          })}
        </ul>
      ) : <p className="muted">None</p>}

      <AppointmentSection title="Past" items={list.past} />

      <details>
        <summary>All open slots ({slots.length})</summary>
        <ul>
          {slots.map((s) => (
            <li key={s.id}>
              {fmt(s.datetime)} · <strong>{s.specialty}</strong> with {s.provider}
              {s.description && <> · {s.description}</>} {bookButton(s)}
            </li>
          ))}
        </ul>
      </details>
    </section>
  )
}
