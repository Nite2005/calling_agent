# Quick Reference Guide

Fast lookup for common tasks and commands.

## 🚀 Quick Start Commands

### Start Development Environment
```bash
# Terminal 1: Ollama (required)
ollama serve

# Terminal 2: ngrok (for webhooks)
ngrok http 9001

# Terminal 3: Application
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 9001 --reload
```

### Test Application is Running
```bash
curl http://localhost:9001/health
# Should return 200 OK
```

## 📱 Common API Calls

### Create Agent
```bash
curl -X POST http://localhost:9001/v1/convai/agents \
  -H "Content-Type: application/json" \
  -H "xi-api-key: default" \
  -d '{
    "name": "Sales Agent",
    "system_prompt": "You are a helpful sales representative. Be concise and professional.",
    "first_message": "Hi! How can I help you today?",
    "voice_id": "aura-2-thalia-en",
    "interrupt_enabled": true
  }'

# Returns: {"agent_id": "agent-xxx-xxx-xxx", "name": "Sales Agent", ...}
# Save the agent_id for later use
```

### List All Agents
```bash
curl -X GET http://localhost:9001/v1/convai/agents \
  -H "xi-api-key: default"
```

### Get Agent Details
```bash
curl -X GET http://localhost:9001/v1/convai/agents/{agent_id} \
  -H "xi-api-key: default"
```

### Make Outbound Call
```bash
curl -X POST http://localhost:9001/v1/convai/outbound \
  -H "Content-Type: application/json" \
  -H "xi-api-key: default" \
  -d '{
    "agent_id": "agent-xxx-xxx-xxx",
    "to_number": "+1234567890",
    "dynamic_variables": {
      "name": "John",
      "company": "Acme"
    }
  }'
```

### List Conversations
```bash
curl -X GET "http://localhost:9001/v1/convai/conversations?agent_id={agent_id}" \
  -H "xi-api-key: default"
```

### Get Conversation Details
```bash
curl -X GET http://localhost:9001/v1/convai/conversations/{conversation_id} \
  -H "xi-api-key: default"
```

## 🔧 Configuration Quick Reference

### Interrupt Detection Tuning
```env
# More sensitive (faster detection)
INTERRUPT_MIN_ENERGY=600
INTERRUPT_DEBOUNCE_MS=300
INTERRUPT_BASELINE_FACTOR=2.5
INTERRUPT_MIN_SPEECH_MS=80

# Less sensitive (fewer false positives)
INTERRUPT_MIN_ENERGY=1000
INTERRUPT_DEBOUNCE_MS=600
INTERRUPT_BASELINE_FACTOR=3.5
INTERRUPT_MIN_SPEECH_MS=150
```

### Voice Models (Deepgram)
```env
# Natural, clear voice
DEEPGRAM_VOICE=aura-2-thalia-en

# Available options (check Deepgram docs)
# aura-2-asteria-en, aura-2-orion-en, aura-2-arcas-en, etc.
```

### LLM Models (Ollama)
```bash
# Pull different models
ollama pull mistral:latest           # Faster, less powerful
ollama pull llama3:8b-instruct       # Balanced
ollama pull llama3:70b-instruct      # Most powerful
ollama pull neural-chat:latest       # Conversation-optimized

# Set in .env
OLLAMA_MODEL=mistral:latest
```

## 📊 Monitoring & Debugging

### View Live Logs
```bash
tail -f server.log
```

### Filter by Event Type
```bash
# Call starts
grep "CALL_START" server.log

# Call ends
grep "CALL_END" server.log

# Interruptions
grep "INTERRUPT" server.log

# Errors
grep "ERROR" server.log

# LLM responses
grep "LLM" server.log | head -20
```

### Count Active Calls
```bash
grep -o "CALL_START" server.log | wc -l
```

### Performance Metrics
```bash
# Average response time
grep "TOTAL TIME:" server.log | awk '{sum+=$NF; count++} END {print "Avg:", sum/count "ms"}'

# Latency tracking (if enabled)
grep "⏱️" server.log
```

## 🐛 Common Issues & Fixes

