"""7-day activity plan."""

from datetime import date

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import PlanDay

router = APIRouter(tags=["next steps"])


@router.get("/plan")
def get_plan(user_id: str = Depends(get_user_id)) -> list[PlanDay]:
    """Return the next 7 days of the plan, counted from the seed's as_of date (demo "today")."""
    today = date.fromisoformat(store.get(user_id, "as_of"))
    days = sorted((PlanDay.model_validate(d) for d in store.get(user_id, "plan")), key=lambda d: d.date)
    return [d for d in days if d.date >= today][:7]
