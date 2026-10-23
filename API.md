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
  readiness: Readiness | null  # Readiness { score: int (0-100), label: str, sleep_hours: float, hrv_ms: int | null, resting_hr: int | null, summary: str }
  today_plan: str | null       # "Easy 5 mi run" / "30 min walk"
  nutrition_tip: str | null
  pregnancy_week: int | null
  care_checklist: CareChecklist | null   # CareChecklist { found: int, total: int, items: list[CareItem] }, CareItem { role: str, provider: str | null, done: bool }
  recent_checkins: list[CheckinResult]   # last 7
  mood: int | null             # 1-5, from the latest check-in
  focus: list[FocusItem]       # "Today's Focus"
  trend: list[TrendPoint]      # last 7 days of readiness, oldest first
  metrics: list[Metric]        # 3 tiles under the trend chart
  care_note: CareNote | null   # a line from her doctor's plan in the last 120 days, else that visit's summary, else Em's note on a flagged lab
  ask_suggestions: list[str]   # short questions for the "Ask Em" chips
}
FocusItem { kind: "workout" | "nutrition" | "appointment" | "records" | "lab" | "checkin", title: str, detail: str, time: str | null }
TrendPoint { date: date, readiness: int }
Metric { label: str, value: str, unit: str | null }
CareNote { author: str, text: str, source: "visit" | "em" }
```
Computed from seed data, no Gemini. Readiness blends last night's sleep score with HRV and resting HR against the persona's own 14-day baseline.

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
  doctor_notes: DoctorNote | null  # completed visits only, from seed (mocked records)
}
VisitSummary {
  summary: str                         # plain-language, factual recap of the doctor's notes. Generated once by Gemini, stored in seed
  action_items: list[str]              # set in seed from the doctor's plan, never model-written
  follow_up: str | null                # set in seed from the doctor's plan, never model-written
  suggested_activities: list[SuggestedActivity]  # Em's ideas, generated live by POST /appointments/{id}/activities. Default []
}
DoctorNote { author: str, written_on: date, reason_for_visit: str, subjective: str, objective: list[str], assessment: list[str], plan: list[str] }
SuggestedActivity { title: str, detail: str, category: "training" | "nutrition" | "recovery" | "self_care", based_on: str }  # based_on: the doctor's plan line it follows
SuggestedAppointment { specialty: str, reason: str, urgency: "soon" | "routine" }  # reason: 1-2 sentences on how this care helps her goals, shown on hover in em.doc
```

### GET /providers?specialty=...
`list[Provider]`, Provider { id: str, name: str, specialty: str, distance_mi: float, in_network: bool, rating: float }

### GET /appointments/slots?specialty=...
`list[Slot]`, Slot { id: str, provider: str, specialty: str, datetime: datetime, description: str | null } (description is the visit type, e.g. "Glucose screening", null for a general visit). Prefer slots that fit the user's free calendar windows.

### POST /appointments/book
Body `{ slot_id: str, for_person: str = "self" }` returns `Appointment`. Removes the slot, drops suggestions for that specialty, and ticks the care checklist. 404 if the slot id is unknown.

### POST /appointments/suggestions
Asks Gemini for fresh suggestions from the profile, care team, appointments, providers, open slots, and records. Never suggests a specialty that already has an upcoming appointment. Saves and returns `list[SuggestedAppointment]`; `GET /appointments` returns the saved list after that. 503 if Gemini fails (saved suggestions are kept).

### POST /appointments/{id}/prep
"Come with me" before the visit. Gemini writes up to 5 short questions to ask, from recent check-ins, flagged labs, goals, and missing records. Never diagnoses or suggests medication changes. Saves to `prep_questions` and returns `Appointment`. 404 unknown id, 503 if Gemini fails.

### POST /appointments/{id}/note
Post-appointment quick note. Multipart `audio` (optional) and/or `text`. Returns `Appointment` with `visit_summary` filled and any follow-ups added as alerts.

### POST /appointments/{id}/activities
"Appointment buddy" after a completed visit. Gemini suggests up to 4 activities that follow the doctor's plan and fit her recent check-ins (mood, energy, stress, sleep, symptoms). Never diagnoses, never suggests medication or supplement changes, pregnancy-safe for pregnant users. Empty list if her latest check-in was urgent. Saves to `visit_summary.suggested_activities` and returns `Appointment`. 404 unknown id, 409 if the visit has no doctor notes, 503 if Gemini fails.

