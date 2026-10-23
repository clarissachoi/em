"""GET /suggestions for the em.well page. Gemini, personalized, with safety rules enforced in code.

Curated path: when the seed has wellness_cards (fixed titles, venues, images), Gemini only writes each reason.
Generated path: otherwise Gemini suggests the cards.
"""

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

import gemini
from data import store
from deps import get_user_id
from models import CardReasons, Suggestion, SuggestionDraft, SuggestionIdea, Suggestions
from prompts import EM_SYSTEM_PROMPT, WELLNESS_PREGNANCY_RULES, WELLNESS_PROMPT, WELLNESS_REASONS_PROMPT
from routers.home import recent_doctor_note
from routers.labs import _visible_panels

router = APIRouter(tags=["next steps"])
logger = logging.getLogger("emcare.suggestions")

SECTIONS = ("nutrition", "workouts", "classes", "sleep")

# (user_id, context hash) -> result. A new check-in, goal, or plan change gives a new hash and a fresh call.
_cache: dict[tuple[str, str], Suggestions] = {}

SUPPLEMENT = re.compile(r"\b(supplements?|capsules?|pills?|tablets?|gumm(?:y|ies)|powders?|\d+\s?mg)\b", re.I)
PREGNANCY_UNSAFE = re.compile(
    r"\b(sauna|hot tub|jacuzzi|steam room|hot yoga|bikram|contact sports?|kickboxing|boxing|skiing|horseback|scuba|"
    r"sushi|sashimi|raw fish|unpasteuri[sz]ed|alcohol|wine|beer|swordfish|king mackerel|lying flat on (?:your|her) back)\b",
    re.I,
)
NEGATION = re.compile(r"\b(no|avoid|avoiding|without|skip|instead of|not)\s+(\w+\s+){0,2}$", re.I)


def _unsafe(text: str, pattern: re.Pattern[str]) -> str | None:
    """First match of pattern that is not negated ("avoid sushi" is fine), else None."""
    for m in pattern.finditer(text):
        if not NEGATION.search(text[max(0, m.start() - 30):m.start()]):
            return m.group(0)
    return None


def _no_em_dash(text: str) -> str:
    """User-facing copy never has em dashes."""
    return text.replace("—", ", ")


def _headline(data: dict[str, Any], today: date) -> str:
    """Focus line from her data, e.g. 'Low ferritin · Marathon in 16 weeks'. Never model-written."""
    profile, goals = data["profile"], data.get("goals", {})
    parts = []
    if profile.get("pregnancy"):
        parts.append(f"Week {profile['pregnancy']['week']}")
    panels = sorted(_visible_panels(profile["id"]), key=lambda p: p["date"], reverse=True)
    flagged = [r for r in panels[0]["results"] if r["flag"] != "normal"] if panels else []
    parts += [f"{r['flag'].title()} {r['marker'].lower()}" for r in flagged[:1]]
    if profile.get("pregnancy"):
        parts += [a.capitalize() for a in goals.get("focus_areas", []) if a in ("sleep", "walking", "nutrition", "energy")][:2]
    elif goals.get("target_date"):
        weeks = round((date.fromisoformat(goals["target_date"]) - today).days / 7)
        parts.append(f"{goals['primary_goal'].split(' on ')[0]} in {weeks} weeks")
    return " · ".join(parts) or goals.get("primary_goal", "")


