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
