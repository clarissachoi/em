"""Request/response shapes from API.md. Change API.md first, then this file. Add new models below."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Score = Annotated[int, Field(ge=1, le=5)]


# ---------- Users ----------

class UserSummary(BaseModel):
    """Entry in the persona switcher."""
    id: str
    name: str
    age: int
    tagline: str


class Pregnancy(BaseModel):
    """Current pregnancy details."""
    week: int
    due_date: date
    pregnancy_number: int


class Connection(BaseModel):
    """A mocked external data source."""
    source: str
    kind: Literal["wearable", "fitness", "cycle", "pregnancy", "calendar", "records"]
    connected: bool


class UserProfile(BaseModel):
    """Full profile for GET /me."""
    id: str
    name: str
    age: int
    life_stage: Literal["general", "pregnant", "postpartum"]
    pregnancy: Pregnancy | None
    primary_goal: str
    connections: list[Connection]


# ---------- Appointments ----------

class DoctorNote(BaseModel):
    """Clinician's note from a completed visit (mocked records)."""
    author: str
    written_on: date
    reason_for_visit: str
    subjective: str
    objective: list[str]
    assessment: list[str]
    plan: list[str]


class SuggestedActivity(BaseModel):
    """An activity Em suggests after a visit, tied to one line of the doctor's plan."""
    title: str
    detail: str
    category: Literal["training", "nutrition", "recovery", "self_care"]
    based_on: str


class SuggestedActivityList(BaseModel):
    """Gemini response schema for POST /appointments/{id}/activities."""
    activities: list[SuggestedActivity]


class VisitSummaryText(BaseModel):
    """Gemini response schema for the one-off visit summary script."""
    summary: str


class VisitSummary(BaseModel):
    """What happened at a completed visit."""
    summary: str
    action_items: list[str]
    follow_up: str | None
    suggested_activities: list[SuggestedActivity] = []


class Appointment(BaseModel):
    """A booked or completed appointment."""
    id: str
    for_person: str
    provider: str
    specialty: str
    datetime: datetime
    location: str
    status: Literal["upcoming", "completed"]
    prep_questions: list[str]
    visit_summary: VisitSummary | None
    doctor_notes: DoctorNote | None = None


class SuggestedAppointment(BaseModel):
    """An appointment Em recommends booking."""
    specialty: str
    reason: str
    urgency: Literal["soon", "routine"]


class AppointmentList(BaseModel):
    """Response for GET /appointments."""
    upcoming: list[Appointment]
    past: list[Appointment]
    suggested: list[SuggestedAppointment]


class Provider(BaseModel):
    """A provider from the mocked directory."""
    id: str
    name: str
    specialty: str
    distance_mi: float
    in_network: bool
    rating: float


class Slot(BaseModel):
    """An open time on a provider's calendar. `provider` matches Provider.name."""
    id: str
    provider: str
    specialty: str
    datetime: datetime
    description: str | None = None


class BookRequest(BaseModel):
    """Body for POST /appointments/book."""
    slot_id: str
    for_person: str = "self"


class SuggestedAppointmentList(BaseModel):
    """Gemini response schema for POST /appointments/suggestions."""
    suggested: list[SuggestedAppointment]


class PrepQuestionList(BaseModel):
    """Gemini response schema for POST /appointments/{id}/prep."""
    questions: list[str]


class ScribeResult(BaseModel):
    """Gemini response schema for POST /appointments/{id}/scribe."""
    transcript: str
    summary: str
    key_points: list[str]
    doctor_instructions: list[str]
    follow_ups: list[str]


class ScribeNote(BaseModel):
    """A saved ambient scribe note from a visit."""
    id: str
    appointment_id: str
    provider: str
    specialty: str
    created_at: datetime
    duration_sec: int | None
    summary: str
    key_points: list[str]
    doctor_instructions: list[str]
    follow_ups: list[str]
    transcript: str
    disclaimer: str


# ---------- Records ----------

class RecordRequest(BaseModel):
    """A records transfer request to a previous provider."""
    id: str
    item: str
    from_provider: str
    status: Literal["not_requested", "requested", "received"]
    requested_on: date | None
    needed_by: date | None
    overdue: bool


class RecordStatusUpdate(BaseModel):
    """Body for PATCH /records/{id}."""
    status: Literal["not_requested", "requested", "received"]


# ---------- Labs ----------

class LabResult(BaseModel):
    """One marker in a lab panel."""
    marker: str
    value: float
    unit: str
    ref_low: float | None
    ref_high: float | None
    flag: Literal["low", "normal", "high"]


class LabPanel(BaseModel):
    """A set of lab results from one draw."""
    id: str
    date: date
    source: str
    results: list[LabResult]


class LabsResponse(BaseModel):
    """Response for GET /labs."""
    panels: list[LabPanel]
    upcoming: list[str]


class LabExplainRequest(BaseModel):
    """Body for POST /labs/explain."""
    panel_id: str


