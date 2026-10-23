"""The only place that talks to Gemini. Use generate_structured, generate_text, generate_speech, live_session."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from google import genai
from google.genai import errors, live, types
from pydantic import BaseModel

from config import settings
from prompts import ENGLISH_ONLY

logger = logging.getLogger("emcare.gemini")

T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return the shared Gemini client, creating it on first use."""
    global _client
    if _client is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to the repo-root .env file.")
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _summarize(contents: list[Any]) -> str:
    """Describe request contents for logs: truncated text, byte parts as size only."""
    pieces = []
    for item in contents:
        if isinstance(item, str):
            pieces.append(repr(item[:80] + ("..." if len(item) > 80 else "")))
        elif isinstance(item, types.Part) and item.inline_data is not None:
            size = len(item.inline_data.data or b"")
            pieces.append(f"<{item.inline_data.mime_type} {size} bytes>")
        elif isinstance(item, types.Part) and item.text is not None:
            pieces.append(repr(item.text[:80]))
        else:
            pieces.append(f"<{type(item).__name__}>")
    return ", ".join(pieces)


def _is_overloaded(exc: errors.APIError) -> bool:
    """True for 503 / overloaded errors that are worth retrying."""
    return exc.code == 503 or "overloaded" in str(exc).lower()


async def _generate(
    contents: list[Any],
    config: types.GenerateContentConfig,
    models: tuple[str, str] | None = None,
) -> types.GenerateContentResponse:
    """Call Gemini with one retry on 503, then one attempt on the fallback model."""
    client = get_client()
    summary = _summarize(contents)
    primary, fallback = models or (settings.TEXT_MODEL, settings.FALLBACK_MODEL)
    attempts = [primary, primary, fallback]
    last_exc: errors.APIError | None = None

    for i, model in enumerate(attempts):
        start = time.perf_counter()
        try:
            resp = await client.aio.models.generate_content(model=model, contents=contents, config=config)
        except errors.APIError as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info("gemini error model=%s code=%s latency_ms=%d prompt=[%s]", model, exc.code, latency_ms, summary)
            if not _is_overloaded(exc) or i == len(attempts) - 1:
                raise
            last_exc = exc
            continue
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("gemini ok model=%s latency_ms=%d prompt=[%s]", model, latency_ms, summary)
        return resp

    raise last_exc  # unreachable, loop either returns or raises


def _english_only(system_instruction: str | None) -> str:
    """Add the English-only guardrail to a system instruction."""
    return f"{system_instruction}\n\n{ENGLISH_ONLY}" if system_instruction else ENGLISH_ONLY


async def generate_structured(
    prompt: str,
    schema: type[T],
    parts: list[types.Part] | None = None,
    *,
    system_instruction: str | None = None,
    thinking_level: str | None = None,
) -> T:
    """Generate JSON parsed into the given Pydantic schema. Extra parts (audio, PDF) go before the prompt.

    Pass thinking_level="low" for faster replies on simple tasks (about 4s instead of 15s).
    """
    config = types.GenerateContentConfig(
        system_instruction=_english_only(system_instruction),
        response_mime_type="application/json",
        response_schema=schema,
        thinking_config=types.ThinkingConfig(thinking_level=thinking_level) if thinking_level else None,
    )
    resp = await _generate([*(parts or []), prompt], config)
    if resp.parsed is None:
        raise ValueError(f"Gemini returned no parseable {schema.__name__}")
    return resp.parsed


async def generate_text(prompt: str, *, system_instruction: str | None = None) -> str:
    """Generate plain text from a prompt."""
    config = types.GenerateContentConfig(system_instruction=_english_only(system_instruction))
    resp = await _generate([prompt], config)
    return resp.text or ""


async def generate_speech(text: str) -> tuple[bytes, int]:
    """Read fixed text aloud in Em's voice. Returns (16-bit mono PCM, sample rate)."""
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=settings.EM_VOICE))
        ),
    )
    resp = await _generate(
        [text],  # text only: TTS models read any style instruction aloud too
        config,
        models=(settings.TTS_MODEL, settings.TTS_FALLBACK_MODEL),
    )
    part = resp.candidates[0].content.parts[0].inline_data if resp.candidates else None
    if part is None or not part.data:
        raise ValueError("Gemini returned no speech audio")
    rate = 24000
    for piece in (part.mime_type or "").replace(" ", "").split(";"):
        if piece.startswith("rate="):
            rate = int(piece.removeprefix("rate="))
    return part.data, rate


@asynccontextmanager
async def live_session(config: types.LiveConnectConfig, *, label: str) -> AsyncIterator[tuple[live.AsyncSession, str]]:
    """Open a Gemini Live session with one retry, then the fallback live model. Yields (session, model)."""
    if isinstance(config.system_instruction, str) or config.system_instruction is None:
        config = config.model_copy(update={"system_instruction": _english_only(config.system_instruction)})
    client = get_client()
    attempts = [settings.LIVE_MODEL, settings.LIVE_MODEL, settings.LIVE_FALLBACK_MODEL]
    for i, model in enumerate(attempts):
        start = time.perf_counter()
        try:
            cm = client.aio.live.connect(model=model, config=config)
            session = await cm.__aenter__()
        except Exception as exc:  # connect errors come as APIError or websocket errors
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info("gemini live connect error model=%s err=%s latency_ms=%d session=[%s]", model, type(exc).__name__, latency_ms, label)
            if i == len(attempts) - 1:
                raise
            continue
        logger.info("gemini live open model=%s latency_ms=%d session=[%s]", model, int((time.perf_counter() - start) * 1000), label)
        opened = time.perf_counter()
        try:
            yield session, model
        finally:
            await cm.__aexit__(None, None, None)
            logger.info("gemini live closed model=%s duration_s=%.1f session=[%s]", model, time.perf_counter() - opened, label)
        return
