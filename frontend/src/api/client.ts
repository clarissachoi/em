// Typed client for the EmCare FastAPI backend. Mirrors backend/models.py and API.md.
// Dates and datetimes arrive as ISO strings. Add new types and endpoint functions below.

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api'

// ---------- Transport ----------

let currentUserId = 'maya'

/** Set the persona sent as X-User-Id on every request. */
export function setUserId(id: string) {
  currentUserId = id
}

/** Fetch JSON from the backend with the persona header. Throws on non-2xx. */
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('X-User-Id', currentUserId)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (!res.ok) throw new Error(`${init.method ?? 'GET'} ${path} failed: ${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

// ---------- Health ----------

export interface HealthStatus { ok: boolean }

export const getHealth = () => request<HealthStatus>('/health')

// ---------- Users ----------

export interface UserSummary { id: string; name: string; age: number; tagline: string }
export interface Pregnancy { week: number; due_date: string; pregnancy_number: number }
export interface Connection {
  source: string
  kind: 'wearable' | 'fitness' | 'cycle' | 'pregnancy' | 'calendar' | 'records'
  connected: boolean
}
export interface UserProfile {
  id: string
  name: string
  age: number
  life_stage: 'general' | 'pregnant' | 'postpartum'
  pregnancy: Pregnancy | null
  primary_goal: string
  connections: Connection[]
}

export const getUsers = () => request<UserSummary[]>('/users')
export const getMe = () => request<UserProfile>('/me')

// ---------- Next steps ----------

export interface Goals {
  primary_goal: string
  focus_areas: string[]
  target_date: string | null
  dietary_prefs: string[]
  activity_level: 'low' | 'medium' | 'high'
  notes: string | null
}
export interface PlanDay {
  date: string
  activity: string
  duration_min: number
  intensity: 'rest' | 'easy' | 'moderate' | 'hard'
  adjusted: boolean
  adjustment_reason: string | null
}

export const getGoals = () => request<Goals>('/goals')
export const putGoals = (goals: Goals) => request<Goals>('/goals', { method: 'PUT', body: JSON.stringify(goals) })
export const getPlan = () => request<PlanDay[]>('/plan')

// ---------- Voice ----------

export interface CheckinResult {
  id: string
  created_at: string
  transcript: string
  mood: number
  energy: number
  stress: number
  sleep_quality: number | null
  symptoms: string[]
  cycle_phase: string | null
  em_reply: string
  insight: string | null
  urgent: boolean
  escalation_message: string | null
}
export interface VoiceSettings { voice_alerts: boolean }
export type VoiceEvent =
  | { type: 'ready'; model: string }
  | { type: 'transcript'; role: 'user' | 'em'; text: string }
  | { type: 'turn_complete' }
  | { type: 'interrupted' }
  | { type: 'tool'; name: string; summary: string; changed: boolean }
  | { type: 'checkin'; checkin: CheckinResult }
  | { type: 'urgent'; message: string; speak: boolean }
  | { type: 'error'; message: string }

export const getVoiceSettings = () => request<VoiceSettings>('/voice/settings')
export const putVoiceSettings = (settings: VoiceSettings) =>
  request<VoiceSettings>('/voice/settings', { method: 'PUT', body: JSON.stringify(settings) })
/** WebSocket URL for live voice. Persona goes in the query since sockets cannot send headers. */
export const voiceSocketUrl = () => `${BASE.replace(/^http/, 'ws')}/voice?user_id=${encodeURIComponent(currentUserId)}`
export const urgentAudioUrl = `${BASE}/voice/urgent-audio`

// ---------- Labs ----------

export interface LabResult {
  marker: string
  value: number
  unit: string
  ref_low: number | null
  ref_high: number | null
  flag: 'low' | 'normal' | 'high'
}
export interface LabPanel { id: string; date: string; source: string; results: LabResult[] }
export interface LabsResponse { panels: LabPanel[]; upcoming: string[] }
export interface LabFlag { marker: string; meaning: string; why_it_matters_for_you: string }
export interface LabExplanation {
  plain_summary: string
  flags: LabFlag[]
  plan_changes: string[]
  follow_up: string | null
  disclaimer: string
}

export const getLabs = () => request<LabsResponse>('/labs')
/** Calls Gemini on the backend; takes a few seconds the first time per panel. */
export const explainLabs = (panel_id: string) =>
  request<LabExplanation>('/labs/explain', { method: 'POST', body: JSON.stringify({ panel_id }) })

// ---------- Home ----------

export interface Alert {
  type: 'appointment' | 'medication' | 'travel' | 'records' | 'lab'
  title: string
  detail: string
  severity: 'info' | 'warning'
}
export interface Readiness {
  score: number
  label: string
  sleep_hours: number
  hrv_ms: number | null
  resting_hr: number | null
  summary: string
}
export interface CareItem { role: string; provider: string | null; done: boolean }
export interface CareChecklist { found: number; total: number; items: CareItem[] }
export interface FocusItem {
  kind: 'workout' | 'nutrition' | 'appointment' | 'records' | 'lab' | 'checkin'
  title: string
  detail: string
  time: string | null
}
export interface TrendPoint { date: string; readiness: number }
export interface Metric { label: string; value: string; unit: string | null }
export interface CareNote { author: string; text: string; source: 'visit' | 'em' }
export interface HomeData {
  user_name: string
  greeting: string
  alerts: Alert[]
  quote: string
  readiness: Readiness | null
  today_plan: string | null
  nutrition_tip: string | null
  pregnancy_week: number | null
  care_checklist: CareChecklist | null
  recent_checkins: CheckinResult[]
  mood: number | null
  focus: FocusItem[]
  trend: TrendPoint[]
  metrics: Metric[]
  care_note: CareNote | null
  ask_suggestions: string[]
}

export const getHome = () => request<HomeData>('/home')

// ---------- Appointments ----------

export interface DoctorNote {
  author: string
  written_on: string
  reason_for_visit: string
  subjective: string
  objective: string[]
  assessment: string[]
  plan: string[]
}
export interface SuggestedActivity { title: string; detail: string; category: 'training' | 'nutrition' | 'recovery' | 'self_care'; based_on: string }
export interface VisitSummary { summary: string; action_items: string[]; follow_up: string | null; suggested_activities: SuggestedActivity[] }
export interface Appointment {
  id: string
  for_person: string
  provider: string
  specialty: string
  datetime: string
  location: string
  status: 'upcoming' | 'completed'
  prep_questions: string[]
  visit_summary: VisitSummary | null
  doctor_notes: DoctorNote | null
}
export interface SuggestedAppointment { specialty: string; reason: string; urgency: 'soon' | 'routine' }
export interface AppointmentList { upcoming: Appointment[]; past: Appointment[]; suggested: SuggestedAppointment[] }
export interface Slot { id: string; provider: string; specialty: string; datetime: string; description: string | null }
export interface ScribeNote {
  id: string
  appointment_id: string
  provider: string
  specialty: string
  created_at: string
  duration_sec: number | null
  summary: string
  key_points: string[]
  doctor_instructions: string[]
  follow_ups: string[]
  transcript: string
  disclaimer: string
}

export const getAppointments = () => request<AppointmentList>('/appointments')
export const getSlots = (specialty?: string) =>
  request<Slot[]>(`/appointments/slots${specialty ? `?specialty=${encodeURIComponent(specialty)}` : ''}`)
export const bookSlot = (slot_id: string, for_person = 'self') =>
  request<Appointment>('/appointments/book', { method: 'POST', body: JSON.stringify({ slot_id, for_person }) })
/** Calls Gemini on the backend; a few seconds. */
export const prepAppointment = (id: string) => request<Appointment>(`/appointments/${id}/prep`, { method: 'POST' })
/** Uploads a visit recording; Gemini transcribes and saves the note. Can take 10-30s for long visits. */
export function scribeVisit(id: string, audio: Blob, duration_sec: number) {
  const form = new FormData()
  const ext = audio.type.includes('mp4') ? 'mp4' : audio.type.includes('ogg') ? 'ogg' : 'webm'
  form.append('audio', audio, `visit.${ext}`)
  form.append('duration_sec', String(Math.round(duration_sec)))
  return request<ScribeNote>(`/appointments/${id}/scribe`, { method: 'POST', body: form })
}
export const getScribeNotes = () => request<ScribeNote[]>('/scribe-notes')
/** Calls Gemini on the backend for fresh suggestions; a few seconds. 503 keeps the saved ones. */
export const refreshSuggestions = () => request<SuggestedAppointment[]>('/appointments/suggestions', { method: 'POST' })

// ---------- em.well ----------

export interface Suggestion {
  title: string
  description: string
  reason: string
  duration_min: number | null
  tag: string
  when: string | null
  where: string | null
  image: string | null
  distance_mi: number | null
  near_tag: string | null
  /** 'doctor' = her clinician's instruction (e.g. prescribed iron), not Em's idea */
  source: 'em' | 'doctor'
}
export interface Suggestions {
  headline: string
  nutrition: Suggestion[]
  workouts: Suggestion[]
  classes: Suggestion[]
  sleep: Suggestion[]
}
export interface Insight { text: string; evidence: string }

/** Calls Gemini on the backend; about 10 seconds the first time, cached after. */
export const getSuggestions = () => request<Suggestions>('/suggestions')
export const getInsights = () => request<Insight[]>('/insights')
