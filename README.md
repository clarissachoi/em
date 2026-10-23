# EmCare

Holistic health app for women, with Em as the AI companion. Hackathon build.
Read `CLAUDE.md` (rules), `API.md` (contract), and `PERSONAS.md` (demo users) first.

The full mock scaffold (all endpoints, seed data, typed client, pages) lives on the `scaffold` branch.

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
