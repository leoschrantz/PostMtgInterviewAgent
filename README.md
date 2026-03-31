# Post-Meeting Interview Agent

A voice-powered AI debrief tool for sales teams. After completing a client meeting, salespeople have a natural voice conversation with an AI interviewer that captures what happened, follows up on pre-meeting objectives, and generates a structured summary for CRM entry.

## What It Does

1. **Meetings Dashboard** - Displays upcoming/recent meetings pulled from Microsoft Dynamics CRM (mocked for this prototype) with interview completion status
2. **Voice Interview** - An ElevenLabs Conversational AI agent interviews the salesperson about their meeting using natural voice conversation (no button-pressing between turns)
3. **Smart Follow-ups** - The agent cross-references the salesperson's answers against pre-meeting objectives and asks about anything they missed (specific products, features, or action items)
4. **Structured Summary** - Claude generates a structured summary including: meeting outcome, key takeaways, client sentiment, action items, deal status assessment, and recommended next steps
5. **CRM Sync** - Summary and raw transcript are synced back to Dynamics (mocked via session state for this prototype)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| App Framework | Python + Streamlit |
| Voice Conversation | ElevenLabs Conversational AI (handles STT + LLM + TTS) |
| LLM (in voice agent) | Claude Sonnet (via ElevenLabs) |
| LLM (summarization) | Claude Sonnet (via Anthropic API) |
| CRM | Microsoft Dynamics (mocked) |
| Hosting | Streamlit Community Cloud |

## Project Structure

```
app.py                  # Entry point, page routing, global styling
agent.py                # Claude API summarization + ElevenLabs transcript retrieval
mock_data.py            # Mock Dynamics CRM meetings data
utils.py                # Transcript formatting, JSON persistence
pages/
    dashboard.py        # Meeting list with status tracking
    interview.py        # ElevenLabs voice widget + summary generation
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
  - [ElevenLabs](https://elevenlabs.io/) (Conversational AI agent + transcript retrieval)

### ElevenLabs Agent Setup

1. Go to [elevenlabs.io/app/conversational-ai](https://elevenlabs.io/app/conversational-ai)
2. Create a new agent with Claude Sonnet as the LLM
3. Set the system prompt to include `{{meeting_context}}` as a dynamic variable for meeting context injection
4. Set the first message (e.g., "Hi! I'm ready for your post-meeting debrief. How did the meeting go overall?")
5. Under Advanced settings, set the agent to **Public**
6. Copy the Agent ID and update `AGENT_ID` in `pages/interview.py`

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Create secrets file
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your API keys

# Run the app
streamlit run app.py
```

### Streamlit Cloud Deployment

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set `app.py` as the main file
4. Add secrets in the app settings:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ELEVENLABS_API_KEY = "xi-..."
   ```
5. Deploy

### Required Secrets

| Key | Description |
|-----|-------------|
| `ANTHROPIC_API_KEY` | Claude API key for summary generation |
| `ELEVENLABS_API_KEY` | ElevenLabs API key (must have Conversational AI permissions for transcript retrieval) |

## Usage

1. Open the app and view the **Meetings Dashboard**
2. Tap **Start Interview** on any pending meeting
3. Tap the **call button** (bottom-right) to begin the voice conversation
4. Talk naturally with the AI interviewer about your meeting
5. When done, hang up and click **End Interview & Generate Summary**
6. Review the structured summary and optionally sync to Dynamics CRM

## Notes

- **Mobile**: Optimized for mobile use (salespeople typically debrief from their phones)
- **Browser support**: Voice works on Chrome, Edge, Safari (desktop and mobile) via ElevenLabs WebRTC
- **Fallback**: If voice/transcript retrieval fails, a manual text recap option is available
- **Prototype scope**: Dynamics CRM integration is mocked. In production, this would connect via the Dynamics 365 Web API

## Future Enhancements

- Real Microsoft Dynamics 365 API integration
- Automatic meeting detection (no manual selection needed)
- Multi-language support
- Team-level analytics dashboard
- Calendar integration for scheduling follow-ups
- CRM field auto-population from summaries
