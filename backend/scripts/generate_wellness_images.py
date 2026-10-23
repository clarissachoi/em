"""One-off: generate em.well card photos with Gemini and save them to frontend/public/wellness/.

Run from backend/: python -m scripts.generate_wellness_images [card_id ...] [--force]
Only cards listed in PROMPTS are drawn. Existing files are skipped unless --force is given.
"""

import asyncio
import io
import json
import logging
import sys

from google.genai import types
from PIL import Image

import gemini
from config import ROOT_DIR, settings
from data.store import PERSONAS_DIR

OUT_DIR = ROOT_DIR / "frontend" / "public" / "wellness"
SIZE = (512, 280)  # matches the existing em.well photos

STYLE = (
    "Realistic lifestyle photograph, warm natural light, soft muted earthy palette, shallow depth of field, calm and "
    "inviting, wide 16:9 framing. No text, no logos, no watermarks. Any people are seen from behind or at a distance, "
    "faces not in focus."
)

# card id -> what to draw. Pregnancy-safe scenes only: no lying flat on the back, no hot rooms, no raw fish.
PROMPTS = {
    "jas_saxon_walk": "A woman with a small pregnancy bump walking at an easy pace on a flat paved path through autumn "
    "woods, wooden benches along the path, golden morning light.",
    "jas_stroller_walk": "A parent pushing a stroller with a toddler along a leafy suburban sidewalk toward a small park, "
    "late afternoon light, fallen autumn leaves.",
    "jas_prenatal_yoga": "A small, bright prenatal yoga studio, a few pregnant women seated upright on mats with bolsters "
    "and blankets doing a gentle seated side stretch, plants and wooden floors.",
    "jas_lentil_bowl": "A warm bowl of lentils with wilted spinach, roasted sweet potato cubes, and a lemon wedge on a "
    "linen napkin, wooden kitchen table by a window.",
    "jas_seed_snack": "A small ceramic bowl of pumpkin seeds next to dried apricots and a peeled clementine on a kitchen "
    "counter, a reusable snack bag beside them.",
    "jas_sheet_pan": "A sheet pan of golden roasted chicken thighs with sweet potato wedges and broccoli, fully cooked, "
    "with a small toddler plate of the same food beside it on a family dinner table.",
}


def _cards() -> dict[str, dict]:
    """Every wellness card across persona seeds, by id."""
    cards = {}
    for path in sorted(PERSONAS_DIR.glob("*/seed.json")):
        for card in json.loads(path.read_text()).get("wellness_cards", []):
            cards[card["id"]] = card
    return cards


async def draw(card_id: str) -> bytes:
    """Ask Gemini for one photo and return the raw image bytes."""
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="16:9"),
    )
    resp = await gemini._generate([f"{PROMPTS[card_id]} {STYLE}"], config, (settings.IMAGE_MODEL, settings.IMAGE_MODEL))
    for part in resp.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            return part.inline_data.data
    raise ValueError(f"No image returned for {card_id}")


def save(data: bytes, filename: str) -> None:
    """Center-crop to the em.well card shape, shrink, and write a PNG."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    target = SIZE[0] / SIZE[1]
    w, h = img.size
    if w / h > target:
        cut = int((w - h * target) / 2)
        img = img.crop((cut, 0, w - cut, h))
    else:
        cut = int((h - w / target) / 2)
        img = img.crop((0, cut, w, h - cut))
    img.resize(SIZE, Image.LANCZOS).save(OUT_DIR / filename, optimize=True)


async def main() -> None:
    """Draw the requested cards (default: all in PROMPTS) whose image file is missing."""
    force = "--force" in sys.argv
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")] or list(PROMPTS)
    cards = _cards()
    for card_id in wanted:
        filename = cards[card_id]["image"].removeprefix("/wellness/")
        if (OUT_DIR / filename).exists() and not force:
            print(f"skip {filename} (exists)")
            continue
        save(await draw(card_id), filename)
        print(f"wrote {filename}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
