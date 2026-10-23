"""Live voice Em: persona context, tools, and the browser <-> Gemini Live relay."""

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import live, types
from pydantic import ValidationError

import gemini
from config import settings
from data import store
from models import Appointment, CheckinResult, LogCheckinArgs, PlanDay, RecordRequest
from prompts import EM_VOICE_PROMPT, PREGNANCY_VOICE_RULES, URGENT_ESCALATION, is_urgent

logger = logging.getLogger("emcare.voice")

MIC_MIME = "audio/pcm;rate=16000"
KICKOFF = "(She just opened voice chat with you. Greet her by first name in one short sentence and ask how she is doing today.)"


# ---------- Persona context ----------

def today(user_id: str) -> date:
    """The demo's "today": the seed's as_of date, or the real date if missing."""
    as_of = store.get(user_id, "as_of", None)
    return date.fromisoformat(as_of) if as_of else date.today()


def _plan_from(user_id: str, start: date, days: int) -> list[dict[str, Any]]:
    """Plan days from start for the given number of days."""
    end = start + timedelta(days=days)
    return [d for d in store.get(user_id, "plan", []) if start <= date.fromisoformat(d["date"]) < end]


def _flagged_labs(labs: dict[str, Any]) -> list[dict[str, Any]]:
    """Out-of-range lab results across visible panels, with the panel date."""
    return [
        {"date": p["date"], "source": p["source"], **r}
        for p in labs.get("panels", [])
        for r in p["results"]
        if r["flag"] != "normal"
    ]


def build_system_prompt(user_id: str) -> str:
    """Em's live system prompt with a trimmed summary of this persona's data."""
    data = store.get_user(user_id)
    day = today(user_id)
    profile = data["profile"]
    pregnant = profile.get("life_stage") == "pregnant"
    keep = (
        "name", "age", "life_stage", "pregnancy", "primary_goal", "home_location", "work_location",
        "last_physical", "previous_location", "moved_on", "work", "prior_pregnancies", "family",
    )
    labs = data.get("labs", {})
    appts = data.get("appointments", {})
    context = {
        "profile": {k: profile[k] for k in keep if k in profile},
        "goals": data.get("goals"),
        "cycle": data.get("cycle"),
        "pregnancy_tracker": data.get("pregnancy_tracker"),
        "sleep_notes": data.get("sleep"),
        "wearable_last_7_days": data.get("wearable", [])[-7:],
        "recent_runs": data.get("strava_runs", [])[-4:],
        "recent_checkins": [
            {k: c.get(k) for k in ("created_at", "transcript", "mood", "energy", "stress", "sleep_quality", "symptoms")}
            for c in data.get("checkins", [])[-3:]
        ],
        "calendar": data.get("calendar"),
        "care_team": data.get("care_team"),
        "plan_next_7_days": _plan_from(user_id, day, 7),
        "upcoming_appointments": appts.get("upcoming"),
        "suggested_appointments": appts.get("suggested"),
        "records": data.get("records"),
        "out_of_range_labs": _flagged_labs(labs),
        "upcoming_labs": labs.get("upcoming"),
        "lab_panels_waiting_on_records": [
            {"record_id": lp["unlocked_by_record"], "date": lp["panel"]["date"], "source": lp["panel"]["source"]}
            for lp in labs.get("locked_panels", [])
        ],
        "walking_routes": data.get("walking_routes"),
    }
    context = {k: v for k, v in context.items() if v}
    return EM_VOICE_PROMPT.format(
        name=profile["name"],
        ob_note=" (her OB, Dr. Ortiz, for anything pregnancy related)" if pregnant else "",
        pregnancy_signs=", severe or sudden swelling, reduced baby movement" if pregnant else "",
        pregnancy_rules=PREGNANCY_VOICE_RULES if pregnant else "",
        today=f"{day:%A, %B %-d, %Y}",
        context=json.dumps(context, separators=(",", ":"), default=str),
    )


# ---------- Tools ----------

class ToolError(Exception):
    """Bad tool input. The message goes back to Gemini so Em can recover."""


@dataclass
class ToolOutcome:
    """Result for Gemini plus a one-line summary for the UI."""
    result: dict[str, Any]
    summary: str
    changed: bool = False


def _when(iso: str) -> str:
    """Speakable datetime, e.g. "Thu Oct 29, 5:15 PM"."""
    return f"{datetime.fromisoformat(iso):%a %b %-d, %-I:%M %p}"


