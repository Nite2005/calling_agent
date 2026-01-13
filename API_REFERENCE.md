# AI SDR Agent - API Reference

## Base URL
```
http://localhost:9001
```

## Authentication
All endpoints require API key header:
```
Headers:
  xi-api-key: your_api_key
```

---

## Agent Management APIs

### Create Agent
```http
POST /v1/convai/agents
Content-Type: application/json
xi-api-key: your_api_key

{
  "name": "Sales Agent",
  "system_prompt": "You are a helpful sales representative...",
  "first_message": "Hello! How can I help you today?",
  "voice_id": "aura-2-thalia-en",
  "model_name": "llama3:8b-instruct-q4_K_S",
  "interrupt_enabled": true,
  "silence_threshold_sec": 0.3
}
```

**Response (200):**
```json
{
  "agent_id": "agent_1234567890",
  "name": "Sales Agent",
  "system_prompt": "You are a helpful...",
  "first_message": "Hello! How can I help...",
  "voice_provider": "deepgram",
  "voice_id": "aura-2-thalia-en",
  "model_provider": "ollama",
  "model_name": "llama3:8b-instruct-q4_K_S",
  "interrupt_enabled": true,
  "silence_threshold_sec": 0.3,
  "is_active": true,
  "created_at": "2026-01-10T18:30:00",
  "updated_at": "2026-01-10T18:30:00"
}
```

### Get Agent
```http
GET /v1/convai/agents/{agent_id}
xi-api-key: your_api_key
```

**Response (200):**
```json
{
  "agent_id": "agent_1234567890",
  "name": "Sales Agent",
  ...
}
```

### List Agents
```http
GET /v1/convai/agents?skip=0&limit=100&is_active=true
xi-api-key: your_api_key
```

**Response (200):**
```json
{
  "agents": [
    {
      "agent_id": "agent_1",
      "name": "Sales Agent",
      ...
    },
    {
      "agent_id": "agent_2",
      "name": "Support Agent",
      ...
    }
  ],
  "total": 2,
  "skip": 0,
  "limit": 100
}
```

### Update Agent
```http
PATCH /v1/convai/agents/{agent_id}
Content-Type: application/json
xi-api-key: your_api_key

{
  "system_prompt": "Updated prompt...",
  "interrupt_enabled": false
}
```

**Response (200):**
```json
{
  "agent_id": "agent_1234567890",
  "system_prompt": "Updated prompt...",
  "interrupt_enabled": false,
  ...
}
```

### Delete Agent
```http
DELETE /v1/convai/agents/{agent_id}
xi-api-key: your_api_key
```

**Response (200):**
```json
{
  "success": true,
  "message": "Agent deleted"
}
```

---

## Call Management APIs

### Initiate Outbound Call
```http
POST /v1/convai/twilio/outbound-call
Content-Type: application/json
xi-api-key: your_api_key

{
  "agent_id": "agent_123",
  "to_number": "+1234567890",
  "dynamic_variables": {
    "name": "John",
    "company": "ACME"
  },
  "custom_first_message": "Hello John from ACME!",
  "custom_voice_id": "aura-2-luna-en",
  "custom_model": "llama3:13b",
  "enable_recording": true
}
```

**Response (200):**
```json
{
  "success": true,
  "call_sid": "CA1234567890abcdef",
  "agent_id": "agent_123",
  "to_number": "+1234567890",
  "status": "initiated",
  "started_at": "2026-01-10T18:30:00"
}
```

### End Call
```http
POST /v1/convai/calls/{call_sid}/end
xi-api-key: your_api_key

{
  "reason": "completed"
}
```

**Response (200):**
```json
{
  "success": true,
  "call_sid": "CA1234567890",
  "ended_at": "2026-01-10T18:35:00",
  "duration_seconds": 300
}
```

---

## Conversation APIs

### Get Conversation
```http
GET /v1/convai/conversations/{conversation_id}
xi-api-key: your_api_key
```

**Response (200):**
```json
{
  "conversation_id": "CA1234567890",
  "agent_id": "agent_123",
  "status": "completed",
  "phone_number": "+1234567890",
  "transcript": "User: Hello\nAgent: Hi there!...",
  "started_at": "2026-01-10T18:30:00",
  "ended_at": "2026-01-10T18:35:00",
  "created_at": "2026-01-10T18:30:00"
}
```

