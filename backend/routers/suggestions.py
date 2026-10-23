"""GET /suggestions for the em.well page. Gemini, personalized, with safety rules enforced in code."""

import hashlib
import json
import logging
import re
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

import gemini
from data import store
from deps import get_user_id
from models import Suggestion, SuggestionDraft, Suggestions
from prompts import EM_SYSTEM_PROMPT, WELLNESS_PREGNANCY_RULES, WELLNESS_PROMPT
from routers.labs import _visible_panels

router = APIRouter(tags=["next steps"])
logger = logging.getLogger("emcare.suggestions")

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
    context = {
        "today": f"{today:%A} {today.isoformat()}",
        "profile": {k: profile.get(k) for k in ("name", "age", "life_stage", "primary_goal", "prior_pregnancies")},
        "pregnancy": {k: (data.get("pregnancy_tracker") or {}).get(k) for k in ("week", "trimester")} if profile.get("pregnancy") else None,
        "goals": {k: goals.get(k) for k in ("focus_areas", "activity_level", "dietary_prefs", "notes", "target_date")},
        "out_of_range_labs": [
            {k: r[k] for k in ("marker", "value", "unit", "flag")} for r in (panels[0]["results"] if panels else []) if r["flag"] != "normal"
        ],
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


def _clean(items: list[Suggestion], pregnant: bool, section: str) -> list[Suggestion]:
    """Strip em dashes and drop anything unsafe that slipped past the prompt."""
    kept = []
    for s in items:
        text = f"{s.title} {s.description}"
        bad = _unsafe(text, SUPPLEMENT) or (pregnant and _unsafe(text, PREGNANCY_UNSAFE))
        if bad:
            logger.warning("dropped %s suggestion %r (matched %r)", section, s.title, bad)
            continue
        kept.append(Suggestion.model_validate_json(s.model_dump_json().replace("\\u2014", ", ").replace("—", ", ")))
    return kept


@router.get("/suggestions")
async def get_suggestions(user_id: str = Depends(get_user_id)) -> Suggestions:
    """Personalized move, eat, and rest ideas for em.well."""
    data = store.get_user(user_id)
    today = date.fromisoformat(data["as_of"])
    pregnant = data["profile"].get("life_stage") == "pregnant"
    context = _context(data, today)
    key = (user_id, hashlib.sha256(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest())
    if key in _cache:
        return _cache[key]

    prompt = WELLNESS_PROMPT.format(
        name=data["profile"]["name"],
        counts=f"2 workouts, 1 class, 3 nutrition, {2 if pregnant else 1} sleep",
        pregnancy_rules=WELLNESS_PREGNANCY_RULES if pregnant else "",
        context=json.dumps(context, default=str),
    )
    try:
        draft = await gemini.generate_structured(prompt, SuggestionDraft, system_instruction=EM_SYSTEM_PROMPT, thinking_level="low")
    except Exception as exc:
        logger.warning("suggestions failed user=%s err=%s", user_id, type(exc).__name__)
        raise HTTPException(status_code=503, detail="Em could not put together suggestions right now. Please try again.") from exc

    result = Suggestions(
        headline=_headline(data, today),
        **{section: _clean(getattr(draft, section), pregnant, section) for section in ("nutrition", "workouts", "classes", "sleep")},
    )
    _cache[key] = result
    return result
