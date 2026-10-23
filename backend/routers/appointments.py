"""Appointments, provider directory, open slots, booking, Gemini suggestions, visit prep, ambient scribe, and post-visit activities."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from google.genai import types

import gemini
from data import store
from deps import get_user_id
from models import (
    Appointment,
    AppointmentList,
    BookRequest,
    PrepQuestionList,
    Provider,
    ScribeNote,
    ScribeResult,
    Slot,
    SuggestedActivityList,
    SuggestedAppointment,
    SuggestedAppointmentList,
)
from prompts import EM_SYSTEM_PROMPT, VISIT_ACTIVITIES_PROMPT, VISIT_PREGNANCY_RULES
from voice import ToolError, today, tool_book_slot

logger = logging.getLogger("emcare.appointments")

router = APIRouter(tags=["appointments"])

SUGGEST_PROMPT = """Today is {today}. Suggest up to 4 appointments she should book next, most important first.

Rules:
- Only suggest care she does not already have booked. These specialties already have an upcoming appointment, never suggest them
  or another name for the same care (for example Gynecology when OB-GYN is booked, Ophthalmology when Optometry is): {booked}.
- Look for gaps: overdue routine care (annual physical, dental cleaning every 6 months, eye exam), unfilled roles on her care team checklist, care for family members, and anything her life stage calls for.
- Care team roles marked done already have a provider. Do not suggest establishing care for those.
- Use a specialty name exactly as written in the provider directory when one fits, so she can book it.
- reason: always fill it. One or two short sentences (under 30 words total), written to her as "you", on how this kind
  of care helps her goals or life stage, using her own data (goals, check-ins, labs, care gaps). No dates or provider names.
- urgency: "soon" if overdue or time sensitive, otherwise "routine".
- Never diagnose. Do not use em dashes.{pregnancy}

Her data:
{context}"""

PREGNANCY_NOTE = "\n- She is pregnant. Only suggest care that is safe in pregnancy, and say to check timing with her OB where it matters."


PREP_PROMPT = """Today is {today}. {name} has this visit coming up: {visit}.
Write up to 5 short questions she could ask at this visit, most useful first.

Rules:
- Base them on her data below: recent check-ins (mood, energy, stress, sleep, symptoms), out-of-range labs, goals,
  and records that are still missing. Only ask about things that fit this specialty.
- Write each as a question she would say, in first person, under 20 words.
- Never diagnose. Never suggest starting, stopping, or changing a medication or supplement. Do not use em dashes.{pregnancy}

Her data:
{context}"""

SCRIBE_PROMPT = """This is an audio recording of {name}'s visit with {provider} ({specialty}).
Write her visit notes.

Rules:
- transcript: what was said, labeled "Doctor:" and "Patient:" (use "Other:" for anyone else), one line per turn.
- summary: 2 to 4 plain-language sentences on what the visit covered.
- key_points: findings, results, and topics discussed.
- doctor_instructions: only what the clinician actually said to do, kept close to their words. Include medication
  instructions exactly as the clinician gave them. Never add advice, doses, or instructions of your own.
