"""Goals, also used by onboarding. PUT persists to state.json."""

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import Goals

router = APIRouter(tags=["next steps"])


@router.get("/goals")
def get_goals(user_id: str = Depends(get_user_id)) -> Goals:
    """Return the persona's goals."""
    return Goals.model_validate(store.get(user_id, "goals"))


@router.put("/goals")
def put_goals(goals: Goals, user_id: str = Depends(get_user_id)) -> Goals:
    """Replace the persona's goals."""
    store.save(user_id, "goals", goals.model_dump(mode="json"))
    return goals
