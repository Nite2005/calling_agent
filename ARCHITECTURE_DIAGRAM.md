# AI SDR System Architecture - High Level Overview

## System Architecture Diagram

```
╔════════════════════════════════════════════════════════════════════════════╗
║                       AI VOICE SDR SYSTEM                                  ║
║                      Enterprise Voice Agent Platform                        ║
╚════════════════════════════════════════════════════════════════════════════╝

                              EXTERNAL INTEGRATIONS
                        ┌─────────────────────────────────┐
                        │                                 │
                 ┌──────▼─────┐  ┌──────────────┐  ┌─────▼─────┐
                 │   Twilio   │  │  Deepgram    │  │   Ollama  │
                 │ Phone/Call │  │ STT/TTS/     │  │    LLM    │
                 │ Management │  │ Voice Stream │  │ Language  │
                 └──────┬─────┘  └──────────────┘  └───────────┘
                        │
        ┌───────────────┼───────────────────────────────────────────┐
        │               │                                           │
        ▼               ▼                                           ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │                     PRESENTATION LAYER                             │
   │                     FastAPI Application                            │
   ├─────────────────────────────────────────────────────────────────────┤
   │                                                                     │
   │  ┌───────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
   │  │  REST API Routes  │  │   WebSocket      │  │   TwiML Voice  │ │
   │  ├───────────────────┤  │   Connections    │  │   Response     │ │
   │  │ Agent Management  │  ├──────────────────┤  ├─────────────────┤ │
   │  │ Conversation CRUD │  │ /media-stream    │  │ /voice/inbound │ │
   │  │ Knowledge Base    │  │ Media streaming  │  │ /voice/outbound│ │
   │  │ Tools & Webhooks  │  │ Real-time I/O    │  │ TwiML Response │ │
   │  │ Phone Numbers     │  │ Event handling   │  │ Call control   │ │
   │  └───────────────────┘  └──────────────────┘  └─────────────────┘ │
   │                                                                     │
   └────────────────┬──────────────────────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │               BUSINESS LOGIC & ORCHESTRATION LAYER                  │
   ├─────────────────────────────────────────────────────────────────────┤
   │                                                                     │
   │  ┌──────────────────────────────────────────────────────────────┐  │
   │  │           VOICE PIPELINE (voice_pipeline.py)                 │  │
   │  ├──────────────────────────────────────────────────────────────┤  │
   │  │                                                              │  │
   │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │  │
   │  │  │   Audio      │  │    STT       │  │   Interruption  │  │  │
   │  │  │   Capture    │  │   (Deepgram  │  │   Detection     │  │  │
   │  │  │   & Resampl. │  │    Stream)   │  │   (VAD + Energy)│  │  │
   │  │  └──────────────┘  └──────────────┘  └──────────────────┘  │  │
   │  │                                                              │  │
   │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │  │
   │  │  │   Intent     │  │     RAG      │  │     LLM          │  │  │
   │  │  │  Detection   │  │   Query      │  │   Response       │  │  │
   │  │  │   (Classifier)   │ (ChromaDB)   │  │  Generation      │  │  │
   │  │  └──────────────┘  └──────────────┘  └──────────────────┘  │  │
   │  │                                                              │  │
   │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │  │
   │  │  │     TTS      │  │     Tool     │  │    Webhook       │  │  │
   │  │  │  (Deepgram)  │  │   Execution  │  │   Callbacks      │  │  │
   │  │  │  Streaming   │  │   & Control  │  │   & Events       │  │  │
   │  │  └──────────────┘  └──────────────┘  └──────────────────┘  │  │
   │  │                                                              │  │
   │  └──────────────────────────────────────────────────────────────┘  │
   │                                                                     │
   │  ┌──────────────────────────────────────────────────────────────┐  │
   │  │        CONNECTION MANAGER (utils.py)                         │  │
   │  ├──────────────────────────────────────────────────────────────┤  │
   │  │                                                              │  │
   │  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │  │
   │  │  │  Call Session  │  │  Conversation  │  │  Agent       │  │  │
   │  │  │   State        │  │  History/CTX   │  │  Config      │  │  │
   │  │  │   Management   │  │  Preservation  │  │  Override    │  │  │
   │  │  └────────────────┘  └────────────────┘  └──────────────┘  │  │
   │  │                                                              │  │
   │  └──────────────────────────────────────────────────────────────┘  │
   │                                                                     │
   └────────────────┬──────────────────────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │                     DATA & PERSISTENCE LAYER                        │
   ├─────────────────────────────────────────────────────────────────────┤
   │                                                                     │
   │  ┌──────────────────┐  ┌────────────────────┐  ┌──────────────┐   │
   │  │   SQLite DB      │  │   ChromaDB         │  │  Models &    │   │
   │  │   (models.py)    │  │   (Vector Store)   │  │  Schemas     │   │
   │  ├──────────────────┤  ├────────────────────┤  │  (py files)  │   │
   │  │ • Agents         │  │ • Embeddings       │  └──────────────┘   │
   │  │ • Conversations  │  │ • Knowledge Base   │                     │
   │  │ • Webhooks       │  │ • Semantic Search  │                     │
   │  │ • Tools          │  │ • Agent KB Index   │                     │
   │  │ • PhoneNumbers   │  │ • Query Results    │                     │
   │  │ • KnowledgeBase  │  │                    │                     │
   │  │ • Recordings     │  │                    │                     │
   │  └──────────────────┘  └────────────────────┘                     │
   │                                                                     │
   └─────────────────────────────────────────────────────────────────────┘

```

