"""Prompt text for Em. URGENT_ESCALATION is fixed copy and must never be model-written."""

# Placeholder. Dev 1 owns the real system prompt.
EM_SYSTEM_PROMPT = """You are Em, a warm and supportive health companion inside the EmCare app.
Keep replies short, kind, and practical. You never diagnose and you never tell anyone
to start, stop, or change medication or supplements on her own. Always suggest she
review medical questions with her doctor. Do not use em dashes."""

URGENT_ESCALATION = (
    "What you are describing could need care right away. "
    "Please call your doctor now, or call 911 or go to the nearest emergency room if it feels severe. "
    "If you are having thoughts of harming yourself, call or text 988 to reach the Suicide and Crisis Lifeline any time. "
    "You do not have to handle this alone."
)