class LabFlag(BaseModel):
    """Plain-language meaning of one flagged marker."""
    marker: str
    meaning: str
    why_it_matters_for_you: str


class LabExplanation(BaseModel):
    """Plain-language lab explanation. The disclaimer always says to review with her doctor."""
    plain_summary: str
    flags: list[LabFlag]
    plan_changes: list[str]
    follow_up: str | None
    disclaimer: str


# ---------- Home ----------

class CheckinResult(BaseModel):
    """Structured result of a "How are you doing" check-in."""
    id: str
    created_at: datetime
    transcript: str
    mood: Score
    energy: Score
    stress: Score
    sleep_quality: Score | None
    symptoms: list[str]
    cycle_phase: str | None
    em_reply: str
    insight: str | None
    urgent: bool
    escalation_message: str | None


class Alert(BaseModel):
    """Dashboard alert."""
    type: Literal["appointment", "medication", "travel", "records", "lab"]
    title: str
    detail: str
    severity: Literal["info", "warning"]


class Readiness(BaseModel):
    """Recovery snapshot from wearable data."""
    score: int = Field(ge=0, le=100)
    label: str
    sleep_hours: float
    hrv_ms: int | None
    resting_hr: int | None
    summary: str


class CareItem(BaseModel):
    """One role in the care transition checklist."""
    role: str
    provider: str | None
    done: bool


class CareChecklist(BaseModel):
    """Care team progress, e.g. 2 of 4 providers found."""
    found: int
    total: int
    items: list[CareItem]


class FocusItem(BaseModel):
    """One task in Today's Focus."""
    kind: Literal["workout", "nutrition", "appointment", "records", "lab", "checkin"]
    title: str
    detail: str
    time: str | None


class TrendPoint(BaseModel):
    """One day of the readiness trend."""
    date: date
    readiness: int


class Metric(BaseModel):
    """A tile under the trend chart."""
    label: str
    value: str
    unit: str | None


class CareNote(BaseModel):
    """Latest clinician note, or Em's note on a flagged lab."""
    author: str
    text: str
    source: Literal["visit", "em"]


class HomeData(BaseModel):
    """Everything the Home dashboard needs."""
    user_name: str
    greeting: str
    alerts: list[Alert]
    quote: str
    readiness: Readiness | None
    today_plan: str | None
    nutrition_tip: str | None
    pregnancy_week: int | None
    care_checklist: CareChecklist | None
    recent_checkins: list[CheckinResult]
    mood: int | None
    focus: list[FocusItem]
    trend: list[TrendPoint]
    metrics: list[Metric]
    care_note: CareNote | None
    ask_suggestions: list[str]


# ---------- Next steps ----------

class Goals(BaseModel):
    """User goals, also set during onboarding."""
    primary_goal: str
    focus_areas: list[str]
    target_date: date | None
    dietary_prefs: list[str]
    activity_level: Literal["low", "medium", "high"]
    notes: str | None


class PlanDay(BaseModel):
    """One day of the adaptive plan."""
    date: date
    activity: str
    duration_min: int
    intensity: Literal["rest", "easy", "moderate", "hard"]
    adjusted: bool
    adjustment_reason: str | None


class SuggestionIdea(BaseModel):
    """The part of an em.well card Gemini writes."""
    title: str
    description: str
    reason: str
    duration_min: int | None
    tag: str
    when: str | None
    where: str | None


class Suggestion(SuggestionIdea):
    """One em.well card. Image, distance, near_tag, and source are filled in code, never by Gemini."""
    image: str | None = None
    distance_mi: float | None = None
    near_tag: str | None = None
    source: Literal["em", "doctor"] = "em"


class SuggestionDraft(BaseModel):
    """What Gemini returns for GET /suggestions when there are no curated cards."""
    nutrition: list[SuggestionIdea]
    workouts: list[SuggestionIdea]
    classes: list[SuggestionIdea]
    sleep: list[SuggestionIdea]


class CardReason(BaseModel):
    """Gemini's personal reason for one curated card."""
    id: str
    reason: str


class CardReasons(BaseModel):
    """What Gemini returns for curated cards."""
    reasons: list[CardReason]


class Suggestions(BaseModel):
    """Response for GET /suggestions."""
    headline: str
    nutrition: list[Suggestion]
    workouts: list[Suggestion]
    classes: list[Suggestion]
    sleep: list[Suggestion]


class Insight(BaseModel):
    """A cross-data pattern Em noticed."""
    text: str
    evidence: str


# ---------- Voice ----------

class VoiceSettings(BaseModel):
    """Per-persona voice preferences."""
    voice_alerts: bool = True  # read urgent alerts aloud


class LogCheckinArgs(BaseModel):
    """What Em extracts from a live conversation when she calls log_checkin."""
    mood: Score
    energy: Score
    stress: Score
    sleep_quality: Score | None = None
    symptoms: list[str] = []
    em_reply: str
    insight: str | None = None
