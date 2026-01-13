# Transcript Handling: Intermediate vs. Final

## Current Implementation Summary

The system uses **BOTH intermediate and final transcripts**, but with different purposes:

```
Deepgram STT Stream
        │
        ├─ is_final = FALSE  (Intermediate transcripts)
        │  └─ Used for: Real-time feedback, UI updates (NOT for LLM queries)
        │
        └─ is_final = TRUE   (Final transcripts)
           └─ Used for: LLM processing, conversation history
```

---

## Detailed Behavior

### 1. **INTERMEDIATE TRANSCRIPTS** (is_final = False)
**When received:**
- During active speech
- Before speech ends
- Multiple times per utterance (partial results)

**Current usage:**
```python
# voice_pipeline.py: lines 717-724
else:  # is_final = False
    conn.last_interim_time = now
    conn.last_interim_text = transcript
    
    if not conn.stt_transcript_buffer or not conn.stt_is_final:
        conn.stt_transcript_buffer = transcript
        _logger.info(f"🎙️ Interim as buffer: '{transcript}'")
```

**What happens:**
- Stored in `conn.last_interim_text` (for reference only)
- Stored in `conn.stt_transcript_buffer` IF buffer is empty
- **NOT used for LLM processing** ❌
- **NOT marked as final** (stt_is_final = False)
- Helps track ongoing speech for interrupt detection

**Example sequence:**
```
User: "I want to schedule a meeting tomorrow at 3 PM"

Time 1: [interim] "I want"
Time 2: [interim] "I want to schedule"
Time 3: [interim] "I want to schedule a"
Time 4: [interim] "I want to schedule a meeting"
...
```

---

### 2. **FINAL TRANSCRIPTS** (is_final = True)
**When received:**
- After user finishes speaking and goes silent
- One per sentence/utterance
- Replaces intermediate result with confirmed text

**Current usage:**
```python
# voice_pipeline.py: lines 699-712
if is_final:
    current_buffer = conn.stt_transcript_buffer.strip()
    
    if current_buffer:
        if (not current_buffer.endswith((".", "!", "?")) and len(transcript) > 3):
            conn.stt_transcript_buffer += " " + transcript
        else:
            conn.stt_transcript_buffer = transcript
    else:
        conn.stt_transcript_buffer = transcript
    
    conn.stt_is_final = True  # ← IMPORTANT FLAG
    _logger.info(f"🎙️ Complete buffer: '{conn.stt_transcript_buffer.strip()}'")
```

**What happens:**
- Replaces provisional transcript with confirmed final text
- Sets `conn.stt_is_final = True` flag
- Updates `conn.last_speech_time` (for silence detection)
- **READY for LLM processing** ✅

**Example sequence:**
```
User: "I want to schedule a meeting tomorrow at 3 PM"

Time 5: [final] "I want to schedule a meeting tomorrow at 3 PM"
        └─ stt_is_final = True
        └─ Ready for LLM → process_streaming_transcript()
```

---

## Flow: When is LLM Called?

The LLM is **ONLY called after final transcripts** via this check:

```python
# main.py: lines 623-624
if not conn.stt_is_final:
    _logger.debug("⸸ Waiting for FINAL result...")
    return
```

### Full Decision Tree:

```
Media received from Twilio
    │
    ├─ Send to Deepgram STT
    │
    ├─ Deepgram returns: is_final = False (interim)
    │  └─ Store in: conn.stt_transcript_buffer
    │  └─ Store in: conn.last_interim_text
    │  └─ NOT processed → return
    │
    └─ Deepgram returns: is_final = True (final)
       └─ Update: conn.stt_transcript_buffer
       └─ Set: conn.stt_is_final = True
       └─ Wait for silence threshold (1.5s default)
       │
       └─ Once silence threshold met:
           ├─ Extract user intent
           ├─ Query RAG (semantic search)
           ├─ Generate LLM response
           └─ Stream TTS back to caller
```

---

## Silence Detection (The Final Gate)

Even AFTER receiving a final transcript, the system waits for silence:

```python
# main.py: lines 633-642
if conn.last_speech_time is None:
    return  # No speech detected yet

silence_elapsed = now - conn.last_speech_time

if silence_elapsed < SILENCE_THRESHOLD_SEC:  # Default: 1.5 seconds
    _logger.debug("⸸ Waiting for silence: %.2fs / %.1fs",
                  silence_elapsed, SILENCE_THRESHOLD_SEC)
    return
```

**Why?**
- Deepgram marks sentences as "final" but user might continue speaking
- Need to ensure user has **completely finished**
- Avoids interrupting mid-utterance

**Example:**
```
Time 1: [final] "I want to schedule"       ← stt_is_final = True
Time 2: User keeps speaking...
Time 3: [final] "a meeting tomorrow"       ← stt_is_final = True (updated)
Time 4: Silence for 1.5 seconds
Time 5: NOW process with LLM
```

---

## Summary: When Processing Happens

| Condition | Action |
|-----------|--------|
| Intermediate transcript received | Store in buffer, wait for final |
| Final transcript received | Mark `stt_is_final = True` |
| Final + silence < 1.5s | Wait more |
| Final + silence ≥ 1.5s | **PROCESS: Extract intent → Query RAG → Call LLM** |
| No new interim for 0.3s | Stop waiting, process now |
| User starts speaking again | Reset timer, wait for new final |

---

## Configuration Variables

Located in [utils.py](utils.py):

```python
SILENCE_THRESHOLD_SEC = 1.5          # Wait time after last speech
UTTERANCE_END_MS = 300               # Additional safety window (ms)
INTERRUPT_ENABLED = True             # Allow user to interrupt agent
INTERRUPT_MIN_SPEECH_MS = 200        # Min energy spike to trigger interrupt
```

---

## Visual Timeline

```
Timeline of a User Utterance:
═════════════════════════════════════════════════════════════════

T=0.0s  User starts speaking: "I want to schedule"
        └─ Deepgram: [interim]

T=0.5s  User continues: "a meeting"
        └─ Deepgram: [interim]

T=1.0s  User finishes: "tomorrow"
        └─ Deepgram: [final] "I want to schedule a meeting tomorrow"
        │  stt_is_final = True
        │  conn.last_speech_time = 1.0s

T=1.0s - 2.5s  Waiting for silence threshold
        └─ Check: now (2.5s) - last_speech_time (1.0s) = 1.5s ✓

T=2.5s  SILENCE THRESHOLD MET
        ├─ Extract intent
        ├─ Query RAG with: "I want to schedule a meeting tomorrow"
        ├─ Get context from knowledge base
        ├─ Call LLM with final transcript
        ├─ Stream response back
        └─ Agent speaks response to caller

T=3.0s  Back to listening
        └─ Waiting for next user speech
```

---

## Key Takeaways

✅ **System uses FINAL transcripts for LLM processing**
- Ensures accuracy
- Waits for silence to confirm user finished
- Avoids processing partial/incomplete thoughts

⏳ **Intermediate transcripts stored but NOT used for reasoning**
- Available in `conn.last_interim_text`
- Could be used for UI updates (not currently implemented)
- Helps with interrupt detection (energy-based)

🎯 **Two-stage confirmation:**
1. Deepgram marks result as "final"
2. System waits 1.5 seconds of silence
3. THEN processes with LLM

