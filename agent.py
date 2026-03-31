"""Claude API summarization + ElevenLabs conversation transcript retrieval."""

import json
import requests
import streamlit as st
import anthropic


anthropic_client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-20250514"


SUMMARY_SYSTEM_PROMPT = """You are a sales meeting analyst. Given a transcript of a post-meeting debrief interview, produce a structured JSON summary.

Output ONLY valid JSON with this exact structure (no markdown, no code fences):
{
    "meeting_outcome": "Brief 1-2 sentence overview of what happened in the meeting",
    "key_takeaways": ["takeaway 1", "takeaway 2", "takeaway 3"],
    "client_sentiment": "Positive/Neutral/Negative - brief explanation",
    "action_items": [
        {"owner": "person name", "action": "what needs to be done", "deadline": "date or TBD"}
    ],
    "deal_status": {
        "stage_recommendation": "current or recommended new stage",
        "confidence_level": "High/Medium/Low",
        "risks": ["risk 1", "risk 2"],
        "deal_value_change": "no change / increased to $X / decreased to $X"
    },
    "follow_up_date": "suggested next follow-up date",
    "additional_notes": "anything else noteworthy from the conversation"
}"""


def fetch_conversation_transcript(conversation_id: str) -> list[dict] | None:
    """Fetch the transcript from an ElevenLabs conversation.

    Returns a list of {"role": "user"|"assistant", "content": "..."} dicts,
    or None if the transcript isn't available yet.
    """
    resp = requests.get(
        f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}",
        headers={"xi-api-key": st.secrets["ELEVENLABS_API_KEY"]},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    # Extract transcript from the conversation data
    transcript_entries = data.get("transcript", [])
    if not transcript_entries:
        return None

    messages = []
    for entry in transcript_entries:
        role_raw = entry.get("role", "")
        content = entry.get("message", "")
        if not content:
            continue
        role = "assistant" if role_raw == "agent" else "user"
        messages.append({"role": role, "content": content})

    return messages if messages else None


def generate_summary(transcript: list[dict], meeting: dict) -> dict:
    """Generate a structured summary from the interview transcript."""
    transcript_text = format_transcript_for_summary(transcript)

    meeting_context = (
        f"Client: {meeting['client_name']} ({meeting['client_contact']})\n"
        f"Meeting type: {meeting['type']}\n"
        f"Deal: {meeting['deal_name']} - {meeting['deal_stage']} - {meeting['deal_value']}\n"
        f"Date: {meeting['date']} at {meeting['time']}"
    )

    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Meeting Context:\n{meeting_context}\n\nDebrief Transcript:\n{transcript_text}",
            }
        ],
    )

    try:
        return json.loads(response.content[0].text)
    except json.JSONDecodeError:
        text = response.content[0].text
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            return json.loads(text.strip())
        return {"error": "Could not parse summary", "raw": response.content[0].text}


def format_transcript_for_summary(messages: list[dict]) -> str:
    """Format conversation messages into a readable transcript."""
    lines = []
    for msg in messages:
        role = "Interviewer" if msg["role"] == "assistant" else "Salesperson"
        lines.append(f"{role}: {msg['content']}")
    return "\n\n".join(lines)
