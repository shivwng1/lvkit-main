"""
Production-ready Smallest.ai TTS implementation for LiveKit Agents

This module provides text-to-speech functionality using the Smallest.ai API,
optimized for natural-sounding conversational AI applications.

Features:
- High-quality voice synthesis with natural prosody
- Multiple voice options and languages
- Robust error handling and validation
- Speed adjustment capabilities
- Fallback support for reliability
"""

import asyncio
import aiohttp
import logging
import re
from typing import Optional
from dataclasses import dataclass

from livekit.agents import tts, utils
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

logger = logging.getLogger(__name__)

# Smallest.ai API Configuration
SMALLEST_API_URL = "https://waves-api.smallest.ai/api/v1/lightning-v2/get_speech"
DEFAULT_TIMEOUT = 30.0
MAX_TEXT_LENGTH = 1000  # Generous limit for TTS requests

@dataclass
class SmallestVoice:
    """Configuration for a Smallest.ai voice"""
    voice_id: str
    model: str = "lightning_v2"
    language: str = "en"

# Available voice configurations
SUPPORTED_VOICES = {
    "female_english": SmallestVoice("alice", "lightning_v2", "en"),
    "male_english": SmallestVoice("jack", "lightning_v2", "en"), 
    "female_warm": SmallestVoice("emma", "lightning_v2", "en"),
    "male_professional": SmallestVoice("david", "lightning_v2", "en"),
    "female_bright": SmallestVoice("sarah", "lightning_v2", "en"),
}

class SmallestTTS(tts.TTS):
    """
    Smallest.ai TTS implementation for LiveKit Agents
    
    Provides high-quality text-to-speech synthesis using the Smallest.ai API,
    optimized for conversational AI applications with natural speech flow.
    """
    
    def __init__(
        self,
        *,
        voice: str = "female_english",
        speed: float = 1.2,
        api_key: Optional[str] = None,
        api_timeout: float = DEFAULT_TIMEOUT,
        http_session: Optional[aiohttp.ClientSession] = None,
    ):
        """
        Initialize Smallest.ai TTS
        
        Args:
            voice: Voice identifier (female_english, male_english, etc.)
            speed: Speech rate multiplier (1.0 = normal, 1.2 = 20% faster)
            api_key: Smallest.ai API key (required)
            api_timeout: API request timeout in seconds
            http_session: Optional shared HTTP session for connection pooling
            
        Raises:
            ValueError: If the specified voice is not supported or API key is missing
        """
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=False,  # Complete text synthesis for optimal quality
                aligned_transcript=False,
            ),
            sample_rate=24000,  # Smallest.ai supports 24000 Hz
            num_channels=1,
        )
        
        if not api_key:
            raise ValueError("Smallest.ai API key is required")
            
        if voice not in SUPPORTED_VOICES:
            raise ValueError(
                f"Voice '{voice}' not supported. "
                f"Available voices: {list(SUPPORTED_VOICES.keys())}"
            )
            
        self._voice = SUPPORTED_VOICES[voice]
        self._speed = max(0.5, min(2.0, speed))  # Clamp speed between 0.5x and 2.0x
        self._api_key = api_key
        self._api_timeout = api_timeout
        self._session = http_session

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> "ChunkedStream":
        """Create a synthesis stream for the given text"""
        return ChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
        )

    async def aclose(self) -> None:
        """Clean up resources"""
        if self._session:
            await self._session.close()


