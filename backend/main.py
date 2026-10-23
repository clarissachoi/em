"""EmCare FastAPI app. Run from backend/: uvicorn main:app --reload --port 8000"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import goals, plan, users

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
app.include_router(goals.router, prefix="/api")
app.include_router(plan.router, prefix="/api")
