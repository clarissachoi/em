"""GET /home dashboard. Computed from seed data, no Gemini, so it loads instantly."""

from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import (
    Alert,
    CareChecklist,
    CareItem,
    CareNote,
    CheckinResult,
    FocusItem,
    HomeData,
    Metric,
    Readiness,
    TrendPoint,
)
from routers.labs import _visible_panels

router = APIRouter(tags=["home"])

IRON_MARKERS = {"ferritin", "iron", "hemoglobin"}


def _clamp(value: float) -> float:
    """Clamp to 0-100."""
    return max(0.0, min(100.0, value))


def _readiness_score(day: dict[str, Any], base_hrv: float, base_rhr: float) -> int:
    """Blend sleep score with HRV and resting HR relative to the persona's own baseline."""
    sleep = day.get("sleep_score") or 70
    hrv = _clamp(70 + (day["hrv_ms"] / base_hrv - 1) * 150) if day.get("hrv_ms") and base_hrv else 70
    rhr = _clamp(70 - (day["resting_hr"] / base_rhr - 1) * 300) if day.get("resting_hr") and base_rhr else 70
    return round(0.5 * sleep + 0.3 * hrv + 0.2 * rhr)


def _readiness_label(score: int) -> str:
    """Short label for a readiness score."""
    if score >= 80:
        return "Rested & Ready"
    if score >= 65:
        return "Rested & Rebuilding"
    if score >= 50:
        return "Recovering"
    return "Go Gently"


def _quote(score: int | None) -> str:
    """Subtitle under the greeting, matched to readiness."""
    if score is None or score >= 65:
        return "Fresh Start, Clear Focus"
    if score >= 50:
        return "Steady Steps, Kind Pace"
    return "Rest Is Progress Too"


def _greeting(name: str) -> str:
    """Time-of-day greeting from the server clock."""
    hour = datetime.now().hour
    part = "Morning" if hour < 12 else "Afternoon" if hour < 17 else "Evening"
    return f"Good {part}, {name}"


def _clock(hhmm: str) -> str:
    """'17:15' -> '5:15 PM'."""
    return datetime.strptime(hhmm, "%H:%M").strftime("%-I:%M %p")


def _free_window_start(calendar: dict[str, Any], today: date) -> str | None:
    """Start of the first free calendar window today, e.g. '6:30 AM'."""
    weekday = today.strftime("%a")
    for window in calendar.get("free_windows", []):
        if weekday in window.get("days", []):
            return _clock(window["start"])
    return None


def _flagged(user_id: str) -> list[dict[str, Any]]:
    """Out-of-range results from the newest visible lab panel."""
    panels = sorted(_visible_panels(user_id), key=lambda p: p["date"], reverse=True)
    return [r for r in panels[0]["results"] if r["flag"] != "normal"] if panels else []


def _alerts(data: dict[str, Any], today: date, flagged: list[dict[str, Any]], pregnant: bool) -> list[Alert]:
    """Travel, records, appointments, and labs worth surfacing this week."""
    week_end = today + timedelta(days=7)
    alerts = []
    for e in data.get("calendar", {}).get("events", []):
        if e.get("type") != "travel":  # other events can be recurring with time-only starts
            continue
        start = datetime.fromisoformat(e["start"]).date()
        if today <= start <= week_end:
            end = datetime.fromisoformat(e["end"]).date()
            alerts.append(Alert(type="travel", title=f"{e.get('location') or e['title']}, {start:%a} to {end:%a}",
                                detail="Em can adjust your plan around the trip.", severity="info"))
    for r in data.get("records", []):
        if r.get("overdue"):
            alerts.append(Alert(type="records", title=f"{r['item']} not received",
                                detail=f"Requested from {r['from_provider']}.", severity="warning"))
    for a in data.get("appointments", {}).get("upcoming", []):
        when = datetime.fromisoformat(a["datetime"])
        if today <= when.date() <= week_end:
            alerts.append(Alert(type="appointment", title=f"{a['specialty']} visit {when:%a %b %-d} at {when:%-I:%M %p}",
                                detail=a["provider"], severity="info"))
    for r in flagged:
        who = "your OB" if pregnant else "your doctor"
        alerts.append(Alert(type="lab", title=f"{r['marker']} is {r['flag']}",
                            detail=f"Review with {who}.", severity="warning"))
    return alerts


