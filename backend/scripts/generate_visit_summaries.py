"""One-off: write a Gemini visit summary into each persona seed for past visits with doctor notes.

Run from backend/: python -m scripts.generate_visit_summaries
Only visit_summary.summary is generated; action_items and follow_up stay hand-written.
"""

import asyncio
import json
import logging

import gemini
from data.store import PERSONAS_DIR
from models import VisitSummaryText
from prompts import VISIT_SUMMARY_PROMPT


async def summarize(note: dict) -> str:
    """Ask Gemini for a factual summary of one doctor note."""
    result = await gemini.generate_structured(
        VISIT_SUMMARY_PROMPT.format(note=json.dumps(note)), VisitSummaryText, thinking_level="low"
    )
    return result.summary.replace("—", ", ").replace("–", "-").strip()


async def main() -> None:
    """Fill summaries for every persona seed and save the files."""
    for path in sorted(PERSONAS_DIR.glob("*/seed.json")):
        seed = json.loads(path.read_text())
        for appt in seed.get("appointments", {}).get("past", []):
            note, summary = appt.get("doctor_notes"), appt.get("visit_summary")
            if not note or not summary:
                continue
            summary["summary"] = await summarize(note)
            print(f"{path.parent.name}/{appt['id']}: {summary['summary']}\n")
        path.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
