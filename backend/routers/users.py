"""Persona list and profile."""

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import UserProfile, UserSummary

router = APIRouter(tags=["users"])


@router.get("/users")
def list_users() -> list[UserSummary]:
    """Return every demo persona for the switcher."""
    return [UserSummary.model_validate(store.get(u, "summary")) for u in store.user_ids()]


@router.get("/me")
def get_me(user_id: str = Depends(get_user_id)) -> UserProfile:
    """Return the current persona's profile."""
    return UserProfile.model_validate(store.get(user_id, "profile"))
