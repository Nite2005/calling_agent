# Architecture & Design Documentation

Deep dive into the system architecture, design patterns, and data flow.

## System Architecture

### High-Level Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         AI SDR Voice Agent                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Presentation Layer                       │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │  │
│  │  │ REST API │  │ WebSocket│  │ Webhooks │  │ TwiML    │   │  │
│  │  │ Endpoints│  │ Voice I/O│  │ Events   │  │ Voice    │   │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              △                                     │
│                              │                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Business Logic Layer                     │  │
│  │  ┌──────────────────────────────────────────────────────┐   │  │
│  │  │         Voice Processing Pipeline                   │   │  │
│  │  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐   │   │  │
│  │  │  │  Audio │  │ Intent │  │  LLM   │  │ Action │   │   │  │
│  │  │  │ Capture│  │Classify│  │Query   │  │Execute │   │   │  │
│  │  │  └────────┘  └────────┘  └────────┘  └────────┘   │   │  │
│  │  └──────────────────────────────────────────────────────┘   │  │
│  │                                                             │  │
│  │  ┌──────────────────────────────────────────────────────┐   │  │
│  │  │         Call State Management                        │   │  │
│  │  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐    │   │  │
│  │  │  │ Session│  │ History│  │Context │  │Interrupt   │   │  │
│  │  │  │ State  │  │ Track  │  │Cache   │  │Handling    │   │  │
│  │  │  └────────┘  └────────┘  └────────┘  └────────┘    │   │  │
│  │  └──────────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              △                                     │
│                              │                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Data Layer                              │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │  │
│  │  │ SQLite   │  │ ChromaDB │  │ Vector   │  │ File     │   │  │
│  │  │ (RDB)    │  │ (Vector) │  │ Cache    │  │ Storage  │   │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
        │                      │                    │
        ▼                      ▼                    ▼
    ┌─────────┐          ┌──────────┐         ┌──────────┐
    │ Twilio  │          │ Deepgram │         │ Ollama   │
    │ Voice   │          │ STT/TTS  │         │ LLM      │
    └─────────┘          └──────────┘         └──────────┘
```

## Component Details

### 1. Presentation Layer (main.py)

**Responsibility:** HTTP/WebSocket interface

**Key Components:**

```python
# REST API Router
@app.post("/v1/convai/agents")
async def create_agent(agent: AgentCreate, db: Session):
    # Agent CRUD operations
    # Returns: agent_id, config
    
@app.post("/v1/convai/outbound")
async def make_outbound_call(request: OutboundCallRequest):
    # Initiate outbound call
    # Returns: call_sid

# WebSocket Handler
@app.websocket("/ws/voice/{call_sid}")
async def voice_inbound(websocket: WebSocket, call_sid: str):
    # Real-time voice I/O
    # Bidirectional streaming with Twilio
```

**Data Flow:**
```
User HTTP Request
    ↓
FastAPI Route Handler
    ↓
Request Validation (Pydantic)
    ↓
Business Logic Processing
    ↓
Database Query/Update
    ↓
HTTP Response
```

### 2. Voice Processing Layer (voice_pipeline.py)

**Responsibility:** Audio processing, STT/TTS, interruption detection

**Architecture:**

```
┌──────────────────────────────────────┐
│      WebSocket Connection (Twilio)   │
└─────────────────────┬────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
   ┌─────────┐               ┌──────────┐
   │ Inbound │               │ Outbound │
   │ Media   │               │ Media    │
   │ Stream  │               │ Stream   │
   └────┬────┘               └──────────┘
        │
        ▼
   ┌─────────────────────────────────────┐
   │    Audio Energy Analysis            │
   │  - Calculate RMS energy             │
   │  - Update baseline                  │
   │  - Detect speech vs noise           │
   └────┬────────────────────────────────┘
        │
        ▼
   ┌─────────────────────────────────────┐
   │  Interrupt Detection                │
   │  - Check if energy > threshold      │
   │  - Validate sustained speech        │
   │  - Check debounce                   │
   │  - Trigger if all checks pass       │
   └────┬────────────────────────────────┘
        │
   ┌────┴──────────┬───────────────────┐
   │               │                   │
   No Interrupt    Interrupt Triggered
   │               │
   │               ▼
   │         ┌──────────────┐
   │         │ Clear TTS    │
   │         │ Reset Buffers│
   │         │ Ready Input  │
   │         └──────────────┘
   │
   ▼