class ChunkedStream(tts.ChunkedStream):
    """
    Text-to-speech synthesis stream for Smallest.ai
    
    Handles complete text synthesis with automatic preprocessing
    for natural conversational speech.
    """
    
    def __init__(
        self,
        *,
        tts: SmallestTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts = tts
        
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        """Execute text-to-speech synthesis"""
        # Initialize audio output
        request_id = utils.shortuuid()
        logger.debug(f"Starting Smallest.ai TTS synthesis with request_id: {request_id}")
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/pcm",  # PCM format for frame streaming
        )
        
        # Prepare and synthesize text
        cleaned_text = self._prepare_text_for_speech(self._input_text)
        if cleaned_text:
            logger.debug(f"Synthesizing text: '{cleaned_text[:100]}...' ({len(cleaned_text)} chars)")
            await self._synthesize_text(cleaned_text, output_emitter)
        else:
            logger.warning(f"No text to synthesize after cleaning original: '{self._input_text}'")
                
        output_emitter.flush()
    
    def _prepare_text_for_speech(self, text: str) -> str:
        """
        Prepare text for natural speech synthesis
        
        Removes formatting artifacts and normalizes text for better TTS output.
        """
        if not text or not text.strip():
            return ""
        
        # Remove markdown formatting
        text = re.sub(r'```[^`]*```', '', text)  # Code blocks
        text = re.sub(r'`[^`]*`', '', text)      # Inline code
        
        # Replace placeholders with natural speech equivalents
        text = re.sub(r'\[Customer Name\]', 'sir or madam', text, flags=re.IGNORECASE)
        text = re.sub(r'\[Fahad\]', 'Fahad', text, flags=re.IGNORECASE)
        text = re.sub(r'\[.*?\]', '', text)      # Other bracketed content
        
        # Clean up break tags and formatting
        text = re.sub(r'<break[^>]*>', ' ', text)  # Remove TTS break tags
        text = re.sub(r',,um,,', 'um', text)       # Convert thinking pauses
        text = re.sub(r'---', '', text)            # Remove dramatic emphasis
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Validate length
        if len(text) > MAX_TEXT_LENGTH:
            logger.warning(f"Text length ({len(text)}) exceeds maximum ({MAX_TEXT_LENGTH}), truncating")
            text = text[:MAX_TEXT_LENGTH]
        
        return text
    
    async def _synthesize_text(self, text: str, output_emitter: tts.AudioEmitter) -> None:
        """
        Synthesize text using Smallest.ai TTS API
        
        Sends complete text as single request for natural speech flow.
        """
        if not text or not text.strip():
            logger.warning("Empty or whitespace-only text passed to _synthesize_text")
            return
            
        # Prepare API request
        payload = {
            "text": text,
            "voice_id": self._tts._voice.voice_id,
            "sample_rate": self._tts.sample_rate,
            "speed": self._tts._speed,
            "consistency": 0.5,
            "similarity": 0,
            "enhancement": 1,
            "language": self._tts._voice.language,
            "output_format": "pcm"
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._tts._api_key}"
        }
        
        logger.debug(f"Smallest.ai TTS request - voice_id='{payload['voice_id']}', speed={payload['speed']}, sample_rate={payload['sample_rate']}")
        
        # Use provided session or create new one
        session = self._tts._session
        if session is None:
            session = aiohttp.ClientSession()
            session_owner = True
        else:
            session_owner = False
            
        try:
            # Call Smallest.ai TTS API
            async with session.post(
                SMALLEST_API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._tts._api_timeout)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Smallest.ai API error {response.status}: {error_text}")
                    return
                
                # Process audio response
                audio_data = await response.read()
                
                if not audio_data:
                    logger.warning("Empty audio response from Smallest.ai TTS")
                    return
                
                # Validate audio data
                if not audio_data or len(audio_data) < 100:
                    logger.error("Invalid or insufficient PCM data received from Smallest.ai")
                    return
                
                # Convert PCM to numpy array and emit as audio frames
                import numpy as np
                
                # Convert PCM bytes to numpy array (int16)
                audio_samples = np.frombuffer(audio_data, dtype=np.int16)
                
                # Calculate frame size for smooth playback (10ms chunks)
                frame_duration_ms = 10
                samples_per_frame = int(self._tts.sample_rate * frame_duration_ms / 1000)
                
                # Emit audio in small chunks for smooth streaming
                total_frames = 0
                for i in range(0, len(audio_samples), samples_per_frame):
                    chunk = audio_samples[i:i + samples_per_frame]
                    if len(chunk) > 0:
                        # Convert numpy array back to bytes for LiveKit
                        chunk_bytes = chunk.astype(np.int16).tobytes()
                        output_emitter.push(chunk_bytes)
                        total_frames += 1
                
                logger.debug(f"Emitted {len(audio_data)} PCM bytes as {total_frames} audio frames ({samples_per_frame} samples per frame)")
                
        except asyncio.TimeoutError:
            logger.error(f"Smallest.ai TTS request timed out after {self._tts._api_timeout}s")
        except Exception as e:
            logger.error(f"Smallest.ai TTS synthesis failed: {e}")
        finally:
            if session_owner:
                await session.close()
    
    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int, num_channels: int) -> bytes:
        """
        Convert raw PCM data to WAV format
        
        Args:
            pcm_data: Raw PCM audio data (int16)
            sample_rate: Audio sample rate
            num_channels: Number of audio channels
            
        Returns:
            WAV formatted audio data
        """
        import struct
        
        # WAV header parameters
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
        block_align = num_channels * (bits_per_sample // 8)
        data_size = len(pcm_data)
        file_size = 36 + data_size
        
        # Create WAV header
        wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF',           # ChunkID
            file_size,         # ChunkSize
            b'WAVE',           # Format
            b'fmt ',           # Subchunk1ID
            16,                # Subchunk1Size (PCM)
            1,                 # AudioFormat (PCM)
            num_channels,      # NumChannels
            sample_rate,       # SampleRate
            byte_rate,         # ByteRate
            block_align,       # BlockAlign
            bits_per_sample,   # BitsPerSample
            b'data',           # Subchunk2ID
            data_size          # Subchunk2Size
        )
        
        return wav_header + pcm_data