### POST /appointments/{id}/scribe
Ambient scribe. Multipart `audio` (the recording of the visit, webm/ogg/mp4/wav, max 19 MB) and optional `duration_sec` (int). Gemini transcribes and writes the note. Only records what was said at the visit; adds no advice of its own. Saves to the `scribe_notes` section and returns `ScribeNote`. 404 unknown id, 413 audio too large, 503 if Gemini fails.
```
ScribeNote {
  id: str
  appointment_id: str
  provider: str
  specialty: str
  created_at: datetime
  duration_sec: int | null
  summary: str                    # plain-language recap of the visit
  key_points: list[str]           # findings and topics discussed
  doctor_instructions: list[str]  # what the clinician said to do, close to their words
  follow_ups: list[str]           # tests, referrals, next visits mentioned
  transcript: str                 # speaker-labeled ("Doctor:", "Patient:")
  disclaimer: str                 # fixed "review with your doctor" text, never model-written
}
```

### GET /scribe-notes
`list[ScribeNote]`, newest first.

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
Powers the em.well page. Gemini, personalized from goals, labs, recent check-ins, plan, calendar, and pregnancy. Cached per persona until her data changes.
```
Suggestions {
  headline: str                # focus line from her data, e.g. "Low ferritin · Marathon in 16 weeks" (not model-written)
  nutrition: list[Suggestion]  # food only, never supplements
  workouts: list[Suggestion]
  classes: list[Suggestion]
  sleep: list[Suggestion]      # not shown on em.well; currently always empty
}
Suggestion {
  title: str
  description: str             # plain language
  reason: str                  # why this is for her, from her own data
  duration_min: int | null
  tag: str                     # short card label, e.g. "Recovery", "Iron-rich", "From your doctor"
  when: str | null             # e.g. "Today · 7:30 PM", "Tomorrow · 9:00 AM", "Walk-in or prebook"
  where: str | null            # generic ("Hotel gym") or a place from her seed data, never invented by Gemini
  image: str | null            # e.g. "/wellness/kensho.png", served by the frontend
  distance_mi: float | null
  near_tag: str | null         # e.g. "1.4 mi from your Chicago hotel" when the card falls during a trip
  source: "em" | "doctor"      # "doctor" = her clinician's instruction (e.g. a prescribed iron dose), not Em's idea
}
```
If the persona's seed has `wellness_cards` (curated titles, venues, images), those are used and Gemini only writes each `reason`. Otherwise Gemini suggests the cards.
A curated card with `requires_medication` (e.g. Maya's iron card) only appears once her seed has a matching `medications` entry from her doctor, and its title and copy come from that entry.
Pregnancy-safe for Jasmine and no supplements are enforced in code as well as in the prompt for anything Em suggests (unsafe items are dropped). Only `source: "doctor"` cards can mention a supplement.

### GET /insights
Cross-data patterns. `list[Insight]`, Insight { text: str, evidence: str }
e.g. "You sleep better on days you walk 30+ minutes" / "Energy dips on heavy travel weeks".

## Coverage (insurance, FSA/HSA, employer benefits)

### GET /insurance
Computed from the persona's `insurance` seed section plus her appointments and providers. No Gemini. Costs are estimates; the screen always shows `disclaimer`.
```
Coverage {
  plan: InsurancePlan
  upcoming: list[VisitCost]          # one per upcoming appointment, soonest first
  tips: list[CoverageTip]            # up to 2, from suggested appointments (in vs out of network, free preventive care)
  spending: Spending
  accounts: list[BenefitAccount]     # FSA / HSA
  employer_benefits: list[EmployerBenefit]
  ask_suggestions: list[str]         # "Ask Em" chips
  disclaimer: str                    # fixed text
}
InsurancePlan { insurer: str, name: str, type: str, employer: str, member_id: str, group_number: str, plan_year: int, resets_on: date, covers: list[str], medical: bool, dental: bool, vision: bool }
VisitCost {
  appointment_id: str
  title: str                         # e.g. "Eye exam"
  specialty: str
  provider: str
  for_person: str                    # "self" or family member id
  for_name: str | null               # e.g. "Leo"
  datetime: datetime
  cost: float | null                 # null when no rule matches
  cost_label: str                    # e.g. "Office visit copay", "Deductible not met yet"
  plan: "medical" | "dental" | "vision" | null
  in_network: bool
  pay_with: "FSA" | "HSA" | null     # an account that can pay this cost
}
CoverageTip { title: str, text: str }
Spending {
  year: int
  total: float                       # out of pocket this plan year
  by_category: list[SpendCategory]   # SpendCategory { category: "copay" | "deductible" | "coinsurance" | "prescription", label: str, amount: float }
  by_year: list[YearTotal]           # YearTotal { year: int, total: float }, newest first
  premiums: float                    # paid from paychecks this plan year, not part of total
  deductible: Progress               # Progress { used: float, limit: float }
  out_of_pocket: Progress
}
BenefitAccount {
  type: "health_fsa" | "dependent_care_fsa" | "hsa"
  name: str
  balance: float                     # left to spend (FSA) or account balance (HSA)
  elected: float | null              # FSA yearly election
  spent: float | null
  use_by: date | null
  grace_until: date | null
  contributed_you: float | null      # HSA, this year
  contributed_employer: float | null
  annual_limit: float | null
  note: str
}
EmployerBenefit { name: str, detail: str, status: "available" | "in_use" | "not_started" | "plan_ahead", status_label: str }
```
Cost rules: `copay` is a fixed amount, `free` is $0 (preventive), `deductible` is the allowed rate until the deductible is met, then coinsurance. Out-of-network providers use the plan's flat estimate.

Em's voice agent has a `get_coverage` tool that returns this same data.

## Data settings

### GET /data-settings  /  PUT /data-settings
Per persona. Opened from the profile icon. Both choices are **off by default** (opt in). The demo only stores the choice; nothing is trained on or shared.
```
DataSettings {
  model_training: bool        # use her data to train and improve EmCare's AI models
  third_party_sharing: bool   # share or sell her data to third parties for tailored offers
  updated_at: datetime | null # set by the server on PUT
}
```
PUT takes `{ model_training, third_party_sharing }` and returns `DataSettings`.

## Voice (live Em, Gemini Live API)

The browser never talks to Gemini. It streams audio to our backend, which relays to Gemini Live.

### WS /voice?user_id=maya
WebSocket. Browsers cannot set headers on a WebSocket, so the persona comes as the `user_id` query param (same values as `X-User-Id`, unknown ids close with code 4404).

Client to server:
- Binary frame: raw mic audio, 16-bit PCM, little endian, mono, 16 kHz. Send continuously while the mic is on (~40 ms chunks).
- `{ "type": "text", "text": str }`: typed message instead of speech.
- `{ "type": "end" }`: end the session. The server closes the socket.

Server to client:
- Binary frame: Em's voice, 16-bit PCM, little endian, mono, 24 kHz. Play in order.
- `VoiceEvent` JSON, one of:
```
{ type: "ready", model: str }                               # Gemini session open, start sending audio
{ type: "transcript", role: "user" | "em", text: str }      # incremental chunk, append to the current turn
{ type: "turn_complete" }                                   # Em finished speaking
{ type: "interrupted" }                                     # user talked over Em, drop queued audio now
{ type: "tool", name: str, summary: str, changed: bool }    # Em looked something up or changed data (changed=true: refresh views)
{ type: "checkin", checkin: CheckinResult }                 # Em saved a check-in from the conversation
{ type: "urgent", message: str, speak: bool }               # fixed prompts.URGENT_ESCALATION text; Em's audio is muted until the user speaks again
{ type: "error", message: str }
```
`speak` is the persona's `voice_alerts` setting when the session opened. The client uses its current toggle (so a mid-session change applies) and, when on, plays `GET /voice/urgent-audio`. The urgent wording is never model-written: Em's own speech is dropped and only the fixed text is shown and read.

Tools Em can call during the conversation (confirms out loud before anything marked *changes data*):
`log_checkin` (*changes data*, saves a CheckinResult), `flag_urgent`, `get_appointments`, `find_slots(specialty?)`, `book_slot(slot_id, for_person)` (*changes data*, also updates the care checklist), `get_records`, `update_record_status(record_id, status)` (*changes data*, receiving lab records unlocks their panel), `get_labs`, `get_plan`, `adjust_plan_day(date, activity, duration_min, intensity, reason)` (*changes data*).

### GET /voice/settings  /  PUT /voice/settings
Per persona.
```
VoiceSettings { voice_alerts: bool }   # read urgent alerts aloud, default true
```

### GET /voice/urgent-audio
`audio/wav` of `URGENT_ESCALATION` read aloud (cached after first call). 503 if speech generation fails; the client then falls back to the browser's speech synthesis.

## Health

### GET /health
`{ ok: true }`

### GET /health/gemini
One tiny Gemini call. `{ ok: bool, model: str, latency_ms: int }`
