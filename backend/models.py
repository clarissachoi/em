"""Request/response shapes from API.md. Change API.md first, then this file. Add new models below."""

from datetime import date
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
