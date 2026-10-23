"""Appointments, provider directory, and open slots."""

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import AppointmentList, Provider, Slot

router = APIRouter(tags=["appointments"])


def _matches(value: str, specialty: str | None) -> bool:
    """True when no specialty filter is given or it matches case-insensitively."""
    return specialty is None or value.casefold() == specialty.strip().casefold()


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