- follow_ups: tests, referrals, and next visits that were mentioned.
- Only use what is in the recording. If part of it is unclear, leave it out. If there is no clear speech, say so in
  the summary and leave the lists empty. Never diagnose. Do not use em dashes."""

SCRIBE_DISCLAIMER = (
    "Em took these notes from the recording of your visit and they may miss things. "
    "Check anything about medication or treatment with {provider} before acting on it."
)

MAX_AUDIO_BYTES = 19 * 1024 * 1024  # stay under Gemini's 20 MB inline request limit


def _find_appointment(appts: dict[str, Any], appointment_id: str) -> dict[str, Any]:
    """Return an upcoming or past appointment by id, or raise 404."""
    for appt in [*appts.get("upcoming", []), *appts.get("past", [])]:
        if appt["id"] == appointment_id:
            return appt
    raise HTTPException(404, f"No appointment with id {appointment_id!r}.")


# Names that mean the same kind of care, so "Gynecology" counts as booked when "OB-GYN" is
_CARE_GROUPS = {
    "primary care": ("primary care", "family medicine", "internal medicine", "general practice", "annual physical"),
    "ob-gyn": ("ob-gyn", "obgyn", "ob/gyn", "obstetrics", "gynecology", "midwife", "midwifery"),
    "eye care": ("optometry", "ophthalmology", "eye exam", "eye care", "vision"),
    "dental": ("dentistry", "dentist", "dental"),
    "dermatology": ("dermatology", "dermatologist", "skin check"),
    "pediatrics": ("pediatrics", "pediatrician"),
    "physical therapy": ("physical therapy", "physiotherapy", "physical therapist"),
}


def _care_key(specialty: str) -> str:
    """Group a specialty name with its synonyms; unknown names stand alone."""
    name = specialty.strip().casefold()
    for key, aliases in _CARE_GROUPS.items():
        if any(alias in name for alias in aliases):
            return key
    return name


def _drop_booked(suggested: list[dict[str, Any]], upcoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove suggestions for any kind of care that already has an upcoming appointment."""
    booked = {_care_key(a["specialty"]) for a in upcoming}
    return [s for s in suggested if _care_key(s["specialty"]) not in booked]


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
    """Return upcoming, past, and suggested appointments. Suggestions never repeat booked care."""
    appts = store.get(user_id, "appointments")
    appts["suggested"] = _drop_booked(appts.get("suggested", []), appts.get("upcoming", []))
    return AppointmentList.model_validate(appts)


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
    booked = {a["specialty"] for a in appts.get("upcoming", [])}
    pregnant = store.get(user_id, "profile").get("life_stage") == "pregnant"
    prompt = SUGGEST_PROMPT.format(
        today=today(user_id).isoformat(),
        booked=", ".join(sorted(booked, key=str.casefold)) or "none",
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

    # Enforce the no-overlap rule in code, not just in the prompt, and drop repeats of one kind of care
    seen: set[str] = set()
    suggested = []
    for s in result.suggested:
        key = _care_key(s.specialty)
        if key in seen or not _drop_booked([s.model_dump()], appts.get("upcoming", [])):
            continue
        seen.add(key)
        suggested.append(s.model_copy(update={"reason": _no_em_dashes(s.reason)}))
    appts["suggested"] = [s.model_dump() for s in suggested]
    store.save(user_id, "appointments", appts)
    return suggested


def _no_em_dashes(text: str) -> str:
    """Swap em and en dashes for plain punctuation in model output."""
    return text.replace("—", ", ").replace("–", "-")


@router.post("/appointments/{appointment_id}/activities")
async def suggest_activities(appointment_id: str, user_id: str = Depends(get_user_id)) -> Appointment:
    """Ask Gemini for activities that follow the doctor's plan and fit recent check-ins, and save them."""
    appts = store.get(user_id, "appointments")
    appt = next((a for a in appts.get("past", []) if a["id"] == appointment_id), None)
    if appt is None:
        raise HTTPException(404, f"No completed appointment with id {appointment_id!r}.")
    if not appt.get("doctor_notes") or not appt.get("visit_summary"):
        raise HTTPException(409, "This visit has no doctor notes yet.")

    data = store.get_user(user_id)
    checkins = data.get("checkins", [])[-7:]
    if checkins and checkins[-1].get("urgent"):
        activities = []  # urgent check-in: point to care, not workouts
    else:
        pregnant = data["profile"].get("life_stage") == "pregnant"
        visit = {k: appt[k] for k in ("specialty", "provider", "doctor_notes")}
        context = {
            "goals": data.get("goals"),
            "pregnancy_week": (data["profile"].get("pregnancy") or {}).get("week"),
            "recent_checkins": [
                {k: c.get(k) for k in ("created_at", "mood", "energy", "stress", "sleep_quality", "symptoms", "transcript")}
                for c in checkins
            ],
        }
        prompt = VISIT_ACTIVITIES_PROMPT.format(
            today=today(user_id).isoformat(),
            name=data["profile"]["name"],
            visit_date=appt["datetime"][:10],
            pregnancy_rules=VISIT_PREGNANCY_RULES if pregnant else "",
            visit=json.dumps(visit, default=str),
            context=json.dumps(context, default=str),
        )
        try:
            result = await gemini.generate_structured(
                prompt, SuggestedActivityList, system_instruction=EM_SYSTEM_PROMPT, thinking_level="low"
            )
        except Exception as exc:  # keep any saved activities on Gemini failure
            logger.warning("activities failed user=%s appt=%s err=%s", user_id, appointment_id, exc)
            raise HTTPException(503, "Could not get activity ideas right now.") from exc
        activities = [
            a.model_copy(update={"title": _no_em_dashes(a.title), "detail": _no_em_dashes(a.detail)})
            for a in result.activities[:4]
        ]

    appt["visit_summary"]["suggested_activities"] = [a.model_dump() for a in activities]
    store.save(user_id, "appointments", appts)
    return Appointment.model_validate(appt)


@router.post("/appointments/{appointment_id}/prep")
async def prep_questions(appointment_id: str, user_id: str = Depends(get_user_id)) -> Appointment:
    """Ask Gemini for questions to bring to a visit, and save them on the appointment."""
    appts = store.get(user_id, "appointments")
    appt = _find_appointment(appts, appointment_id)
    data = store.get_user(user_id)
    pregnant = data["profile"].get("life_stage") == "pregnant"
    context = {
        "goals": data.get("goals"),
        "pregnancy": data["profile"].get("pregnancy"),
        "recent_checkins": [
            {k: c.get(k) for k in ("created_at", "mood", "energy", "stress", "sleep_quality", "symptoms")}
            for c in data.get("checkins", [])[-7:]
        ],
        "flagged_labs": [
            {"date": p["date"], **r}
            for p in data.get("labs", {}).get("panels", [])
            for r in p["results"]
            if r["flag"] != "normal"
        ],
        "missing_records": [r for r in data.get("records", []) if r.get("status") != "received"],
    }
    prompt = PREP_PROMPT.format(
        today=today(user_id).isoformat(),
        name=data["profile"]["name"],
        visit=json.dumps({k: appt[k] for k in ("specialty", "provider", "datetime", "for_person")}, default=str),
        pregnancy=PREGNANCY_NOTE if pregnant else "",
        context=json.dumps(context, default=str),
    )
    try:
        result = await gemini.generate_structured(
            prompt, PrepQuestionList, system_instruction=EM_SYSTEM_PROMPT, thinking_level="low"
        )
    except Exception as exc:  # keep any saved questions on Gemini failure
        logger.warning("prep failed user=%s appt=%s err=%s", user_id, appointment_id, exc)
        raise HTTPException(503, "Could not get prep questions right now.") from exc

    appt["prep_questions"] = [_no_em_dashes(q) for q in result.questions[:5]]
    store.save(user_id, "appointments", appts)
    return Appointment.model_validate(appt)


@router.post("/appointments/{appointment_id}/scribe")
async def scribe_visit(
    appointment_id: str,
    audio: UploadFile = File(...),
    duration_sec: int | None = Form(None),
    user_id: str = Depends(get_user_id),
) -> ScribeNote:
    """Transcribe a visit recording into notes with Gemini and save them."""
    appt = _find_appointment(store.get(user_id, "appointments"), appointment_id)
    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "That recording is too long to process. Try one under about an hour.")
    if not audio_bytes:
        raise HTTPException(422, "The recording was empty.")

    mime = (audio.content_type or "audio/webm").split(";")[0]
    name = store.get(user_id, "profile")["name"]
    prompt = SCRIBE_PROMPT.format(name=name, provider=appt["provider"], specialty=appt["specialty"])
    try:
        result = await gemini.generate_structured(
            prompt, ScribeResult, [types.Part.from_bytes(data=audio_bytes, mime_type=mime)], thinking_level="low"
        )
    except Exception as exc:
        logger.warning("scribe failed user=%s appt=%s err=%s", user_id, appointment_id, exc)
        raise HTTPException(503, "Could not process the recording right now. Please try again.") from exc

    note = ScribeNote(
        id=f"scribe_{uuid.uuid4().hex[:8]}",
        appointment_id=appointment_id,
        provider=appt["provider"],
        specialty=appt["specialty"],
        created_at=datetime.now().replace(microsecond=0),
        duration_sec=duration_sec,
        summary=_no_em_dashes(result.summary),
        key_points=[_no_em_dashes(k) for k in result.key_points],
        doctor_instructions=[_no_em_dashes(i) for i in result.doctor_instructions],
        follow_ups=[_no_em_dashes(f) for f in result.follow_ups],
        transcript=_no_em_dashes(result.transcript),
        disclaimer=SCRIBE_DISCLAIMER.format(provider=appt["provider"]),
    )
    notes = store.get(user_id, "scribe_notes", [])
    notes.append(note.model_dump(mode="json"))
    store.save(user_id, "scribe_notes", notes)
    return note


@router.get("/scribe-notes")
def list_scribe_notes(user_id: str = Depends(get_user_id)) -> list[ScribeNote]:
    """Return saved scribe notes, newest first."""
    notes = [ScribeNote.model_validate(n) for n in store.get(user_id, "scribe_notes", [])]
    return sorted(notes, key=lambda n: n.created_at, reverse=True)
