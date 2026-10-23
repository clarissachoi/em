"""7-day adaptive plan. MOCK: seed plan and a canned adapted plan."""

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import PlanDay

router = APIRouter(tags=["next steps"])


@router.get("/plan")
def get_plan(user_id: str = Depends(get_user_id)) -> list[PlanDay]:
    """Return the next 7 days of the persona's plan."""
    return [PlanDay.model_validate(d) for d in store.get(user_id, "training_plan")[:7]]


@router.post("/plan/adapt")
def adapt_plan(user_id: str = Depends(get_user_id)) -> list[PlanDay]:
    """Re-plan using sleep, travel, cycle/pregnancy, labs, and check-ins. MOCK: canned result."""
    # TODO(Dev 3): build persona context from store and call gemini.generate_structured. Pregnancy-safe for Jasmine.
    return [PlanDay.model_validate(d) for d in store.get(user_id, "mock")["adapted_plan"]]
