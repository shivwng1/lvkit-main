"""
Production-ready TTS Manager with multiple provider fallback support

This module provides a robust TTS system that can automatically fallback
between multiple TTS providers for maximum reliability and uptime.

Features:
- Automatic fallback between providers
- Health monitoring and provider scoring
- Configurable retry logic
- Performance metrics tracking
- Production-ready error handling
"""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from livekit.agents import tts, utils
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

from bhashini_tts import BhashiniTTS
from smallest_tts import SmallestTTS

logger = logging.getLogger(__name__)

class TTSProvider(Enum):
    """Available TTS providers"""
    SMALLEST = "smallest"
    BHASHINI = "bhashini"

@dataclass
class ProviderHealth:
    """Health metrics for a TTS provider"""
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    avg_response_time: float = 0.0
    consecutive_failures: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 100.0
        return (self.success_count / total) * 100.0
    
    @property
    def is_healthy(self) -> bool:
        """Check if provider is considered healthy"""
        # Consider unhealthy if more than 3 consecutive failures
        # or success rate below 70% with at least 10 attempts
        if self.consecutive_failures > 3:
            return False
        
        total_attempts = self.success_count + self.failure_count
        if total_attempts >= 10 and self.success_rate < 70.0:
            return False
            
        return True

class TTSManager(tts.TTS):
    """
    Production-ready TTS Manager with multi-provider fallback
    
    Automatically manages multiple TTS providers with health monitoring,
    fallback logic, and performance optimization for maximum reliability.
    """
    
    def __init__(
        self,
        *,
        primary_provider: TTSProvider = TTSProvider.SMALLEST,
        smallest_api_key: Optional[str] = None,
        voice: str = "english",  # Unified voice config
        speed: float = 1.2,
        api_timeout: float = 15.0,
        max_retries: int = 2,
    ):
        """
        Initialize TTS Manager with multiple providers
        
        Args:
            primary_provider: Preferred TTS provider to use first
            smallest_api_key: API key for Smallest.ai (required if using Smallest)
            voice: Voice identifier (mapped to provider-specific voices)
            speed: Speech rate multiplier
            api_timeout: API request timeout
            max_retries: Maximum retry attempts per provider
        """
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=False,
                aligned_transcript=False,
            ),
            sample_rate=24000,  # Use 24000 Hz for compatibility with Smallest.ai
            num_channels=1,
        )
        
        self._primary_provider = primary_provider
        self._voice = voice
        self._speed = speed
        self._api_timeout = api_timeout
        self._max_retries = max_retries
        
        # Initialize provider health tracking
        self._health: Dict[TTSProvider, ProviderHealth] = {
            TTSProvider.SMALLEST: ProviderHealth(),
            TTSProvider.BHASHINI: ProviderHealth(),
        }
        
        # Initialize TTS providers
        self._providers: Dict[TTSProvider, tts.TTS] = {}
        
        # Initialize Smallest.ai if API key provided
        if smallest_api_key:
            try:
                voice_map = {
                    "english": "female_english",
                    "hindi": "female_english",  # Fallback to English
                    "kannada": "female_english",  # Fallback to English
                }
                self._providers[TTSProvider.SMALLEST] = SmallestTTS(
                    voice=voice_map.get(voice, "female_english"),
                    speed=speed,
                    api_key=smallest_api_key,
                    api_timeout=api_timeout,
                )
                logger.info("Smallest.ai TTS provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Smallest.ai TTS: {e}")
        
        # Initialize Bhashini (no API key required)
        try:
            self._providers[TTSProvider.BHASHINI] = BhashiniTTS(
                voice=voice,
                speed=speed,
                api_timeout=api_timeout,
            )
            logger.info("Bhashini TTS provider initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Bhashini TTS: {e}")
        
        if not self._providers:
            raise ValueError("No TTS providers could be initialized")
        
        logger.info(f"TTS Manager initialized with {len(self._providers)} providers: {list(self._providers.keys())}")

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> "ManagedStream":
        """Create a synthesis stream with fallback support"""
        return ManagedStream(
            tts_manager=self,
            input_text=text,
            conn_options=conn_options,
        )
    
    def _get_provider_priority(self) -> List[TTSProvider]:
        """Get providers ordered by priority (health + preference)"""
        available_providers = list(self._providers.keys())
        
        # Sort by health score, then by primary preference
        def sort_key(provider: TTSProvider) -> tuple:
            health = self._health[provider]
            
            # Primary scoring factors:
            # 1. Is healthy (boolean)
            # 2. Success rate
            # 3. Inverse of consecutive failures
            # 4. Primary provider preference
            is_primary = 1 if provider == self._primary_provider else 0
            
            return (
                health.is_healthy,
                health.success_rate,
                -health.consecutive_failures,
                is_primary,
            )
        
        return sorted(available_providers, key=sort_key, reverse=True)
    
    def _record_success(self, provider: TTSProvider, response_time: float):
        """Record successful synthesis"""
        health = self._health[provider]
        health.success_count += 1
        health.last_success = time.time()
        health.consecutive_failures = 0
        
        # Update average response time (simple moving average)
        if health.avg_response_time == 0:
            health.avg_response_time = response_time
        else:
            health.avg_response_time = (health.avg_response_time + response_time) / 2
        
        logger.debug(f"{provider.value} TTS success - rate: {health.success_rate:.1f}%, avg_time: {health.avg_response_time:.2f}s")
    
    def _record_failure(self, provider: TTSProvider, error: str):
        """Record failed synthesis"""
        health = self._health[provider]
        health.failure_count += 1
        health.last_failure = time.time()
        health.consecutive_failures += 1
        
        logger.warning(f"{provider.value} TTS failure #{health.consecutive_failures} - rate: {health.success_rate:.1f}%, error: {error}")
    
    def get_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get current health status of all providers"""
        status = {}
        for provider, health in self._health.items():
            status[provider.value] = {
                "is_healthy": health.is_healthy,
                "success_rate": health.success_rate,
                "success_count": health.success_count,
                "failure_count": health.failure_count,
                "consecutive_failures": health.consecutive_failures,
                "avg_response_time": health.avg_response_time,
            }
        return status

    async def aclose(self) -> None:
        """Clean up all providers"""
        for provider_tts in self._providers.values():
            await provider_tts.aclose()


class ManagedStream(tts.ChunkedStream):
    """
    Managed TTS stream with automatic fallback support
    """
    
    def __init__(
        self,
        *,
        tts_manager: TTSManager,
        input_text: str,
        conn_options: APIConnectOptions,
    ):
        super().__init__(tts=tts_manager, input_text=input_text, conn_options=conn_options)
        self._manager = tts_manager
        
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        """Execute TTS synthesis with fallback logic"""
        # Initialize audio output
        request_id = utils.shortuuid()
        logger.debug(f"Starting managed TTS synthesis with request_id: {request_id}")
        
        # Try providers in priority order
        providers_to_try = self._manager._get_provider_priority()
        last_error = None
        
        for provider_type in providers_to_try:
            provider_tts = self._manager._providers[provider_type]
            
            logger.debug(f"Attempting TTS with {provider_type.value} provider")
            
            try:
                start_time = time.time()
                
                # Create synthesis stream for this provider
                stream = provider_tts.synthesize(self._input_text, conn_options=self._conn_options)
                
                # Track if we successfully emit any audio
                audio_emitted = False
                
                async for audio_event in stream:
                    if not audio_emitted:
                        # Initialize emitter on first successful audio chunk
                        output_emitter.initialize(
                            request_id=request_id,
                            sample_rate=provider_tts.sample_rate,
                            num_channels=provider_tts.num_channels,
                            mime_type="audio/pcm" if provider_type == TTSProvider.SMALLEST else "audio/mp3",
                        )
                        audio_emitted = True
                    
                    # Handle different audio data formats from providers
                    audio_data = audio_event.frame.data
                    if hasattr(audio_data, 'tobytes'):
                        # Numpy array - convert to bytes
                        output_emitter.push(audio_data.tobytes())
                    else:
                        # Already bytes
                        output_emitter.push(audio_data)
                
                # Record success if we emitted audio
                if audio_emitted:
                    response_time = time.time() - start_time
                    self._manager._record_success(provider_type, response_time)
                    logger.info(f"TTS synthesis successful with {provider_type.value} provider ({response_time:.2f}s)")
                    break
                else:
                    raise Exception("No audio frames were generated")
                    
            except Exception as e:
                last_error = str(e)
                self._manager._record_failure(provider_type, last_error)
                logger.warning(f"TTS synthesis failed with {provider_type.value}: {e}")
                continue
        else:
            # All providers failed
            logger.error(f"All TTS providers failed. Last error: {last_error}")
            raise Exception(f"TTS synthesis failed with all providers. Last error: {last_error}")
        
        output_emitter.flush()