"""GET /insights: cross-data patterns computed from seed data. No Gemini, so the numbers are always real."""

from statistics import mean
from typing import Any

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import Insight

router = APIRouter(tags=["next steps"])


def _split_avg(days: list[dict[str, Any]], test, field: str) -> tuple[float, float, int, int] | None:
    """Average of field on days that pass test vs days that don't, or None if either side is empty."""
    yes = [d[field] for d in days if d.get(field) is not None and test(d)]
    no = [d[field] for d in days if d.get(field) is not None and not test(d)]
    return (mean(yes), mean(no), len(yes), len(no)) if yes and no else None


@router.get("/insights")
def get_insights(user_id: str = Depends(get_user_id)) -> list[Insight]:
    """Patterns across wearables, runs, and check-ins, strongest first."""
    data = store.get_user(user_id)
    wearable = data.get("wearable", [])
    found: list[tuple[float, Insight]] = []  # (strength, insight)

    if any("walk_minutes" in d for d in wearable):
        s = _split_avg(wearable, lambda d: (d.get("walk_minutes") or 0) >= 30, "sleep_hours")
        if s and s[0] - s[1] >= 0.3:
            found.append((s[0] - s[1], Insight(
                text="You sleep better on days you walk 30+ minutes",
                evidence=f"{s[0]:.1f} h of sleep on {s[2]} walk days vs {s[1]:.1f} h on the other {s[3]} days",
            )))

    if any(d.get("travel_day") for d in wearable):
        s = _split_avg(wearable, lambda d: bool(d.get("travel_day")), "sleep_hours")
        if s and s[1] - s[0] >= 0.5:
            found.append((s[1] - s[0], Insight(
                text="Your sleep drops on travel days",
                evidence=f"{s[0]:.1f} h on {s[2]} travel days vs {s[1]:.1f} h at home",
            )))

    if any(d.get("workload") for d in wearable):
        s = _split_avg(wearable, lambda d: d.get("workload") == "heavy", "sleep_score")
        if s and s[1] - s[0] >= 5:
            found.append(((s[1] - s[0]) / 10, Insight(
                text="Heavy work days cut into your sleep",
                evidence=f"Sleep score {s[0]:.0f} after {s[2]} heavy days vs {s[1]:.0f} on lighter days",
            )))

    runs = data.get("strava_runs", [])[-4:]
    flat = sum(r.get("felt") == "flat" for r in runs)
    if len(runs) >= 3 and flat >= 2:
        found.append((flat / 2, Insight(text="Your runs have felt flat lately", evidence=f"{flat} of your last {len(runs)} runs felt flat")))

    energies = [c["energy"] for c in data.get("checkins", [])[-5:] if c.get("energy")]
    if len(energies) >= 3 and mean(energies) <= 2.5:
        found.append((1.0, Insight(
            text="Your energy has been running low",
            evidence=f"Average energy {mean(energies):.1f} out of 5 across your last {len(energies)} check-ins",
        )))

    return [i for _, i in sorted(found, key=lambda x: x[0], reverse=True)]
