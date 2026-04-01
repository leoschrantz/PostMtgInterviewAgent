# Post-Meeting Interview Agent

A voice-powered AI debrief tool for sales teams. After completing a client meeting, salespeople have a natural voice conversation with an AI interviewer that captures what happened, follows up on pre-meeting objectives, and generates a structured summary for CRM entry.

## What It Does

1. **Meetings Dashboard** - Displays upcoming/recent meetings pulled from Microsoft Dynamics CRM (mocked for this prototype) with interview completion status
2. **Voice Interview** - A Gemini Live API voice agent interviews the salesperson about their meeting using natural bidirectional voice conversation with automatic turn-taking
3. **Smart Follow-ups** - The agent cross-references the salesperson's answers against pre-meeting objectives and asks about anything they missed (specific products, features, or action items)
4. **Structured Summary** - Claude generates a structured summary including: meeting outcome, key takeaways, client sentiment, action items, deal status assessment, and recommended next steps
5. **CRM Sync** - Summary and raw transcript are synced back to Dynamics (mocked via session state for this prototype)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| App Framework | Python + Streamlit |
| Voice Conversation | Google Gemini Live API (direct browser-to-Gemini WebSocket) |
| LLM (voice agent) | Gemini 3.1 Flash Live Preview (native audio, via Live API) |
| LLM (summarization) | Claude Sonnet (via Anthropic API) |
| CRM | Microsoft Dynamics (mocked) |
| Hosting | Streamlit Community Cloud |

## Project Structure

```
app.py                  # Entry point, page routing, global styling
agent.py                # Claude API summarization
mock_data.py            # Mock Dynamics CRM meetings data
utils.py                # Transcript formatting, data persistence
pages/
    dashboard.py        # Meeting list with status tracking
    interview.py        # Gemini Live API voice widget + summary generation
    summary.py          # Structured summary display + mock CRM sync
.streamlit/
    config.toml         # Streamlit theme configuration
    secrets.toml        # API keys (local only, not committed)
```

## Setup

### Prerequisites

- Python 3.10+
- API keys for:
  - [Anthropic](https://console.anthropic.com/) (Claude API for summarization)
  - [Google AI Studio](https://aistudio.google.com/) (Gemini Live API for voice conversations)

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Create secrets file
mkdir -p .streamlit
cat > .streamlit/secrets.toml << 'EOF'
ANTHROPIC_API_KEY = "sk-ant-..."
GOOGLE_API_KEY = "your-google-ai-studio-key"
EOF

# Run the app
streamlit run app.py
```

### Required Secrets

| Key | Description |
|-----|-------------|
| `ANTHROPIC_API_KEY` | Claude API key for summary generation |
| `GOOGLE_API_KEY` | Google AI Studio API key for Gemini Live API voice conversations |

## Usage

1. Open the app and view the **Meetings Dashboard**
2. Tap **Start Interview** on any pending meeting
3. Tap the **microphone button** to begin the voice conversation
4. Talk naturally with the AI interviewer about your meeting
5. When done, tap the stop button and click **End Interview & Generate Summary**
6. Review the structured summary and optionally sync to Dynamics CRM

## Architecture

```
Browser (phone/desktop)                          Google
┌──────────────────────┐                        ┌─────────┐
│ Mic capture          │───── WSS (direct) ────▶│ Gemini  │
│ (Web Audio API +     │                        │ Live API│
│  AudioWorklet)       │◀──── Audio + text ─────│         │
│ Speaker playback     │    (bidirectional)      └─────────┘
│ Live transcription   │
└──────────────────────┘
       │ transcript
       ▼
Streamlit Cloud ──── Claude API (summarization)
```

The browser connects **directly** to Gemini's WebSocket endpoint via
the Gemini Live API (`BidiGenerateContent`). No intermediary voice server
needed — works on Streamlit Community Cloud out of the box.

Audio is captured at 16kHz via AudioWorklet, sent as base64 PCM over
WebSocket, and Gemini responds with 24kHz audio for playback. Both input
and output transcriptions stream in real-time.

## Notes

- **Mobile**: Optimized for mobile use (salespeople typically debrief from their phones)
- **Browser support**: Voice works on Chrome, Edge, Safari (desktop and mobile) via Web Audio API + WebSocket
- **Barge-in**: Users can interrupt the AI interviewer mid-sentence; audio stops immediately
- **Fallback**: If voice/transcript retrieval fails, a manual text recap option is available
- **Security**: API key is passed to the browser for direct WebSocket connection. For production, consider using ephemeral tokens
- **Prototype scope**: Dynamics CRM integration is mocked. In production, this would connect via the Dynamics 365 Web API

## Future Enhancements

- Ephemeral tokens for secure browser-to-Gemini authentication
- Real Microsoft Dynamics 365 API integration
- Automatic meeting detection (no manual selection needed)
- Multi-language support
- Team-level analytics dashboard
- Calendar integration for scheduling follow-ups
- CRM field auto-population from summaries