| Issue | Quick Fix |
|-------|-----------|
| `Connection refused: localhost:11434` | `ollama serve` not running in another terminal |
| `ModuleNotFoundError: No module named 'torch'` | `pip install -r requirements.txt` |
| Webhook not receiving calls | Update PUBLIC_URL in .env with ngrok URL |
| No audio output | Check Deepgram API key, verify model is available |
| Interruption not working | Check `INTERRUPT_ENABLED=true`, lower `INTERRUPT_MIN_ENERGY` |
| High latency | Check CPU usage, reduce model size, verify network |
| `Database is locked` | Stop app, `rm agents.db-wal agents.db-shm`, restart |

## 🔐 Security Checklist

```bash
# Protect .env file
chmod 600 .env

# Verify API key is set
grep "API_KEYS" utils.py

# Check logs don't contain secrets
grep -i "token\|key\|secret" server.log

# Rotate credentials regularly
# - Twilio: Console → Security → API Keys
# - Deepgram: Console → Settings → API Keys
```

## 📈 Performance Tips

1. **Faster responses**: Use smaller model
   ```env
   OLLAMA_MODEL=mistral:latest  # Instead of llama3
   ```

2. **Better interruption**: Lower thresholds
   ```env
   INTERRUPT_MIN_ENERGY=600
   INTERRUPT_MIN_SPEECH_MS=80
   ```

3. **More concurrent calls**: Use GPU
   ```bash
   # Verify GPU is detected
   nvidia-smi
   # Set in terminal before starting
   export CUDA_VISIBLE_DEVICES=0
   ```

4. **Reduce database overhead**: Archive old conversations
   ```bash
   sqlite3 agents.db "DELETE FROM conversations WHERE created_at < date('now', '-30 days')"
   ```

## 🧪 Testing Endpoints

### Health Check
```bash
curl http://localhost:9001/health
```

### Create Test Agent
```bash
curl -X POST http://localhost:9001/v1/convai/agents \
  -H "Content-Type: application/json" \
  -H "xi-api-key: default" \
  -d '{"name":"Test","system_prompt":"Test","first_message":"Hi"}'
```

### Load Test (5 concurrent calls)
```bash
for i in {1..5}; do
  curl -X POST http://localhost:9001/v1/convai/outbound \
    -H "Content-Type: application/json" \
    -H "xi-api-key: default" \
    -d "{\"agent_id\":\"agent-xyz\",\"to_number\":\"+1234567890$i\"}" &
done
wait
```

## 📚 File Quick Reference

| File | Purpose |
|------|---------|
| `main.py` | API endpoints, call routing |
| `voice_pipeline.py` | STT/TTS, interruption |
| `models.py` | Database schemas |
| `utils.py` | Helpers, config |
| `schemas.py` | Request validation |
| `.env` | Environment config |
| `agents.db` | SQLite database |
| `README.md` | Full documentation |
| `API_ENDPOINTS.md` | API reference |

## 🎓 Learn More

- **API Endpoints**: See `API_ENDPOINTS.md`
- **Architecture**: See `MODULARIZATION_SUMMARY.md`
- **Full Setup**: See `INSTALLATION.md`
- **Code Details**: See function docstrings in `.py` files

## 🚨 Emergency Commands

```bash
# Stop all Python processes
pkill -f python
pkill -f ollama
pkill -f ngrok

# Kill specific port
sudo lsof -i :9001
sudo kill -9 <PID>

# Clear database
rm agents.db chroma_db/* server.log

# Force restart
systemctl restart ai-sdr  # if using systemd
```

## 💡 Pro Tips

1. **Use aliases** for common commands:
   ```bash
   alias start-sdr="source venv/bin/activate && uvicorn main:app --port 9001"
   ```

2. **Monitor in separate window**:
   ```bash
   watch -n 1 'tail -5 server.log'
   ```

3. **Test locally without Twilio**:
   ```bash
   # Make API call directly without phone
   curl -X POST http://localhost:9001/v1/convai/agents ...
   ```

4. **Backup configurations**:
   ```bash
   cp .env .env.backup-$(date +%Y%m%d)
   cp agents.db agents.db.backup-$(date +%Y%m%d)
   ```

---

**Last Updated:** January 10, 2026
