"""Shared FastAPI dependencies."""

from fastapi import Header, HTTPException

from data import store


def get_user_id(x_user_id: str = Header(default="maya")) -> str:
    """Return the persona id from the X-User-Id header, defaulting to maya."""
    if x_user_id not in store.user_ids():
        raise HTTPException(status_code=404, detail=f"Unknown user {x_user_id!r}. Valid: {store.user_ids()}")
    return x_user_id