def tool_get_appointments(user_id: str, args: dict[str, Any]) -> ToolOutcome:
    """Upcoming, past, and suggested appointments."""
    appts = store.get(user_id, "appointments", {})
    return ToolOutcome(appts, "Checked your appointments")


def tool_find_slots(user_id: str, args: dict[str, Any]) -> ToolOutcome:
    """Open slots, optionally by specialty, joined with provider details."""
    specialty = (args.get("specialty") or "").strip().lower()
    providers = {p["name"]: p for p in store.get(user_id, "providers", [])}
    slots = []
    for s in store.get(user_id, "slots", []):
        if specialty and specialty not in s["specialty"].lower() and s["specialty"].lower() not in specialty:
            continue
        p = providers.get(s["provider"], {})
        slots.append({**s, "when": _when(s["datetime"]), **{k: p[k] for k in ("in_network", "rating", "distance_mi") if k in p}})
    free = store.get(user_id, "calendar", {}).get("free_windows", [])
    label = args.get("specialty") or "any specialty"
    return ToolOutcome({"slots": slots, "free_calendar_windows": free}, f"Found {len(slots)} open slots for {label}")


def _care_role_matches(role: str, specialty: str) -> bool:
    """Loose match so "Pediatrician (Leo)" fits "Pediatrics" and "Dentist" fits "Dentistry"."""
    return role.lower().split(" (")[0][:5] == specialty.lower()[:5]


def tool_book_slot(user_id: str, args: dict[str, Any]) -> ToolOutcome:
    """Book a slot: add the appointment, drop the slot, tick the care checklist."""
    slots = store.get(user_id, "slots", [])
    slot = next((s for s in slots if s["id"] == args.get("slot_id")), None)
    if slot is None:
        raise ToolError(f"No open slot with id {args.get('slot_id')!r}. Call find_slots for current ids.")

    for_person = (args.get("for_person") or "self").strip()
    family = store.get(user_id, "profile", {}).get("family") or []
    member = next((f for f in family if for_person.lower() in (f["id"].lower(), f["name"].lower())), None)
    for_person = member["id"] if member else "self"

    provider = next((p for p in store.get(user_id, "providers", []) if p["name"] == slot["provider"]), None)
    location = f"{slot['provider']}, {provider['distance_mi']} mi from home" if provider else slot["provider"]
    appt = Appointment(
        id=f"appt_{slot['id']}",
        for_person=for_person,
        provider=slot["provider"],
        specialty=slot["specialty"],
        datetime=slot["datetime"],
        location=location,
        status="upcoming",
        prep_questions=[],
        visit_summary=None,
    ).model_dump(mode="json")

    appts = store.get(user_id, "appointments", {"upcoming": [], "past": [], "suggested": []})
    appts["upcoming"] = sorted([*appts.get("upcoming", []), appt], key=lambda a: a["datetime"])
    appts["suggested"] = [s for s in appts.get("suggested", []) if s["specialty"] != slot["specialty"]]
    store.save(user_id, "appointments", appts)
    store.save(user_id, "slots", [s for s in slots if s["id"] != slot["id"]])

    result: dict[str, Any] = {"booked": appt}
    care = store.get(user_id, "care_team", None)
    if care:
        item = next((c for c in care if not c["done"] and _care_role_matches(c["role"], slot["specialty"])), None)
        if item:
            item.update(provider=slot["provider"], done=True)
            store.save(user_id, "care_team", care)
        result["care_checklist"] = f"{sum(c['done'] for c in care)} of {len(care)} providers found"

    who = member["name"] if member else "you"
    return ToolOutcome(result, f"Booked {slot['specialty']} with {slot['provider']} for {who}, {_when(slot['datetime'])}", True)


def tool_get_records(user_id: str, args: dict[str, Any]) -> ToolOutcome:
    """Record transfer requests and their status."""
    records = store.get(user_id, "records", [])
    return ToolOutcome({"records": records}, "Checked your record requests")


