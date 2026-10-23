# EmCare

Holistic health app for women, with Em as the AI companion. Hackathon build.
Read `CLAUDE.md` (rules), `API.md` (contract), and `PERSONAS.md` (demo users) first.

## Setup

```bash
cp .env.example .env          # add GEMINI_API_KEY; TEXT_MODEL / FALLBACK_MODEL are optional overrides
python3 -m venv .venv         # Python 3.11+
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## Run the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Gemini check: http://localhost:8000/api/health/gemini (needs `GEMINI_API_KEY` in `.env`)
- Switch persona with the `X-User-Id` header (`maya` or `jasmine`, default `maya`):

```bash
curl -H "X-User-Id: jasmine" http://localhost:8000/api/home
```

## Demo data

- `backend/data/seed.json` is the shared, read-only seed for both personas. Edit it only after pinging the team.
- Changes made through the API (booking, goals, record status) are saved to `backend/data/state.json`, which is gitignored.
- To reset the demo, stop the server and delete `backend/data/state.json`.

## Status

All endpoints return mock data from the seed. Only `/api/health/gemini` calls Gemini.
Look for `TODO(Dev N)` in `backend/routers/` for where real AI logic goes.
