"""POST /checkin. MOCK: returns canned seed data. Dev 1 replaces with Gemini."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from data import store
from deps import get_user_id
from models import CheckinResult

router = APIRouter(tags=["home"])


@router.post("/checkin")
async def create_checkin(
    audio: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    user_id: str = Depends(get_user_id),
) -> CheckinResult:
    """Analyze a voice or text check-in. Currently returns a canned result."""
    if audio is None and not text:
        raise HTTPException(status_code=422, detail="Provide audio, text, or both.")
    mock = store.get(user_id, "mock")["checkin"]
    # TODO(Dev 1): send audio/text to gemini.generate_structured, check URGENT_ESCALATION rules, save the result.
    return CheckinResult(
        id=f"chk-{user_id}-{uuid.uuid4().hex[:8]}",
        created_at=datetime.now().replace(microsecond=0),
        transcript=text or mock["transcript"],
        mood=mock["mood"],
        energy=mock["energy"],
        stress=mock["stress"],
        sleep_quality=mock["sleep_quality"],
        symptoms=mock["symptoms"],
        cycle_phase=mock["cycle_phase"],
        em_reply=mock["em_reply"],
        insight=mock["insight"],
        urgent=False,
        escalation_message=None,
    )
