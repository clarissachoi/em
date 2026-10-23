"""Health checks. /health/gemini is the only real Gemini call in the scaffold."""

import logging
import time

from fastapi import APIRouter

import gemini
from config import settings
from models import HealthGemini, HealthStatus

router = APIRouter(tags=["health"])
logger = logging.getLogger("emcare.health")


@router.get("/health")
def health() -> HealthStatus:
    """Liveness check."""
    return HealthStatus(ok=True)


@router.get("/health/gemini")
async def health_gemini() -> HealthGemini:
    """Make one tiny Gemini call and report whether it worked."""
    start = time.perf_counter()
    try:
        await gemini.generate_text("Reply with the single word: ok")
        ok = True
    except Exception as exc:
        logger.warning("gemini health check failed: %s", type(exc).__name__)
        ok = False
    return HealthGemini(ok=ok, model=settings.TEXT_MODEL, latency_ms=int((time.perf_counter() - start) * 1000))
