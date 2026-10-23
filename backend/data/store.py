"""Only access point for demo data.

seed.json is read-only shared data keyed by user id. Writes go to state.json (gitignored),
which overlays seed.json per user per top-level section. Delete state.json to reset the demo.
"""

import copy
import json
import threading
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent
SEED_PATH = DATA_DIR / "seed.json"
STATE_PATH = DATA_DIR / "state.json"

_lock = threading.Lock()


def _read(path: Path) -> dict[str, Any]:
    """Read a JSON file, returning {} if it does not exist."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load() -> dict[str, Any]:
    """Return all users' data with state.json applied over seed.json."""
    data = copy.deepcopy(_read(SEED_PATH))
    for user_id, sections in _read(STATE_PATH).items():
        data.setdefault(user_id, {}).update(sections)
    return data


def user_ids() -> list[str]:
    """Return every persona id in the seed."""
    return list(_read(SEED_PATH).keys())


def get_user(user_id: str) -> dict[str, Any]:
    """Return one user's merged data."""
    return load()[user_id]


def get(user_id: str, section: str) -> Any:
    """Return one top-level section (e.g. "goals", "records") for a user."""
    return get_user(user_id)[section]


def save(user_id: str, section: str, value: Any) -> None:
    """Persist one section for a user to state.json. Never touches seed.json."""
    with _lock:
        state = _read(STATE_PATH)
        state.setdefault(user_id, {})[section] = value
        STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def reset() -> None:
    """Drop all saved state so the demo starts fresh from seed.json."""
    with _lock:
        STATE_PATH.unlink(missing_ok=True)
