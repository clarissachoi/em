// Typed client for the EmCare FastAPI backend. Mirrors backend/models.py and API.md.
// Dates and datetimes arrive as ISO strings.

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api'

// ---------- Users ----------

export type UserId = 'maya' | 'jasmine'

export interface UserSummary { id: UserId; name: string; age: number; tagline: string }
export interface Pregnancy { week: number; due_date: string; pregnancy_number: number }
export interface Connection {
  source: string
  kind: 'wearable' | 'fitness' | 'cycle' | 'pregnancy' | 'calendar' | 'records'
  connected: boolean
}
export interface UserProfile {
  id: UserId
  name: string
  age: number
  life_stage: 'general' | 'pregnant' | 'postpartum'
  pregnancy: Pregnancy | null
  primary_goal: string
  connections: Connection[]
}

// ---------- Home ----------

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
export interface Alert {
  type: 'appointment' | 'medication' | 'travel' | 'records' | 'lab'
  title: string
  detail: string
  severity: 'info' | 'warning'
}
export interface Readiness { score: number; sleep_hours: number; hrv_ms: number | null; resting_hr: number | null; summary: string }
export interface CareItem { role: string; provider: string | null; done: boolean }
export interface CareChecklist { found: number; total: number; items: CareItem[] }
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
}

// ---------- Appointments ----------

export interface VisitSummary { summary: string; action_items: string[]; follow_up: string | null }
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
}
export interface SuggestedAppointment { specialty: string; reason: string; urgency: 'soon' | 'routine' }
export interface AppointmentList { upcoming: Appointment[]; past: Appointment[]; suggested: SuggestedAppointment[] }
export interface Provider { id: string; name: string; specialty: string; distance_mi: number; in_network: boolean; rating: number }
export interface Slot { id: string; provider: string; specialty: string; datetime: string }

// ---------- Labs, records, policy ----------

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
export type RecordStatus = 'not_requested' | 'requested' | 'received'
export interface RecordRequest {
  id: string
  item: string
  from_provider: string
  status: RecordStatus
  requested_on: string | null
  needed_by: string | null
  overdue: boolean
}
export interface PolicyAnswer { answer: string; covered: 'yes' | 'no' | 'unclear'; relevant_clause: string | null }

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
export interface Suggestion { title: string; description: string; reason: string; duration_min: number | null }
export interface Suggestions { nutrition: Suggestion[]; workouts: Suggestion[]; classes: Suggestion[]; sleep: Suggestion[] }
export interface Insight { text: string; evidence: string }

// ---------- Health ----------

export interface HealthStatus { ok: boolean }
export interface HealthGemini { ok: boolean; model: string; latency_ms: number }

// ---------- Transport ----------

let currentUserId: UserId = 'maya'

/** Set the persona sent as X-User-Id on every request. */
export function setUserId(id: UserId) {
  currentUserId = id
}

/** Fetch JSON from the backend with the persona header. Throws on non-2xx. */
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('X-User-Id', currentUserId)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (!res.ok) throw new Error(`${init.method ?? 'GET'} ${path} failed: ${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

/** Build a multipart body, skipping empty values. */
function form(fields: Record<string, string | Blob | undefined>): FormData {
  const fd = new FormData()
  for (const [key, value] of Object.entries(fields)) if (value !== undefined) fd.append(key, value)
  return fd
}

const query = (specialty?: string) => (specialty ? `?specialty=${encodeURIComponent(specialty)}` : '')

// ---------- Endpoints ----------

export const getUsers = () => request<UserSummary[]>('/users')
export const getMe = () => request<UserProfile>('/me')

export const postCheckin = (input: { audio?: Blob; text?: string }) =>
  request<CheckinResult>('/checkin', { method: 'POST', body: form(input) })
export const getHome = () => request<HomeData>('/home')

export const getAppointments = () => request<AppointmentList>('/appointments')
export const getProviders = (specialty?: string) => request<Provider[]>(`/providers${query(specialty)}`)
export const getSlots = (specialty?: string) => request<Slot[]>(`/appointments/slots${query(specialty)}`)
export const bookAppointment = (slot_id: string, for_person = 'self') =>
  request<Appointment>('/appointments/book', { method: 'POST', body: JSON.stringify({ slot_id, for_person }) })
export const prepAppointment = (id: string) =>
  request<Appointment>(`/appointments/${encodeURIComponent(id)}/prep`, { method: 'POST' })
export const addVisitNote = (id: string, input: { audio?: Blob; text?: string }) =>
  request<Appointment>(`/appointments/${encodeURIComponent(id)}/note`, { method: 'POST', body: form(input) })

export const getLabs = () => request<LabsResponse>('/labs')
export const explainLabs = (panel_id: string) =>
  request<LabExplanation>('/labs/explain', { method: 'POST', body: JSON.stringify({ panel_id }) })

export const getRecords = () => request<RecordRequest[]>('/records')
export const updateRecord = (id: string, status: RecordStatus) =>
  request<RecordRequest>(`/records/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ status }) })

export const reviewPolicy = (question: string, file?: Blob) =>
  request<PolicyAnswer>('/policy/review', { method: 'POST', body: form({ question, file }) })

export const getGoals = () => request<Goals>('/goals')
export const putGoals = (goals: Goals) => request<Goals>('/goals', { method: 'PUT', body: JSON.stringify(goals) })
export const getPlan = () => request<PlanDay[]>('/plan')
export const adaptPlan = () => request<PlanDay[]>('/plan/adapt', { method: 'POST' })
export const getSuggestions = () => request<Suggestions>('/suggestions')
export const getInsights = () => request<Insight[]>('/insights')

export const getHealth = () => request<HealthStatus>('/health')
export const getHealthGemini = () => request<HealthGemini>('/health/gemini')
