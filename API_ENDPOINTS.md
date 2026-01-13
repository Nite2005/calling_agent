# Complete API Endpoints Documentation

This document lists all available API endpoints in the AI Voice Call System.

## Authentication
All endpoints (except `/`, `/gpu-status`, `/tools/status`, `/widget`, and WebSocket `/media-stream`) require an API key via the `xi-api-key` header.

---

## Agent Management APIs

### Create Agent
```
POST /v1/convai/agents
```
Creates a new agent with voice and model configurations.

**Request:**
```json
{
  "name": "Sales Agent",
  "system_prompt": "You are a helpful sales agent...",
  "first_message": "Hello, how can I help you?",
  "voice_id": "Rachel",
  "model_name": "gpt-4",
  "silence_threshold_sec": 1.5
}
```

**Response:**
```json
{
  "agent_id": "agent_abc123",
  "name": "Sales Agent",
  "system_prompt": "You are a helpful sales agent...",
  "first_message": "Hello, how can I help you?",
  "voice_id": "Rachel",
  "model_name": "gpt-4",
  "silence_threshold_sec": 1.5
}
```

---

### Get Agent
```
GET /v1/convai/agents/{agent_id}
```
Retrieves a specific agent by ID.

---

### List Agents
```
GET /v1/convai/agents
```
Lists all agents with optional filtering.

**Query Parameters:**
- `skip`: Number of agents to skip (default: 0)
- `limit`: Maximum number of agents to return (default: 10)

---

### Update Agent
```
PATCH /v1/convai/agents/{agent_id}
```
Updates agent configuration.

---

### Delete Agent
```
DELETE /v1/convai/agents/{agent_id}
```
Deletes an agent.

---

## Conversation APIs

### Get Conversation
```
GET /v1/convai/conversations/{conversation_id}
```
Retrieves conversation details including transcript and metadata.

---

### List Conversations
```
GET /v1/convai/conversations
```
Lists all conversations with optional filtering.

**Query Parameters:**
- `agent_id`: Filter by agent ID
- `status`: Filter by status (in-progress, completed)
- `direction`: Filter by direction (inbound, outbound)
- `skip`: Number of conversations to skip
- `limit`: Maximum number to return

---

## Webhooks API

### Create Webhook
```
POST /v1/convai/webhooks
```
Creates a webhook for event notifications.

**Request:**
```json
{
  "webhook_url": "https://your-api.com/webhook",
  "events": ["call.started", "call.ended"],
  "agent_id": "agent_abc123"
}
```

**Response:**
```json
{
  "webhook_id": 1,
  "webhook_url": "https://your-api.com/webhook",
  "events": ["call.started", "call.ended"],
  "agent_id": "agent_abc123",
  "is_active": true
}
```

---

### List Webhooks
```
GET /v1/convai/webhooks
```
Lists all active webhooks.

**Query Parameters:**
- `agent_id`: Filter by agent ID (optional)

---

### Delete Webhook
```
DELETE /v1/convai/webhooks/{webhook_id}
```
Deletes a webhook (soft delete - sets `is_active` to false).

---

## Phone Numbers API

### Register Phone Number
```
POST /v1/convai/phone-numbers
```
Registers a new phone number.

**Request:**
```json
{
  "phone_number": "+1234567890",
  "agent_id": "agent_abc123",
  "label": "Main Sales Line"
}
```

**Response:**
```json
{
  "phone_id": "phone_xyz789",
  "phone_number": "+1234567890",
  "agent_id": "agent_abc123",
  "label": "Main Sales Line",
  "is_active": true
}
```

---

### List Phone Numbers
```
GET /v1/convai/phone-numbers
```
Lists all registered active phone numbers.

---

### Update Phone Number
```
PATCH /v1/convai/phone-numbers/{phone_id}
```
Updates phone number configuration (agent link, label).

**Request:**
```json
{
  "agent_id": "agent_new_id",
  "label": "Updated Label"
}
```

---

### Delete Phone Number
```
DELETE /v1/convai/phone-numbers/{phone_id}
```
Deletes a phone number (soft delete).

---

## Knowledge Base API

### Add Knowledge
```
POST /v1/convai/agents/{agent_id}/knowledge-base
```
Adds documents to an agent's knowledge base.

**Request:**
```json
{
  "content": "Your knowledge content here...",
  "metadata": {
    "source": "documentation",
    "category": "faq"
  }
}
```

**Response:**
```json
{
  "document_id": "doc_abc123",
  "agent_id": "agent_xyz",
  "chunks_created": 5
}
```

---

### List Agent Knowledge
```
GET /v1/convai/agents/{agent_id}/knowledge-base
```
Lists all knowledge base documents for an agent.

