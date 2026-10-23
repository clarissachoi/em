"""GET /home dashboard. MOCK: assembled from seed data."""

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import Alert, CareChecklist, CareItem, CheckinResult, HomeData, Readiness

router = APIRouter(tags=["home"])


@router.get("/home")
def get_home(user_id: str = Depends(get_user_id)) -> HomeData:
    """Return the Home dashboard for the current persona."""
    user = store.get_user(user_id)
    home = user["home"]
    profile = user["profile"]

    alerts = [Alert.model_validate(a) for a in home["alerts"]]
    if not any(r["overdue"] for r in user["records"]):
        alerts = [a for a in alerts if a.type != "records"]

    checklist = None
    if user["care_team"]:
        items = [CareItem.model_validate(i) for i in user["care_team"]["items"]]
        checklist = CareChecklist(found=sum(i.done for i in items), total=len(items), items=items)

    recent = sorted(user["checkins"], key=lambda c: c["created_at"], reverse=True)[:7]
    plan = user["training_plan"]

    return HomeData(
        user_name=profile["name"],
        greeting=home["greeting"],
        alerts=alerts,
        quote=home["quote"],
        readiness=Readiness.model_validate(home["readiness"]) if home["readiness"] else None,
        today_plan=plan[0]["activity"] if plan else None,
        nutrition_tip=home["nutrition_tip"],
        pregnancy_week=profile["pregnancy"]["week"] if profile["pregnancy"] else None,
        care_checklist=checklist,
        recent_checkins=[CheckinResult.model_validate(c) for c in recent],
    )
