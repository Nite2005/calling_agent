"""
Voice Processing Module

Handles speech-to-text, text-to-speech, interrupts, and voice pipeline
"""

import asyncio
import base64
import time
import struct
import io
import wave
import os
try:
    import audioop
except ImportError:
    # audioop might not be available on Windows Python 3.13+
    # We'll implement a fallback in the code
    audioop = None
from typing import Dict, Optional, List
from collections import deque
from datetime import datetime as dt

from fastapi import WebSocket
import httpx
import torch
import ollama
from deepgram import LiveTranscriptionEvents, LiveOptions

from utils import (
    _logger, DEEPGRAM_API_KEY, DEEPGRAM_VOICE, DEVICE, INTERRUPT_ENABLED,
    INTERRUPT_MIN_ENERGY, INTERRUPT_DEBOUNCE_MS, INTERRUPT_BASELINE_FACTOR,
    INTERRUPT_MIN_SPEECH_MS, SILENCE_THRESHOLD_SEC, UTTERANCE_END_MS,
    OLLAMA_MODEL, TOP_K, deepgram, embedder, collection, clean_markdown_for_tts,
    parse_llm_response
)


# ================================
# AUDIOOP FALLBACK IMPLEMENTATIONS
# ================================

if audioop is None:
    """Fallback implementations for audioop module (not available on some systems)"""
    
    class _AudioopFallback:
        @staticmethod
        def ulaw2lin(data: bytes, width: int) -> bytes:
            """Convert mu-law compressed audio to linear PCM"""
            # Simple mu-law to linear conversion lookup table
            ulaw_table = [
                -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
                -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
                -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
                -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
                -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
                -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
                -3908, -3780, -3652, -3524, -3396, -3268, -3140, -3012,
                -2884, -2756, -2628, -2500, -2372, -2244, -2116, -1988,
                -1924, -1860, -1796, -1732, -1668, -1604, -1540, -1476,
                -1412, -1348, -1284, -1220, -1156, -1092, -1028, -964,
                -924, -892, -860, -828, -796, -764, -732, -700,
                -668, -636, -604, -572, -540, -508, -476, -444,
                -412, -380, -348, -316, -284, -252, -220, -188,
                -156, -124, -92, -60, -28, 4, 36, 68,
                100, 132, 164, 196, 228, 260, 292, 324,
                356, 388, 420, 452, 484, 516, 548, 580,
                612, 644, 676, 708, 740, 772, 804, 836,
                868, 900, 932, 964, 996, 1028, 1060, 1092,
                1124, 1156, 1188, 1220, 1252, 1284, 1316, 1348,
                1380, 1412, 1444, 1476, 1508, 1540, 1572, 1604,
                1636, 1668, 1700, 1732, 1764, 1796, 1828, 1860,
                1924, 1956, 1988, 2020, 2052, 2084, 2116, 2148,
                2180, 2212, 2244, 2276, 2308, 2340, 2372, 2404,
                2436, 2468, 2500, 2532, 2564, 2596, 2628, 2660,
                2692, 2724, 2756, 2788, 2820, 2852, 2884, 2916,
                2948, 2980, 3012, 3044, 3076, 3108, 3140, 3172,
                3204, 3236, 3268, 3300, 3332, 3364, 3396, 3428,
                3460, 3492, 3524, 3556, 3588, 3620, 3652, 3684,
                3716, 3748, 3780, 3812, 3844, 3876, 3908, 3940,
                4004, 4068, 4132, 4196, 4260, 4324, 4388, 4452,
                4516, 4580, 4644, 4708, 4772, 4836, 4900, 4964,
                5028, 5092, 5156, 5220, 5284, 5348, 5412, 5476,
                5540, 5604, 5668, 5732, 5796, 5860, 5924, 5988,
                6052, 6116, 6180, 6244, 6308, 6372, 6436, 6500,
                6564, 6628, 6692, 6756, 6820, 6884, 6948, 7012,
                7076, 7140, 7204, 7268, 7332, 7396, 7460, 7524,
                7588, 7652, 7716, 7780, 7844, 7908, 7972, 8036,
                8100, 8164, 8228, 8292, 8356, 8420, 8484, 8548,
                8612, 8676, 8740, 8804, 8868, 8932, 8996, 9060,
                9124, 9188, 9252, 9316, 9380, 9444, 9508, 9572,
                9636, 9700, 9764, 9828, 9892, 9956, 10020, 10084,
                10148, 10212, 10276, 10340, 10404, 10468, 10532, 10596,
                10660, 10724, 10788, 10852, 10916, 10980, 11044, 11108,
                11172, 11236, 11300, 11364, 11428, 11492, 11556, 11620,
                11684, 11748, 11812, 11876, 11940, 12004, 12068, 12132,
                12196, 12260, 12324, 12388, 12452, 12516, 12580, 12644,
                12708, 12772, 12836, 12900, 12964, 13028, 13092, 13156,
                13220, 13284, 13348, 13412, 13476, 13540, 13604, 13668,
                13732, 13796, 13860, 13924, 13988, 14052, 14116, 14180,
                14244, 14308, 14372, 14436, 14500, 14564, 14628, 14692,
                14756, 14820, 14884, 14948, 15012, 15076, 15140, 15204,
                15268, 15332, 15396, 15460, 15524, 15588, 15652, 15716,
                15780, 15844, 15908, 15972, 16036, 16100, 16164, 16228,
            ]
            
            result = bytearray()
            for byte in data:
                value = ulaw_table[byte & 0xFF]
                result.extend(struct.pack('<h', value))
            return bytes(result)
        
        @staticmethod
        def rms(data: bytes, width: int) -> int:
            """Calculate RMS energy of audio data"""
            if not data or len(data) < width:
                return 0
            
            fmt = f'<{len(data) // width}h' if width == 2 else f'<{len(data) // width}B'
            samples = struct.unpack(fmt, data)
            
            sum_sq = sum(s * s for s in samples)
            mean_sq = sum_sq / len(samples) if samples else 0
            rms_val = int((mean_sq ** 0.5) + 0.5)
            return max(0, min(32767, rms_val))
        
        @staticmethod
        def lin2ulaw(data: bytes, width: int) -> bytes:
            """Convert linear PCM to mu-law compressed audio"""
            # Mu-law compression lookup (inverse of ulaw2lin)
            def lin2ulaw_sample(sample: int) -> int:
                BIAS = 0x84
                CLIP = 32635
                sample = min(CLIP, max(-CLIP, sample))
                
                if sample >= 0:
                    sign = 0
                else:
                    sign = 0x80
                    sample = -sample
                
                sample += BIAS
                exponent = 0
                mantissa = sample
                
                if mantissa >= 256:
                    exponent = 7
                    while exponent > 0 and mantissa >= (1 << (exponent + 8)):
                        exponent -= 1
                    mantissa >>= (exponent + 3)
                else:
                    exponent = 0
                    mantissa >>= 3
                
                ulaw = sign | (exponent << 4) | (mantissa & 0x0F)
                return ulaw ^ 0xFF
            
            result = bytearray()
            for i in range(0, len(data), width):
                if i + width <= len(data):
                    sample = struct.unpack('<h', data[i:i+width])[0]
                    result.append(lin2ulaw_sample(sample))
            
            return bytes(result)
        
        @staticmethod
        def ratecv(data: bytes, nchannels: int, sampwidth: int, inrate: int, outrate: int, state=None):
            """Resample audio data from inrate to outrate"""
            if inrate == outrate:
                return data, state
            
            # Simple resampling: just downsample by skipping samples
            ratio = inrate / outrate
            samples = len(data) // sampwidth
            sample_fmt = '<h' if sampwidth == 2 else '<B'
            
            result = bytearray()
            pos = 0.0
            
            while int(pos) < samples:
                idx = int(pos) * sampwidth
                if idx + sampwidth <= len(data):
                    sample = struct.unpack(sample_fmt, data[idx:idx+sampwidth])[0]
                    result.extend(struct.pack(sample_fmt, sample))
                pos += ratio
            
            return bytes(result), state
    
    audioop = _AudioopFallback()



