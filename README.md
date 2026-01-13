# AI SDR (Sales Development Representative) - Voice Call Agent

A powerful, self-hosted voice AI system for intelligent phone conversations with call center capabilities, real-time transcription, dynamic agent responses, and advanced features like call interruption handling and tool execution.

## 🎯 Overview

This is an enterprise-grade voice AI system that:
- **Conducts intelligent phone conversations** using Twilio voice calls
- **Processes speech in real-time** with Deepgram STT/TTS
- **Generates responses dynamically** with Ollama LLM (local inference)
- **Handles call interruptions naturally** - like a human agent would
- **Executes tools and actions** based on conversation flow
- **Maintains conversation context** with RAG (Retrieval-Augmented Generation)
- **Manages multiple concurrent calls** with WebSocket streaming

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Twilio account with phone number
- Deepgram API key
- Ollama running locally
- ngrok (for local tunneling during development)

### Installation

1. **Clone and setup:**
```bash
cd /root/AI_SDR
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your credentials:
# - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
# - DEEPGRAM_API_KEY
# - PUBLIC_URL (your ngrok/production domain)
```

3. **Start Ollama:**
```bash
ollama pull llama3:8b-instruct-q4_K_S
ollama serve
```

4. **Run the application:**
```bash
# Development with reload
uvicorn main:app --host 0.0.0.0 --port 9001 --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 9001
```

5. **Expose with ngrok (development):**
```bash
ngrok http 9001
# Update PUBLIC_URL in .env with ngrok URL
```

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   REST API   │    │  WebSocket   │    │   Webhooks   │   │
│  │  Endpoints   │    │  Voice I/O   │    │  Management  │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                              │                                │
│                              ▼                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │         Voice Pipeline (voice_pipeline.py)             │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │ │
│  │  │ STT Flow │  │ TTS Flow │  │Interrupts│              │ │
│  │  │ (Deepgram)  │ (Deepgram)  │Detection │              │ │
│  │  └──────────┘  └──────────┘  └──────────┘              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                              │                                │
│                              ▼                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │         Processing Pipeline (main.py)                   │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │ │
│  │  │ Intent   │  │   LLM    │  │  Tool    │              │ │
│  │  │Detection │  │(Ollama)  │  │Execution │              │ │
│  │  └──────────┘  └──────────┘  └──────────┘              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                              │                                │
│                              ▼                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │       Data Layer (models.py, utils.py)                 │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │ │
│  │  │  SQLite  │  │ ChromaDB │  │ External │              │ │
│  │  │  Agent   │  │  Vector  │  │   APIs   │              │ │
│  │  │   Data   │  │   DB     │  │          │              │ │
│  │  └──────────┘  └──────────┘  └──────────┘              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
    ┌──────────────┐           ┌──────────────────┐
    │   Twilio     │           │ External Services│
    │  Voice API   │           │  - Deepgram      │
    │              │           │  - Ollama        │
    │              │           │  - Webhooks      │
    └──────────────┘           └──────────────────┘