def tool_update_record_status(user_id: str, args: dict[str, Any]) -> ToolOutcome:
    """Change a record request's status. Receiving lab records unlocks their lab panel."""
    records = store.get(user_id, "records", [])
    record = next((r for r in records if r["id"] == args.get("record_id")), None)
    if record is None:
        raise ToolError(f"No record request with id {args.get('record_id')!r}.")
    status = args.get("status")
    if status == "requested" and record.get("requested_on") is None:
        record["requested_on"] = today(user_id).isoformat()
    if status == "received":
        record["overdue"] = False
    record["status"] = status
    try:
        RecordRequest.model_validate(record)
    except ValidationError as exc:
        raise ToolError(f"Invalid status {status!r}. Use not_requested, requested, or received.") from exc
    store.save(user_id, "records", records)

    result: dict[str, Any] = {"record": record}
    labs = store.get(user_id, "labs", {})
    unlocked = [lp for lp in labs.get("locked_panels", []) if status == "received" and lp["unlocked_by_record"] == record["id"]]
    if unlocked:
        labs["panels"] = [*labs.get("panels", []), *(lp["panel"] for lp in unlocked)]
        labs["locked_panels"] = [lp for lp in labs["locked_panels"] if lp not in unlocked]
        store.save(user_id, "labs", labs)
        result["unlocked_lab_panels"] = [lp["panel"] for lp in unlocked]
    labels = {"requested": "requested", "received": "received", "not_requested": "not requested"}
    return ToolOutcome(result, f"Marked {record['item']} as {labels.get(status, status)}", True)


def tool_get_labs(user_id: str, args: dict[str, Any]) -> ToolOutcome:
    """Visible lab panels, upcoming labs, and panels waiting on records."""
    labs = store.get(user_id, "labs", {})
    result = {
        "panels": labs.get("panels", []),
        "upcoming": labs.get("upcoming", []),
        "waiting_on_records": [lp["unlocked_by_record"] for lp in labs.get("locked_panels", [])],
        "reminder": "Explain in plain language, never diagnose, and say to review with her doctor.",
    }
    return ToolOutcome(result, "Checked your labs")


def tool_get_plan(user_id: str, args: dict[str, Any]) -> ToolOutcome:
    """Plan days from today, default the next 7."""
    days = max(1, min(int(args.get("days") or 7), 21))
    return ToolOutcome({"plan": _plan_from(user_id, today(user_id), days)}, f"Checked your plan for the next {days} days")


def tool_adjust_plan_day(user_id: str, args: dict[str, Any]) -> ToolOutcome:
    """Replace one plan day and mark it adjusted with a reason."""
    plan = store.get(user_id, "plan", [])
    idx = next((i for i, d in enumerate(plan) if d["date"] == args.get("date")), None)
    if idx is None:
        raise ToolError(f"No plan day on {args.get('date')!r}. Call get_plan for the dates.")
    try:
        day = PlanDay(
            date=args["date"],
            activity=args["activity"],
            duration_min=args["duration_min"],
            intensity=args["intensity"],
            adjusted=True,
            adjustment_reason=args.get("reason"),
        ).model_dump(mode="json")
    except (KeyError, ValidationError) as exc:
        raise ToolError(f"Invalid plan day: {exc}") from exc
    plan[idx] = day
    store.save(user_id, "plan", plan)
    return ToolOutcome({"updated": day}, f"Changed {datetime.fromisoformat(day['date']):%a %b %-d} to {day['activity']}", True)


ToolFn = Callable[[str, dict[str, Any]], ToolOutcome]

TOOLS: dict[str, ToolFn] = {
    "get_appointments": tool_get_appointments,
    "find_slots": tool_find_slots,
    "book_slot": tool_book_slot,
    "get_records": tool_get_records,
    "update_record_status": tool_update_record_status,
    "get_labs": tool_get_labs,
    "get_plan": tool_get_plan,
    "adjust_plan_day": tool_adjust_plan_day,
}

_SCORE = {"type": "integer", "minimum": 1, "maximum": 5}


def _decl(name: str, description: str, properties: dict[str, Any] | None = None, required: list[str] | None = None) -> types.FunctionDeclaration:
    """Build a function declaration from a JSON schema."""
    schema = {"type": "object", "properties": properties or {}, "required": required or []}
    return types.FunctionDeclaration(name=name, description=description, parameters_json_schema=schema)


