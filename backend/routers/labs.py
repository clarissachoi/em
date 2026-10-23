"""Lab panels and explanations. MOCK: seed data and a canned explanation."""

from fastapi import APIRouter, Depends, HTTPException

from data import store
from deps import get_user_id
from models import LabExplainRequest, LabExplanation, LabPanel, LabsResponse

router = APIRouter(tags=["labs"])


def _visible_panels(user_id: str) -> list[LabPanel]:
    """Panels the user can see. Some only appear once their record is marked received."""
    received = {r["id"] for r in store.get(user_id, "records") if r["status"] == "received"}
    panels = store.get(user_id, "labs")["panels"]
    return [
        LabPanel.model_validate(p)
        for p in panels
        if p.get("available_after_record") is None or p["available_after_record"] in received
    ]


@router.get("/labs")
def list_labs(user_id: str = Depends(get_user_id)) -> LabsResponse:
    """Return visible lab panels (newest first) and upcoming tests."""
    panels = sorted(_visible_panels(user_id), key=lambda p: p.date, reverse=True)
    return LabsResponse(panels=panels, upcoming=store.get(user_id, "labs")["upcoming"])


@router.post("/labs/explain")
def explain_labs(body: LabExplainRequest, user_id: str = Depends(get_user_id)) -> LabExplanation:
    """Explain a panel in plain language. MOCK: canned explanation."""
    if body.panel_id not in {p.id for p in _visible_panels(user_id)}:
        raise HTTPException(status_code=404, detail=f"Lab panel {body.panel_id!r} not found")
    # TODO(Dev 2): explain with gemini.generate_structured. Always keep a review-with-your-doctor disclaimer.
    return LabExplanation.model_validate(store.get(user_id, "mock")["lab_explanation"])
