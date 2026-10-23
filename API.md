# EmCare API contract

Base URL: `http://localhost:8000/api`. All responses JSON. No auth.
Every endpoint takes the persona via header `X-User-Id: maya | jasmine` (default `maya`).
Pydantic models live in `backend/models.py`. Field names are snake_case on both sides.
Personas and their seed data: see `PERSONAS.md`.

## Users (shared)

### GET /users
`list[UserSummary]`, UserSummary { id: str, name: str, age: int, tagline: str }

### GET /me
```
UserProfile {
  id: str
  name: str
  age: int
  life_stage: "general" | "pregnant" | "postpartum"
  pregnancy: Pregnancy | null      # Pregnancy { week: int, due_date: date, pregnancy_number: int }
  primary_goal: str                # e.g. "Marathon on 2027-02-14", "Care transition"
  connections: list[Connection]    # Connection { source: str, kind: "wearable" | "fitness" | "cycle" | "pregnancy" | "calendar" | "records", connected: bool }
}
```

## Home (Dev 1)

### POST /checkin
Multipart: `audio` (file, optional, audio/webm) and/or `text` (string, optional). At least one required.
```
CheckinResult {
  id: str
  created_at: datetime
  transcript: str
  mood: int            # 1-5
  energy: int          # 1-5
  stress: int          # 1-5
  sleep_quality: int | null   # 1-5
  symptoms: list[str]  # e.g. "soreness", "swelling", "nausea"
  cycle_phase: str | null
  em_reply: str        # Em's warm, short response
  insight: str | null  # pattern Em noticed, e.g. "Energy dips on heavy work weeks"
  urgent: bool
  escalation_message: str | null   # fixed text from prompts.URGENT_ESCALATION when urgent
}
```

### GET /home
```
HomeData {
  user_name: str
  greeting: str
  alerts: list[Alert]          # Alert { type: "appointment" | "medication" | "travel" | "records" | "lab", title: str, detail: str, severity: "info" | "warning" }
  quote: str
  readiness: Readiness | null  # Readiness { score: int (0-100), sleep_hours: float, hrv_ms: int | null, resting_hr: int | null, summary: str }
  today_plan: str | null       # "Easy 5 mi run" / "30 min walk"
  nutrition_tip: str | null
  pregnancy_week: int | null
  care_checklist: CareChecklist | null   # CareChecklist { found: int, total: int, items: list[CareItem] }, CareItem { role: str, provider: str | null, done: bool }
  recent_checkins: list[CheckinResult]   # last 7
}
```

## Appointments, labs, records (Dev 2)

### GET /appointments
```
AppointmentList { upcoming: list[Appointment], past: list[Appointment], suggested: list[SuggestedAppointment] }
Appointment {
  id: str
  for_person: str              # "self" or a family member, e.g. "toddler"
  provider: str
  specialty: str
  datetime: datetime
  location: str
  status: "upcoming" | "completed"
  prep_questions: list[str]
  visit_summary: VisitSummary | null
}
VisitSummary { summary: str, action_items: list[str], follow_up: str | null }
SuggestedAppointment { specialty: str, reason: str, urgency: "soon" | "routine" }
```

### GET /providers?specialty=...
`list[Provider]`, Provider { id: str, name: str, specialty: str, distance_mi: float, in_network: bool, rating: float }

### GET /appointments/slots?specialty=...
`list[Slot]`, Slot { id: str, provider: str, specialty: str, datetime: datetime }. Prefer slots that fit the user's free calendar windows.

### POST /appointments/book
Body `{ slot_id: str, for_person: str = "self" }` returns `Appointment`.

### POST /appointments/{id}/prep
"Come with me" before the visit. Questions from recent check-ins, labs, and missing records. Returns `Appointment`.

### POST /appointments/{id}/note
Post-appointment quick note. Multipart `audio` (optional) and/or `text`. Returns `Appointment` with `visit_summary` filled and any follow-ups added as alerts.

### GET /labs
```
LabPanel { id: str, date: date, source: str, results: list[LabResult] }
LabResult { marker: str, value: float, unit: str, ref_low: float | null, ref_high: float | null, flag: "low" | "normal" | "high" }
Response: { panels: list[LabPanel], upcoming: list[str] }
```

### POST /labs/explain
Body `{ panel_id: str }`.
```
LabExplanation {
  plain_summary: str
  flags: list[LabFlag]          # LabFlag { marker: str, meaning: str, why_it_matters_for_you: str }
  plan_changes: list[str]       # e.g. "Add iron-rich meals", "Soften next 2 weeks of training"
  follow_up: str | null         # e.g. "Recheck ferritin in 8 weeks"
  disclaimer: str               # always "Review with your doctor" style text
}
```

### GET /records
```
RecordRequest { id: str, item: str, from_provider: str, status: "not_requested" | "requested" | "received", requested_on: date | null, needed_by: date | null, overdue: bool }
Response: list[RecordRequest]
```

### PATCH /records/{id}
Body `{ status: str }` returns `RecordRequest`.

### POST /policy/review
Multipart: `file` (PDF, optional, uses seeded sample policy if absent), `question` (str).
```
PolicyAnswer { answer: str, covered: "yes" | "no" | "unclear", relevant_clause: str | null }
```

## Next steps (Dev 3)

### GET /goals  /  PUT /goals
Also used by onboarding.
```
Goals {
  primary_goal: str
  focus_areas: list[str]     # e.g. ["marathon", "energy"] or ["care transition", "sleep", "walking"]
  target_date: date | null   # race date or due date
  dietary_prefs: list[str]
  activity_level: "low" | "medium" | "high"
  notes: str | null
}
```

### GET /plan
Adaptive training/activity plan for the next 7 days.
```
PlanDay { date: date, activity: str, duration_min: int, intensity: "rest" | "easy" | "moderate" | "hard", adjusted: bool, adjustment_reason: str | null }
Response: list[PlanDay]
```

### POST /plan/adapt
Re-plans using latest sleep, travel, cycle/pregnancy week, labs, check-ins. Returns `list[PlanDay]` with `adjusted` / `adjustment_reason` set.

### GET /suggestions
```
Suggestions {
  nutrition: list[Suggestion]
  workouts: list[Suggestion]
  classes: list[Suggestion]
  sleep: list[Suggestion]      # mainly for Jasmine
}
Suggestion { title: str, description: str, reason: str, duration_min: int | null }
```

### GET /insights
Cross-data patterns. `list[Insight]`, Insight { text: str, evidence: str }
e.g. "You sleep better on days you walk 30+ minutes" / "Energy dips on heavy travel weeks".

## Health

### GET /health
`{ ok: true }`

### GET /health/gemini
One tiny Gemini call. `{ ok: bool, model: str, latency_ms: int }`