### List Conversations
```http
GET /v1/convai/conversations?agent_id=agent_123&status=completed&skip=0&limit=50
xi-api-key: your_api_key
```

**Response (200):**
```json
{
  "conversations": [
    {
      "conversation_id": "CA1234567890",
      "agent_id": "agent_123",
      "status": "completed",
      "transcript": "User: Hello\nAgent: Hi...",
      "started_at": "2026-01-10T18:30:00",
      "ended_at": "2026-01-10T18:35:00"
    }
  ],
  "total": 25,
  "skip": 0,
  "limit": 50
}
```

---

## Metrics & Monitoring APIs

### Get Call Latency
```http
GET /v1/convai/latency/{call_sid}
```

**Response (200):**
```json
{
  "call_sid": "CA1234567890",
  "agent_id": "agent_123",
  "call_initiated_ms": 150,
  "stt_latency_ms": 250,
  "llm_generation_ms": 1200,
  "tts_generation_ms": 450,
  "first_audio_sent_ms": 150,
  "full_response_cycle_ms": 2050,
  "total_call_duration_ms": 5000,
  "currently_speaking": true,
  "is_responding": false,
  "call_phase": "DISCOVERY"
}
```

---

## Webhook Management APIs

### Register Webhook
```http
POST /v1/convai/webhooks
Content-Type: application/json
xi-api-key: your_api_key

{
  "url": "https://your-domain.com/webhook",
  "events": ["call.started", "call.ended", "user.interrupted"],
  "agent_id": "agent_123"
}
```

**Response (200):**
```json
{
  "webhook_id": "webhook_123",
  "url": "https://your-domain.com/webhook",
  "events": ["call.started", "call.ended"],
  "agent_id": "agent_123",
  "is_active": true,
  "created_at": "2026-01-10T18:30:00"
}
```

### List Webhooks
```http
GET /v1/convai/webhooks?agent_id=agent_123
xi-api-key: your_api_key
```

**Response (200):**
```json
{
  "webhooks": [
    {
      "webhook_id": "webhook_123",
      "url": "https://your-domain.com/webhook",
      "events": ["call.started", "call.ended"],
      "agent_id": "agent_123"
    }
  ],
  "total": 1
}
```

### Delete Webhook
```http
DELETE /v1/convai/webhooks/{webhook_id}
xi-api-key: your_api_key
```

**Response (200):**
```json
{
  "success": true,
  "message": "Webhook deleted"
}
```

---

## Webhook Events

### Webhook Payload Format
```json
{
  "event": "call.started",
  "timestamp": "2026-01-10T18:30:00",
  "call_sid": "CA1234567890",
  "agent_id": "agent_123",
  "data": {
    "phone_number": "+1234567890",
    "duration_ms": 5000
  }
}
```

### Supported Events
- `call.started` - Call begins
- `call.ended` - Call completes
- `call.failed` - Call error
- `user.interrupted` - User interrupts agent
- `agent.responded` - Agent responds to user
- `message.sent` - Message sent
- `tool.executed` - Tool/action executed

---

## Knowledge Base APIs

### Upload Knowledge Base
```http
POST /v1/convai/agents/{agent_id}/knowledge-base
Content-Type: application/json
xi-api-key: your_api_key

{
  "file_type": "pdf",
  "file_path": "/path/to/document.pdf",
  "chunk_size": 384
}
```

**Response (200):**
```json
{
  "success": true,
  "chunks_created": 45,
  "agent_id": "agent_123"
}
```

### Get Knowledge Base
```http
GET /v1/convai/agents/{agent_id}/knowledge-base
xi-api-key: your_api_key
```

**Response (200):**
```json
{
  "agent_id": "agent_123",
  "documents": [
    {
      "id": "doc_123",
      "name": "document.pdf",
      "chunks": 45,
      "created_at": "2026-01-10T18:30:00"
    }
  ],
  "total_chunks": 45
}
```

---

## Tools/Actions APIs