TOOL_DECLARATIONS = [
    _decl(
        "log_checkin",
        "Save today's check-in once you know her mood, energy, stress, sleep, and symptoms. Call once per conversation.",
        {
            "mood": _SCORE, "energy": _SCORE, "stress": _SCORE,
            "sleep_quality": {**_SCORE, "description": "Omit if she did not say"},
            "symptoms": {"type": "array", "items": {"type": "string"}, "description": "Short lowercase words, e.g. soreness, swelling"},
            "em_reply": {"type": "string", "description": "One or two warm sentences to show with the saved check-in"},
            "insight": {"type": "string", "description": "A pattern in her data, only if clearly supported"},
        },
        ["mood", "energy", "stress", "symptoms", "em_reply"],
    ),
    _decl("flag_urgent", "Call immediately if she mentions an urgent warning sign. The app shows a fixed safety message.",
          {"reason": {"type": "string"}}, ["reason"]),
    _decl("get_appointments", "Her upcoming, past, and suggested appointments."),
    _decl("find_slots", "Open appointment slots with provider network status, rating, and distance, plus her free calendar windows.",
          {"specialty": {"type": "string", "description": "e.g. Primary care, Pediatrics, Dentistry. Omit for all."}}),
    _decl("book_slot", "Book an open slot. Only after she clearly says yes.",
          {"slot_id": {"type": "string"},
           "for_person": {"type": "string", "description": "self, or a family member's id or name, e.g. toddler or Leo"}},
          ["slot_id"]),
    _decl("get_records", "Medical record transfer requests from previous providers and their status."),
    _decl("update_record_status", "Change a record request status. Only after she confirms.",
          {"record_id": {"type": "string"}, "status": {"type": "string", "enum": ["not_requested", "requested", "received"]}},
          ["record_id", "status"]),
    _decl("get_labs", "Her lab panels and upcoming labs."),
    _decl("get_plan", "Her activity or training plan from today.", {"days": {"type": "integer", "minimum": 1, "maximum": 21}}),
    _decl("adjust_plan_day", "Replace one day of her plan, e.g. swap a tempo run for an easy run. Only after she confirms. Pregnancy-safe if pregnant.",
          {"date": {"type": "string", "description": "YYYY-MM-DD"},
           "activity": {"type": "string"},
           "duration_min": {"type": "integer", "minimum": 0},
           "intensity": {"type": "string", "enum": ["rest", "easy", "moderate", "hard"]},
           "reason": {"type": "string", "description": "Short reason shown to her"}},
          ["date", "activity", "duration_min", "intensity", "reason"]),
]


def live_config(user_id: str) -> types.LiveConnectConfig:
    """Gemini Live config for a voice session with this persona."""
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=settings.EM_VOICE))
        ),
        system_instruction=build_system_prompt(user_id),
        tools=[types.Tool(function_declarations=TOOL_DECLARATIONS)],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
    )


# ---------- Relay ----------