## Data Flow - A Single Voice Interaction

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    VOICE CALL FLOW DIAGRAM                              │
└─────────────────────────────────────────────────────────────────────────┘

1. CALL INITIATION
   ┌──────────────┐
   │ Make Call    │ ──→ Twilio API ──→ WebSocket /media-stream
   │ (Outbound)   │
   └──────────────┘

2. CALL CONNECTED (WebSocket Established)
   ┌────────────────────────────────────────┐
   │ "start" event received                 │
   │ • Setup connection manager             │
   │ • Load agent config from DB            │
   │ • Initialize speech detection          │
   │ • Queue greeting message               │
   └────────────────────────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ Speak Greeting (TTS Stream)            │
   │ └─ Deepgram TTS ──→ Audio chunks       │
   │ └─ Stream to Twilio                    │
   └────────────────────────────────────────┘

3. USER SPEECH (Real-time)
   ┌────────────────────────────────────────┐
   │ "media" events from Twilio             │
   │ Raw audio (μ-law, 8000 Hz)             │
   └────────────────────────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ Resampler: 8000 Hz → 16000 Hz          │
   │ audioop.ratecv()                       │
   └────────────────────────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ Send to Deepgram Live STT Stream       │
   │ • Continuous transcription             │
   │ • Get partial & final results          │
   │ • Track confidence scores              │
   └────────────────────────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ Voice Activity Detection (VAD)         │
   │ • Energy-based detection               │
   │ • Baseline tracking                    │
   │ • Interrupt detection (if speaking)    │
   └────────────────────────────────────────┘

4. TRANSCRIPTION FINALIZED
   ┌────────────────────────────────────────┐
   │ Wait for silence threshold             │
   │ (Default: 1.5 seconds)                 │
   │ Mark: stt_is_final = true              │
   └────────────────────────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ INTENT CLASSIFICATION                  │
   │ • Is this "GOODBYE"?                   │
   │ • Needs confirmation?                  │
   │ • Clear topic intent?                  │
   └────────────────────────────────────────┘

5. CONTEXT RETRIEVAL (RAG)
   ┌────────────────────────────────────────┐
   │ Embed user text (sentence-transformer) │
   │ Query ChromaDB for similar docs        │
   │ Get top-K knowledge base results       │
   │ Filter by semantic similarity (>0.7)   │
   └────────────────────────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ PROMPT CONSTRUCTION                    │
   │ • Agent system prompt                  │
   │ • Retrieved context chunks             │
   │ • Conversation history (last 6 turns)  │
   │ • Dynamic variables (lead info)        │
   │ • User current question                │
   └────────────────────────────────────────┘