class WSConn:
    """WebSocket connection state"""
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.stream_sid: Optional[str] = None
        self.inbound_ulaw_buffer: bytearray = bytearray()
        self.is_responding: bool = False
        self.last_transcript: str = ""
        self.stream_ready: bool = False
        self.speech_detected: bool = False
        self.currently_speaking: bool = False
        self.interrupt_requested: bool = False
        self.conversation_history: List[Dict[str, str]] = []
        
        # Call awareness
        self.call_phase: str = "CALL_START"
        self.last_intent: Optional[str] = None

        # Agent and call data
        self.agent_id: Optional[str] = None
        self.agent_config: Optional[Dict] = None
        self.dynamic_variables: Optional[Dict] = None
        self.custom_first_message: Optional[str] = None
        self.custom_voice_id: Optional[str] = None
        self.custom_model: Optional[str] = None
        self.conversation_id: Optional[str] = None

        # Streaming STT
        self.deepgram_live = None
        self.stt_transcript_buffer: str = ""
        self.stt_is_final: bool = False
        self.last_speech_time: Optional[float] = None
        self.silence_start: Optional[float] = None

        # Streaming TTS
        self.tts_queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        self.tts_task: Optional[asyncio.Task] = None

        # Smart interrupt detection
        self.user_speech_detected: bool = False
        self.speech_start_time: Optional[float] = None
        self.speech_energy_buffer: deque = deque(maxlen=10)
        self.last_interrupt_time: float = 0
        self.interrupt_debounce: float = INTERRUPT_DEBOUNCE_MS / 1000.0

        self.baseline_energy: float = INTERRUPT_MIN_ENERGY * 0.5
        self.background_samples: deque = deque(maxlen=30)

        self.last_interim_text: str = ""
        self.last_interim_time: float = 0.0
        self.last_interim_conf: float = 0.0
        self.last_tts_send_time: float = 0.0

        # Pending action confirmation
        self.pending_action: Optional[dict] = None
        # VAD validation
        self.vad_triggered_time: Optional[float] = None
        self.vad_validation_threshold: float = 0.3
        self.vad_validated: bool = False
        self.vad_timeout: float = 2.0  # Reduced from 5.0 to 2.0 seconds for faster response
        self.energy_drop_time: Optional[float] = None
        self.last_valid_speech_energy: float = 0.0

        # Session-level resampler state
        self.resampler_state = None
        self.resampler_initialized: bool = False


