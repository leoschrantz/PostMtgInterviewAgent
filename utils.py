"""Utility functions for transcript formatting and data persistence."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "interviews"


def format_transcript(messages: list[dict]) -> str:
    """Format conversation messages into a human-readable transcript."""
    lines = []
    for msg in messages:
        role = "Agent" if msg["role"] == "assistant" else "You"
        lines.append(f"**{role}:** {msg['content']}")
    return "\n\n".join(lines)


def save_interview(meeting_id: str, transcript: list[dict], summary: dict):
    """Save interview data to a JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DATA_DIR / f"{meeting_id}.json"
    data = {
        "meeting_id": meeting_id,
        "transcript": transcript,
        "summary": summary,
    }
    filepath.write_text(json.dumps(data, indent=2))


def load_interview(meeting_id: str) -> dict | None:
    """Load saved interview data, if it exists."""
    filepath = DATA_DIR / f"{meeting_id}.json"
    if filepath.exists():
        return json.loads(filepath.read_text())
    return None
