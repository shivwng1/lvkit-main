"""
Production-ready Bhashini TTS implementation for LiveKit Agents

This module provides text-to-speech functionality using the Bhashini TTS API,
optimized for natural-sounding conversational AI applications.

Features:
- Complete text synthesis for natural speech flow
- Automatic text cleaning and preprocessing
- Robust error handling and validation
- Support for multiple Indian languages
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

# Bhashini API Configuration
BHASHINI_API_URL = "https://tts.bhashini.ai/v1/synthesize"
DEFAULT_TIMEOUT = 15.0
MAX_TEXT_LENGTH = 500  # Reasonable limit for TTS requests


@dataclass
class BhashiniVoice:
    """Configuration for a Bhashini voice"""
    language: str
    voice_name: str


# Available voice configurations
SUPPORTED_VOICES = {
    "kannada": BhashiniVoice("Kannada", "Male1"),
    "hindi": BhashiniVoice("Hindi", "Male1"), 
    "english": BhashiniVoice("English", "Female2"),
}


class BhashiniTTS(tts.TTS):
    """
    Bhashini TTS implementation for LiveKit Agents
    
    Provides high-quality text-to-speech synthesis using the Bhashini API,
    optimized for conversational AI applications with natural speech flow.
    """
    
    def __init__(
        self,
        *,
        voice: str = "english",
        speed: float = 1.2,
        api_timeout: float = DEFAULT_TIMEOUT,
        http_session: Optional[aiohttp.ClientSession] = None,
    ):
        """
        Initialize Bhashini TTS
        
        Args:
            voice: Voice identifier (english, hindi, kannada)
            speed: Speech rate multiplier (1.0 = normal, 1.2 = 20% faster)
            api_timeout: API request timeout in seconds
            http_session: Optional shared HTTP session for connection pooling
            
        Raises:
            ValueError: If the specified voice is not supported
        """
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=False,  # Complete text synthesis to prevent stuttering
                aligned_transcript=False,
            ),
            sample_rate=22050,
            num_channels=1,
        )
        
        if voice not in SUPPORTED_VOICES:
            raise ValueError(
                f"Voice '{voice}' not supported. "
                f"Available voices: {list(SUPPORTED_VOICES.keys())}"
            )
            
        self._voice = SUPPORTED_VOICES[voice]
        self._speed = max(0.5, min(2.0, speed))  # Clamp speed between 0.5x and 2.0x
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
    Text-to-speech synthesis stream
    
    Handles complete text synthesis with automatic preprocessing
    for natural conversational speech.
    """
    
    def __init__(
        self,
        *,
        tts: BhashiniTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts = tts
        
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        """Execute text-to-speech synthesis"""
        # Initialize audio output
        request_id = utils.shortuuid()
        logger.debug(f"Starting TTS synthesis with request_id: {request_id}")
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/mp3",
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
        text = re.sub(r'\[.*?\]', '', text)      # Other bracketed content
        
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
        Synthesize text using Bhashini TTS API
        
        Sends complete text as single request for natural speech flow.
        """
        if not text or not text.strip():
            logger.warning("Empty or whitespace-only text passed to _synthesize_text")
            return
            
        # Prepare API request
        payload = {
            "text": text,
            "language": self._tts._voice.language,
            "voiceName": self._tts._voice.voice_name
        }
        
        headers = {"Content-Type": "application/json"}
        
        # Use provided session or create new one
        session = self._tts._session
        if session is None:
            session = aiohttp.ClientSession()
            session_owner = True
        else:
            session_owner = False
            
        try:
            # Call Bhashini TTS API
            async with session.post(
                BHASHINI_API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._tts._api_timeout)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Bhashini API error {response.status}: {error_text}")
                    return
                
                # Process audio response
                audio_data = await response.read()
                
                if not audio_data:
                    logger.warning("Empty audio response from Bhashini TTS")
                    return
                
                # Validate audio format
                if not self._is_valid_mp3(audio_data):
                    logger.error("Invalid MP3 data received from Bhashini")
                    return
                
                # Apply speed adjustment if needed
                if abs(self._tts._speed - 1.0) > 0.05:  # Only process if speed differs significantly
                    logger.debug(f"Applying {self._tts._speed}x speed adjustment")
                    audio_data = self._adjust_audio_speed(audio_data, self._tts._speed)
                
                # Emit entire audio as single chunk to prevent stuttering
                logger.debug(f"Emitting {len(audio_data)} bytes of MP3 audio as single chunk")
                output_emitter.push(audio_data)
                
        except asyncio.TimeoutError:
            logger.error(f"Bhashini TTS request timed out after {self._tts._api_timeout}s")
        except Exception as e:
            logger.error(f"Bhashini TTS synthesis failed: {e}")
        finally:
            if session_owner:
                await session.close()
    
    def _is_valid_mp3(self, data: bytes) -> bool:
        """
        Validate MP3 audio data format
        
        Checks for standard MP3 file signatures to ensure valid audio data.
        """
        if len(data) < 10:
            return False
            
        # Check for ID3 metadata tag
        if data[:3] == b"ID3":
            return True
        
        # Check for MP3 frame sync pattern (0xFFE0-0xFFFF)
        if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
            return True
            
        logger.debug(f"Unrecognized audio format signature: {data[:10].hex()}")
        return False
    
    def _adjust_audio_speed(self, mp3_data: bytes, speed: float) -> bytes:
        """
        Adjust audio playback speed using ffmpeg
        
        Args:
            mp3_data: Original MP3 audio data
            speed: Speed multiplier (e.g., 1.2 for 20% faster)
            
        Returns:
            Speed-adjusted MP3 audio data
        """
        import tempfile
        import subprocess
        import os
        
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as input_file:
                input_file.write(mp3_data)
                input_path = input_file.name
            
            output_path = input_path.replace('.mp3', '_speed.mp3')
            
            try:
                # Use ffmpeg to adjust speed
                # atempo filter maintains pitch while changing speed
                cmd = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-filter:a', f'atempo={speed}',
                    '-acodec', 'libmp3lame',
                    '-loglevel', 'error',
                    output_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"Speed adjustment failed: {result.stderr}")
                    return mp3_data  # Return original if processing fails
                
                # Read speed-adjusted audio
                with open(output_path, 'rb') as f:
                    adjusted_data = f.read()
                
                logger.debug(f"Speed adjusted: {len(mp3_data)} -> {len(adjusted_data)} bytes")
                return adjusted_data
                
            finally:
                # Clean up temporary files
                if os.path.exists(input_path):
                    os.unlink(input_path)
                if os.path.exists(output_path):
                    os.unlink(output_path)
                    
        except Exception as e:
            logger.warning(f"Speed adjustment error: {e}, using original audio")
            return mp3_data