class VoiceSession:
    """One browser WebSocket bridged to one Gemini Live session."""

    def __init__(self, ws: WebSocket, user_id: str, voice_alerts: bool):
        """Set up per-session state. Call run() to start relaying."""
        self.ws = ws
        self.user_id = user_id
        self.voice_alerts = voice_alerts
        self.session: live.AsyncSession | None = None
        self.user_turns: list[str] = []  # finished user turns, for the check-in transcript
        self.current_turn = ""
        self.urgent = False
        self.muted = False  # drop Em's audio after an escalation until she speaks again
        self.mute_turn_done = False

    async def send_json(self, event: dict[str, Any]) -> None:
        """Send one VoiceEvent to the browser."""
        await self.ws.send_text(json.dumps(event, default=str))

    async def run(self) -> None:
        """Relay audio both ways until either side ends."""
        try:
            async with gemini.live_session(live_config(self.user_id), label=f"voice user={self.user_id}") as (session, model):
                self.session = session
                await self.send_json({"type": "ready", "model": model})
                await session.send_realtime_input(text=KICKOFF)
                tasks = {asyncio.create_task(self._from_browser()), asyncio.create_task(self._from_gemini())}
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    exc = task.exception()
                    if exc and not isinstance(exc, WebSocketDisconnect):
                        raise exc
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.exception("voice session failed user=%s", self.user_id)
            try:
                await self.send_json({"type": "error", "message": f"Voice session ended: {type(exc).__name__}"})
            except Exception:
                pass
        finally:
            try:
                await self.ws.close()
            except Exception:
                pass

    async def _from_browser(self) -> None:
        """Forward mic audio and typed text to Gemini."""
        assert self.session is not None
        while True:
            msg = await self.ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("bytes"):
                await self.session.send_realtime_input(audio=types.Blob(data=msg["bytes"], mime_type=MIC_MIME))
            elif msg.get("text"):
                event = json.loads(msg["text"])
                if event.get("type") == "end":
                    return
                if event.get("type") == "text" and (text := str(event.get("text", "")).strip()):
                    await self._on_user_text(text, final=True)
                    await self.session.send_realtime_input(text=text)

    async def _from_gemini(self) -> None:
        """Forward Em's audio, transcripts, and events to the browser, and run tool calls."""
        assert self.session is not None
        while True:
            got_any = False
            async for msg in self.session.receive():  # ends after each turn_complete, so loop
                got_any = True
                if msg.tool_call:
                    await self._handle_tool_call(msg.tool_call)
                sc = msg.server_content
                if sc is None:
                    continue
                if sc.input_transcription and sc.input_transcription.text:
                    await self._on_user_text(sc.input_transcription.text, final=False)
                if sc.interrupted:
                    await self.send_json({"type": "interrupted"})
                if sc.model_turn and not self.muted:
                    for part in sc.model_turn.parts or []:
                        if part.inline_data and part.inline_data.data:
                            await self.ws.send_bytes(part.inline_data.data)
                if sc.output_transcription and sc.output_transcription.text and not self.muted:
                    await self.send_json({"type": "transcript", "role": "em", "text": sc.output_transcription.text})
                if sc.turn_complete:
                    self._finish_user_turn()
                    if self.muted:
                        self.mute_turn_done = True
                    await self.send_json({"type": "turn_complete"})
            if not got_any:  # Gemini closed the stream
                return

    async def _on_user_text(self, text: str, *, final: bool) -> None:
        """Track what she said, echo it to the browser, and check for urgent signs."""
        if self.muted and self.mute_turn_done:
            self.muted = False  # she is talking again after the escalation, let Em respond
        self.current_turn += text if not final else f" {text}"
        await self.send_json({"type": "transcript", "role": "user", "text": text})
        if not self.muted and is_urgent(self.current_turn):
            await self._escalate("transcript")
        if final:
            self._finish_user_turn()

    def _finish_user_turn(self) -> None:
        """Move the in-progress user turn into the session transcript."""
        if self.current_turn.strip():
            self.user_turns.append(self.current_turn.strip())
        self.current_turn = ""

    async def _escalate(self, source: str) -> None:
        """Show the fixed URGENT_ESCALATION text and mute Em's own words about it."""
        if self.muted:
            return  # already escalated this turn
        self.urgent = True
        self.muted = True
        self.mute_turn_done = False
        logger.warning("urgent escalation user=%s source=%s", self.user_id, source)
        await self.send_json({"type": "urgent", "message": URGENT_ESCALATION, "speak": self.voice_alerts})

    async def _handle_tool_call(self, tool_call: types.LiveServerToolCall) -> None:
        """Run each requested tool and send the results back to Gemini."""
        assert self.session is not None
        responses = []
        for fc in tool_call.function_calls or []:
            args = dict(fc.args or {})
            logger.info("voice tool user=%s name=%s args=%s", self.user_id, fc.name, args)
            result = await self._run_tool(fc.name or "", args)
            responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response=result))
        await self.session.send_tool_response(function_responses=responses)

    async def _run_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch one tool call. Errors go back to Gemini as {"error": ...}."""
        if name == "flag_urgent":
            await self._escalate("model")
            return {"shown": True, "note": "The app is showing her the fixed safety message. Add no medical advice. When she speaks again, be gentle and supportive."}
        if name == "log_checkin":
            return await self._log_checkin(args)
        fn = TOOLS.get(name)
        if fn is None:
            return {"error": f"Unknown tool {name}"}
        try:
            outcome = fn(self.user_id, args)
        except ToolError as exc:
            return {"error": str(exc)}
        await self.send_json({"type": "tool", "name": name, "summary": outcome.summary, "changed": outcome.changed})
        return outcome.result

    async def _log_checkin(self, args: dict[str, Any]) -> dict[str, Any]:
        """Save a CheckinResult built from Em's scores and her actual words."""
        try:
            parsed = LogCheckinArgs.model_validate(args)
        except ValidationError as exc:
            return {"error": f"Invalid check-in: {exc}"}
        transcript = " ".join([*self.user_turns, self.current_turn.strip()]).strip() or "(voice check-in)"
        cycle = store.get(self.user_id, "cycle", None) or {}
        checkin = CheckinResult(
            id=f"ci_{self.user_id}_{uuid.uuid4().hex[:8]}",
            created_at=datetime.combine(today(self.user_id), datetime.now().time().replace(microsecond=0)),
            transcript=transcript,
            cycle_phase=cycle.get("phase"),
            urgent=self.urgent,
            escalation_message=URGENT_ESCALATION if self.urgent else None,
            **parsed.model_dump(),
        )
        saved = checkin.model_dump(mode="json")
        store.save(self.user_id, "checkins", [*store.get(self.user_id, "checkins", []), saved])
        await self.send_json({"type": "checkin", "checkin": saved})
        await self.send_json({"type": "tool", "name": "log_checkin", "summary": "Saved today's check-in", "changed": True})
        return {"saved": True, "id": checkin.id}
