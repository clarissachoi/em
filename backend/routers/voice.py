"""Live voice Em: the /voice WebSocket, voice settings, and the spoken urgent alert."""

import asyncio
import io
import logging
import wave

from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket

import gemini
from data import store
from deps import get_user_id
from models import VoiceSettings
from prompts import URGENT_ESCALATION
from voice import VoiceSession

router = APIRouter(tags=["voice"])
logger = logging.getLogger("emcare.voice")

_urgent_wav: bytes | None = None
_urgent_lock = asyncio.Lock()


def _settings(user_id: str) -> VoiceSettings:
    """This persona's saved voice settings, or the defaults."""
    return VoiceSettings.model_validate(store.get(user_id, "voice_settings", None) or {})


@router.websocket("/voice")
async def voice_ws(ws: WebSocket, user_id: str = Query(default="maya")) -> None:
    """Bridge the browser to a Gemini Live session as this persona. See API.md for the protocol."""
    await ws.accept()
    if user_id not in store.user_ids():
        await ws.close(code=4404, reason=f"Unknown user {user_id!r}")
        return
    await VoiceSession(ws, user_id, _settings(user_id).voice_alerts).run()


@router.get("/voice/settings")
def get_voice_settings(user_id: str = Depends(get_user_id)) -> VoiceSettings:
    """Return this persona's voice settings."""
    return _settings(user_id)


@router.put("/voice/settings")
def put_voice_settings(body: VoiceSettings, user_id: str = Depends(get_user_id)) -> VoiceSettings:
    """Save this persona's voice settings."""
    store.save(user_id, "voice_settings", body.model_dump())
    return body


@router.get("/voice/urgent-audio")
async def urgent_audio() -> Response:
    """The fixed URGENT_ESCALATION text read aloud as WAV, generated once and cached."""
    global _urgent_wav
    async with _urgent_lock:
        if _urgent_wav is None:
            try:
                pcm, rate = await gemini.generate_speech(URGENT_ESCALATION)
            except Exception as exc:
                logger.warning("urgent audio generation failed: %s", type(exc).__name__)
                raise HTTPException(status_code=503, detail="Could not generate urgent audio") from exc
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(pcm)
            _urgent_wav = buf.getvalue()
    return Response(content=_urgent_wav, media_type="audio/wav", headers={"Cache-Control": "max-age=3600"})
