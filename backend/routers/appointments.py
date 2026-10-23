"""Appointments, provider directory, open slots, booking, and Gemini suggestions."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

import gemini
from data import store
from deps import get_user_id
from models import Appointment, AppointmentList, BookRequest, Provider, Slot, SuggestedAppointment, SuggestedAppointmentList
from prompts import EM_SYSTEM_PROMPT
from voice import ToolError, today, tool_book_slot

logger = logging.getLogger("emcare.appointments")

router = APIRouter(tags=["appointments"])

SUGGEST_PROMPT = """Today is {today}. Suggest up to 4 appointments she should book next, most important first.

Rules:
- Only suggest care she does not already have booked. These specialties already have an upcoming appointment, never suggest them: {booked}.
- Look for gaps: overdue routine care (annual physical, dental cleaning every 6 months, eye exam), unfilled roles on her care team checklist, care for family members, and anything her life stage calls for.
- Care team roles marked done already have a provider. Do not suggest establishing care for those.
- Use a specialty name exactly as written in the provider directory when one fits, so she can book it.
- reason: usually an empty string. Only if the specialty alone does not explain it, write one very short sentence (under 12 words) on how it supports her goals. No dates or provider names.
- urgency: "soon" if overdue or time sensitive, otherwise "routine".
- Never diagnose. Do not use em dashes.{pregnancy}

Her data:
{context}"""

PREGNANCY_NOTE = "\n- She is pregnant. Only suggest care that is safe in pregnancy, and say to check timing with her OB where it matters."


def _matches(value: str, specialty: str | None) -> bool:
    """True when no specialty filter is given or it matches case-insensitively."""
    return specialty is None or value.casefold() == specialty.strip().casefold()


def _suggestion_context(user_id: str) -> str:
    """Trimmed persona data Gemini needs to suggest appointments."""
    data = store.get_user(user_id)
    profile = {k: v for k, v in data["profile"].items() if k != "connections"}
    appts = data.get("appointments", {})
    context = {
        "profile": profile,
        "goals": data.get("goals"),
        "care_team_checklist": data.get("care_team"),
        "upcoming_appointments": appts.get("upcoming", []),
        "past_appointments": [{k: a[k] for k in ("specialty", "provider", "datetime", "for_person")} for a in appts.get("past", [])],
        "provider_directory": data.get("providers", []),
        "open_slots": data.get("slots", []),
        "free_calendar_windows": data.get("calendar", {}).get("free_windows"),
        "records": data.get("records", []),
    }
    return json.dumps(context, default=str)


@router.get("/appointments")
def list_appointments(user_id: str = Depends(get_user_id)) -> AppointmentList:
    """Return upcoming, past, and suggested appointments."""
    return AppointmentList.model_validate(store.get(user_id, "appointments"))


@router.get("/providers")
def list_providers(specialty: str | None = None, user_id: str = Depends(get_user_id)) -> list[Provider]:
    """Return providers, optionally filtered by specialty."""
    providers = [Provider.model_validate(p) for p in store.get(user_id, "providers")]
    return [p for p in providers if _matches(p.specialty, specialty)]


@router.get("/appointments/slots")
def list_slots(specialty: str | None = None, user_id: str = Depends(get_user_id)) -> list[Slot]:
    """Return open slots, optionally filtered by specialty, soonest first."""
    slots = [Slot.model_validate(s) for s in store.get(user_id, "slots")]
    return sorted((s for s in slots if _matches(s.specialty, specialty)), key=lambda s: s.datetime)


@router.post("/appointments/book")
def book(body: BookRequest, user_id: str = Depends(get_user_id)) -> Appointment:
    """Book an open slot. Shares the voice agent's booking logic."""
    try:
        outcome = tool_book_slot(user_id, body.model_dump())
    except ToolError as exc:
        raise HTTPException(404, f"No open slot with id {body.slot_id!r}.") from exc
    return Appointment.model_validate(outcome.result["booked"])


@router.post("/appointments/suggestions")
async def refresh_suggestions(user_id: str = Depends(get_user_id)) -> list[SuggestedAppointment]:
    """Ask Gemini for new suggestions, drop any that overlap upcoming bookings, and save them."""
    appts = store.get(user_id, "appointments")
    booked = {a["specialty"].casefold() for a in appts.get("upcoming", [])}
    pregnant = store.get(user_id, "profile").get("life_stage") == "pregnant"
    prompt = SUGGEST_PROMPT.format(
        today=today(user_id).isoformat(),
        booked=", ".join(sorted(booked)) or "none",
        pregnancy=PREGNANCY_NOTE if pregnant else "",
        context=_suggestion_context(user_id),
    )
    try:
        result = await gemini.generate_structured(
            prompt, SuggestedAppointmentList, system_instruction=EM_SYSTEM_PROMPT, thinking_level="low"
        )
    except Exception as exc:  # keep the saved suggestions on any Gemini failure
        logger.warning("suggestions failed user=%s err=%s", user_id, exc)
        raise HTTPException(503, "Could not get suggestions right now. Showing the saved ones.") from exc

    # Enforce the no-overlap rule in code, not just in the prompt
    suggested = [
        s.model_copy(update={"reason": s.reason.replace("—", ", ").replace("–", "-")})
        for s in result.suggested
        if s.specialty.casefold() not in booked
    ]
    appts["suggested"] = [s.model_dump() for s in suggested]
    store.save(user_id, "appointments", appts)
    return suggested
