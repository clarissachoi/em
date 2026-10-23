"""Personalized suggestions. MOCK: canned seed data."""

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import Suggestions

router = APIRouter(tags=["next steps"])


@router.get("/suggestions")
def get_suggestions(user_id: str = Depends(get_user_id)) -> Suggestions:
    """Return nutrition, workout, class, and sleep suggestions."""
    # TODO(Dev 3): personalize from goals and latest check-in via Gemini. Pregnancy-safe for Jasmine.
    return Suggestions.model_validate(store.get(user_id, "mock")["suggestions"])
