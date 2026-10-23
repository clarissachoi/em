"""Only access point for demo data.

Each persona's read-only seed lives at personas/<id>/seed.json. Writes go to state.json
(gitignored), which overlays the seed per user per top-level section. Delete state.json
to reset the demo.
"""

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent
PERSONAS_DIR = DATA_DIR / "personas"
# EMCARE_STATE_PATH overrides. On Vercel the code directory is read-only, so state goes to /tmp
# (per instance and reset on cold start; fine for a demo, swap for Redis/Blob for durable shared state).
STATE_PATH = Path(
    os.environ.get("EMCARE_STATE_PATH") or ("/tmp/emcare-state.json" if os.environ.get("VERCEL") else DATA_DIR / "state.json")
)

_lock = threading.Lock()


def _read(path: Path) -> dict[str, Any]:
    """Read a JSON file, returning {} if it does not exist."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def user_ids() -> list[str]:
    """Return every persona id that has a seed file, sorted."""
    return sorted(p.parent.name for p in PERSONAS_DIR.glob("*/seed.json"))


def get_user(user_id: str) -> dict[str, Any]:
    """Return one persona's seed with any saved state applied over it."""
    data = copy.deepcopy(_read(PERSONAS_DIR / user_id / "seed.json"))
    data.update(_read(STATE_PATH).get(user_id, {}))
    return data


_MISSING = object()


def get(user_id: str, section: str, default: Any = _MISSING) -> Any:
    """Return one top-level section (e.g. "profile", "records") for a persona. Raises KeyError unless a default is given."""
    data = get_user(user_id)
    if default is _MISSING:
        return data[section]
    return data.get(section, default)


def save(user_id: str, section: str, value: Any) -> None:
    """Persist one section for a persona to state.json. Never touches the seed files."""
    with _lock:
        state = _read(STATE_PATH)
        state.setdefault(user_id, {})[section] = value
        STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def reset() -> None:
    """Drop all saved state so the demo starts fresh from the seeds."""
    with _lock:
        STATE_PATH.unlink(missing_ok=True)