def _focus(data: dict[str, Any], today: date, flagged: list[dict[str, Any]], pregnant: bool) -> list[FocusItem]:
    """Today's Focus: workout, food, one care task, and a check-in if none today."""
    items = []
    plan_today = next((d for d in data.get("plan", []) if d["date"] == today.isoformat()), None)
    if plan_today:
        items.append(FocusItem(kind="workout", title=plan_today["activity"],
                               detail=f"{plan_today['duration_min']} min · {plan_today['intensity']}",
                               time=_free_window_start(data.get("calendar", {}), today)))

    low_iron = any(r["marker"].lower() in IRON_MARKERS and r["flag"] == "low" for r in flagged)
    if low_iron:
        items.append(FocusItem(kind="nutrition", title="Iron-rich lunch",
                               detail="Pair with vitamin C, keep coffee an hour away", time="12:30 PM"))
    elif pregnant:
        items.append(FocusItem(kind="nutrition", title="Protein and iron-rich snack",
                               detail="Greek yogurt with berries, or hummus and veggies", time="3:00 PM"))

    overdue = next((r for r in data.get("records", []) if r.get("overdue")), None)
    upcoming = sorted(data.get("appointments", {}).get("upcoming", []), key=lambda a: a["datetime"])
    soon = next((s for s in data.get("appointments", {}).get("suggested", []) if s.get("urgency") == "soon"), None)
    if overdue:
        days = (today - date.fromisoformat(overdue["requested_on"])).days if overdue.get("requested_on") else None
        items.append(FocusItem(kind="records", title=f"Follow up on {overdue['item'].lower()}",
                               detail=f"Requested from {overdue['from_provider']}" + (f" {days} days ago" if days else ""),
                               time=None))
    elif upcoming and datetime.fromisoformat(upcoming[0]["datetime"]).date() <= today + timedelta(days=7):
        a = upcoming[0]
        when = datetime.fromisoformat(a["datetime"])
        items.append(FocusItem(kind="appointment", title=f"{a['specialty']} visit {when:%a %b %-d}",
                               detail=a["provider"], time=f"{when:%-I:%M %p}"))
    elif soon:
        items.append(FocusItem(kind="appointment", title=f"Book {soon['specialty'].lower()}", detail=soon["reason"], time=None))

    checkins = data.get("checkins", [])
    if not checkins or datetime.fromisoformat(checkins[-1]["created_at"]).date() < today:
        items.append(FocusItem(kind="checkin", title="Check in with Em", detail="A quick voice check-in", time=None))
    return items


def _care_note(data: dict[str, Any], flagged: list[dict[str, Any]], pregnant: bool) -> CareNote | None:
    """Latest clinician visit summary; if the latest visit was only a lab draw, Em's note on a flagged result."""
    past = sorted(data.get("appointments", {}).get("past", []), key=lambda a: a["datetime"], reverse=True)
    visit = next((a for a in past if a.get("visit_summary") and a.get("specialty") != "Lab work"), None)
    if visit:
        return CareNote(author=visit["provider"], text=visit["visit_summary"]["summary"], source="visit")
    if flagged:
        r = flagged[0]
        who = "your OB" if pregnant else "your doctor"
        return CareNote(author="Em", text=f"Your {r['marker'].lower()} came back {r['flag']}. Worth reviewing with {who}.", source="em")
    return None


