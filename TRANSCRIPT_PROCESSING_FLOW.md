# Transcript Processing Flow: Interim vs Final

## Quick Answer
**Your system uses FINAL transcripts** with a 2-stage confirmation:
1. Deepgram marks transcript as `is_final = True`
2. System waits for silence threshold (0.1 seconds currently)
3. **Then** processes with LLM

---

## Visual Processing Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│         USER SPEAKS: "I want to schedule a meeting"                 │
└─────────────────────────────────────────────────────────────────────┘

DEEPGRAM STT STREAM:
│
├─ T=0.5s  [INTERIM] "I want"
│          ├─ stored in: conn.last_interim_text
│          ├─ stored in: conn.stt_transcript_buffer (if empty)
│          ├─ stt_is_final = False
│          └─ NOT processed ❌
│
├─ T=1.0s  [INTERIM] "I want to schedule"
│          ├─ stored in: conn.last_interim_text
│          ├─ stt_is_final = False
│          └─ NOT processed ❌
│
├─ T=1.5s  [INTERIM] "I want to schedule a"
│          ├─ stored in: conn.last_interim_text
│          ├─ stt_is_final = False
│          └─ NOT processed ❌
│
└─ T=2.0s  [FINAL] "I want to schedule a meeting"
           ├─ Replaces buffer: conn.stt_transcript_buffer = "I want to schedule a meeting"
           ├─ Sets flag: conn.stt_is_final = True ✅
           ├─ Updates: conn.last_speech_time = 2.0s
           └─ Ready for processing (but still waiting...)

SILENCE DETECTION:
│
├─ T=2.0s  Start checking silence
│          └─ requirement: wait SILENCE_THRESHOLD_SEC = 0.1s
│
├─ T=2.05s ✅ Silence threshold met (2.05 - 2.0 = 0.05s < 0.1s)
│          └─ Final check: did user speak again?
│
└─ T=2.1s  Final silence confirmed
           └─ User is definitely finished

PROCESSING TRIGGERED:
│
├─ Check: conn.stt_is_final = True? ✅
├─ Check: silence >= SILENCE_THRESHOLD_SEC? ✅
├─ Extract intent from final transcript
├─ Query RAG with final transcript
├─ Call LLM with final transcript
└─ Stream TTS response

```

---

## Code Flow in `process_streaming_transcript()`

### Stage 1: Wait for FINAL Result

```python
# main.py: lines 623-624
if not conn.stt_is_final:
    _logger.debug("⸸ Waiting for FINAL result...")
    return  # Don't process interim transcripts
```

**This is the gate** ← Only processes when `stt_is_final = True`

### Stage 2: Wait for Silence Threshold

```python
# main.py: lines 633-642
silence_elapsed = now - conn.last_speech_time

if silence_elapsed < SILENCE_THRESHOLD_SEC:  # Currently 0.1 seconds
    _logger.debug("⸸ Waiting for silence: %.2fs / %.1fs",
                  silence_elapsed, SILENCE_THRESHOLD_SEC)
    return  # Wait more
```

**This is the lock** ← Only processes after silence confirmed

### Stage 3: All Checks Passed → Process

```python
# main.py: lines 655-663
if conn.last_interim_time and (time.time() - conn.last_interim_time) < 0.3:
    _logger.debug("⸸ New interim detected - waiting")
    return  # User is still speaking

# ALL CHECKS PASSED
_logger.info("✅ %.1fs silence threshold met", SILENCE_THRESHOLD_SEC)

try:
    text = conn.stt_transcript_buffer.strip()  # ← Use FINAL transcript
    intent = detect_intent(text)                 # Process intent
    # ... continue to LLM query
```

---

## Where Interim vs Final Transcripts Are Set

### Interim Transcripts (voice_pipeline.py)

```python
# voice_pipeline.py: lines 717-724
else:  # is_final = False (interim)
    conn.last_interim_time = now
    conn.last_interim_text = transcript  # Store for reference only
    
    if not conn.stt_transcript_buffer or not conn.stt_is_final:
        conn.stt_transcript_buffer = transcript
        _logger.info(f"🎙️ Interim as buffer: '{transcript}'")
```

**Purpose:** 
- Stored in `conn.last_interim_text`
- Used to detect if user is still speaking
- Acts as temporary buffer if no final received yet
- **NOT used for LLM** ❌

### Final Transcripts (voice_pipeline.py)

```python
# voice_pipeline.py: lines 699-714
if is_final:
    current_buffer = conn.stt_transcript_buffer.strip()
    
    if current_buffer:
        if (not current_buffer.endswith((".", "!", "?")) and len(transcript) > 3):
            conn.stt_transcript_buffer += " " + transcript
        else:
            conn.stt_transcript_buffer = transcript
    else:
        conn.stt_transcript_buffer = transcript
    
    conn.stt_is_final = True  # ← FLAG SET HERE
    _logger.info(f"🎙️ Complete buffer: '{conn.stt_transcript_buffer.strip()}'")