class ConnectionManager:
    """Manage WebSocket connections"""
    def __init__(self):
        self._conns: Dict[str, WSConn] = {}

    async def connect(self, call_sid: str, ws: WebSocket):
        self._conns[call_sid] = WSConn(ws)

    async def disconnect(self, call_sid: str):
        conn = self._conns.pop(call_sid, None)
        if conn:
            if conn.deepgram_live:
                try:
                    conn.deepgram_live.finish()
                except:
                    pass

            if conn.tts_task and not conn.tts_task.done():
                conn.tts_task.cancel()

            try:
                await conn.ws.close()
            except Exception:
                pass

    def get(self, call_sid: str) -> Optional[WSConn]:
        return self._conns.get(call_sid)

    async def send_media_chunk(self, call_sid: str, stream_sid: str, raw_mulaw_bytes: bytes):
        conn = self.get(call_sid)
        if not conn or not conn.ws or not conn.stream_ready:
            return False

        if conn.interrupt_requested:
            return False

        if not raw_mulaw_bytes or len(raw_mulaw_bytes) == 0:
            return False

        if not stream_sid or stream_sid != conn.stream_sid:
            _logger.warning(f"Invalid stream_sid: {stream_sid} vs {conn.stream_sid}")
            return False

        payload = base64.b64encode(raw_mulaw_bytes).decode("utf-8")

        msg = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": payload
            }
        }

        try:
            await conn.ws.send_json(msg)
            return True
        except Exception as e:
            return False


