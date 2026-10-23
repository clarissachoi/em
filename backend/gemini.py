"""The only place that talks to Gemini. Use generate_structured and generate_text."""

import logging
import time
from typing import Any, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from config import settings

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


async def _generate(contents: list[Any], config: types.GenerateContentConfig) -> types.GenerateContentResponse:
    """Call Gemini with one retry on 503, then one attempt on the fallback model."""
    client = get_client()
    summary = _summarize(contents)
    attempts = [settings.TEXT_MODEL, settings.TEXT_MODEL, settings.FALLBACK_MODEL]
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


async def generate_structured(
    prompt: str,
    schema: type[T],
    parts: list[types.Part] | None = None,
    *,
    system_instruction: str | None = None,
) -> T:
    """Generate JSON parsed into the given Pydantic schema. Extra parts (audio, PDF) go before the prompt."""
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=schema,
    )
    resp = await _generate([*(parts or []), prompt], config)
    if resp.parsed is None:
        raise ValueError(f"Gemini returned no parseable {schema.__name__}")
    return resp.parsed


async def generate_text(prompt: str, *, system_instruction: str | None = None) -> str:
    """Generate plain text from a prompt."""
    config = types.GenerateContentConfig(system_instruction=system_instruction)
    resp = await _generate([prompt], config)
    return resp.text or ""
