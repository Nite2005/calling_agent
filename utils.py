"""
Core Utilities Module

Contains utility functions, configuration, logging, and client initialization
"""

import os
import re
import logging
import uuid
import time
import asyncio
from logging.handlers import RotatingFileHandler
from datetime import datetime as dt
from typing import Dict, Optional, List, Tuple

from dotenv import load_dotenv
import torch
import httpx
import ollama
from deepgram import DeepgramClient, DeepgramClientOptions
from sentence_transformers import SentenceTransformer
import chromadb
from twilio.rest import Client as TwilioClient

# ================================
# ENVIRONMENT CONFIGURATION
# ================================

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
PUBLIC_URL = os.getenv("PUBLIC_URL")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_VOICE = os.getenv("DEEPGRAM_VOICE", "aura-2-thalia-en")
DATA_FILE = os.getenv("DATA_FILE", "./data/data.json")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "384"))
TOP_K = int(os.getenv("TOP_K", "3"))

# 🎯 SMART INTERRUPT SETTINGS - Optimized for fast, natural interruption
INTERRUPT_ENABLED = os.getenv("INTERRUPT_ENABLED", "true").lower() == "true"
INTERRUPT_MIN_ENERGY = int(os.getenv("INTERRUPT_MIN_ENERGY", "500"))  # Lower threshold for better sensitivity
INTERRUPT_DEBOUNCE_MS = int(os.getenv("INTERRUPT_DEBOUNCE_MS", "300"))  # Faster re-interrupt capability
INTERRUPT_BASELINE_FACTOR = float(os.getenv("INTERRUPT_BASELINE_FACTOR", "2.0"))  # More sensitive to speech
INTERRUPT_MIN_SPEECH_MS = int(os.getenv("INTERRUPT_MIN_SPEECH_MS", "100"))  # Faster interrupt trigger
INTERRUPT_REQUIRE_TEXT = os.getenv("INTERRUPT_REQUIRE_TEXT", "false").lower() == "true"
INTERRUPT_DEBUG = os.getenv("INTERRUPT_DEBUG", "false").lower() == "true"  # Enable detailed interrupt logging
INTERRUPT_USE_VAD = os.getenv("INTERRUPT_USE_VAD", "true").lower() == "true"  # Use Deepgram VAD for interrupt validation

# ✅ SILENCE DETECTION
SILENCE_THRESHOLD_SEC = float(os.getenv("SILENCE_THRESHOLD_SEC", "0.8"))
UTTERANCE_END_MS = int(SILENCE_THRESHOLD_SEC * 1000)

# ✅ INTERIM TRANSCRIPT PROCESSING (Lower Latency)
ENABLE_INTERIM_PROCESSING = os.getenv("ENABLE_INTERIM_PROCESSING", "false").lower() == "true"
INTERIM_MIN_LENGTH = int(os.getenv("INTERIM_MIN_LENGTH", "5"))  # Min chars to process
INTERIM_CONFIDENCE_THRESHOLD = float(os.getenv("INTERIM_CONFIDENCE_THRESHOLD", "0.7"))  # Min confidence (0-1)

# Validation
REQUIRE_ENV = [TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, PUBLIC_URL, DEEPGRAM_API_KEY]
if not all(REQUIRE_ENV):
    raise RuntimeError("Missing required env: TWILIO_*, PUBLIC_URL, DEEPGRAM_API_KEY")

# JWT Secret
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")

# API Key Authentication
API_KEYS = os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else []

# Webhook Events
WEBHOOK_EVENTS = [
    "call.initiated",
    "call.started", 
    "call.ended",
    "call.failed",
    "transcript.partial",
    "transcript.final",
    "agent.response",
    "tool.called",
    "user.interrupted"
]

# ================================
# LOGGING CONFIGURATION
# ================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "server.log")

_logger = logging.getLogger("new")
_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
_ch = logging.StreamHandler()
_ch.setFormatter(_fmt)
_logger.addHandler(_ch)

try:
    _fh = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=2)
    _fh.setFormatter(_fmt)
    _logger.addHandler(_fh)
except Exception:
    pass


# ================================
# GPU DETECTION & OPTIMIZATION
# ================================

