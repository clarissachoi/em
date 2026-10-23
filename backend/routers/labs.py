"""Lab panels and plain-language explanations. /labs/explain calls Gemini."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

import gemini
from data import store
from deps import get_user_id
from models import LabExplainRequest, LabExplanation, LabPanel, LabsResponse
from prompts import LAB_EXPLAIN_PROMPT, LAB_PREGNANCY_RULES, lab_disclaimer

router = APIRouter(tags=["labs"])
logger = logging.getLogger("emcare.labs")

# (user_id, panel_id) -> explanation. Panels never change, so one Gemini call per panel per server run.
_cache: dict[tuple[str, str], LabExplanation] = {}


def _visible_panels(user_id: str) -> list[dict[str, Any]]:
    """Visible panels plus locked ones whose record is received, however that status was set."""
    labs = store.get(user_id, "labs", {})
    received = {r["id"] for r in store.get(user_id, "records", []) if r["status"] == "received"}
    unlocked = [lp["panel"] for lp in labs.get("locked_panels", []) if lp["unlocked_by_record"] in received]
    seen = {p["id"] for p in labs.get("panels", [])}
    return [*labs.get("panels", []), *(p for p in unlocked if p["id"] not in seen)]


def _context(user_id: str, panel: dict[str, Any]) -> dict[str, Any]:
    """The slice of persona data Gemini needs to personalize a lab explanation. Never the whole seed."""
    data = store.get_user(user_id)
    profile = data["profile"]
    goals = data.get("goals", {})
    context = {
        "profile": {k: profile.get(k) for k in ("name", "age", "life_stage", "pregnancy", "primary_goal")},
        "goals": {k: goals.get(k) for k in ("focus_areas", "activity_level", "target_date")},
        "panel": panel,
        "recent_runs": [
            {k: r.get(k) for k in ("date", "name", "distance_mi", "perceived_effort", "felt", "note")}
            for r in data.get("strava_runs", [])[-4:]
        ],
        "recent_checkins": [
            {k: c.get(k) for k in ("created_at", "transcript", "energy", "sleep_quality", "symptoms")}
            for c in data.get("checkins", [])[-3:]
        ],
        "upcoming_labs": data.get("labs", {}).get("upcoming", []),
    }
    return {k: v for k, v in context.items() if v}


@router.get("/labs")
def list_labs(user_id: str = Depends(get_user_id)) -> LabsResponse:
    """Return visible lab panels (newest first) and upcoming tests."""
    panels = sorted((LabPanel.model_validate(p) for p in _visible_panels(user_id)), key=lambda p: p.date, reverse=True)
    return LabsResponse(panels=panels, upcoming=store.get(user_id, "labs", {}).get("upcoming", []))


@router.post("/labs/explain")
async def explain_labs(body: LabExplainRequest, user_id: str = Depends(get_user_id)) -> LabExplanation:
    """Explain one panel in plain language with Gemini, personalized to the persona."""
    panel = next((p for p in _visible_panels(user_id) if p["id"] == body.panel_id), None)
    if panel is None:
        raise HTTPException(status_code=404, detail=f"Lab panel {body.panel_id!r} not found")
    if (user_id, body.panel_id) in _cache:
        return _cache[(user_id, body.panel_id)]

    profile = store.get(user_id, "profile")
    pregnant = profile.get("life_stage") == "pregnant"
    prompt = LAB_EXPLAIN_PROMPT.format(
        name=profile["name"],
        clinician="her OB" if pregnant else "her doctor",
        pregnancy_rules=LAB_PREGNANCY_RULES if pregnant else "",
        context=json.dumps(_context(user_id, panel), default=str),
    )
    try:
        result = await gemini.generate_structured(prompt, LabExplanation)
    except Exception as exc:
        logger.warning("lab explain failed for %s/%s: %s", user_id, body.panel_id, type(exc).__name__)
        raise HTTPException(status_code=503, detail="Em could not explain these labs right now. Please try again.") from exc

    # Safety copy is fixed, never model-written, and user-facing text never has em dashes.
    clean = json.loads(result.model_dump_json().replace("\\u2014", ", ").replace("—", ", "))
    clean["disclaimer"] = lab_disclaimer(pregnant)
    explanation = LabExplanation.model_validate(clean)
    _cache[(user_id, body.panel_id)] = explanation
    return explanation