6. LLM GENERATION (Ollama)
   ┌────────────────────────────────────────┐
   │ Stream from Ollama                     │
   │ • Streaming tokens                     │
   │ • Temperature: 0.2 (deterministic)     │
   │ • Max tokens: 1200                     │
   │ • Stop sequences: ["User:", "Assistant:"]
   └────────────────────────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ SENTENCE SPLITTING & CLEANUP           │
   │ • Extract completed sentences          │
   │ • Remove markdown formatting           │
   │ • Queue sentences for TTS              │
   └────────────────────────────────────────┘

7. STREAMING TTS & PLAYBACK
   ┌────────────────────────────────────────┐
   │ Sentence → Deepgram TTS Stream         │
   │ MP3 chunks → Audio frames              │
   │ Frame → Twilio WebSocket               │
   │ Audio plays on caller's phone          │
   └────────────────────────────────────────┘

8. TOOL EXECUTION (If Detected)
   ┌────────────────────────────────────────┐
   │ Parse tool name from LLM response      │
   │ • [TOOL: transfer_call]                │
   │ • [TOOL: book_meeting] ...             │
   │ • [CONFIRM_TOOL:...]                  │
   └────────────────────────────────────────┘
                    ▼
   ┌────────────────────────────────────────┐
   │ If requires confirmation:              │
   │ • Ask user "yes or no?"                │
   │ • Wait for response                    │
   │ • Execute if confirmed                 │
   │                                        │
   │ If immediate:                          │
   │ • Call webhook URL                     │
   │ • Send tool parameters                 │
   │ • Get result                           │
   └────────────────────────────────────────┘

9. LOOP BACK
   └─→ Wait for next user input (step 3)

10. CALL TERMINATION
   ┌────────────────────────────────────────┐
   │ User says "GOODBYE" or transfer/end    │
   │ • Save conversation transcript to DB   │
   │ • Record call duration                 │
   │ • Fire "call.ended" webhooks           │
   │ • Clean up resources                   │
   │ • Close WebSocket                      │
   └────────────────────────────────────────┘

```

## Component Interaction Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    KEY COMPONENT INTERACTIONS                           │
└─────────────────────────────────────────────────────────────────────────┘

API REQUEST                          WEBSOCKET CALL (Real-time)
    │                                       │
    ▼                                       ▼
┌──────────────┐                    ┌──────────────────┐
│ REST Handler │                    │ WebSocket Handler│
│ (main.py)    │                    │ (main.py)        │
└──────────────┘                    └──────────────────┘
    │                                       │
    ├─ validate request                     ├─ accept connection
    ├─ call utils functions                 ├─ manager.connect()
    ├─ database query/update                ├─ setup voice pipeline
    ├─ return JSON response                 ├─ setup STT stream
    │                                       ├─ setup TTS queue
    │                                       │
    │      VOICE PIPELINE                  ├─ listen for media events
    │      (voice_pipeline.py)              │
    │       │                              │
    │       ├─ ConnectionManager            │
    │       │  (in-memory session state)   │
    │       │                              │
    │       ├─ AudioProcessor               │
    │       │  (resampling, energy calc)   │
    │       │                              │
    │       ├─ Deepgram STT Stream          │
    │       │  (live transcription)        │
    │       │                              │
    │       ├─ Deepgram TTS Stream          │
    │       │  (voice synthesis)           │
    │       │                              │
    │       └─ EventLoop Integration        │
    │                                       │
    ▼                                       ▼
┌──────────────────┐             ┌──────────────────────┐
│ Business Logic   │             │ Real-time Processing │
│ (main.py)        │             │ (main.py)            │
│                  │             │                      │
│ • query_rag()    │             │ • process_streaming  │
│ • detect_intent()│             │ • execute_tool()     │
│ • parse_response │             │ • speak_text()       │
│ • save_transcript│             │ • update_state()     │
│                  │             │                      │
└──────────────────┘             └──────────────────────┘
    │                                       │
    ▼                                       ▼
┌──────────────────┐             ┌──────────────────────┐
│ Data Access      │             │ External Services    │
│ (models.py)      │             │                      │
│                  │             │ • Twilio             │
│ • SQLite DB      │             │ • Deepgram           │
│ • ChromaDB       │             │ • Ollama             │
│                  │             │ • Webhooks           │
└──────────────────┘             └──────────────────────┘

```