def detect_gpu():
    """Detect and configure GPU"""
    if torch.cuda.is_available():
        device = 'cuda'
        gpu_count = torch.cuda.device_count()
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        cuda_version = torch.version.cuda

        _logger.info("=" * 60)
        _logger.info("🚀 GPU DETECTED!")
        _logger.info(f"   Device: {gpu_name}")
        _logger.info(f"   Count: {gpu_count}")
        _logger.info(f"   Memory: {gpu_memory:.2f} GB")
        _logger.info(f"   CUDA: {cuda_version}")
        _logger.info("=" * 60)

        if torch.cuda.get_device_capability()[0] >= 8:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            _logger.info("✅ TF32 enabled (Ampere+ GPU)")

        torch.cuda.empty_cache()

    elif torch.backends.mps.is_available():
        device = 'mps'
        _logger.info("=" * 60)
        _logger.info("🚀 Apple Silicon GPU detected")
        _logger.info("=" * 60)
    else:
        device = 'cpu'
        _logger.warning("=" * 60)
        _logger.warning("⚠️ NO GPU DETECTED - Using CPU")
        _logger.warning("=" * 60)

    return device


DEVICE = detect_gpu()

_logger.info("🚀 Config: PUBLIC_URL=%s DEVICE=%s", PUBLIC_URL, DEVICE)
_logger.info("🎯 Interrupt: ENABLED=%s MIN_SPEECH=%dms MIN_ENERGY=%d BASELINE_FACTOR=%.1f",
             INTERRUPT_ENABLED, INTERRUPT_MIN_SPEECH_MS, INTERRUPT_MIN_ENERGY, INTERRUPT_BASELINE_FACTOR)
_logger.info("⏱️ Silence Threshold: %.1fs (utterance_end=%dms)",
             SILENCE_THRESHOLD_SEC, UTTERANCE_END_MS)


def public_ws_host() -> str:
    host = PUBLIC_URL.replace("https://", "").replace("http://", "").rstrip("/")
    return host


# ================================
# CLIENT INITIALIZATION
# ================================

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

deepgram_config = DeepgramClientOptions(options={"keepalive": "true", "timeout": "60"})
deepgram = DeepgramClient(DEEPGRAM_API_KEY, config=deepgram_config)

# Test Deepgram connection at startup
try:
    _logger.info(f"🎤 Testing Deepgram API connection...")
    # This won't actually test the connection until we use it, but we can at least verify the client is created
    if DEEPGRAM_API_KEY:
        _logger.info(f"✅ Deepgram API key configured")
    else:
        _logger.error(f"❌ Deepgram API key NOT configured!")
except Exception as e:
    _logger.error(f"❌ Deepgram initialization failed: {e}")

# 🚀 GPU-ACCELERATED EMBEDDING MODEL
_logger.info(f"📦 Loading SentenceTransformer on {DEVICE}...")
start_time = time.time()

embedder = SentenceTransformer(EMBED_MODEL, device=DEVICE)
embedder.eval()

if DEVICE == 'cuda':
    try:
        embedder.half()
        _logger.info("✅ FP16 precision enabled")
    except Exception as e:
        _logger.warning(f"⚠️ Could not enable FP16: {e}")

load_time = time.time() - start_time
_logger.info(f"✅ Model loaded in {load_time:.2f}s")

_logger.info("🔥 Warming up GPU...")
with torch.no_grad():
    _ = embedder.encode(
        ["warmup sentence for GPU initialization"],
        device=DEVICE,
        show_progress_bar=False,
        convert_to_numpy=True,
        batch_size=1
    )
_logger.info("✅ GPU warmed up")

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection("docs")

response_cache = {}


# ================================
# UTILITY FUNCTIONS
# ================================

def generate_agent_id() -> str:
    """Generate unique agent ID"""
    return f"agent_{uuid.uuid4().hex[:16]}"


def generate_conversation_id() -> str:
    """Generate unique conversation ID"""
    return f"conv_{uuid.uuid4().hex[:16]}"


def clean_markdown_for_tts(text: str) -> str:
    """Remove markdown formatting before TTS to prevent reading symbols aloud"""
    # Remove bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    
    # Remove italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    
    # Remove strikethrough: ~~text~~
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    
    # Remove code blocks: `text` or ```text```
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    
    # Remove links: [text](url) -> text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    
    # Remove headers: # text -> text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Remove bullet points: - text or * text -> text
    text = re.sub(r'^[\-\*]\s+', '', text, flags=re.MULTILINE)
    
    # Remove numbered lists: 1. text -> text
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def detect_intent(text: str) -> str:
    """Detect user intent - only detect GOODBYE"""
    t = text.lower().strip()

    if any(x in t for x in ["bye", "goodbye", "end the call", "that's all", "talk later"]):
        return "GOODBYE"

    return "QUESTION"


