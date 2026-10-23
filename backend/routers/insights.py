"""Cross-data insights. MOCK: canned seed data."""

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import Insight

router = APIRouter(tags=["next steps"])


@router.get("/insights")
def get_insights(user_id: str = Depends(get_user_id)) -> list[Insight]:
    """Return patterns Em noticed across wearables, check-ins, and calendar."""
    # TODO(Dev 3): derive from wearables, runs, calendar, and check-ins.
    return [Insight.model_validate(i) for i in store.get(user_id, "mock")["insights"]]