**Response:**
```json
{
  "agent_id": "agent_xyz",
  "documents": [
    {
      "document_id": "doc_abc123",
      "content_preview": "Your knowledge content...",
      "metadata": {"source": "documentation"},
      "created_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 1
}
```

---

### Delete Knowledge
```
DELETE /v1/convai/agents/{agent_id}/knowledge-base/{document_id}
```
Removes a document from the knowledge base.

---

## Custom Tools API

### Add Tool to Agent
```
POST /v1/convai/agents/{agent_id}/tools
```
Adds a custom tool/webhook that the agent can call.

**Request:**
```json
{
  "tool_name": "weather",
  "description": "Get weather information",
  "webhook_url": "https://api.weather.com/get",
  "parameters": {
    "location": {
      "type": "string",
      "required": true,
      "description": "City name"
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "tool_id": 1,
  "tool_name": "weather",
  "agent_id": "agent_xyz",
  "webhook_url": "https://api.weather.com/get"
}
```

---

### List Agent Tools
```
GET /v1/convai/agents/{agent_id}/tools
```
Lists all custom tools for an agent.

---

### Delete Tool
```
DELETE /v1/convai/agents/{agent_id}/tools/{tool_id}
```
Removes a tool from an agent.

---

## Recording API

### Recording Callback (Twilio)
```
POST /recording-callback
```
Webhook endpoint for Twilio to notify of completed recordings. Called automatically by Twilio.

---

### Get Recording
```
GET /v1/convai/conversations/{conversation_id}/recording
```
Retrieves the recording URL for a conversation.

**Response:**
```json
{
  "conversation_id": "call_abc123",
  "recording_url": "https://recordings.example.com/file.wav",
  "recording_metadata": {
    "recording_sid": "RE...",
    "recording_duration": "120"
  }
}
```

---

## Widget & JWT API

### Get Signed Widget URL
```
GET /v1/convai/conversation/get-signed-url
```
Generates a JWT-signed URL for embedding the widget.

**Query Parameters:**
- `agent_id`: The agent ID to embed

**Response:**
```json
{
  "signed_url": "https://your-domain.com/widget?token=eyJ...",
  "expires_in": 86400,
  "agent_id": "agent_xyz"
}
```

---

### Widget Page
```
GET /widget
```
Serves the embedded widget page with JWT validation.

**Query Parameters:**
- `token`: JWT token from `/get-signed-url`

**Response:**
```json
{
  "valid": true,
  "agent_id": "agent_xyz",
  "agent_name": "Sales Agent",
  "message": "Widget authentication successful"
}
```

---

## Voice & Streaming API

### Initiate Outbound Call
```
POST /v1/convai/twilio/outbound-call
```
Initiates an outbound call to a phone number.

**Request:**
```json
{
  "to_number": "+1234567890",
  "agent_id": "agent_abc123",
  "enable_recording": true,
  "custom_first_message": "Custom greeting here"
}
```

---

### Twilio Voice Webhook
```
POST /voice/outbound
```
Webhook endpoint for Twilio to establish media stream connection.

---

### WebSocket Media Stream
```
WebSocket /media-stream
```
Maintains WebSocket connection for real-time audio streaming and transcription.

---

## Status & Health API

### Health Check
```
GET /
```
Returns system status and available features.

**Response:**
```json
{
  "status": "ok",
  "message": "Twilio RAG Voice System",
  "device": "cuda",
  "features": [...]
}
```

---

### GPU Status
```
GET /gpu-status
```
Returns GPU and model information.

**Response:**
```json
{
  "device": "cuda",
  "torch_version": "2.0.0",
  "cuda_available": true,
  "gpu_name": "NVIDIA A100",
  "ollama": {
    "models": ["llama2", "mistral"],
    "current_model": "ollama_model"
  }
}
```

---

### Tools Status
```
GET /tools/status
```
Returns available tools and their configuration.

**Response:**
```json
{
  "tools_available": ["end_call", "transfer_call"],
  "departments": {
    "sales": "+1111111111",
    "support": "+2222222222"
  },
  "confirmation_system": "enabled",
  "transfer_requires_confirmation": true,
  "silence_threshold_sec": 1.5
}
```

---

## Test Endpoints

### Test End Call
```
POST /test-end-call
```
Test the end call functionality.

---

### Test Transfer
```
POST /test-transfer
```
Test the call transfer functionality.

---

## Webhook Events

The following events can be configured in webhooks:
- `call.started` - When a call begins
- `call.ended` - When a call ends
- `message.sent` - When a message is sent
- `transcript.updated` - When transcript is updated

## Error Responses

All endpoints return appropriate HTTP status codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized (invalid API key)
- `404` - Not Found
- `500` - Server Error

Error responses include:
```json
{
  "detail": "Error message describing the issue"
}
```