manager = ConnectionManager()


def calculate_audio_energy(mulaw_bytes: bytes) -> int:
    """Calculate RMS energy of audio chunk"""
    if not mulaw_bytes or len(mulaw_bytes) < 160:
        return 0
    try:
        pcm = audioop.ulaw2lin(mulaw_bytes, 2)
        return audioop.rms(pcm, 2)
    except Exception:
        return 0


def update_baseline(conn: WSConn, energy: int):
    """Update background noise baseline"""
    if not conn.currently_speaking:
        if energy < max(conn.baseline_energy * 2, 600):
            conn.background_samples.append(energy)
            if len(conn.background_samples) >= 20:
                recent_samples = list(conn.background_samples)[-20:]
                sorted_samples = sorted(recent_samples)
                weighted_median = sorted_samples[len(sorted_samples) // 2]
                conn.baseline_energy = (conn.baseline_energy * 0.7) + (weighted_median * 0.3)


async def handle_interrupt(call_sid: str):
    """Handle user interruption with INSTANT audio cutoff"""
    conn = manager.get(call_sid)
    if not conn:
        return

    _logger.info("⚡ INTERRUPT TRIGGERED - Immediate audio stop")

    # PRIORITY 1: Stop audio INSTANTLY
    conn.interrupt_requested = True
    conn.currently_speaking = False
    conn.is_responding = False

    # PRIORITY 2: Clear Twilio audio stream FIRST (most important for user experience)
    try:
        if conn.stream_sid:
            await conn.ws.send_json({
                "event": "clear",
                "streamSid": conn.stream_sid
            })
            # Send multiple clear commands for reliability
            await asyncio.sleep(0.01)
            await conn.ws.send_json({
                "event": "clear",
                "streamSid": conn.stream_sid
            })
            _logger.info("📡 Audio cleared in stream")
    except Exception as e:
        _logger.warning(f"Stream clear warning: {e}")

    # PRIORITY 3: Aggressively clear TTS queue
    cleared = 0
    while not conn.tts_queue.empty():
        try:
            conn.tts_queue.get_nowait()
            conn.tts_queue.task_done()
            cleared += 1
        except:
            break

    # PRIORITY 4: Reset all state for clean user input
    conn.stt_transcript_buffer = ""
    conn.stt_is_final = False
    conn.last_transcript = ""
    
    # Reset speech detection
    conn.speech_energy_buffer.clear()
    conn.speech_start_time = None
    conn.user_speech_detected = False
    conn.last_speech_time = time.time()
    conn.silence_start = None

    # Reset interim processing
    conn.last_interim_text = ""
    conn.last_interim_time = 0.0
    conn.last_interim_conf = 0.0

    _logger.info(f"✅ INTERRUPT COMPLETE: Cleared {cleared} TTS items, ready for user")


async def stream_tts_worker(call_sid: str):
    """Stream TTS worker"""
    conn = manager.get(call_sid)
    if not conn:
        return

    try:
        while True:
            text = await conn.tts_queue.get()

            if text is None:
                conn.tts_queue.task_done()
                break

            conn.tts_queue.task_done()

            if not text or not text.strip():
                continue

            if conn.interrupt_requested:
                _logger.info("⚡ TTS interrupted - immediate stop")
                # Aggressively clear remaining TTS queue
                while not conn.tts_queue.empty():
                    try:
                        conn.tts_queue.get_nowait()
                        conn.tts_queue.task_done()
                    except:
                        break
                # Reset all speaking state
                conn.currently_speaking = False
                conn.interrupt_requested = False
                conn.speech_energy_buffer.clear()
                conn.speech_start_time = None
                _logger.info("✅ TTS stopped, ready for user")
                break

            _logger.info("🎤 TTS sentence (%d chars): '%s...'",
                         len(text), text[:80])

            t_start = time.time()
            conn.currently_speaking = True
            conn.speech_energy_buffer.clear()
            conn.speech_start_time = None
            is_first_chunk = True
            audio_chunks_buffer = []

            try:
                url = "https://api.deepgram.com/v1/speak"
                headers = {
                    "Authorization": f"Token {DEEPGRAM_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {"text": text}
                
                voice_to_use = DEEPGRAM_VOICE
                voice_source = "env_default"
                
                if conn.custom_voice_id and str(conn.custom_voice_id).strip():
                    voice_to_use = conn.custom_voice_id
                    voice_source = "api_override"
                elif conn.agent_config and conn.agent_config.get("voice_id"):
                    voice_to_use = conn.agent_config["voice_id"]
                    voice_source = "agent_config"
                
                _logger.info(f"🎤 TTS Voice: {voice_to_use} (source: {voice_source})")
                
                params = {
                    "model": voice_to_use,
                    "encoding": "linear16",
                    "sample_rate": "16000"
                }

                interrupted = False
                chunk_count = 0

                async with httpx.AsyncClient(timeout=30.0) as client:
                    async with client.stream("POST", url, json=payload,
                                             headers=headers, params=params) as response:
                        response.raise_for_status()

                        async for audio_chunk in response.aiter_bytes(chunk_size=3200):
                            if conn.interrupt_requested:
                                _logger.info("🛑 TTS interrupted at chunk %d", chunk_count)
                                interrupted = True
                                break

                            if len(audio_chunk) == 0:
                                continue

                            try:
                                resampler_chunk_size = int(os.getenv('RESAMPLER_CHUNK_BUFFER_SIZE', '160'))
                                resampler_width = int(os.getenv('RESAMPLER_SAMPLE_WIDTH', '2'))
                                resampler_channels = int(os.getenv('RESAMPLER_CHANNELS', '1'))
                                resampler_input_rate = int(os.getenv('RESAMPLER_INPUT_RATE', '16000'))
                                resampler_output_rate = int(os.getenv('RESAMPLER_OUTPUT_RATE', '8000'))
                                
                                if conn.resampler_state is None:
                                    _, conn.resampler_state = audioop.ratecv(
                                        b'\x00' * resampler_chunk_size, resampler_width, resampler_channels,
                                        resampler_input_rate, resampler_output_rate, None
                                    )

                                pcm_8k, conn.resampler_state = audioop.ratecv(
                                    audio_chunk, resampler_width, resampler_channels,
                                    resampler_input_rate, resampler_output_rate,
                                    conn.resampler_state
                                )

                                if is_first_chunk and len(pcm_8k) >= 320:
                                    samples = list(struct.unpack(
                                        f'<{len(pcm_8k)//2}h', pcm_8k))

                                    fade_samples = min(160, len(samples))
                                    for i in range(fade_samples):
                                        fade_factor = (i + 1) / fade_samples
                                        samples[i] = int(samples[i] * fade_factor)

                                    pcm_8k = struct.pack(f'<{len(samples)}h', *samples)
                                    is_first_chunk = False

                                audio_chunks_buffer.append(pcm_8k)
                                
                                # Don't buffer - send immediately for smooth playback
                                if len(audio_chunks_buffer) >= 1:
                                    chunk_to_convert = audio_chunks_buffer.pop(0)
                                    mulaw = audioop.lin2ulaw(chunk_to_convert, 2)

                                    for i in range(0, len(mulaw), 160):
                                        if conn.interrupt_requested:
                                            interrupted = True
                                            break

                                        chunk_to_send = mulaw[i:i+160]
                                        if len(chunk_to_send) < 160:
                                            chunk_to_send += b'\xff' * (160 - len(chunk_to_send))

                                        success = await manager.send_media_chunk(
                                            call_sid, conn.stream_sid, chunk_to_send
                                        )
                                        if not success:
                                            interrupted = True
                                            break

                                        conn.last_tts_send_time = time.time()
                                        chunk_count += 1
                                        # No sleep - send as fast as possible

                                    if interrupted:
                                        break

                            except Exception as e:
                                continue
                
                if not interrupted and audio_chunks_buffer:
                    for idx, chunk_to_convert in enumerate(audio_chunks_buffer):
                        is_last_chunk = (idx == len(audio_chunks_buffer) - 1)
                        
                        if is_last_chunk and len(chunk_to_convert) >= 320:
                            try:
                                samples = list(struct.unpack(
                                    f'<{len(chunk_to_convert)//2}h', chunk_to_convert))
                                
                                fade_samples = min(160, len(samples))
                                start_idx = len(samples) - fade_samples
                                for i in range(fade_samples):
                                    fade_factor = 1.0 - ((i + 1) / fade_samples)
                                    samples[start_idx + i] = int(
                                        samples[start_idx + i] * fade_factor)
                                
                                chunk_to_convert = struct.pack(
                                    f'<{len(samples)}h', *samples)
                            except Exception as e:
                                _logger.warning(f"⚠️ Fade-out failed: {e}")
                        
                        mulaw = audioop.lin2ulaw(chunk_to_convert, 2)
                        
                        for i in range(0, len(mulaw), 160):
                            if conn.interrupt_requested:
                                interrupted = True
                                break

                            chunk_to_send = mulaw[i:i+160]
                            if len(chunk_to_send) < 160:
                                chunk_to_send += b'\xff' * (160 - len(chunk_to_send))

                            success = await manager.send_media_chunk(
                                call_sid, conn.stream_sid, chunk_to_send
                            )
                            if not success:
                                interrupted = True
                                break

                            conn.last_tts_send_time = time.time()
                            chunk_count += 1
                            # No sleep - send continuously

                        if interrupted:
                            break
                    
                    audio_chunks_buffer.clear()

                t_end = time.time()

                if interrupted:
                    await handle_interrupt(call_sid)
                    while not conn.tts_queue.empty():
                        try:
                            conn.tts_queue.get_nowait()
                            conn.tts_queue.task_done()
                        except:
                            break
                else:
                    _logger.info("✅ Sentence completed in %.0fms (%d chunks)",
                                 (t_end - t_start)*1000, chunk_count)

            except Exception as e:
                _logger.error(f"❌ TTS streaming error: {e}")
                if "resampler" in str(e).lower() or "ratecv" in str(e).lower():
                    _logger.warning("⚠️ Resampler error detected - resetting state")
                    conn.resampler_state = None

            if conn.tts_queue.empty():
                conn.currently_speaking = False
                conn.interrupt_requested = False
                conn.speech_energy_buffer.clear()
                conn.speech_start_time = None
                conn.user_speech_detected = False
                _logger.info("🎤 TTS queue empty - agent finished speaking")

    except asyncio.CancelledError:
        pass
    except Exception as e:
        pass
    finally:
        conn.currently_speaking = False
        conn.interrupt_requested = False


async def speak_text_streaming(call_sid: str, text: str):
    """Queue text with sentence splitting"""
    conn = manager.get(call_sid)
    if not conn or not conn.stream_sid:
        return

    try:
        if conn.stream_sid:
            await conn.ws.send_json({
                "event": "clear",
                "streamSid": conn.stream_sid
            })
    except:
        pass

    # Set flag immediately - agent is about to speak
    conn.currently_speaking = True
    conn.interrupt_requested = False
    conn.speech_energy_buffer.clear()
    conn.user_speech_detected = False

    # Split into sentences
    sentences = []
    current = ""
    for char in text:
        current += char
        if char in '.!?' and len(current.strip()) > 10:
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())

    for sentence in sentences:
        if sentence:
            try:
                await asyncio.wait_for(conn.tts_queue.put(sentence), timeout=2.0)
            except asyncio.TimeoutError:
                break
            except Exception as e:
                break

    # Wait for TTS processing to complete
    # stream_tts_worker will manage currently_speaking flag during streaming
    await conn.tts_queue.join()


async def setup_streaming_stt(call_sid: str):
    """Setup Deepgram streaming STT"""
    conn = manager.get(call_sid)
    if not conn:
        _logger.error("❌ Connection not found for call_sid: %s", call_sid)
        return

    try:
        _logger.info("🎤 Creating Deepgram live connection...")
        dg_connection = deepgram.listen.live.v("1")

        def on_message(self, result, **kwargs):
            try:
                if not result or not result.channel:
                    return
                alt = result.channel.alternatives[0]
                transcript = alt.transcript
                if not transcript:
                    return

                is_final = result.is_final
                now = time.time()

                _logger.info("🎙️ STT %s: '%s'",
                             "FINAL" if is_final else "interim", transcript)

                conn.last_speech_time = now

                if is_final:
                    current_buffer = conn.stt_transcript_buffer.strip()

                    if current_buffer:
                        if (not current_buffer.endswith((".", "!", "?")) and len(transcript) > 3):
                            conn.stt_transcript_buffer += " " + transcript
                            _logger.info(f"➕ Appending to sentence: '{transcript}'")
                        else:
                            conn.stt_transcript_buffer = transcript
                            _logger.info(f"🔄 New sentence: '{transcript}'")
                    else:
                        conn.stt_transcript_buffer = transcript

                    conn.stt_is_final = True

                    _logger.info(f"🎙️ Complete buffer: '{conn.stt_transcript_buffer.strip()}'")

                else:
                    conn.last_interim_time = now
                    conn.last_interim_text = transcript

                    if not conn.stt_transcript_buffer or not conn.stt_is_final:
                        conn.stt_transcript_buffer = transcript
                        _logger.info(f"🎙️ Interim as buffer: '{transcript}'")

            except Exception as e:
                _logger.error(f"❌ Error in on_message: {e}")

        def on_open(self, open, **kwargs):
            _logger.info("✅ Deepgram connection opened")

        def on_error(self, error, **kwargs):
            _logger.error(f"❌ Deepgram error: {error}")

        def on_close(self, close_msg, **kwargs):
            _logger.info("🔌 Deepgram connection closed")

        def on_speech_started(self, speech_started, **kwargs):
            conn.vad_triggered_time = time.time()
            conn.user_speech_detected = True
            conn.speech_start_time = time.time()
            _logger.info("🎤 VAD: Speech trigger (needs validation)")

        def on_utterance_end(self, utterance_end, **kwargs):
            now = time.time()

            if conn.last_interim_time and (now - conn.last_interim_time) < 0.2:
                _logger.info("⭐ UtteranceEnd ignored - recent interim detected")
                return

            if conn.user_speech_detected:
                _logger.info("✅ UtteranceEnd - clearing VAD")
                conn.user_speech_detected = False
                conn.speech_start_time = None
                conn.vad_triggered_time = None
                conn.vad_validated = False
                conn.energy_drop_time = None

            conn.last_speech_time = now

        dg_connection.on(LiveTranscriptionEvents.Open, on_open)
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
        dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)

        options = LiveOptions(
            model=os.getenv("DEEPGRAM_STT_MODEL", "nova-2"),
            language="en-US",
            smart_format=True,
            interim_results=True,
            vad_events=True,
            encoding="mulaw",
            sample_rate=8000,
            channels=1,
            endpointing=UTTERANCE_END_MS,
        )

        start_ok = False
        try:
            _logger.info("🎤 Starting Deepgram with options: %s", options)
            start_ok = dg_connection.start(options)
            _logger.info("✅ Deepgram start() returned: %s", start_ok)
        except Exception as e:
            _logger.error(f"❌ Deepgram start failed: {e}")

        if not start_ok:
            fallback = LiveOptions(
                model=os.getenv("DEEPGRAM_STT_FALLBACK_MODEL", "nova-2-general"),
                encoding="mulaw",
                sample_rate=8000,
                interim_results=True,
            )
            try:
                _logger.info("🎤 Trying fallback Deepgram model...")
                start_ok = dg_connection.start(fallback)
            except Exception as e2:
                _logger.error(f"❌ Fallback failed: {e2}")
                return

        if start_ok:
            conn.deepgram_live = dg_connection
            _logger.info("✅ Streaming STT initialized")
        else:
            _logger.error("❌ Deepgram start() returned False")

    except Exception as e:
        _logger.error(f"❌ Setup streaming STT failed: {e}")
