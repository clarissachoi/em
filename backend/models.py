"""Request/response shapes from API.md. Change API.md first, then this file. Add new models below."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


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

class VisitSummary(BaseModel):
    """What happened at a completed visit."""
    summary: str
    action_items: list[str]
    follow_up: str | None


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
