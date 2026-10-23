"""Every request/response shape in API.md. Change API.md first, then this file."""

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


# ---------- Appointments ----------

class VisitSummary(BaseModel):
    """What happened at a visit."""
    summary: str
    action_items: list[str]
    follow_up: str | None


class Appointment(BaseModel):
    """A booked or past appointment."""
    id: str
    for_person: str
    provider: str
    specialty: str
    datetime: datetime
    location: str
    status: Literal["upcoming", "completed"]
    prep_questions: list[str]
    visit_summary: VisitSummary | None


class SuggestedAppointment(BaseModel):
    """An appointment Em thinks the user should book."""
    specialty: str
    reason: str
    urgency: Literal["soon", "routine"]


class AppointmentList(BaseModel):
    """GET /appointments response."""
    upcoming: list[Appointment]
    past: list[Appointment]
    suggested: list[SuggestedAppointment]


class Provider(BaseModel):
    """Provider directory entry."""
    id: str
    name: str
    specialty: str
    distance_mi: float
    in_network: bool
    rating: float


class Slot(BaseModel):
    """Bookable appointment slot."""
    id: str
    provider: str
    specialty: str
    datetime: datetime


class BookRequest(BaseModel):
    """POST /appointments/book body."""
    slot_id: str
    for_person: str = "self"


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
    """GET /labs response."""
    panels: list[LabPanel]
    upcoming: list[str]


class LabExplainRequest(BaseModel):
    """POST /labs/explain body."""
    panel_id: str


class LabFlag(BaseModel):
    """Plain-language meaning of one flagged marker."""
    marker: str
    meaning: str
    why_it_matters_for_you: str


class LabExplanation(BaseModel):
    """Plain-language lab explanation. Always includes a review-with-your-doctor disclaimer."""
    plain_summary: str
    flags: list[LabFlag]
    plan_changes: list[str]
    follow_up: str | None
    disclaimer: str


# ---------- Records ----------

RecordStatus = Literal["not_requested", "requested", "received"]


class RecordRequest(BaseModel):
    """A record being transferred from a previous provider."""
    id: str
    item: str
    from_provider: str
    status: RecordStatus
    requested_on: date | None
    needed_by: date | None
    overdue: bool


class RecordStatusUpdate(BaseModel):
    """PATCH /records/{id} body."""
    status: RecordStatus


# ---------- Policy ----------

class PolicyAnswer(BaseModel):
    """Answer to an insurance policy question."""
    answer: str
    covered: Literal["yes", "no", "unclear"]
    relevant_clause: str | None


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


class Suggestion(BaseModel):
    """One personalized suggestion."""
    title: str
    description: str
    reason: str
    duration_min: int | None


class Suggestions(BaseModel):
    """GET /suggestions response."""
    nutrition: list[Suggestion]
    workouts: list[Suggestion]
    classes: list[Suggestion]
    sleep: list[Suggestion]


class Insight(BaseModel):
    """A cross-data pattern Em noticed."""
    text: str
    evidence: str


# ---------- Health ----------

class HealthStatus(BaseModel):
    """GET /health response."""
    ok: bool


class HealthGemini(BaseModel):
    """GET /health/gemini response."""
    ok: bool
    model: str
    latency_ms: int
