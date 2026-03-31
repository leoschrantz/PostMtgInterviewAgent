#!/bin/bash
# Start both the Streamlit app and the Gemini voice server.
# Usage: ./start.sh

set -e

echo "Starting Gemini voice server on port 8001..."
uvicorn voice_server:app --host 0.0.0.0 --port 8001 &
VOICE_PID=$!

echo "Starting Streamlit app on port 8501..."
streamlit run app.py --server.port 8501 &
STREAMLIT_PID=$!

# Clean shutdown
trap "echo 'Shutting down...'; kill $VOICE_PID $STREAMLIT_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo "Voice server:  http://localhost:8001"
echo "Streamlit app: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop both servers."

wait
