"""EmCare FastAPI app. Run from backend/: uvicorn main:app --reload --port 8000"""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import appointments, goals, home, insights, insurance, labs, plan, records, suggestions, users, voice

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="EmCare API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, bool]:
    """Liveness check."""
    return {"ok": True}


app.include_router(api)
app.include_router(users.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(appointments.router, prefix="/api")
app.include_router(goals.router, prefix="/api")
app.include_router(plan.router, prefix="/api")
app.include_router(labs.router, prefix="/api")
app.include_router(home.router, prefix="/api")
app.include_router(insurance.router, prefix="/api")
app.include_router(suggestions.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