def _context(data: dict[str, Any], today: date) -> dict[str, Any]:
    """The slice of persona data Gemini needs for suggestions. Never the whole seed."""
    profile, goals = data["profile"], data.get("goals", {})
    week_end = (today + timedelta(days=7)).isoformat()
    panels = sorted(_visible_panels(profile["id"]), key=lambda p: p["date"], reverse=True)
    visit = recent_doctor_note(data, today)
    notes = (visit or {}).get("doctor_notes")
    context = {
        "today": f"{today:%A} {today.isoformat()}",
        "profile": {k: profile.get(k) for k in ("name", "age", "life_stage", "primary_goal", "prior_pregnancies")},
        "pregnancy": {k: (data.get("pregnancy_tracker") or {}).get(k) for k in ("week", "trimester")} if profile.get("pregnancy") else None,
        "goals": {k: goals.get(k) for k in ("focus_areas", "activity_level", "dietary_prefs", "notes", "target_date")},
        "out_of_range_labs": [
            {k: r[k] for k in ("marker", "value", "unit", "flag")} for r in (panels[0]["results"] if panels else []) if r["flag"] != "normal"
        ],
        "latest_doctor_note": {k: notes.get(k) for k in ("author", "written_on", "assessment", "plan")} if notes else None,
        "medications_from_her_doctor": data.get("medications"),
        "recent_checkins": [
            {k: c.get(k) for k in ("created_at", "transcript", "energy", "stress", "sleep_quality", "symptoms")}
            for c in data.get("checkins", [])[-3:]
        ],
        "plan_this_week": [d for d in data.get("plan", []) if today.isoformat() <= d["date"] < week_end],
        "free_windows": data.get("calendar", {}).get("free_windows"),
        "travel_this_week": [
            {k: e.get(k) for k in ("title", "start", "end")}
            for e in data.get("calendar", {}).get("events", [])
            if e.get("type") == "travel" and today.isoformat() <= e["start"][:10] < week_end
        ],
        "wearable_last_7_days": [
            {k: w.get(k) for k in ("date", "sleep_hours", "sleep_score", "steps", "walk_minutes", "travel_day", "workload") if k in w}
            for w in data.get("wearable", [])[-7:]
        ],
        "recent_runs": [{k: r.get(k) for k in ("date", "name", "distance_mi", "felt")} for r in data.get("strava_runs", [])[-4:]],
        "walking_routes": data.get("walking_routes"),
        "sleep_notes": data.get("sleep"),
        "cycle_phase": (data.get("cycle") or {}).get("phase"),
    }
    return {k: v for k, v in context.items() if v}


def _when_label(when: str | None, today: date) -> str | None:
    """ISO datetime -> 'Today · 7:30 PM', 'Tonight · 9:30 PM', 'Tomorrow · 9:00 AM', 'Wed · 7:00 AM'. Other text as is."""
    if not when:
        return None
    try:
        at = datetime.fromisoformat(when)
    except ValueError:
        return when
    delta = (at.date() - today).days
    day = ("Tonight" if at.hour >= 21 else "Today") if delta == 0 else "Tomorrow" if delta == 1 else f"{at:%a}"
    return f"{day} · {at:%-I:%M %p}"


def _near_tag(card: dict[str, Any], events: list[dict[str, Any]]) -> str | None:
    """'1.4 mi from your Chicago hotel' when a hotel-relative card falls during a trip with a hotel."""
    if card.get("distance_from") != "hotel" or not card.get("distance_mi"):
        return None
    try:
        at = datetime.fromisoformat(card["when"])
    except (TypeError, ValueError):
        return None
    for e in events:
        if e.get("type") == "travel" and e.get("hotel") and datetime.fromisoformat(e["start"]) <= at <= datetime.fromisoformat(e["end"]):
            city = (e.get("location") or e["hotel"]).split(",")[0]
            return f"{card['distance_mi']:g} mi from your {city} hotel"
    return None


def _clean(items: list[SuggestionIdea], pregnant: bool, section: str) -> list[Suggestion]:
    """Strip em dashes and drop anything Em suggested that is unsafe and slipped past the prompt."""
    kept = []
    for s in items:
        text = f"{s.title} {s.description}"
        bad = _unsafe(text, SUPPLEMENT) or (pregnant and _unsafe(text, PREGNANCY_UNSAFE))
        if bad:
            logger.warning("dropped %s suggestion %r (matched %r)", section, s.title, bad)
            continue
        kept.append(Suggestion(**{k: _no_em_dash(v) if isinstance(v, str) else v for k, v in s.model_dump().items()}))
    return kept