┌──────────────────────────────────────┐
│   Send to STT (Deepgram)             │
│   - Stream audio chunks              │
│   - Get interim transcripts          │
│   - Collect final result             │
└──────────────────────────────────────┘
```

**Key Data Structures:**

```python
class WSConn:
    """Per-connection state"""
    # Audio buffers
    inbound_ulaw_buffer: bytearray       # Raw audio from user
    stt_transcript_buffer: str           # Current STT result
    
    # TTS queue
    tts_queue: asyncio.Queue             # Sentences to speak
    
    # Interruption state
    interrupt_requested: bool            # Flag to stop current speech
    speech_energy_buffer: deque          # Recent energy levels
    speech_start_time: float             # When speech started
    
    # Conversation state
    conversation_history: List[Dict]     # Chat history
    call_phase: str                      # CALL_START, DISCOVERY, ACTIVE
    
    # LLM/Vector search
    agent_config: Dict                   # Agent settings
    dynamic_variables: Dict              # Custom variables
```

### 3. Business Logic Layer (main.py)

**Call Processing Pipeline:**

```
User Input Received
    ↓
├─ [Validity Check]
│  ├─ Is response in progress?
│  ├─ Is interrupt pending?
│  ├─ Has silence threshold passed?
│  └─ Do we have final transcript?
│
├─ [Intent Classification]
│  ├─ HELLO - Greeting
│  ├─ GOODBYE - End call
│  ├─ CONFIRM - Yes/No response
│  ├─ QUESTION - Information request
│  └─ ACTION - Execute tool
│
├─ [Context Retrieval]
│  ├─ Embed user query
│  ├─ Search ChromaDB
│  ├─ Retrieve top-K relevant docs
│  └─ Format as context
│
├─ [LLM Generation]
│  ├─ Build system prompt
│  ├─ Add conversation history
│  ├─ Add retrieved context
│  ├─ Query Ollama with stream
│  └─ Collect full response
│
├─ [Response Processing]
│  ├─ Parse LLM output
│  ├─ Extract tool calls (if any)
│  ├─ Clean for TTS
│  └─ Split into sentences
│
├─ [Tool Execution] (Optional)
│  ├─ Validate tool parameters
│  ├─ Execute action
│  ├─ Collect result
│  └─ Return to conversation
│
└─ [TTS Generation]
   ├─ Queue each sentence
   ├─ Stream audio from Deepgram
   ├─ Send audio chunks to Twilio
   └─ Monitor for interrupts
```

### 4. Data Layer (models.py + utils.py)

**Database Schema:**

```sql
-- Agents: Voice agent configurations
CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT,
    system_prompt TEXT,
    first_message TEXT,
    voice_id TEXT,
    interrupt_enabled BOOLEAN DEFAULT 1,
    created_at DATETIME,
    updated_at DATETIME
);

-- Conversations: Call session history
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,  -- Twilio call_sid
    agent_id TEXT,
    status TEXT,  -- in-progress, completed, abandoned
    transcript TEXT,
    metadata JSONB,
    created_at DATETIME,
    updated_at DATETIME
);

-- WebhookConfigs: Notification endpoints
CREATE TABLE webhook_configs (
    id INTEGER PRIMARY KEY,
    event_type TEXT,
    url TEXT,
    agent_id TEXT,
    created_at DATETIME
);