```

**Purpose:**
- Updates `conn.stt_transcript_buffer` with final text
- Sets `conn.stt_is_final = True` flag
- Updates `conn.last_speech_time` for silence tracking
- **Ready for LLM processing** ✅

---

## Processing Decision Tree

```
Media chunk received from Twilio
    │
    ▼
Send to Deepgram STT
    │
    ├─ Deepgram returns: is_final = False (interim)
    │  │
    │  ├─ Store in: conn.last_interim_text
    │  ├─ Store in: conn.stt_transcript_buffer (if buffer empty)
    │  ├─ Check: process_streaming_transcript()
    │  │  └─ "if not conn.stt_is_final: return" ← GATE BLOCKS
    │  │
    │  └─ Result: ❌ NOT PROCESSED
    │
    └─ Deepgram returns: is_final = True (final)
       │
       ├─ Update: conn.stt_transcript_buffer
       ├─ Set: conn.stt_is_final = True
       ├─ Update: conn.last_speech_time
       ├─ Check: process_streaming_transcript()
       │  │
       │  ├─ "if not conn.stt_is_final:" → PASS ✅
       │  ├─ "if silence_elapsed < 0.1s:" → WAIT ⏳
       │  │
       │  └─ Once silence threshold met:
       │     ├─ Check for new interim (< 0.3s)
       │     ├─ All checks passed
       │     └─ PROCESS: Extract intent → RAG → LLM ✅
       │
       └─ Result: ✅ PROCESSED

```

---

## Current Configuration vs Recommended

| Setting | Current Value | What It Does |
|---------|---------------|--------------|
| `SILENCE_THRESHOLD_SEC` | **0.1s** | Wait this long after last speech before processing |
| Uses final transcript | **Yes** | Only LLM processes final transcripts |
| Stores interim | **Yes** | Stored in `last_interim_text` (for reference) |
| VAD detection | **Energy-based** | Detects user still speaking |

**⚠️ Note:** Your 0.1 second threshold is **very aggressive**!
- Recommended: 0.5 - 1.5 seconds
- 0.1s means user barely has time to pause before LLM processes

---

## What Happens During Processing

When `stt_is_final = True` + silence threshold met:

```python
# main.py: lines 665-738
text = conn.stt_transcript_buffer.strip()  # ← FINAL transcript

# 1. INTENT DETECTION
intent = detect_intent(text)
conn.last_intent = intent

# 2. RAG QUERY
async for token in query_rag_streaming(
    text,  # ← Using FINAL transcript
    conn.conversation_history,
    call_sid=call_sid
):
    # 3. STREAM TOKENS
    response_buffer += token
    sentence_buffer += token
    
    # 4. QUEUE SENTENCES FOR TTS
    if sentence_buffer.rstrip().endswith(('.', '?', '!')):
        await conn.tts_queue.put(clean_sentence)

# 5. SAVE TO CONVERSATION HISTORY
conn.conversation_history.append({
    "user": text,         # ← FINAL transcript
    "assistant": cleaned_response,
    "timestamp": time.time()
})
```

**Key Point:** All processing uses the FINAL transcript stored in `conn.stt_transcript_buffer`

---

## Example Processing Timeline

```
T=0.0s  User: "I want to meet tomorrow"
T=0.2s  [interim] "I want"              → stored, not processed
T=0.4s  [interim] "I want to"           → stored, not processed
T=0.6s  [interim] "I want to meet"      → stored, not processed
T=0.8s  [final]   "I want to meet"      → stt_is_final=True, buffered
T=0.9s  [interim] "I want to meet tomorrow" → last_interim_text updated
T=1.0s  [final]   "I want to meet tomorrow" → stt_is_final=True, buffered
T=1.1s  Silence check: 0.1s elapsed ✅  → PROCESS NOW!
        ├─ Intent: "SCHEDULE_MEETING"
        ├─ Query RAG
        ├─ Call LLM with: "I want to meet tomorrow"
        ├─ Get response: "Sure, what time works best?"
        ├─ Stream TTS
        └─ Save to history

T=2.0s  Agent finishes speaking
T=2.5s  Back to listening for next user input
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **Processing Uses** | **FINAL transcripts only** |
| **When is_final=False** | Stored but NOT processed (waits for final) |
| **When is_final=True** | Buffered, then waits for silence |
| **Silence Requirement** | 0.1 seconds (your current setting) |
| **LLM Processes** | Only after final + silence confirmed |
| **Interim Purpose** | Real-time feedback, interrupt detection |
| **Final Purpose** | LLM processing, conversation history |

