"""Persona list and profile (shared)."""

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import UserProfile, UserSummary

router = APIRouter(tags=["users"])


@router.get("/users")
def list_users() -> list[UserSummary]:
    """Return every demo persona for the switcher."""
    return [UserSummary.model_validate(u["profile"]) for u in store.load().values()]


@router.get("/me")
def get_me(user_id: str = Depends(get_user_id)) -> UserProfile:
    """Return the current persona's profile."""
    return UserProfile.model_validate(store.get(user_id, "profile"))