-- KnowledgeBase: Embedded documents
CREATE TABLE knowledge_bases (
    id INTEGER PRIMARY KEY,
    agent_id TEXT,
    document TEXT,
    embedding BLOB,  -- Vector stored separately in ChromaDB
    created_at DATETIME
);
```

**Vector Database (ChromaDB):**

```python
# Document chunks stored with embeddings
ChromaDB Collection:
  - Document ID: unique identifier
  - Text: document chunk
  - Embedding: 384-dim vector (all-MiniLM-L6-v2)
  - Metadata: source, agent_id, timestamp
```

## Call State Machine

```
┌─────────────┐
│  CALL_START │  ← Call initiated
└──────┬──────┘
       │ Agent plays greeting
       ▼
┌─────────────┐
│ DISCOVERY   │  ← Gather info phase
├─────────────┤
│ • Listen to │
│   user      │
│ • Ask Qs    │
│ • Confirm   │
└──────┬──────┘
       │ After 2+ exchanges
       ▼
┌─────────────┐
│  ACTIVE     │  ← Main conversation
├─────────────┤
│ • Answer Qs │
│ • Execute   │
│   tools     │
│ • Handle    │
│   requests  │
└──────┬──────┘
       │ User says goodbye / timeout
       ▼
┌─────────────┐
│ COMPLETION  │  ← End call
├─────────────┤
│ • Play bye  │
│ • Log call  │
│ • Cleanup   │
└─────────────┘
```

## Interrupt Detection Algorithm

```python
def detect_interrupt():
    """
    Smart interruption detection that mimics human listening
    """
    
    while streaming_audio:
        # 1. Measure audio energy
        energy = calculate_rms_energy(audio_chunk)
        
        # 2. Adapt baseline (noise floor)
        if not currently_speaking:
            update_baseline(energy)
        
        # 3. Check if energy indicates speech
        threshold = max(
            baseline_energy * FACTOR,      # 2.8x baseline
            MIN_ENERGY                     # 800 floor
        )
        
        if energy > threshold:
            # 4. Buffer samples (need 2+ high-energy samples)
            speech_buffer.append(energy)
            
            if count(high_energy_samples) >= 2:
                # 5. Check duration (need 100ms+ of speech)
                duration = now - speech_start_time
                
                if duration >= MIN_SPEECH_MS:
                    # 6. Check debounce (avoid rapid interrupts)
                    since_last = now - last_interrupt_time
                    
                    if since_last >= DEBOUNCE_MS:
                        # 7. TRIGGER INTERRUPT!
                        handle_interrupt()
                        break
        else:
            # Reset detection when energy drops
            speech_buffer.clear()
            speech_start_time = None
```

**Detection Timeline:**
```
User starts talking:
  [Chunk 1] energy=600 (below threshold 2240)  ← No action
  [Chunk 2] energy=2500 (above threshold)      ← Start timer
  [Chunk 3] energy=2800 (above threshold)      ← 2 samples collected
                                                ← Duration check: 30ms
                                                ← Still waiting...
  [Chunk 4] energy=2600                        ← Duration: 60ms
                                                ← Still waiting...
  [Chunk 5] energy=2700                        ← Duration: 100ms+
                                                ← INTERRUPT! ✓
  
Total detection time: ~100-150ms (realistic interrupt)
```

## Request/Response Flow Examples

### Making an Outbound Call

```
Client Request:
POST /v1/convai/outbound
{
  "agent_id": "agent-123",
  "to_number": "+1234567890",
  "dynamic_variables": {"name": "John"}
}

Server Processing:
1. Validate agent exists
2. Load agent config
3. Create Conversation record
4. Call Twilio API
5. Return call_sid

Response:
{
  "call_sid": "CA123456789",
  "status": "initiated",
  "message": "Call queued"
}

Backend:
→ Twilio dials number
→ When answered, POSTs to /twiml/voice_outbound
→ FastAPI returns TwiML with WebSocket URL
→ Twilio connects WebSocket to /ws/voice/{call_sid}
→ Agent plays greeting
→ Conversation flow begins
```

### Processing User Input

```
Audio Streaming via WebSocket:
{
  "event": "media",
  "media": {
    "payload": "base64_encoded_ulaw_audio"
  },
  "streamSid": "SM123456"
}

