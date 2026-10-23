"""Records transfer checklist."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from data import store
from deps import get_user_id
from models import RecordRequest, RecordStatusUpdate

router = APIRouter(tags=["records"])


@router.get("/records")
def list_records(user_id: str = Depends(get_user_id)) -> list[RecordRequest]:
    """Return the persona's records requests."""
    return [RecordRequest.model_validate(r) for r in store.get(user_id, "records")]


@router.patch("/records/{record_id}")
def update_record(record_id: str, body: RecordStatusUpdate, user_id: str = Depends(get_user_id)) -> RecordRequest:
    """Update a record's status, stamping requested_on and clearing overdue as needed."""
    records = [RecordRequest.model_validate(r) for r in store.get(user_id, "records")]
    record = next((r for r in records if r.id == record_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown record {record_id!r}")

    record.status = body.status
    if body.status == "requested" and record.requested_on is None:
        record.requested_on = date.today()
    if body.status == "received":
        record.overdue = False

    store.save(user_id, "records", [r.model_dump(mode="json") for r in records])
    return record
