"""Appointments, providers, and slots. MOCK: seed data; booking persists to state.json."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from data import store
from deps import get_user_id
from models import Appointment, AppointmentList, BookRequest, Provider, Slot, SuggestedAppointment, VisitSummary

router = APIRouter(tags=["appointments"])


def _find_appointment(user_id: str, appointment_id: str) -> Appointment:
    """Return one appointment or raise 404."""
    for a in store.get(user_id, "appointments"):
        if a["id"] == appointment_id:
            return Appointment.model_validate(a)
    raise HTTPException(status_code=404, detail=f"Appointment {appointment_id!r} not found")


def _matches(specialty: str | None, value: str) -> bool:
    """Case-insensitive specialty filter. None matches everything."""
    return specialty is None or specialty.lower() == value.lower()


@router.get("/appointments")
def list_appointments(user_id: str = Depends(get_user_id)) -> AppointmentList:
    """Return upcoming, past, and suggested appointments."""
    appts = sorted((Appointment.model_validate(a) for a in store.get(user_id, "appointments")), key=lambda a: a.datetime)
    return AppointmentList(
        upcoming=[a for a in appts if a.status == "upcoming"],
        past=[a for a in reversed(appts) if a.status == "completed"],
        suggested=[SuggestedAppointment.model_validate(s) for s in store.get(user_id, "suggested_appointments")],
    )


@router.get("/providers")
def list_providers(specialty: str | None = None, user_id: str = Depends(get_user_id)) -> list[Provider]:
    """Return mocked directory providers, optionally filtered by specialty."""
    return [Provider.model_validate(p) for p in store.get(user_id, "providers") if _matches(specialty, p["specialty"])]


@router.get("/appointments/slots")
def list_slots(specialty: str | None = None, user_id: str = Depends(get_user_id)) -> list[Slot]:
    """Return open slots. Seed slots already fit the persona's free calendar windows."""
    slots = [Slot.model_validate(s) for s in store.get(user_id, "slots") if _matches(specialty, s["specialty"])]
    return sorted(slots, key=lambda s: s.datetime)


@router.post("/appointments/book")
def book_appointment(body: BookRequest, user_id: str = Depends(get_user_id)) -> Appointment:
    """Book a slot: removes it from open slots and adds an upcoming appointment."""
    slots = store.get(user_id, "slots")
    slot = next((s for s in slots if s["id"] == body.slot_id), None)
    if slot is None:
        raise HTTPException(status_code=404, detail=f"Slot {body.slot_id!r} not found")
    appt = Appointment(
        id=f"appt-{user_id}-{uuid.uuid4().hex[:8]}",
        for_person=body.for_person,
        provider=slot["provider"],
        specialty=slot["specialty"],
        datetime=slot["datetime"],
        location=slot.get("location", slot["provider"]),
        status="upcoming",
        prep_questions=[],
        visit_summary=None,
    )
    store.save(user_id, "slots", [s for s in slots if s["id"] != body.slot_id])
    store.save(user_id, "appointments", [*store.get(user_id, "appointments"), appt.model_dump(mode="json")])
    return appt


@router.post("/appointments/{appointment_id}/prep")
def prep_appointment(appointment_id: str, user_id: str = Depends(get_user_id)) -> Appointment:
    """Come with me, before the visit. MOCK: canned questions, not saved."""
    appt = _find_appointment(user_id, appointment_id)
    # TODO(Dev 2): generate from recent check-ins, labs, and missing records via gemini.generate_structured.
    appt.prep_questions = store.get(user_id, "mock")["prep_questions"]
    return appt


@router.post("/appointments/{appointment_id}/note")
async def add_visit_note(
    appointment_id: str,
    audio: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    user_id: str = Depends(get_user_id),
) -> Appointment:
    """Post-visit quick note. MOCK: canned visit summary, not saved."""
    if audio is None and not text:
        raise HTTPException(status_code=422, detail="Provide audio, text, or both.")
    appt = _find_appointment(user_id, appointment_id)
    # TODO(Dev 2): summarize audio/text with Gemini, save it, and add follow-ups as alerts.
    appt.visit_summary = VisitSummary.model_validate(store.get(user_id, "mock")["visit_note"])
    return appt
