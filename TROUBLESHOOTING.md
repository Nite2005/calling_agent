# Troubleshooting Guide

Comprehensive guide to diagnose and fix issues.

## 🔍 Diagnostic Steps

### 1. Check All Services Running

```bash
# Is Ollama running?
curl http://localhost:11434/api/tags
# Expected: {"models": [...]}

# Is FastAPI running?
curl http://localhost:9001/health
# Expected: 200 OK

# Is ngrok running?
curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*'
# Expected: Shows ngrok URL
```

### 2. Check Credentials

```bash
# Verify Twilio
python3 << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv()
print(f"TWILIO_ACCOUNT_SID: {os.getenv('TWILIO_ACCOUNT_SID')[:5]}...visible")
print(f"TWILIO_PHONE_NUMBER: {os.getenv('TWILIO_PHONE_NUMBER')}")
print(f"PUBLIC_URL: {os.getenv('PUBLIC_URL')}")
print(f"DEEPGRAM_API_KEY: {os.getenv('DEEPGRAM_API_KEY')[:10]}...visible")
EOF

# Test Deepgram API
curl -s https://api.deepgram.com/v1/models \
  -H "Authorization: Token YOUR_KEY" | head -20
```

### 3. Check Logs for Errors

```bash
# Recent errors
tail -20 server.log | grep -i error

# Full error context
grep -B5 -A5 "ERROR" server.log | tail -30

# Specific component
grep "voice_pipeline\|llm\|interrupt" server.log | tail -20
```

## 🚨 Common Issues & Solutions

### Issue 1: Application Won't Start

**Error:** `OSError: [Errno 98] Address already in use`

**Cause:** Port 9001 is already in use

**Solution:**
```bash
# Find what's using port 9001
sudo lsof -i :9001

# Kill the process
sudo kill -9 <PID>

# Or use different port
uvicorn main:app --port 9002
```

---

### Issue 2: Ollama Connection Failed

**Error:** `ConnectionError: Failed to connect to http://localhost:11434`

**Cause:** Ollama not running or not accessible

**Solution:**
```bash
# Start Ollama
ollama serve

# Or verify it's running
ps aux | grep ollama

# Check it's listening
netstat -an | grep 11434
```

---

### Issue 3: Deepgram API Key Rejected

**Error:** `401 Unauthorized` from Deepgram

**Cause:** Invalid or expired API key

**Solution:**
```bash
# Verify key is correct in .env
grep DEEPGRAM_API_KEY .env

# Test API key directly
curl -s https://api.deepgram.com/v1/models \
  -H "Authorization: Token YOUR_KEY"
# Should return model list (not error)

# Get new key from https://console.deepgram.com/
```

---

### Issue 4: Twilio Webhook Not Receiving Calls

**Error:** Call goes to voicemail, no logs appear

**Cause:** Webhook URL misconfigured or unreachable

**Solution:**

1. **Verify PUBLIC_URL is accessible:**
```bash
# Test from external computer/phone
curl YOUR_PUBLIC_URL
# Should respond (not timeout/error)
```

2. **Check webhook configuration:**
   - Go to Twilio Console → Phone Numbers → Your Number
   - Voice Configuration → "When a call comes in"
   - Should be: `YOUR_PUBLIC_URL/twiml/voice` (POST method)

3. **Verify ngrok URL (development):**
```bash
# In ngrok terminal, should show:
# Forwarding   https://xxx.ngrok-free.dev -> http://localhost:9001

# Update in .env:
PUBLIC_URL=https://xxx.ngrok-free.dev

# Restart FastAPI after .env change
```

4. **Check firewall:**
```bash
# If behind firewall, may need to whitelist Twilio IPs
# See: https://www.twilio.com/docs/voice/api/ip-addresses
```

---

### Issue 5: No Audio Output from Agent

**Error:** Call connects but no sound

**Cause:** TTS configuration issue

**Solution:**

1. **Verify Deepgram voice model:**
```bash
# Check model is valid
grep DEEPGRAM_VOICE .env

# List available voices
curl -s https://api.deepgram.com/v1/models \
  -H "Authorization: Token YOUR_KEY" | grep voice
```

2. **Check TTS logs:**
```bash
grep "TTS\|speak" server.log | head -20
```

3. **Test TTS directly:**
```bash
curl -X POST https://api.deepgram.com/v1/speak \
  -H "Authorization: Token YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello"}' \
  -o test_audio.wav

# If successful, should create audio file
ls -lh test_audio.wav
```

---

### Issue 6: Interruption Not Working

**Error:** Agent keeps talking even when user interrupts

**Cause:** Detection threshold too high or interruption disabled

**Solution:**

1. **Enable interruption:**
```bash
# Check it's enabled
grep "INTERRUPT_ENABLED\|interrupt_enabled" .env

# Should show: INTERRUPT_ENABLED=true
```

2. **Check agent config:**
```bash
# In database, verify agent has interruption enabled
sqlite3 agents.db "SELECT agent_id, interrupt_enabled FROM agents;"

# If false, update it:
sqlite3 agents.db "UPDATE agents SET interrupt_enabled = 1;"
```

3. **Lower sensitivity for testing:**
```bash
# Reduce thresholds to make it easier to trigger
INTERRUPT_MIN_ENERGY=600        # was 800
INTERRUPT_DEBOUNCE_MS=300       # was 400
INTERRUPT_BASELINE_FACTOR=2.5   # was 2.8
INTERRUPT_MIN_SPEECH_MS=80      # was 100
```

4. **Monitor detection in logs:**
```bash
# Watch for interrupt attempts
tail -f server.log | grep -i interrupt
```

