# EmCare

Holistic health app for women, with Em as the AI companion. Hackathon build.
Read `CLAUDE.md` (rules), `API.md` (contract), and `PERSONAS.md` (demo users) first.

The full mock scaffold (all endpoints, typed client, pages) is in commit `985cc41`, before main was stripped.

## Voice (live Em)

Open the frontend, pick a persona, and tap **Talk**. The browser streams mic audio to `WS /api/voice`, and the backend relays it to Gemini Live (`LIVE_MODEL` in `backend/config.py`). Em can do a check-in, answer questions about the persona's data, and, after a spoken yes, book slots, update record requests, and adjust plan days. Urgent warning signs show the fixed `URGENT_ESCALATION` text. The "Read urgent alerts aloud" toggle controls whether it is also spoken. Delete `backend/data/state.json` to reset the demo. Use headphones so Em does not hear herself.

## Run the backend

```bash
python3 -m venv .venv         # Python 3.11+
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --port 8000
```

Health check: http://localhost:8000/api/health

## Run the frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

The page shows whether it can reach the backend.