Processing Pipeline:
1. Decode audio
2. Send to Deepgram STT
3. Receive interim + final transcripts
4. When final received:
   a. Check intent
   b. Query LLM with context
   c. Generate response
   d. Stream to TTS
   e. Send audio back via WebSocket

WebSocket Response:
{
  "event": "media",
  "streamSid": "SM123456",
  "media": {
    "payload": "base64_encoded_mulaw_audio"
  }
}
```

## Performance Optimizations

### 1. Streaming Architecture

```
Traditional (Blocking):
User speaks (20s) → Wait → STT (3s) → Wait → LLM (5s) → 
Wait → TTS (8s) → Send → Total 36s felt latency

Streaming (Optimized):
User speaks    ──────→ STT running continuously
               → LLM starts when STT done → LLM running
               → TTS streams while LLM still generating → Parallel
               → Audio sent immediately as ready

Total felt latency: ~2-3s (first audio playback)
```

### 2. Audio Buffering

```
Receive chunks → Process immediately
              ↓
         Interrupt detection (can trigger mid-sentence)
              ↓
         Send to STT (streams continuously)
              ↓
         No waiting for full audio
```

### 3. Vector Search Caching

```
Query: "Tell me about pricing"
  ↓
Embed with sentence-transformers
  ↓
Search ChromaDB (fast, in-memory)
  ↓
Retrieve top-3 docs (~10ms)
  ↓
Include in LLM context
  ↓
Better responses without API overhead
```

## Concurrency Model

```
Per-Call Threading:
┌─────────────────────────────────────┐
│  WebSocket Handler (async task)     │
│  - Receives media events            │
│  - Runs interrupt detection         │
│  - Routes to STT/processing         │
└────────────────┬────────────────────┘
                 │
    ┌────────────┼────────────────┐
    │            │                │
    ▼            ▼                ▼
┌──────────┐ ┌─────────────┐ ┌──────────┐
│  STT     │ │  Response   │ │  TTS     │
│ Stream   │ │ Generation  │ │ Worker   │
│ Handler  │ │ (query_rag) │ │ Task     │
└──────────┘ └─────────────┘ └──────────┘

All async, non-blocking
Multiple calls can run in parallel
Single FastAPI worker handles many calls
```

## Security Considerations

```
1. API Authentication
   - xi-api-key header required
   - Check against API_KEYS list
   - Rate limiting (future)

2. Data Privacy
   - Conversations stored in database
   - Never log sensitive info to stdout
   - Encrypt credentials in .env

3. Input Validation
   - Pydantic schemas validate all input
   - SQL injection prevented (SQLAlchemy ORM)
   - Command injection prevented

4. Call Isolation
   - Each call has isolated WSConn
   - No data leakage between calls
   - Clean up on disconnect
```

## Error Handling Strategy

```
Try/Except Hierarchy:

Outer (FastAPI):
  └─ Catches uncaught exceptions
     → Returns 500 error
     → Logs error
     
WebSocket Handler:
  └─ Catches connection errors
     → Closes connection gracefully
     → Cleans up resources
     
Business Logic:
  └─ Catches operation errors
     → Logs error
     → Sends to user if appropriate
     → Continues conversation
     
Audio Processing:
  └─ Handles partial failures
     → Retry audio chunks
     → Skip corrupted data
     → Never crash audio loop
```

## Future Enhancement Opportunities

1. **Multi-turn Tool Execution**
   - Complex tools requiring multiple steps
   - Tool confirmation before execution

2. **Custom Embeddings**
   - Fine-tuned models per agent
   - Domain-specific embeddings

3. **Sentiment Analysis**
   - Detect user frustration
   - Escalate to human if needed

4. **Multi-language Support**
   - Auto-detect language
   - Translate responses

5. **Voice Cloning**
   - Custom voice per agent
   - Consistency across calls

6. **Advanced Analytics**
   - Call success metrics
   - Sentiment trends
   - Response quality scoring

---

**Last Updated:** January 10, 2026
**Architecture Version:** 1.0
