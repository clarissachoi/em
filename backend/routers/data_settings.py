"""Data use choices from the profile menu. Opt in only; the demo stores the choice and shares nothing."""

from datetime import datetime

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import DataSettings, DataSettingsUpdate

router = APIRouter(tags=["data settings"])


def data_settings(user_id: str) -> DataSettings:
    """Saved choices, or the defaults (everything off)."""
    return DataSettings.model_validate(store.get(user_id, "data_settings", None) or {})


@router.get("/data-settings")
def get_data_settings(user_id: str = Depends(get_user_id)) -> DataSettings:
    """Return this persona's data use choices."""
    return data_settings(user_id)


@router.put("/data-settings")
def put_data_settings(body: DataSettingsUpdate, user_id: str = Depends(get_user_id)) -> DataSettings:
    """Save this persona's data use choices and stamp the time."""
    saved = DataSettings(**body.model_dump(), updated_at=datetime.now().replace(microsecond=0))
    store.save(user_id, "data_settings", saved.model_dump(mode="json"))
    return saved
