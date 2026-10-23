"""EmCare FastAPI app. Run from backend/: uvicorn main:app --reload --port 8000"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import (
    appointments,
    checkin,
    goals,
    health,
    home,
    insights,
    labs,
    plan,
    policy,
    records,
    suggestions,
    users,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="EmCare API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],  # needed for the custom X-User-Id header
)

for module in (users, checkin, home, appointments, labs, records, policy, goals, plan, suggestions, insights, health):
    app.include_router(module.router, prefix="/api")