## Database Schema Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      DATABASE RELATIONSHIPS                             │
│                       (SQLite + ChromaDB)                               │
└─────────────────────────────────────────────────────────────────────────┘

SQLite (Structured Data):
    │
    ├─ AGENTS (1)
    │  ├─ agent_id (PK)
    │  ├─ name, system_prompt, first_message
    │  ├─ voice_provider, voice_id
    │  ├─ model_provider, model_name
    │  └─ is_active, created_at, updated_at
    │
    ├─ CONVERSATIONS (many)
    │  ├─ conversation_id (PK)
    │  ├─ agent_id (FK → AGENTS)
    │  ├─ phone_number, status
    │  ├─ transcript, dynamic_variables
    │  ├─ started_at, ended_at, duration_secs
    │  └─ call_metadata
    │
    ├─ WEBHOOKS
    │  ├─ id (PK)
    │  ├─ agent_id (FK → AGENTS, optional)
    │  ├─ webhook_url, events
    │  └─ is_active, created_at
    │
    ├─ TOOLS
    │  ├─ id (PK)
    │  ├─ agent_id (FK → AGENTS)
    │  ├─ tool_name, description
    │  ├─ webhook_url, parameters
    │  └─ is_active
    │
    ├─ PHONE_NUMBERS
    │  ├─ id (PK)
    │  ├─ phone_number (unique)
    │  ├─ agent_id (FK → AGENTS, optional)
    │  ├─ label, is_active
    │  └─ created_at
    │
    └─ KNOWLEDGE_BASE
       ├─ id (PK)
       ├─ agent_id (FK → AGENTS)
       ├─ document_id
       ├─ content (full text)
       ├─ kb_metadata
       └─ created_at

ChromaDB (Vector Store):
    │
    └─ COLLECTIONS (per agent)
       ├─ agent_{agent_id}
       │  ├─ embeddings (sentence-transformer)
       │  ├─ documents (text chunks)
       │  ├─ metadatas (agent_id, doc_id)
       │  └─ ids (unique per chunk)
       │
       └─ RAG retrieval → top-K similarity search

```

## Deployment Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                       DEPLOYMENT TOPOLOGY                              │
└────────────────────────────────────────────────────────────────────────┘

                          PUBLIC INTERNET
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
               ┌────▼────┐  ┌────▼────┐  ┌───▼────┐
               │  Caller  │  │ Twilio  │  │ Webhook│
               │  Phone   │  │ Network │  │ Client │
               └────┬────┘  └────┬────┘  └───┬────┘
                    │            │            │
                    └────────────┼────────────┘
                                 │
                ┌────────────────▼────────────────┐
                │    REVERSE PROXY / FIREWALL     │
                │    (nginx / cloudflare)         │
                └────────────────┬────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌───────────────┐      ┌──────────────────┐    ┌──────────────┐
│  FastAPI App  │      │  Internal Cache  │    │  File Store  │
│               │      │  (in-memory)     │    │  (recordings)│
│  • 8 workers  │      │                  │    │              │
│  • Async I/O  │      │  • Connections   │    │  • Audio     │
│  • Uvicorn    │      │  • TTL tables    │    │  • Logs      │
└───────┬───────┘      └──────────────────┘    └──────────────┘
        │
        └─────────────────┬────────────────────────────────┐
                          │                                │
                    ┌─────▼──────┐                   ┌────▼────┐
                    │  SQLite DB │                   │ChromaDB │
                    │ (persistent)│                  │(vectors)│
                    └─────┬──────┘                   └────┬────┘
                          │                              │
                          └──────────────┬───────────────┘
                                         │
                    ┌────────────────────▼────────────────┐
                    │   PERSISTENT STORAGE               │
                    │   (Docker volumes)                 │
                    │   • chroma.sqlite3                 │
                    │   • database.db                    │
                    │   • /chroma_db/                    │
                    └────────────────────────────────────┘

External Service Calls:
    │
    ├─ HTTPS → Twilio API (outbound calls, status callbacks)
    ├─ HTTPS → Deepgram API (TTS requests, when needed)
    ├─ HTTP → Ollama Server (local/remote LLM)
    └─ HTTPS → Webhook URLs (agent custom tools, client events)

```

## Concurrency Model

