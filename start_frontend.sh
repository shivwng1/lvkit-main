#!/bin/bash

# Voice AI Assistant Frontend Startup Script
# This script sets up and starts the web frontend for the debt collection agent

set -e

echo "🚀 Starting Voice AI Assistant Frontend..."

# Check if we're in the right directory
if [ ! -f "src/agent.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "   Expected to find src/agent.py in current directory"
    exit 1
fi

# Check UV virtual environment
echo "📦 Checking Python dependencies..."
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtual environment not found. Running: uv sync"
    uv sync
fi

# Verify PyJWT is available
if python3 -c "import sys, os; sys.path.insert(0, os.path.join('.venv', 'lib', 'python3.13', 'site-packages')); import jwt" 2>/dev/null; then
    echo "✅ PyJWT available"
else
    echo "⚠️  PyJWT not found, installing..."
    uv add PyJWT
fi

# Create frontend environment file if it doesn't exist
if [ ! -f ".env.frontend" ]; then
    echo "📝 Creating .env.frontend from example..."
    cp .env.frontend.example .env.frontend
    echo "⚠️  Please edit .env.frontend with your LiveKit credentials before starting calls"
fi

# Load environment variables
if [ -f ".env.frontend" ]; then
    echo "🔧 Loading frontend configuration..."
    set -a
    source .env.frontend
    set +a
fi

# Check for required environment variables
check_env_var() {
    if [ -z "${!1}" ]; then
        echo "⚠️  Warning: $1 not set in .env.frontend"
        return 1
    fi
    return 0
}

echo "🔍 Checking configuration..."
MISSING_VARS=0

if ! check_env_var "LIVEKIT_URL"; then MISSING_VARS=$((MISSING_VARS + 1)); fi
if ! check_env_var "LIVEKIT_API_KEY"; then MISSING_VARS=$((MISSING_VARS + 1)); fi
if ! check_env_var "LIVEKIT_API_SECRET"; then MISSING_VARS=$((MISSING_VARS + 1)); fi

if [ $MISSING_VARS -gt 0 ]; then
    echo ""
    echo "❌ Missing $MISSING_VARS required environment variable(s)"
    echo "   Please edit .env.frontend with your LiveKit credentials"
    echo ""
    echo "   You can get these from:"
    echo "   - LiveKit Cloud: https://cloud.livekit.io"
    echo "   - Or set up a local LiveKit server"
    echo ""
    echo "   Example .env.frontend:"
    echo "   LIVEKIT_URL=wss://your-project.livekit.cloud"
    echo "   LIVEKIT_API_KEY=your_api_key"
    echo "   LIVEKIT_API_SECRET=your_api_secret"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Set default port if not specified
PORT=${PORT:-8080}

echo ""
echo "🌐 Starting frontend server..."
echo "   Server URL: http://localhost:$PORT"
echo "   LiveKit URL: ${LIVEKIT_URL:-'Not configured'}"
echo "   Room Name: ${ROOM_NAME:-'debt-collection-room'}"
echo ""
echo "📋 Next steps:"
echo "   1. Open http://localhost:$PORT in your browser"
echo "   2. Start the agent: uv run python src/agent.py dev"
echo "   3. Click 'Start Call' in the web interface"
echo ""
echo "💡 Tips:"
echo "   - Allow microphone permissions when prompted"
echo "   - Use Chrome/Edge for best compatibility"
echo "   - Check the logs in the web interface for debugging"
echo ""
echo "🛑 Press Ctrl+C to stop the server"
echo ""

# Change to frontend directory and start the server
cd frontend

# Export environment variables for the Python server
export LIVEKIT_URL
export LIVEKIT_API_KEY
export LIVEKIT_API_SECRET
export ROOM_NAME
export PORT

python3 server.py