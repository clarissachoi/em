"""Records transfer checklist. Status changes persist to state.json."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from data import store
from deps import get_user_id
from models import RecordRequest, RecordStatusUpdate

router = APIRouter(tags=["records"])


@router.get("/records")
def list_records(user_id: str = Depends(get_user_id)) -> list[RecordRequest]:
    """Return every record request for the persona."""
    return [RecordRequest.model_validate(r) for r in store.get(user_id, "records")]


@router.patch("/records/{record_id}")
def update_record(record_id: str, body: RecordStatusUpdate, user_id: str = Depends(get_user_id)) -> RecordRequest:
    """Change a record's status. Received records are never overdue."""
    records = store.get(user_id, "records")
    record = next((r for r in records if r["id"] == record_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Record {record_id!r} not found")
    record["status"] = body.status
    if body.status == "requested" and record["requested_on"] is None:
        record["requested_on"] = date.today().isoformat()
    if body.status == "received":
        record["overdue"] = False
    store.save(user_id, "records", records)
    return RecordRequest.model_validate(record)