```
┌────────────────────────────────────────────────────────────────────────┐
│                    ASYNC / CONCURRENCY DESIGN                          │
└────────────────────────────────────────────────────────────────────────┘

Single FastAPI Instance:
    │
    ├─ Event Loop (asyncio)
    │  │
    │  ├─ Multiple WebSocket connections (concurrent)
    │  │  ├─ Call 1 (call_sid_123) ──→ media stream handler
    │  │  ├─ Call 2 (call_sid_456) ──→ media stream handler
    │  │  └─ Call N (call_sid_NNN) ──→ media stream handler
    │  │
    │  ├─ REST API requests (concurrent)
    │  │  ├─ POST /v1/convai/agents (create)
    │  │  ├─ GET /v1/convai/conversations (list)
    │  │  └─ PATCH /v1/convai/agents/{id} (update)
    │  │
    │  └─ Background tasks
    │     ├─ TTS streaming worker (per call)
    │     ├─ STT stream reader (per call)
    │     └─ transcript processing (per call)
    │
    ├─ Thread Pools (for blocking I/O)
    │  ├─ Database queries (run_in_executor)
    │  ├─ Ollama calls (blocking)
    │  ├─ Deepgram API (blocking)
    │  └─ Embedding generation (blocking)
    │
    └─ In-Memory State (per connection)
       ├─ ConnectionManager.get(call_sid)
       │  └─ Stores session-specific data
       │     ├─ WebSocket connection
       │     ├─ STT buffer + transcript
       │     ├─ Conversation history
       │     ├─ Agent config override
       │     ├─ Deepgram streams
       │     └─ Audio processing state

Per-Call Concurrency:
    One call = multiple concurrent streams:
    
    ┌─────────────────────────────────────────┐
    │  CALL_SID_123 Async Operations         │
    ├─────────────────────────────────────────┤
    │                                         │
    │  ┌─────────────┐  ┌─────────────────┐  │
    │  │ STT Reader  │  │   TTS Writer    │  │
    │  │ (listening) │  │  (speaking)     │  │
    │  │ concurrent  │  │  concurrent     │  │
    │  └─────────────┘  └─────────────────┘  │
    │         │                   ▲          │
    │         ├──→ Deepgram  ←────┤          │
    │                              │         │
    │  ┌──────────────────┐  ┌─────▼──────┐ │
    │  │ Intent Detector  │  │  LLM Call  │ │
    │  │ (async)          │  │  (executor)│ │
    │  └──────────────────┘  └────────────┘ │
    │                                         │
    └─────────────────────────────────────────┘

```

---

## Key Design Patterns

### 1. **Async/Await Streaming**
   - Real-time bidirectional communication
   - Non-blocking I/O for all external calls
   - Concurrent handling of multiple calls

### 2. **RAG (Retrieval-Augmented Generation)**
   - Embedding-based semantic search
   - Per-agent knowledge base isolation
   - Relevant context injection into prompts

### 3. **State Machine**
   - Call phases: CALL_START → DISCOVERY → ACTIVE
   - Call status: initiated → in-progress → completed
   - Intent-based flow control

### 4. **Event-Driven Webhooks**
   - Agent-specific or global webhooks
   - Events: call.started, call.ended, tool.called, etc.
   - Decoupled external integrations

### 5. **Connection Management**
   - In-memory session registry (per WebSocket)
   - Automatic cleanup on disconnect
   - Concurrent call isolation

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| **Concurrent Calls** | 50+ (GPU dependent) |
| **First Response Latency** | 2-3 seconds |
| **Interrupt Detection** | <150ms |
| **STT Latency** | 200-500ms (final transcript) |
| **TTS Latency** | 300-800ms (first audio) |
| **LLM Response Time** | 1-2s (average) |
| **Memory per Call** | ~50-100 MB |
| **CPU Usage** | ~2-5% per call (idle) |
| **GPU Memory** | 4-8 GB (model dependent) |

---

## Security Considerations

- **API Keys**: Validated on each request
- **WebSocket**: Secure WSS (wss://) in production
- **Database**: SQLite (local) / encrypted in production
- **Webhooks**: Signed requests with timestamps
- **Conversation Data**: Encrypted at rest (optional)
- **CORS**: Configurable origin restrictions

