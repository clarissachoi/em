"""Insurance policy Q&A. MOCK: canned answer."""

from fastapi import APIRouter, Depends, File, Form, UploadFile

from data import store
from deps import get_user_id
from models import PolicyAnswer

router = APIRouter(tags=["policy"])


@router.post("/policy/review")
async def review_policy(
    question: str = Form(...),
    file: UploadFile | None = File(default=None),
    user_id: str = Depends(get_user_id),
) -> PolicyAnswer:
    """Answer a coverage question from an uploaded PDF or the seeded sample policy."""
    # TODO(Dev 2): pass the PDF (or seeded sample policy) and question to gemini.generate_structured.
    return PolicyAnswer.model_validate(store.get(user_id, "mock")["policy_answer"])
