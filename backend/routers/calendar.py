"""GET /calendar: one merged view of a persona's events, cycle, and pregnancy timeline. Computed, no Gemini."""

import re
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from data import store
from deps import get_user_id
from models import CalendarEvent

router = APIRouter(tags=["calendar"])

EVENT_KINDS = {"appointment", "travel", "work", "family"}
MAX_RANGE_DAYS = 120


def _event(key: str, title: str, kind: str, start: date, end: date | None = None, *, start_time: str | None = None,
           end_time: str | None = None, location: str | None = None, detail: str | None = None,
           recurring: bool = False, predicted: bool = False) -> CalendarEvent:
    """Build a CalendarEvent with sensible defaults."""
    return CalendarEvent(id=key, title=title, kind=kind, start_date=start, end_date=end or start, start_time=start_time,
                         end_time=end_time, location=location, detail=detail, recurring=recurring, predicted=predicted)


def _overlaps(e: CalendarEvent, start: date, end: date) -> bool:
    """True when the event touches the [start, end] range."""
    return e.start_date <= end and e.end_date >= start


def _calendar_events(data: dict[str, Any], start: date, end: date) -> list[CalendarEvent]:
    """One-off events from the seed calendar, plus weekly routines expanded per day."""
    out = []
    for i, e in enumerate(data.get("calendar", {}).get("events", [])):
        kind = e.get("type") if e.get("type") in EVENT_KINDS else "work"
        if e.get("days"):  # weekly routine with time-only start/end
            day = start
            while day <= end:
                if f"{day:%a}" in e["days"]:
                    out.append(_event(f"routine-{i}-{day}", e["title"], "routine", day, start_time=e.get("start"),
                                      end_time=e.get("end"), location=e.get("location"), detail=e.get("detail"), recurring=True))
                day += timedelta(days=1)
            continue
        s, f = datetime.fromisoformat(e["start"]), datetime.fromisoformat(e["end"])
        multi_day = f.date() > s.date()
        out.append(_event(f"event-{i}", e["title"], kind, s.date(), f.date(),
                          start_time=None if multi_day else f"{s:%H:%M}", end_time=None if multi_day else f"{f:%H:%M}",
                          location=e.get("location"), detail=e.get("detail")))
    return out


def _appointments(data: dict[str, Any], existing: list[CalendarEvent]) -> list[CalendarEvent]:
    """Upcoming and past appointments not already on the seed calendar (e.g. new bookings)."""
    taken = {(e.start_date, e.start_time) for e in existing if e.kind == "appointment"}
    out = []
    appts = data.get("appointments", {})
    for a in [*appts.get("upcoming", []), *appts.get("past", [])]:
        at = datetime.fromisoformat(a["datetime"])
        if (at.date(), f"{at:%H:%M}") in taken:
            continue
        who = "" if a.get("for_person", "self") == "self" else f" (for {a['for_person']})"
        out.append(_event(f"appt-{a['id']}", f"{a['specialty']}, {a['provider']}{who}", "appointment", at.date(),
                          start_time=f"{at:%H:%M}", location=a.get("location"),
                          detail="Completed" if a.get("status") == "completed" else None))
    return out


def _plan(data: dict[str, Any]) -> list[CalendarEvent]:
    """Daily training or walking plan."""
    return [
        _event(f"plan-{d['date']}", d["activity"], "plan", date.fromisoformat(d["date"]),
               detail=f"{d['duration_min']} min · {d['intensity']}" + (f" · {d['adjustment_reason']}" if d.get("adjustment_reason") else ""))
        for d in data.get("plan", [])
    ]


def _cycle(cycle: dict[str, Any], start: date, end: date, today: date) -> list[CalendarEvent]:
    """Logged periods from history, then predicted periods and estimated ovulation from the average cycle."""
    length = cycle.get("avg_cycle_length") or 28
    period_len = cycle.get("avg_period_length") or 5
    out = []
    starts = []
    for p in cycle.get("period_history", []):
        s = date.fromisoformat(p["start"])
        starts.append(s)
        out.append(_event(f"period-{s}", "Period", "period", s, s + timedelta(days=p.get("length_days", period_len) - 1)))
    last = max(starts) if starts else (date.fromisoformat(cycle["last_period_start"]) if cycle.get("last_period_start") else None)
    if last is None:
        return out
    if not starts:
        out.append(_event(f"period-{last}", "Period", "period", last, last + timedelta(days=period_len - 1)))
    # predicted cycles until past the requested range; ovulation estimated 14 days before the next period
    cycle_start = last
    while cycle_start <= end + timedelta(days=length):
        nxt = cycle_start + timedelta(days=length)
        ov = nxt - timedelta(days=14)
        if ov >= today:
            out.append(_event(f"ovulation-{ov}", "Ovulation (estimated)", "ovulation", ov, predicted=True,
                              detail="Estimated from your average cycle length"))
        out.append(_event(f"period-{nxt}", "Period (predicted)", "period", nxt, nxt + timedelta(days=period_len - 1), predicted=True,
                          detail=f"Based on a {length}-day average cycle"))
        cycle_start = nxt
    return out


def _week_start(due: date, week: int) -> date:
    """First day of a pregnancy week, counted back from the due date (week 40 ends on the due date)."""
    return due - timedelta(days=(40 - week) * 7)


def _pregnancy(tracker: dict[str, Any]) -> list[CalendarEvent]:
    """Week starts, milestones, and the prenatal schedule turned into dates from the due date."""
    due = date.fromisoformat(tracker["due_date"])
    sizes = tracker.get("baby_size_by_week", {})
    out = []
    for week in range(tracker.get("week", 1), 41):
        size = sizes.get(str(week))
        out.append(_event(f"week-{week}", f"Week {week}", "pregnancy", _week_start(due, week), predicted=True,
                          detail=f"Baby is about the size of a {size}" if size else None))
    for m in tracker.get("milestones", []):
        day = due if m["week"] == 40 else _week_start(due, m["week"])
        out.append(_event(f"milestone-{m['week']}", m["label"], "pregnancy", day, predicted=True))
    for i, item in enumerate(tracker.get("prenatal_schedule", [])):
        weeks = [int(w) for w in re.findall(r"\d+", item["weeks"])]
        if not weeks:
            continue
        s = _week_start(due, weeks[0])
        f = _week_start(due, weeks[-1]) + timedelta(days=6)
        out.append(_event(f"prenatal-{i}", item["item"], "prenatal", s, f, predicted=True,
                          detail=f"Weeks {item['weeks']} · {item.get('status', '')}".rstrip(" ·")))
    return out


@router.get("/calendar")
def get_calendar(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    user_id: str = Depends(get_user_id),
) -> list[CalendarEvent]:
    """Everything on her calendar between start and end (inclusive). Defaults to the month of her as_of date."""
    data = store.get_user(user_id)
    today = date.fromisoformat(data["as_of"])
    start = start or today.replace(day=1)
    end = end or (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=f"end must be on or after start, within {MAX_RANGE_DAYS} days")

    events = _calendar_events(data, start, end)
    events += _appointments(data, events)
    events += _plan(data)
    if data.get("cycle"):
        events += _cycle(data["cycle"], start, end, today)
    if data.get("pregnancy_tracker"):
        events += _pregnancy(data["pregnancy_tracker"])
    return sorted((e for e in events if _overlaps(e, start, end)), key=lambda e: (e.start_date, e.start_time or "", e.title))
