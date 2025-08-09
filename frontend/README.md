# Voice AI Assistant - Web Frontend

A simple web interface for making voice calls with the Bajaj Auto Finance debt collection agent.

## Features

- **Start/Stop Call**: Simple buttons to initiate and end voice calls
- **Real-time Status**: Visual indicators for connection status
- **Audio Controls**: Mute/unmute microphone and volume control
- **Live Logs**: Real-time logging of call events and agent interactions
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## Quick Start

1. **Set up environment variables:**
   ```bash
   cp ../.env.frontend.example .env.frontend
   # Edit .env.frontend with your LiveKit credentials
   ```

2. **Install Python dependencies:**
   ```bash
   pip install PyJWT
   ```

3. **Start the web server:**
   ```bash
   python server.py
   ```

4. **Open your browser:**
   ```
   http://localhost:8080
   ```

5. **Start your LiveKit agent** (in another terminal):
   ```bash
   cd ..
   uv run python src/agent.py dev
   ```

## Configuration

### Environment Variables

Create a `.env.frontend` file with your LiveKit credentials:

```bash
# LiveKit Server URL (use your LiveKit Cloud URL or local server)
LIVEKIT_URL=wss://your-project.livekit.cloud

# LiveKit API credentials
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# Room name (must match the agent configuration)
ROOM_NAME=debt-collection-room

# Web server port
PORT=8080
```

### LiveKit Setup

1. **Using LiveKit Cloud:**
   - Sign up at [cloud.livekit.io](https://cloud.livekit.io)
   - Create a new project
   - Copy your API key, secret, and WebSocket URL

2. **Using Self-hosted LiveKit:**
   - Follow the [self-hosting guide](https://docs.livekit.io/home/self-hosting/)
   - Use `ws://localhost:7880` for local development

## Usage

1. **Start Call**: Click the green "Start Call" button to connect to the LiveKit room
2. **Agent Connection**: Wait for the debt collection agent to join the room
3. **Voice Interaction**: Speak naturally - the agent will respond with debt collection dialogue
4. **Mute Control**: Use the mute button to temporarily disable your microphone
5. **Volume Control**: Adjust the agent's voice volume with the slider
6. **Stop Call**: Click the red "Stop Call" button to end the session

## Development

### File Structure

```
frontend/
├── index.html      # Main web interface
├── app.js          # LiveKit client integration
├── style.css       # UI styling
├── server.py       # Token server and file serving
└── README.md       # This file
```

### Token Server

The included `server.py` provides:
- **Static file serving** for the frontend files
- **Token generation** endpoint (`/token`) for LiveKit authentication
- **Configuration** endpoint (`/config`) for client settings
- **Health check** endpoint (`/health`) for monitoring

### Customization

You can customize the interface by modifying:

- **`style.css`**: Update colors, fonts, and layout
- **`app.js`**: Add new features or modify call logic
- **`index.html`**: Change the UI structure or add new elements

## Troubleshooting

### Common Issues

1. **"Failed to get access token"**
   - Check your `.env.frontend` file has correct LiveKit credentials
   - Ensure the token server is running

2. **"Connection Failed"**
   - Verify your `LIVEKIT_URL` is correct
   - Check if LiveKit server is running
   - Ensure your firewall allows WebSocket connections

3. **"Agent not joining"**
   - Make sure your agent is running (`uv run python src/agent.py dev`)
   - Check that both frontend and agent use the same room name
   - Look at agent logs for connection errors

4. **"No audio"**
   - Allow microphone permissions in your browser
   - Check browser developer tools for audio errors
   - Verify your microphone is working

### Browser Requirements

- **Chrome/Edge**: Recommended for best WebRTC support
- **Firefox**: Supported with some limitations
- **Safari**: Supported on macOS/iOS
- **HTTPS**: Required for microphone access (except localhost)

### Logs and Debugging

1. **Frontend logs**: Check the "Call Logs" section in the web interface
2. **Browser console**: Open Developer Tools (F12) for detailed errors
3. **Agent logs**: Check terminal output where agent is running
4. **Server logs**: Check terminal output where `server.py` is running

## Security Notes

- The token server in this example is for development only
- In production, implement proper authentication and token validation
- Use HTTPS in production for security
- Regularly rotate your LiveKit API credentials

## Integration

To integrate with your existing system:

1. **Replace the token server** with your authentication system
2. **Customize the agent instructions** in `../src/agent.py`
3. **Add call recording** if required for compliance
4. **Implement call analytics** for performance monitoring

## Support

For issues specific to this frontend, check the logs and ensure all dependencies are installed correctly.

For LiveKit-related issues, refer to the [LiveKit documentation](https://docs.livekit.io).