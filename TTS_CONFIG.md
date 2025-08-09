# Bhashini TTS Configuration

## Overview
Production-ready Bhashini TTS integration for natural conversational AI speech.

## Features
- **Complete text synthesis** for natural speech flow
- **Automatic text preprocessing** removes formatting artifacts
- **Multi-language support** (English, Hindi, Kannada)
- **Robust error handling** with graceful fallbacks
- **Optimized performance** with connection pooling

## Usage

```python
from bhashini_tts import BhashiniTTS

# Initialize TTS with 1.2x speed for efficient conversations
tts = BhashiniTTS(voice="english", speed=1.2)  # or "hindi", "kannada"

# Use in agent
session = AgentSession(
    llm=groq.LLM(model="llama3-8b-8192"),
    stt=deepgram.STT(model="nova-3", language="multi"),
    tts=tts,  # Bhashini TTS
)
```

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `voice` | `"english"` | Voice language (`english`, `hindi`, `kannada`) |
| `speed` | `1.2` | Speech rate multiplier (0.5-2.0, 1.2 = 20% faster) |
| `api_timeout` | `15.0` | API request timeout (seconds) |
| `http_session` | `None` | Shared HTTP session for connection pooling |

## Voice Options

| Voice ID | Language | Speaker | Use Case |
|----------|----------|---------|----------|
| `english` | English | Female2 | Business/Professional |
| `hindi` | Hindi | Male1 | Regional conversations |
| `kannada` | Kannada | Male1 | Regional conversations |

## Performance Notes
- Uses complete text synthesis for natural speech flow
- Text automatically cleaned and normalized
- No streaming to avoid decoder race conditions
- Optimal for conversational AI applications

## API Requirements
- No API key required
- Internet connection needed
- Bhashini service availability dependent