---

### Issue 7: Database Locked

**Error:** `sqlite3.OperationalError: database is locked`

**Cause:** Stale connection or concurrent writes

**Solution:**
```bash
# Stop application
pkill -f uvicorn

# Remove lock files
rm agents.db-wal agents.db-shm 2>/dev/null

# Verify database
sqlite3 agents.db "PRAGMA integrity_check;"
# Should return: ok

# Restart
uvicorn main:app --port 9001
```

---

### Issue 8: High Memory Usage

**Error:** System becomes slow, OOM kills process

**Cause:** Large model, many concurrent calls

**Solution:**

1. **Use smaller model:**
```bash
# Check current model
grep OLLAMA_MODEL .env

# Switch to smaller model
OLLAMA_MODEL=mistral:latest    # Much faster than llama3

# Pull it first
ollama pull mistral:latest
```

2. **Limit concurrent calls:**
```bash
# Monitor memory while running
watch -n 1 free -h

# If hitting limits, reduce max parallel calls or queue size
```

3. **Check what's consuming memory:**
```bash
ps aux --sort=-%mem | head -10
```

---

### Issue 9: Slow Response Times

**Error:** Agent takes 10+ seconds to respond

**Cause:** Network latency, slow LLM, vector DB query

**Solution:**

1. **Monitor latency:**
```bash
# Check individual component times
grep "LATENCY\|TOTAL TIME" server.log | tail -20
```

2. **Identify bottleneck:**
   - STT latency high? → Check Deepgram API
   - LLM latency high? → Use smaller model or GPU
   - TTS latency high? → Check Deepgram service
   - Total pipeline high? → May need to parallelize

3. **Optimize LLM:**
```bash
# Use GPU if available
nvidia-smi  # Check GPU

# Use quantized model
OLLAMA_MODEL=llama3:q4_K_S  # Instead of non-quantized

# Use faster model
OLLAMA_MODEL=mistral:latest
```

4. **Check network:**
```bash
# Ping Deepgram
ping api.deepgram.com

# Check latency
curl -w "Time: %{time_total}s\n" https://api.deepgram.com/v1/models \
  -H "Authorization: Token YOUR_KEY"
```

---

### Issue 10: Agent Keeps Repeating Same Response

**Error:** Agent loops or doesn't progress conversation

**Cause:** Intent detection issue or conversation history problem

**Solution:**

1. **Check conversation history:**
```bash
sqlite3 agents.db "SELECT * FROM conversations LIMIT 5;" | head -20
```

2. **Clear conversation and retry:**
```bash
sqlite3 agents.db "DELETE FROM conversations WHERE agent_id='your-agent-id';"
```

3. **Review system prompt:**
```bash
sqlite3 agents.db "SELECT system_prompt FROM agents WHERE agent_id='your-agent-id';"

# Make sure prompt is clear and includes instructions for conversation flow
```

---

## 🔧 Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Set log level
LOG_LEVEL=DEBUG

# In your code, add debug prints
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug(f"State: {variable}")

# Monitor real-time logs
tail -f server.log | grep -E "DEBUG|ERROR|INTERRUPT"
```

## 🧪 Testing Commands

### Test Each Component

```bash
# 1. Test Deepgram STT
curl -X POST https://api.deepgram.com/v1/listen \
  -H "Authorization: Token YOUR_KEY" \
  -H "Content-Type: audio/wav" \
  --data-binary @audio_sample.wav

# 2. Test Ollama LLM
curl http://localhost:11434/api/generate \
  -X POST \
  -d '{
    "model": "llama3:8b-instruct-q4_K_S",
    "prompt": "Hello, who are you?",
    "stream": false
  }'

# 3. Test Twilio
python3 << 'EOF'
from twilio.rest import Client
account_sid = "YOUR_SID"
auth_token = "YOUR_TOKEN"
client = Client(account_sid, auth_token)
call = client.calls.create(to="+1234567890", from_="+YOUR_NUMBER", url="YOUR_URL")
print(f"Call SID: {call.sid}")
EOF

# 4. Test Agent Endpoint
curl -X POST http://localhost:9001/v1/convai/agents \
  -H "Content-Type: application/json" \
  -H "xi-api-key: default" \
  -d '{"name":"Test","system_prompt":"Test","first_message":"Hi"}'
```

## 📊 Performance Profiling

```bash
# Monitor CPU/Memory during call
watch -n 0.5 'ps aux | grep uvicorn | head -5'

# Monitor database size
ls -lh agents.db chroma_db/

# Count active connections
lsof -p $(pgrep uvicorn) | grep -c TCP

# Monitor network
iftop  # or nethogs
```

## 💾 Backup & Recovery

```bash
# Backup everything
tar -czf ai-sdr-backup-$(date +%Y%m%d).tar.gz \
  .env agents.db chroma_db/ server.log

# Restore from backup
tar -xzf ai-sdr-backup-20260110.tar.gz

# Export agent config
sqlite3 agents.db ".dump agents" > agents_backup.sql

# Restore agent config
sqlite3 agents.db < agents_backup.sql
```

## 📞 Getting Help

When asking for help, provide:

1. **Error message:**
```bash
grep -i error server.log | tail -5
```

2. **Configuration:**
```bash
# (without sensitive data)
grep -E "VOICE|MODEL|INTERRUPT" .env
```

3. **System info:**
```bash
uname -a
python --version
pip show fastapi | grep Version
```

4. **Recent logs:**
```bash
tail -50 server.log > debug.log
# Share debug.log
```

---

**Last Updated:** January 10, 2026