def _ask_suggestions(data: dict[str, Any], flagged: list[dict[str, Any]], pregnant: bool) -> list[str]:
    """Two short questions for the Ask Em chips."""
    asks = [f"Why is my {r['marker'].lower()} {r['flag']}?" for r in flagged[:1]]
    if any(r.get("overdue") for r in data.get("records", [])):
        asks.append("Where are my records?")
    asks.append("Safe workouts this week?" if pregnant else "Adjust my runs this week?")
    return asks[:2]


@router.get("/home")
def get_home(user_id: str = Depends(get_user_id)) -> HomeData:
    """Return the Home dashboard for the current persona."""
    data = store.get_user(user_id)
    profile = data["profile"]
    today = date.fromisoformat(data["as_of"])
    pregnant = profile.get("life_stage") == "pregnant"
    flagged = _flagged(user_id)

    wearable = sorted(data.get("wearable", []), key=lambda d: d["date"])
    readiness, trend = None, []
    if wearable:
        base_hrv = mean(d["hrv_ms"] for d in wearable if d.get("hrv_ms")) if any(d.get("hrv_ms") for d in wearable) else 0
        base_rhr = mean(d["resting_hr"] for d in wearable if d.get("resting_hr")) if any(d.get("resting_hr") for d in wearable) else 0
        trend = [TrendPoint(date=d["date"], readiness=_readiness_score(d, base_hrv, base_rhr)) for d in wearable[-7:]]
        last = wearable[-1]
        score = trend[-1].readiness
        readiness = Readiness(
            score=score, label=_readiness_label(score), sleep_hours=last["sleep_hours"],
            hrv_ms=last.get("hrv_ms"), resting_hr=last.get("resting_hr"),
            summary=f"{last['sleep_hours']} h sleep last night, HRV {last.get('hrv_ms')} ms.",
        )

    metrics = [Metric(label="Readiness", value=str(readiness.score), unit=None)] if readiness else []
    if pregnant:
        if readiness:
            metrics.append(Metric(label="Sleep", value=f"{readiness.sleep_hours:g}", unit="h"))
        metrics.append(Metric(label="Week", value=str(profile["pregnancy"]["week"]), unit="of 40"))
    else:
        if readiness and readiness.resting_hr:
            metrics.append(Metric(label="Resting HR", value=str(readiness.resting_hr), unit="bpm"))
        if flagged:
            metrics.append(Metric(label=flagged[0]["marker"], value=f"{flagged[0]['value']:g}", unit=flagged[0]["unit"]))
        elif readiness and readiness.hrv_ms:
            metrics.append(Metric(label="HRV", value=str(readiness.hrv_ms), unit="ms"))

    checklist = None
    if data.get("care_team"):
        items = [CareItem.model_validate(i) for i in data["care_team"]]
        checklist = CareChecklist(found=sum(i.done for i in items), total=len(items), items=items)

    checkins = sorted(data.get("checkins", []), key=lambda c: c["created_at"], reverse=True)
    focus = _focus(data, today, flagged, pregnant)
    nutrition = next((f for f in focus if f.kind == "nutrition"), None)
    plan_today = next((d for d in data.get("plan", []) if d["date"] == today.isoformat()), None)

    return HomeData(
        user_name=profile["name"],
        greeting=_greeting(profile["name"]),
        alerts=_alerts(data, today, flagged, pregnant),
        quote=_quote(readiness.score if readiness else None),
        readiness=readiness,
        today_plan=plan_today["activity"] if plan_today else None,
        nutrition_tip=f"{nutrition.title}: {nutrition.detail}" if nutrition else None,
        pregnancy_week=profile["pregnancy"]["week"] if pregnant and profile.get("pregnancy") else None,
        care_checklist=checklist,
        recent_checkins=[CheckinResult.model_validate(c) for c in checkins[:7]],
        mood=checkins[0]["mood"] if checkins else None,
        focus=focus,
        trend=trend,
        metrics=metrics,
        care_note=_care_note(data, flagged, pregnant),
        ask_suggestions=_ask_suggestions(data, flagged, pregnant),
    )