```

## 📁 Project Structure

```
/root/AI_SDR/
├── main.py                    # FastAPI application & REST endpoints
├── voice_pipeline.py          # STT/TTS streaming, interruption handling
├── models.py                  # SQLAlchemy models (Agent, Conversation, etc.)
├── schemas.py                 # Pydantic request/response schemas
├── utils.py                   # Utilities (logging, embedding, webhooks)
├── requirements.txt           # Python dependencies
├── .env                       # Environment configuration
├── agents.db                  # SQLite database
├── chroma_db/                 # ChromaDB vector storage
├── API_ENDPOINTS.md           # API documentation
├── MODULARIZATION_SUMMARY.md  # System design overview
└── README.md                  # This file
```

## 🔧 Core Modules

### main.py - FastAPI Application
**Responsibility:** REST API endpoints, call routing, response generation

**Key Classes:**
- `FastAPI app` - REST API server

**Key Functions:**
- `create_agent()` - Create new voice agent
- `get_agent()` - Retrieve agent config
- `make_outbound_call()` - Initiate outbound voice call
- `voice_inbound()` - Handle incoming calls (WebSocket)
- `process_streaming_transcript()` - Process user input and generate response
- `execute_detected_tool()` - Run detected tools/actions

**Endpoints:**
- `POST /v1/convai/agents` - Create agent
- `GET /v1/convai/agents/{agent_id}` - Get agent
- `POST /v1/convai/outbound` - Make outbound call
- `POST /twiml/voice_outbound` - Handle outbound call voice
- `POST /twiml/voice` - Receive inbound call webhooks
- `WebSocket /ws/voice/{call_sid}` - Real-time voice I/O

### voice_pipeline.py - Voice Processing
**Responsibility:** STT/TTS streaming, audio processing, interruption detection

**Key Classes:**
- `WSConn` - Connection state per call
- `ConnectionManager` - Manage active connections
- `_AudioopFallback` - Fallback audio processing

**Key Functions:**
- `setup_streaming_stt()` - Initialize Deepgram streaming STT
- `handle_interrupt()` - Handle user interruption seamlessly
- `stream_tts_worker()` - Stream TTS audio to user
- `speak_text_streaming()` - Queue text for TTS
- `calculate_audio_energy()` - Detect speech energy
- `update_baseline()` - Adapt noise baseline

**Latency Optimized:**
- Interrupt debounce: 400ms
- Min speech duration: 100ms
- Response baseline factor: 2.8x

### models.py - Data Models
**Responsibility:** Database schema and models

**Models:**
- `Agent` - Voice agent configuration
- `Conversation` - Call conversation history
- `WebhookConfig` - Webhook endpoint settings
- `PhoneNumber` - Registered phone numbers
- `KnowledgeBase` - Document storage
- `AgentTool` - Custom tool definitions

### schemas.py - Request/Response Schemas
**Responsibility:** Request validation and response serialization

**Schemas:**
- `CallRequest` - Inbound call data
- `AgentCreate/Update` - Agent CRUD
- `OutboundCallRequest` - Outbound call params
- `ToolCreate` - Tool definition

### utils.py - Utilities
**Responsibility:** Logging, configuration, helpers

**Key Functions:**
- `setup_logging()` - Configure logging
- `send_webhook()` - Send webhook notifications
- `detect_intent()` - Classify user intent
- `parse_llm_response()` - Parse LLM output
- `clean_markdown_for_tts()` - Format text for speech

**Config Variables:**
- Twilio credentials & configuration
- Deepgram API & voice settings
- Ollama model & parameters
- Interrupt detection thresholds
- Vector DB (ChromaDB) settings

## 🎤 Call Flow

### Inbound Call

```
1. User calls TWILIO_PHONE_NUMBER
   ▼
2. Twilio → POST /twiml/voice (webhook)
   ▼
3. FastAPI routes to WebSocket /ws/voice/{call_sid}
   ▼
4. WSConn established, streaming initialized
   ▼
5. Agent sends first_message greeting
   ▼
6. Deepgram STT listens to user input
   ▼
7. User finishes speaking (silence detected)
   ▼
8. Transcription → LLM query (with RAG context)
   ▼
9. LLM generates response
   ▼
10. Response → Deepgram TTS
   ▼
11. Audio streamed back via Twilio
   ▼
12. Loop back to step 6
```

### Interruption Flow

```
While Agent Speaking:
  Audio chunks arrive via media event
  ▼
  Energy calculation
  ▼
  Energy > threshold? (baseline_factor * 2.8)
  ├─ No → Continue speaking
  └─ Yes → Buffer energy sample
      ▼
      2+ high-energy samples detected?
      ├─ No → Continue speaking
      └─ Yes → Start timer
          ▼
          Duration ≥ 100ms?
          ├─ No → Waiting...
          └─ Yes → INTERRUPT!
              ▼
              Clear TTS queue
              ▼
              Send media clear to Twilio
              ▼
              Reset buffers
              ▼
              Ready for new input
```

## 🔌 API Endpoints

### Agent Management

**Create Agent**
```http
POST /v1/convai/agents
Content-Type: application/json
xi-api-key: your-api-key

{
  "name": "Sales Bot",
  "system_prompt": "You are a sales representative...",
  "first_message": "Hello, how can I help?",
  "voice_id": "aura-2-thalia-en",
  "interrupt_enabled": true
}
```

**Get Agent**
```http
GET /v1/convai/agents/{agent_id}
xi-api-key: your-api-key
```

### Call Management

**Make Outbound Call**
```http
POST /v1/convai/outbound
Content-Type: application/json
xi-api-key: your-api-key

{
  "agent_id": "agent-xyz",
  "to_number": "+1234567890",
  "dynamic_variables": {
    "name": "John",
    "company": "Acme Inc"
  }
}
```

**List Conversations**
```http
GET /v1/convai/conversations?agent_id=agent-xyz
xi-api-key: your-api-key
```

**Get Conversation Details**
```http
GET /v1/convai/conversations/{conversation_id}
xi-api-key: your-api-key
```

## ⚙️ Configuration

### Environment Variables (.env)

**Required:**
```env
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
TWILIO_PHONE_NUMBER=+1234567890
PUBLIC_URL=https://your-domain.com
DEEPGRAM_API_KEY=your-key
```

**Optional (with defaults):**
```env
# Voice
DEEPGRAM_VOICE=aura-2-thalia-en
DEEPGRAM_STT_MODEL=nova-2

# LLM
OLLAMA_MODEL=llama3:8b-instruct-q4_K_S
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Interruption (ms)
INTERRUPT_ENABLED=true
INTERRUPT_MIN_ENERGY=800
INTERRUPT_DEBOUNCE_MS=400
INTERRUPT_BASELINE_FACTOR=2.8
INTERRUPT_MIN_SPEECH_MS=100