### Create Tool
```http
POST /v1/convai/agents/{agent_id}/tools
Content-Type: application/json
xi-api-key: your_api_key

{
  "name": "book_appointment",
  "description": "Books an appointment for the customer",
  "required_params": ["date", "time", "name"],
  "optional_params": ["notes"],
  "webhook_url": "https://your-api.com/book-appointment"
}
```

**Response (200):**
```json
{
  "tool_id": "tool_123",
  "agent_id": "agent_123",
  "name": "book_appointment",
  "description": "Books an appointment...",
  "required_params": ["date", "time", "name"],
  "optional_params": ["notes"],
  "webhook_url": "https://your-api.com/book-appointment",
  "created_at": "2026-01-10T18:30:00"
}
```

### List Tools
```http
GET /v1/convai/agents/{agent_id}/tools
xi-api-key: your_api_key
```

**Response (200):**
```json
{
  "tools": [
    {
      "tool_id": "tool_123",
      "name": "book_appointment",
      "description": "Books an appointment...",
      "required_params": ["date", "time", "name"]
    }
  ],
  "total": 1
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid request parameters",
  "error": "name is required"
}
```

### 401 Unauthorized
```json
{
  "detail": "Invalid API key"
}
```

### 404 Not Found
```json
{
  "detail": "Agent not found",
  "error": "agent_id: agent_999"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error",
  "error": "Database connection failed"
}
```

---

## Rate Limits

- **Calls per minute:** 100
- **API requests per minute:** 1000
- **Concurrent calls:** 50 (configurable)

Headers returned:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1234567890
```

---

## Code Examples

### Python - Create Agent and Start Call

```python
import requests

API_KEY = "your_api_key"
BASE_URL = "http://localhost:9001"
HEADERS = {"xi-api-key": API_KEY}

# 1. Create agent
agent_data = {
    "name": "Sales Bot",
    "system_prompt": "You are a sales representative...",
    "first_message": "Hi! Can I help you with anything?",
    "voice_id": "aura-2-thalia-en"
}

response = requests.post(
    f"{BASE_URL}/v1/convai/agents",
    json=agent_data,
    headers=HEADERS
)
agent = response.json()
agent_id = agent["agent_id"]

# 2. Start call
call_data = {
    "agent_id": agent_id,
    "to_number": "+1234567890",
    "dynamic_variables": {"name": "John"}
}

response = requests.post(
    f"{BASE_URL}/v1/convai/twilio/outbound-call",
    json=call_data,
    headers=HEADERS
)
call = response.json()
print(f"Call started: {call['call_sid']}")

# 3. Check latency
import time
time.sleep(5)

response = requests.get(
    f"{BASE_URL}/v1/convai/latency/{call['call_sid']}"
)
latency = response.json()
print(f"Response time: {latency['full_response_cycle_ms']}ms")
```

### JavaScript - List Conversations

```javascript
const API_KEY = "your_api_key";
const BASE_URL = "http://localhost:9001";

async function getConversations(agentId) {
  const response = await fetch(
    `${BASE_URL}/v1/convai/conversations?agent_id=${agentId}`,
    {
      method: "GET",
      headers: {
        "xi-api-key": API_KEY
      }
    }
  );
  
  const data = await response.json();
  return data.conversations;
}

// Usage
getConversations("agent_123").then(conversations => {
  conversations.forEach(conv => {
    console.log(`${conv.conversation_id}: ${conv.status}`);
  });
});
```

### cURL - Get Agent

```bash
curl -X GET \
  "http://localhost:9001/v1/convai/agents/agent_123" \
  -H "xi-api-key: your_api_key" \
  -H "Content-Type: application/json"
```

---

## WebSocket API (Voice Streaming)

Connection URL:
```
ws://localhost:9001/voice/websocket?call_sid=CA1234567890
```

### Message Format

**Server → Client (Media):**
```json
{
  "event": "media",
  "streamSid": "MO1234567890",
  "media": {
    "payload": "base64_encoded_audio"
  }
}
```

**Client → Server (Media):**
```json
{
  "event": "media",
  "streamSid": "MO1234567890",
  "media": {
    "payload": "base64_encoded_audio"
  }
}
```

---

**Last Updated:** January 2026