def detect_confirmation_response(text: str) -> Optional[str]:
    """Detect if user is confirming or rejecting a pending action"""
    text_lower = text.lower().strip()

    yes_patterns = [
        "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "please",
        "go ahead", "do it", "that's fine", "sounds good",
        "yes please", "yeah please", "sure thing", "absolutely",
        "correct", "right", "affirmative", "proceed", "transfer me",
        "let's do it", "fine", "alright", "all right"
    ]

    no_patterns = [
        "no", "nope", "nah", "not yet", "not now", "maybe later",
        "don't", "wait", "hold on", "cancel", "never mind",
        "not right now", "i'll think about it", "let me think",
        "not really", "not interested"
    ]

    for pattern in yes_patterns:
        if pattern == text_lower or pattern in text_lower:
            if "not " not in text_lower and "no " not in text_lower[:3]:
                return "yes"

    for pattern in no_patterns:
        if pattern == text_lower or pattern in text_lower:
            return "no"

    return None


def parse_llm_response(text: str) -> Tuple[str, Optional[dict]]:
    """Parse LLM response for tool calls"""
    tool_pattern = r'\[TOOL:([^\]]+)\]'
    confirm_pattern = r'\[CONFIRM_TOOL:([^\]]+)\]'

    tool_data = None

    confirm_matches = re.findall(confirm_pattern, text)
    if confirm_matches:
        tool_parts = confirm_matches[0].split(':')
        tool_name = tool_parts[0].strip()

        if tool_name == "transfer":
            department = tool_parts[1].strip() if len(tool_parts) > 1 else "sales"

            valid_departments = ["sales", "support", "technical"]
            if department not in valid_departments:
                _logger.warning(f"❌ Invalid department: {department}")
            else:
                tool_data = {
                    "tool": "transfer_call",
                    "params": {"department": department},
                    "requires_confirmation": True
                }
    else:
        tool_matches = re.findall(tool_pattern, text)
        if tool_matches:
            tool_parts = tool_matches[0].split(':')
            tool_name = tool_parts[0].strip()

            if tool_name == "end_call":
                tool_data = {
                    "tool": "end_call",
                    "params": {"reason": "user_requested"},
                    "requires_confirmation": False
                }
            elif tool_name == "transfer":
                department = tool_parts[1].strip() if len(tool_parts) > 1 else "sales"

                valid_departments = ["sales", "support", "technical"]
                if department not in valid_departments:
                    _logger.warning(f"❌ Invalid department: {department}")
                else:
                    tool_data = {
                        "tool": "transfer_call",
                        "params": {"department": department},
                        "requires_confirmation": False
                    }
            else:
                tool_params = {}
                
                if len(tool_parts) > 1:
                    remaining_parts = tool_parts[1:]
                    for idx, part in enumerate(remaining_parts):
                        tool_params[f"param{idx+1}"] = part.strip()
                
                tool_data = {
                    "tool": tool_name,
                    "params": tool_params,
                    "requires_confirmation": False
                }

    # Remove tool markers from text
    clean_text = re.sub(tool_pattern, '', text)
    clean_text = re.sub(confirm_pattern, '', clean_text)
    clean_text = clean_text.strip()

    return clean_text, tool_data


async def send_webhook(webhook_url: str, event: str, data: Dict) -> bool:
    """Send webhook notification (fire-and-forget)"""
    try:
        if not webhook_url.startswith(("http://", "https://")):
            _logger.error(f"❌ Invalid webhook URL: {webhook_url}")
            return False
        
        async with httpx.AsyncClient() as client:
            payload = {
                "event": event,
                "timestamp": dt.utcnow().isoformat(),
                "data": data
            }
            response = await client.post(webhook_url, json=payload, timeout=10)
            _logger.info(f"📤 Webhook sent: {event} to {webhook_url} (status: {response.status_code})")
            return response.status_code == 200
    except Exception as e:
        _logger.error(f"❌ Webhook failed: {event} to {webhook_url} - {e}")
        return False


async def send_webhook_and_get_response(webhook_url: str, event: str, data: Dict) -> Optional[Dict]:
    """Send webhook and wait for response"""
    try:
        if not webhook_url.startswith(("http://", "https://")):
            _logger.error(f"❌ Invalid webhook URL: {webhook_url}")
            return None
        
        async with httpx.AsyncClient() as client:
            payload = {
                "event": event,
                "timestamp": dt.utcnow().isoformat(),
                "data": data
            }
            response = await client.post(webhook_url, json=payload, timeout=10)
            _logger.info(f"📤 Webhook sent: {event} (status: {response.status_code})")
            
            if response.status_code == 200:
                response_data = response.json()
                _logger.info(f"📥 Webhook response received: {list(response_data.keys())}")
                return response_data
            else:
                _logger.warning(f"⚠️ Webhook returned non-200 status: {response.status_code}")
                return None
    except Exception as e:
        _logger.error(f"❌ Webhook failed: {event} - {e}")
        return None


def _chunk_text(text: str, chunk_size: int = 384, overlap: int = 50) -> List[str]:
    """Simple text chunking for knowledge base"""
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap
    
    return chunks