def _medication_card(card: dict[str, Any], medications: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Fill a doctor card from the matching medication record. None until her doctor has actually recommended it."""
    med = next((m for m in medications if card["requires_medication"].lower() in m.get("name", "").lower()), None)
    if med is None:
        return None
    by = med.get("prescribed_by", "your doctor")
    return {
        **card,
        "title": f"{med['name']} ({med['dose']})" if med.get("dose") else med["name"],
        "description": ", ".join(x for x in (med.get("schedule"), med.get("timing")) if x) + f", as recommended by {by}.",
        "default_reason": f"Recommended by {by}. Ask them before changing how you take it.",
        "when": med.get("when") or card.get("when"),
    }


async def _curated(data: dict[str, Any], today: date, context: dict[str, Any], pregnant: bool) -> dict[str, list[Suggestion]]:
    """Curated cards from the seed. Gemini writes reasons for Em's cards; doctor cards keep fixed copy."""
    cards = data["wellness_cards"]
    em_cards = [c for c in cards if c.get("source") != "doctor"]
    reasons: dict[str, str] = {}
    if em_cards:
        prompt = WELLNESS_REASONS_PROMPT.format(
            name=data["profile"]["name"],
            cards=json.dumps([{k: c.get(k) for k in ("id", "title", "description", "where", "when")} for c in em_cards]),
            context=json.dumps(context, default=str),
        )
        try:
            result = await gemini.generate_structured(prompt, CardReasons, system_instruction=EM_SYSTEM_PROMPT, thinking_level="low")
            for r in result.reasons:
                if not _unsafe(r.reason, SUPPLEMENT):
                    reasons[r.id] = _no_em_dash(r.reason)
        except Exception as exc:  # fall back to the seed's default reasons
            logger.warning("card reasons failed: %s", type(exc).__name__)

    events = data.get("calendar", {}).get("events", [])
    out: dict[str, list[Suggestion]] = {s: [] for s in SECTIONS}
    for c in cards:
        if c.get("requires_medication"):
            c = _medication_card(c, data.get("medications") or [])
            if c is None:
                continue
        if c.get("source") != "doctor":
            text = f"{c['title']} {c['description']}"
            if _unsafe(text, SUPPLEMENT) or (pregnant and _unsafe(text, PREGNANCY_UNSAFE)):
                logger.warning("dropped curated card %r", c["title"])
                continue
        out[c["section"]].append(Suggestion(
            title=c["title"], description=c["description"], reason=reasons.get(c["id"], c["default_reason"]),
            duration_min=c.get("duration_min"), tag=c["tag"], when=_when_label(c.get("when"), today), where=c.get("where"),
            image=c.get("image"), distance_mi=c.get("distance_mi"), near_tag=_near_tag(c, events), source=c.get("source", "em"),
        ))
    return out


async def _generated(data: dict[str, Any], context: dict[str, Any], pregnant: bool, user_id: str) -> dict[str, list[Suggestion]]:
    """Gemini suggests the cards."""
    prompt = WELLNESS_PROMPT.format(
        name=data["profile"]["name"],
        counts="2 workouts, 1 class, 3 nutrition, 0 sleep",
        pregnancy_rules=WELLNESS_PREGNANCY_RULES if pregnant else "",
        context=json.dumps(context, default=str),
    )
    try:
        draft = await gemini.generate_structured(prompt, SuggestionDraft, system_instruction=EM_SYSTEM_PROMPT, thinking_level="low")
    except Exception as exc:
        logger.warning("suggestions failed user=%s err=%s", user_id, type(exc).__name__)
        raise HTTPException(status_code=503, detail="Em could not put together suggestions right now. Please try again.") from exc
    return {section: _clean(getattr(draft, section), pregnant, section) for section in SECTIONS}


@router.get("/suggestions")
async def get_suggestions(user_id: str = Depends(get_user_id)) -> Suggestions:
    """Personalized move and eat ideas for em.well."""
    data = store.get_user(user_id)
    today = date.fromisoformat(data["as_of"])
    pregnant = data["profile"].get("life_stage") == "pregnant"
    context = _context(data, today)
    fingerprint = json.dumps([context, data.get("wellness_cards")], sort_keys=True, default=str)
    key = (user_id, hashlib.sha256(fingerprint.encode()).hexdigest())
    if key in _cache:
        return _cache[key]

    sections = await (_curated(data, today, context, pregnant) if data.get("wellness_cards") else _generated(data, context, pregnant, user_id))
    result = Suggestions(headline=_headline(data, today), **sections)
    _cache[key] = result
    return result
