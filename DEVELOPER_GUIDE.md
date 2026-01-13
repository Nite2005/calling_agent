# AI SDR Agent - Developer Documentation

## Table of Contents
1. [Project Architecture](#project-architecture)
2. [Development Setup](#development-setup)
3. [Module Reference](#module-reference)
4. [API Development](#api-development)
5. [Voice Pipeline](#voice-pipeline)
6. [Database Schema](#database-schema)
7. [Code Examples](#code-examples)
8. [Testing & Debugging](#testing--debugging)
9. [Contributing Guidelines](#contributing-guidelines)

---

## Project Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   REST API   │  │  WebSocket   │  │   Webhooks   │      │
│  │  Endpoints   │  │  (Voice)     │  │   (Twilio)   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │               │
│         └──────────────────┼──────────────────┘               │
│                            │                                  │
│                   ┌────────▼─────────┐                       │
│                   │  Voice Pipeline  │                       │
│                   │  (STT/TTS/LLM)   │                       │
│                   └────────┬─────────┘                       │
│                            │                                  │
│         ┌──────────────────┼──────────────────┐              │
│         │                  │                  │               │
│    ┌────▼────┐        ┌────▼────┐       ┌────▼────┐         │
│    │ Deepgram│        │ Ollama  │       │ Chroma  │         │
│    │ STT/TTS │        │  LLM    │       │  VDB    │         │
│    └─────────┘        └─────────┘       └─────────┘         │
│                                                               │
│    ┌──────────────────────────────────────────────────┐     │
│    │          SQLAlchemy ORM + SQLite DB              │     │
│    │  (Agents, Conversations, Tools, Webhooks)       │     │
│    └──────────────────────────────────────────────────┘     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| `main.py` | FastAPI app + REST API endpoints | `app`, `ConnectionManager` |
| `models.py` | SQLAlchemy ORM models | `Agent`, `Conversation`, `Tool` |
| `schemas.py` | Pydantic request/response models | `AgentCreate`, `CallRequest` |
| `utils.py` | Utilities, config, logging | `_logger`, `embedder`, `collection` |
| `voice_pipeline.py` | STT/TTS/audio processing | `WSConn`, `stream_tts_worker` |

---

## Development Setup

### Prerequisites
- Python 3.10+
- Twilio account with phone number
- Deepgram API key
- Ollama running locally (or remote)
- SQLite (included with Python)

### Local Development

```bash
# 1. Clone and navigate
cd /root/AI_SDR

# 2. Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env  # if exists, or create manually

# 5. Set required environment variables
export TWILIO_ACCOUNT_SID="ACxxx"
export TWILIO_AUTH_TOKEN="token"
export TWILIO_PHONE_NUMBER="+1xxx"
export DEEPGRAM_API_KEY="key"
export PUBLIC_URL="https://xxx.ngrok.dev"

# 6. Start Ollama (if running locally)
ollama serve

# 7. Run development server
uvicorn main:app --host 0.0.0.0 --port 9001 --reload
```

### Environment Variables

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=          # Your account SID
TWILIO_AUTH_TOKEN=           # Your auth token
TWILIO_PHONE_NUMBER=         # Your Twilio number (+1xxx)

# Voice Services
DEEPGRAM_API_KEY=            # Deepgram API key
DEEPGRAM_VOICE=aura-2-thalia-en  # Default voice
DEEPGRAM_STT_MODEL=nova-2    # Speech recognition model

# LLM Configuration
OLLAMA_MODEL=llama3:8b-instruct-q4_K_S
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Knowledge Base
CHROMA_PATH=./chroma_db      # Vector store path
DATA_FILE=./data/data.txt    # Training data

# API Settings
PUBLIC_URL=https://xxx.ngrok.dev  # For Twilio callbacks

# Interruption Settings
INTERRUPT_ENABLED=true
INTERRUPT_MIN_ENERGY=800
INTERRUPT_DEBOUNCE_MS=400
INTERRUPT_BASELINE_FACTOR=2.8
INTERRUPT_MIN_SPEECH_MS=100

# Logging
LOG_LEVEL=INFO
LOG_FILE=server.log
```

---

## Module Reference

### main.py

**Key Functions:**

```python
# Latency tracking
log_latency(conn, metric: str, timestamp: Optional[float])
report_full_latency(conn) -> dict

# Response generation
async def query_rag_streaming(text: str, history: List, call_sid: str)
async def process_streaming_transcript(call_sid: str)

# Call management
async def end_call_tool(call_sid: str, reason: str) -> dict
```

**Key Endpoints:**

```python
POST   /v1/convai/agents              # Create agent
GET    /v1/convai/agents              # List agents
GET    /v1/convai/agents/{agent_id}   # Get agent
PATCH  /v1/convai/agents/{agent_id}   # Update agent
DELETE /v1/convai/agents/{agent_id}   # Delete agent

GET    /v1/convai/conversations/{id}  # Get conversation
GET    /v1/convai/conversations       # List conversations

POST   /v1/convai/twilio/outbound-call  # Initiate call
GET    /voice/outbound                   # Twilio callback
POST   /voice/incoming                   # Incoming call webhook

GET    /v1/convai/latency/{call_sid}  # Latency metrics
```

### models.py

**Agent Model:**
```python
class Agent(Base):
    agent_id: str                    # Unique identifier
    name: str                        # Display name
    system_prompt: str              # AI system prompt
    first_message: str              # Greeting
    voice_id: str                   # Deepgram voice
    model_name: str                 # LLM model
    interrupt_enabled: bool         # Allow interruption
    silence_threshold_sec: float    # Silence timeout
```

**Conversation Model:**
```python
class Conversation(Base):
    conversation_id: str            # Call SID
    agent_id: str                   # Associated agent
    status: str                     # in-progress, completed, failed
    transcript: str                 # Full conversation
    phone_number: str               # Caller number
```

### voice_pipeline.py

**WSConn Class - Connection State:**

```python
class WSConn:
    ws: WebSocket                   # WebSocket connection
    stream_sid: str                 # Twilio media stream ID
    
    # Audio/Speech
    currently_speaking: bool        # Agent speaking
    interrupt_requested: bool       # Interrupt flag
    stt_transcript_buffer: str      # Current transcript
    stt_is_final: bool             # Final result flag
    
    # Agent/Call Data
    agent_id: str                   # Active agent
    agent_config: dict              # Agent settings
    conversation_history: list      # Chat history
    
    # Latency Tracking
    call_start_time: float
    llm_start_time: Optional[float]
    llm_end_time: Optional[float]
    tts_start_time: Optional[float]
    # ... (more timing fields)
```

**Key Functions:**

```python
async def handle_interrupt(call_sid: str)
    """Stop agent speaking and listen for user input"""

async def stream_tts_worker(call_sid: str)
    """Process TTS queue and stream audio to user"""

async def setup_streaming_stt(call_sid: str)
    """Initialize Deepgram speech-to-text streaming"""

def calculate_audio_energy(mulaw_bytes: bytes) -> int
    """Calculate RMS energy for interrupt detection"""
```

### utils.py

**Key Utilities:**

```python
# Configuration
_logger                         # Python logger instance
JWT_SECRET                      # JWT signing key
API_KEYS                        # Valid API keys list

# External Services
twilio_client                   # Twilio SDK client
embedder                        # Sentence transformer model
collection                      # Chroma vector collection
chroma_client                   # Chroma client

# Processing
clean_markdown_for_tts(text)   # Remove markdown for speech
detect_intent(text)            # Intent classification
parse_llm_response(response)   # Parse tool calls from response
```

---

## API Development

### Adding New Endpoints

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/convai", tags=["Example"])

@router.get("/example/{id}")
async def get_example(
    id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get example by ID"""
    try:
        item = db.query(Model).filter(Model.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Not found")
        return item
    except Exception as e:
        _logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router)
```

### Request/Response Validation

Create schemas in `schemas.py`:

```python
from pydantic import BaseModel, Field

class ExampleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    
    class Config:
        example = {
            "name": "Example",
            "description": "Example description"
        }

class ExampleResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True  # Use .dict() for responses
```

### Error Handling

```python
from fastapi import HTTPException

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    _logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )
```

---

## Voice Pipeline

### Audio Processing Flow

```
Twilio Media (µ-law) 
        │
        ▼
[calculate_audio_energy] ──► Interrupt detection
        │
        ▼
[Deepgram STT]
        │
        ▼
Transcript ──► Intent Detection
        │
        ▼
[LLM Generation]
        │
        ▼
Response Text
        │
        ▼
[Deepgram TTS]
        │
        ▼
Audio (PCM 16kHz)
        │
        ▼
[Resample to 8kHz]
        │
        ▼
[Convert to µ-law]
        │
        ▼
[Send to Twilio]
```

### Interrupt Detection Logic

```python
# In media handler (main.py ~1340)
if (INTERRUPT_ENABLED and 
    conn.currently_speaking and 
    energy > energy_threshold):
    
    conn.speech_energy_buffer.append(energy)
    
    # Need sustained energy (2+ samples)
    if len(conn.speech_energy_buffer) >= 2:
        high_count = sum(1 for e in buffer if e > threshold)
        
        # Need minimum duration (100ms)
        if duration_ms >= INTERRUPT_MIN_SPEECH_MS:
            await handle_interrupt(call_sid)
```

### Adding Custom Voice Processing

```python
# In voice_pipeline.py
async def custom_audio_filter(chunk: bytes) -> bytes:
    """Apply custom audio processing"""
    # Convert µ-law to PCM
    pcm = audioop.ulaw2lin(chunk, 2)
    
    # Apply filter (e.g., noise reduction)
    filtered = apply_filter(pcm)
    
    # Convert back to µ-law
    return audioop.lin2ulaw(filtered, 2)

# Use in media handler
filtered_chunk = await custom_audio_filter(chunk)
conn.deepgram_live.send(filtered_chunk)
```

---

## Database Schema

### Agent Table
```sql
CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    first_message TEXT,
    voice_provider TEXT DEFAULT 'deepgram',
    voice_id TEXT DEFAULT 'aura-2-thalia-en',
    model_provider TEXT DEFAULT 'ollama',
    model_name TEXT DEFAULT 'llama3:8b',
    interrupt_enabled BOOLEAN DEFAULT 1,
    silence_threshold_sec FLOAT DEFAULT 0.8,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);
```

### Conversation Table
```sql
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,  -- Twilio call_sid
    agent_id TEXT NOT NULL,
    status TEXT DEFAULT 'in-progress',  -- in-progress, completed, failed
    transcript TEXT,
    phone_number TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP
);
```

### Query Examples

```python
from models import Agent, Conversation, SessionLocal

db = SessionLocal()

# Get agent by ID
agent = db.query(Agent).filter(Agent.agent_id == "agent_123").first()

# Get all conversations for agent
convs = db.query(Conversation).filter(
    Conversation.agent_id == "agent_123"
).all()

# Get active agents
active = db.query(Agent).filter(Agent.is_active == True).all()

# Update agent
agent.system_prompt = "New prompt"
db.commit()

db.close()
```

---

## Code Examples

### Creating an Agent Programmatically

```python
from models import Agent, SessionLocal
from utils import generate_agent_id

db = SessionLocal()

agent = Agent(
    agent_id=generate_agent_id(),
    name="Sales Bot",
    system_prompt="""You are a helpful sales representative...""",
    first_message="Hello! How can I help you today?",
    voice_id="aura-2-thalia-en",
    model_name="llama3:8b-instruct-q4_K_S",
    interrupt_enabled=True,
    silence_threshold_sec=0.3
)

db.add(agent)
db.commit()
db.close()

print(f"Created agent: {agent.agent_id}")
```

### Handling Custom Tools

```python
# In process_streaming_transcript()
if tool_data:
    tool_name = tool_data.get('tool')
    parameters = tool_data.get('parameters', {})
    
    if tool_name == "search_knowledge_base":
        results = await search_kb(parameters['query'])
        response = format_results(results)
    elif tool_name == "book_appointment":
        response = await book_appointment(**parameters)
    
    await speak_text_streaming(call_sid, response)
```

### Implementing Custom LLM Logic

```python
# In query_rag_streaming()
async def custom_rag_query(text: str, history: List):
    """Custom RAG with additional logic"""
    
    # Embed query
    query_embedding = embedder.encode([text])[0]
    
    # Search vector DB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K
    )
    
    # Build context
    context = "\n".join([
        doc for docs in results['documents'] 
        for doc in docs
    ])
    
    # Generate with custom prompt
    prompt = f"""Context:
{context}

Conversation:
{format_history(history)}

User: {text}
Assistant:"""
    
    # Stream response
    async for chunk in ollama.generate(...):
        yield chunk
```

---

## Testing & Debugging

### Unit Testing Template

```python
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture
def test_agent():
    """Create test agent"""
    return {
        "name": "Test Agent",
        "system_prompt": "You are helpful",
        "first_message": "Hello"
    }

def test_create_agent(test_agent):
    response = client.post(
        "/v1/convai/agents",
        json=test_agent,
        headers={"xi-api-key": "test_key"}
    )
    assert response.status_code == 200
    assert "agent_id" in response.json()

def test_get_agent(test_agent):
    # Create first
    create_resp = client.post("/v1/convai/agents", json=test_agent)
    agent_id = create_resp.json()["agent_id"]
    
    # Get agent
    response = client.get(f"/v1/convai/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["name"] == test_agent["name"]
```

### Debugging Voice Issues

```bash
# 1. Check WebSocket connection
tail -f server.log | grep "WebSocket\|voice"

# 2. Monitor audio energy levels
tail -f server.log | grep "energy\|interrupt"

# 3. Check STT results
tail -f server.log | grep "STT\|transcript"

# 4. Check LLM generation
tail -f server.log | grep "Ollama\|generation"

# 5. Check latency
tail -f server.log | grep "⏱️\|LATENCY"
```

### Debug Mode

```python
# In main.py, add debug logging
if os.getenv("DEBUG"):
    _logger.setLevel(logging.DEBUG)
    
    @app.middleware("http")
    async def debug_middleware(request: Request, call_next):
        _logger.debug(f"→ {request.method} {request.url.path}")
        response = await call_next(request)
        _logger.debug(f"← {response.status_code}")
        return response
```

---

## Contributing Guidelines

### Code Style

- Follow PEP 8
- Use type hints for all functions
- Max line length: 100 characters
- Use async/await for I/O operations

```python
# ✅ Good
async def process_request(
    call_sid: str,
    text: str,
    db: Session
) -> Dict[str, Any]:
    """Process user request with RAG."""
    result = await query_rag(text)
    return result

# ❌ Avoid
async def process_request(call_sid, text, db):
    result = await query_rag(text)
    return result
```

### Git Workflow

```bash
# 1. Create feature branch
git checkout -b feature/your-feature

# 2. Make changes and commit
git add .
git commit -m "feat: add new feature description"

# 3. Push and create PR
git push origin feature/your-feature
```

### Commit Messages

Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code restructuring
- `test:` Tests
- `perf:` Performance

Example:
```
feat: add interrupt detection for seamless conversation

- Implement energy-based speech detection
- Add configurable debounce timing
- Add latency tracking for metrics
```

### Testing Requirements

```bash
# Run tests before committing
pytest tests/ -v

# Check coverage
pytest --cov=. tests/

# Lint code
pylint *.py
flake8 *.py
```

---

## Common Development Tasks

### Add a New Agent Setting

1. **Update model** (models.py):
```python
class Agent(Base):
    # ... existing fields ...
    custom_setting = Column(String, default="value")
```

2. **Update schema** (schemas.py):
```python
class AgentCreate(BaseModel):
    # ... existing fields ...
    custom_setting: Optional[str] = None
```

3. **Use in code** (main.py):
```python
agent_config["custom_setting"] = agent.custom_setting
```

### Add a New API Endpoint

1. Create schema
2. Add endpoint with validation
3. Add database queries
4. Add error handling
5. Add to tests

### Debug a Hanging Call

```bash
# 1. Check active connections
sqlite3 agents.db "SELECT conversation_id, status FROM conversations WHERE status='in-progress';"

# 2. Check logs for errors
tail -f server.log | grep ERROR

# 3. Check Twilio call status
curl -X GET "https://api.twilio.com/2010-04-01/Accounts/{SID}/Calls/{CALL_SID}" \
  -u "{SID}:{AUTH_TOKEN}"

# 4. Kill the connection
# In WebSocket handler:
await manager.disconnect(call_sid)
```

---

## Performance Optimization

### Database

```python
# ✅ Use select only needed columns
query = db.query(Agent.agent_id, Agent.name).filter(...)

# ❌ Load entire object if not needed
query = db.query(Agent).filter(...)

# ✅ Use indexing for frequent queries
# In models:
__table_args__ = (
    Index('idx_agent_status', 'agent_id', 'is_active'),
)
```

### LLM

```python
# ✅ Cache common responses
RESPONSE_CACHE = {}

if query_hash in RESPONSE_CACHE:
    return RESPONSE_CACHE[query_hash]

# ✅ Reduce context window
history = history[-5:]  # Keep only last 5 messages

# ❌ Generate long responses
"num_predict": 1200,  # Too long, use 512
```

### Voice

```python
# ✅ Buffer audio for efficiency
AUDIO_BUFFER_SIZE = 3200  # bytes

# ✅ Use appropriate audio format
encoding = "linear16"
sample_rate = "16000"

# ❌ Don't re-encode frequently
# Cache resampler state
conn.resampler_state = initial_state
```

---

## Troubleshooting Development Issues

| Issue | Solution |
|-------|----------|
| ModuleNotFoundError | Activate venv: `source venv/bin/activate` |
| Port 9001 in use | `lsof -i :9001` then `kill -9 PID` |
| Database locked | Delete `agents.db` and recreate schema |
| Ollama errors | Ensure ollama is running: `ollama serve` |
| Deepgram errors | Check API key and rate limits |
| WebSocket timeout | Check firewall/proxy settings |
| Audio quality issues | Check microphone input, audio levels |

---

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Deepgram API](https://developers.deepgram.com)
- [Twilio Voice](https://www.twilio.com/docs/voice)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/)
- [Ollama Documentation](https://ollama.ai)

---

**Last Updated:** January 2026
**Status:** Active Development
