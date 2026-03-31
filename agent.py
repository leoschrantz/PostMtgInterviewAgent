"""Claude API interview agent logic + Deepgram STT + ElevenLabs TTS."""

import json
import requests
import streamlit as st
import anthropic


anthropic_client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-20250514"

INTERVIEW_SYSTEM_PROMPT_TEMPLATE = """You are a post-meeting debrief assistant for a sales team. You are conducting a brief voice interview with a salesperson who just completed a client meeting. Your job is to ask clear, focused questions to capture what happened and what comes next.

IMPORTANT RULES:
- Ask ONE question at a time
- Keep your responses to 1-2 sentences max (they will be spoken aloud)
- Be conversational and natural, like a helpful colleague
- Adapt your follow-up questions based on what the salesperson tells you
- Don't repeat information they've already shared

MEETING CONTEXT:
- Client: {client_name} ({client_contact})
- Meeting type: {meeting_type}
- Deal: {deal_name}
- Current deal stage: {deal_stage}
- Deal value: {deal_value}
- Date: {date} at {time}
- Attendees: {attendees}
- Pre-meeting notes: {notes_pre}

INTERVIEW FLOW (adapt based on responses, skip topics already covered):
1. Opening: Ask how the meeting went overall
2. Key topics: What were the main things discussed?
3. Client reactions: How did the client respond? Any concerns or objections?
4. PRE-MEETING OBJECTIVES CHECK: Compare the salesperson's answers against the pre-meeting notes above. If they haven't mentioned specific products, features, action items, or topics that were listed as objectives in the pre-meeting notes, ask about them directly. For example: "I noticed the prep notes mentioned [specific product/topic]. Did that come up in the meeting?" This is critical -- don't skip this step.
5. Outcomes: Were any decisions made or agreements reached?
6. Next steps: What are the agreed next steps and timelines?
7. Deal assessment: Has anything changed about the deal stage or value? Any risks?
8. Support needed: Anything they need help with from the team?
9. Closing: Briefly confirm what you heard, then say EXACTLY this phrase: "I think I have everything I need for the debrief. Let me generate your summary."

CRITICAL: You MUST check the pre-meeting notes for specific products, features, or objectives and follow up if the salesperson doesn't mention them. This is one of the most valuable things you do -- catching gaps between what was planned and what was discussed.

When you've covered the key topics (you don't need to ask every single question if the salesperson has already covered things), wrap up with the closing phrase above."""


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


def build_system_prompt(meeting: dict) -> str:
    """Build the interview system prompt with meeting context."""
    return INTERVIEW_SYSTEM_PROMPT_TEMPLATE.format(
        client_name=meeting["client_name"],
        client_contact=meeting["client_contact"],
        meeting_type=meeting["type"],
        deal_name=meeting["deal_name"],
        deal_stage=meeting["deal_stage"],
        deal_value=meeting["deal_value"],
        date=meeting["date"],
        time=meeting["time"],
        attendees=", ".join(meeting["attendees"]),
        notes_pre=meeting["notes_pre"],
    )


def get_interview_response(conversation_history: list[dict], meeting: dict) -> str:
    """Get the next interview question/response from Claude.

    Args:
        conversation_history: List of {"role": "user"|"assistant", "content": "..."} dicts.
        meeting: Meeting metadata dict.

    Returns:
        The assistant's next message text.
    """
    system_prompt = build_system_prompt(meeting)
    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=conversation_history,
    )
    return response.content[0].text


def get_opening_question(meeting: dict) -> str:
    """Get the agent's opening question to start the interview.

    Makes an API call with a single user message prompting the opening.
    """
    system_prompt = build_system_prompt(meeting)
    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=system_prompt,
        messages=[
            {"role": "user", "content": "Hi, I just finished the meeting. Ready to debrief."}
        ],
    )
    return response.content[0].text


def generate_summary(transcript: list[dict], meeting: dict) -> dict:
    """Generate a structured summary from the interview transcript.

    Args:
        transcript: Full conversation history.
        meeting: Meeting metadata.

    Returns:
        Structured summary dict.
    """
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
        # If Claude wraps it in code fences, try to extract
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


def is_interview_complete(response: str) -> bool:
    """Check if the agent's response signals the interview is done."""
    return "I have everything I need" in response.lower() or "generate your summary" in response.lower()


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio bytes using Deepgram REST API."""
    resp = requests.post(
        "https://api.deepgram.com/v1/listen",
        headers={
            "Authorization": f"Token {st.secrets['DEEPGRAM_API_KEY']}",
            "Content-Type": "audio/webm",
        },
        params={"model": "nova-3", "smart_format": "true"},
        data=audio_bytes,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["results"]["channels"][0]["alternatives"][0]["transcript"]


def text_to_speech(text: str) -> bytes:
    """Convert text to speech audio using ElevenLabs REST API."""
    resp = requests.post(
        "https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb",
        headers={
            "xi-api-key": st.secrets["ELEVENLABS_API_KEY"],
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "output_format": "mp3_44100_128",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content
