# EmCare

Holistic health app for women. "Em" is the AI companion inside the app. One-day hackathon build: favor working and demoable over complete.

Read `PERSONAS.md` (two demo users: Maya, marathon trainee; Jasmine, 20 weeks pregnant and rebuilding her care team) and `API.md` (the contract) before any task.

## Stack
- Frontend: React + TypeScript + Vite (`frontend/`)
- Backend: FastAPI + Pydantic v2, Python 3.11+ (`backend/`)
- AI: Gemini via the NEW `google-genai` SDK. Never use the old `google-generativeai` package.
- Data: seeded JSON in `backend/data/seed.json`, keyed by user id (`maya`, `jasmine`), accessed only through `backend/data/store.py`. No real database, no auth.
- Persona selection: request header `X-User-Id` (default `maya`). Use the shared FastAPI dependency `get_user_id` in `backend/deps.py`. Frontend has a persona switcher that sets this header.
- All external sources (Apple Watch/Garmin, Oura/Fitbit, Strava, cycle and pregnancy apps, calendar, provider directory, records) are MOCKED in seed data. Do not build real integrations.

## Gemini usage (copy this pattern)
```python
from google import genai
from google.genai import types
from config import settings  # plain imports; run from backend/

client = genai.Client(api_key=settings.GEMINI_API_KEY)

resp = await client.aio.models.generate_content(
    model=settings.TEXT_MODEL,
    contents=[types.Part.from_bytes(data=audio_bytes, mime_type="audio/webm"), "Analyze this check-in."],
    config=types.GenerateContentConfig(
        system_instruction=EM_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=CheckinResult,  # a Pydantic model from backend/models.py
    ),
)
result: CheckinResult = resp.parsed
```
- Always call Gemini through helpers in `backend/gemini.py` (`generate_structured`, `generate_text`). Do not create new clients elsewhere.
- Always use the async client (`client.aio`).
- Model names live only in `backend/config.py`. Never hardcode a model string.
- Retry once on 503 / overloaded, then fall back to `settings.FALLBACK_MODEL`.
- Give Gemini the relevant persona context (profile, goals, recent check-ins, wearable data, labs) from `store.py`, never the whole seed file.

## Safety rules
- Em never diagnoses and never tells anyone to start, stop, or change medication or supplements on her own. Lab explanations and plan changes always say to review with her doctor (OB for Jasmine).
- Urgent warning signs in a check-in (e.g. chest pain, severe headache, vision changes, heavy bleeding, thoughts of self-harm, and for pregnancy: severe swelling, reduced fetal movement) return the fixed `URGENT_ESCALATION` text from `backend/prompts.py`, never model-written wording.
- Pregnancy: all workout and nutrition suggestions must be pregnancy-safe. Watch gently for mood changes and always offer an easy way to reach support.

## General rules
- API keys only in `.env` (gitignored). Never in code, logs, or frontend.
- Frontend never calls Gemini directly. Only calls our FastAPI backend.
- All request/response shapes are Pydantic models in `backend/models.py` and must match `API.md`. Change `API.md` first, tell the team, then change code.
- No em dashes in any user-facing copy.
- Log every Gemini call (model, prompt summary, latency) at INFO. Strip inline audio/file bytes from logs.
- Every function gets a short docstring.

## Ownership (stay in your files)
- Dev 1 (Em + Home): `routers/checkin.py`, `routers/home.py`, `prompts.py`
- Dev 2 (Appointments, labs, records): `routers/appointments.py`, `routers/labs.py`, `routers/records.py`, `routers/policy.py`
- Dev 3 (Next steps + integration): `routers/goals.py`, `routers/plan.py`, `routers/suggestions.py`, `routers/insights.py`, `frontend/src/api/`, deploy
- Shared, frozen after scaffold (ping team before editing): `main.py`, `config.py`, `deps.py`, `gemini.py`, `models.py`, `data/store.py`, `data/seed.json`, `routers/users.py`

## Workflow
- Plan first and list assumptions before writing code. Wait for confirmation.
- Small commits. Pull before starting a new task.
- Run backend: `cd backend && uvicorn main:app --reload --port 8000` (docs at /docs)
- Run frontend: `cd frontend && npm run dev`