# Silence detection (sec)
SILENCE_THRESHOLD_SEC=0.3

# Logging
LOG_LEVEL=INFO
LOG_FILE=server.log
```

## 🧠 Smart Features

### 1. **Call Interruption Handling**
- Detects when user starts speaking while agent is talking
- Automatically stops agent speech
- Seamless transition to user input
- Configurable sensitivity and debounce

### 2. **Intent Detection**
- Classifies user intents (HELLO, GOODBYE, CONFIRM, etc.)
- Informs response generation
- Enables context-aware conversation flow

### 3. **RAG (Retrieval-Augmented Generation)**
- Embeds knowledge base documents in ChromaDB
- Retrieves relevant context for LLM queries
- Improves response accuracy and relevance

### 4. **Tool Execution**
- Detects tool requests in LLM responses
- Executes actions (book meeting, send SMS, etc.)
- Returns results to conversation

### 5. **Dynamic Variables**
- Injects custom data into agent messages
- Personalizes conversation (names, companies, etc.)
- Supports templating in messages

### 6. **Webhook Events**
- Call started, completed, interrupted
- Tool execution status
- Custom event routing

## 📊 Call State Machine

```
[CALL_START] 
    ├─→ Agent plays greeting
    └─→ [DISCOVERY]
        ├─→ Gather user information
        └─→ [ACTIVE]
            ├─→ Main conversation loop
            ├─→ Handle interrupts
            ├─→ Execute tools
            └─→ [COMPLETION]
                ├─→ Goodbye message
                └─→ Call ended
```

## 🔐 Security

- **API Key Authentication**: All endpoints require `xi-api-key` header
- **JWT Support**: Token-based auth for advanced scenarios
- **Input Validation**: Pydantic schema validation
- **Call Isolation**: Each call has isolated connection state
- **Error Handling**: Graceful error messages without leaking internals

## 🚨 Troubleshooting

### Call Not Connecting
- Check Twilio credentials in .env
- Verify PUBLIC_URL is accessible
- Check ngrok tunnel is active (development)

### No Audio Output
- Verify Deepgram API key is valid
- Check DEEPGRAM_VOICE model is available
- Verify internet connection

### Interruption Not Working
- Check INTERRUPT_ENABLED=true
- Verify agent has interrupt_enabled=true
- Check INTERRUPT_MIN_ENERGY threshold (too high blocks detection)
- Check INTERRUPT_DEBOUNCE_MS isn't too long

### LLM Responses Slow
- Verify Ollama is running: `ollama serve`
- Check model is loaded: `ollama list`
- Monitor CPU/GPU usage
- Try smaller model if needed

### High Latency
- Monitor network connection
- Check system resources (CPU, memory, GPU)
- Review server logs for bottlenecks
- Consider load balancing for multiple calls

## 📈 Performance Tips

1. **Use GPU for inference**: Set `CUDA_VISIBLE_DEVICES` or use GPU-optimized models
2. **Reduce model size**: Use quantized models (e.g., `q4_K_S`)
3. **Optimize vector DB**: Regular cleanup of old embeddings
4. **Connection pooling**: Reuse HTTP connections
5. **Caching**: Cache agent configs and knowledge base

## 🔄 Deployment

### Docker
```dockerfile
FROM python:3.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9001"]
```

### Production Checklist
- [ ] Set LOG_LEVEL=WARNING
- [ ] Use strong API keys
- [ ] Enable HTTPS (PUBLIC_URL must be https://)
- [ ] Setup monitoring/alerting
- [ ] Configure database backups
- [ ] Test outbound call limits
- [ ] Load test with concurrent calls

## 📝 Logging

Logs include:
- Call lifecycle events
- Transcription results
- LLM queries and responses
- Tool execution
- Error traces
- Performance metrics (with optional latency tracking)

View logs:
```bash
tail -f server.log
# or filter by level:
grep "ERROR" server.log
grep "⏱️" server.log  # Latency metrics (if enabled)
```

## 🤝 Contributing

To extend the system:

1. **Add new tool**: Edit `models.py` → `AgentTool` class
2. **Custom LLM**: Modify `query_rag_streaming()` in `main.py`
3. **Voice models**: Add to `DEEPGRAM_VOICE` options
4. **Webhooks**: Add to `WEBHOOK_EVENTS` in `utils.py`

## 📄 License

Proprietary - AI SDR System

## 📞 Support

For issues or questions:
1. Check `server.log` for error details
2. Review `API_ENDPOINTS.md` for endpoint reference
3. Check `MODULARIZATION_SUMMARY.md` for system design

---

**Last Updated:** January 10, 2026
**Version:** 1.0.0
**Status:** Production Ready
