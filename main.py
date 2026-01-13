"""
Main FastAPI Application Module

Central application setup and API endpoints
"""

import os
import asyncio
import time
import re
from typing import Dict, Optional
from datetime import datetime as dt

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Security
from fastapi.responses import Response, PlainTextResponse
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse, Connect
from sqlalchemy.orm import Session
import ollama

# Import all submodules
from models import (
    Agent, Conversation, WebhookConfig, PhoneNumber, KnowledgeBase, AgentTool,
    SessionLocal, get_db
)
from schemas import (
    CallRequest, AgentCreate, AgentUpdate, OutboundCallRequest,
    WebhookCreate, WebhookResponse, ToolCreate
)
from utils import (
    _logger, JWT_SECRET, API_KEYS, WEBHOOK_EVENTS, DEVICE, PUBLIC_URL,
    TWILIO_PHONE_NUMBER, twilio_client, embedder, collection, chroma_client,
    DEEPGRAM_VOICE, OLLAMA_MODEL, TOP_K, CHUNK_SIZE, SILENCE_THRESHOLD_SEC,
    UTTERANCE_END_MS, ENABLE_INTERIM_PROCESSING, INTERIM_MIN_LENGTH,
    INTERIM_CONFIDENCE_THRESHOLD, generate_agent_id, generate_conversation_id,
    clean_markdown_for_tts, detect_intent, detect_confirmation_response,
    parse_llm_response, send_webhook, send_webhook_and_get_response,
    _chunk_text
)
from voice_pipeline import (
    manager, stream_tts_worker, setup_streaming_stt, speak_text_streaming,
    ConnectionManager, audioop
)

# Global call data storage
pending_call_data: Dict[str, Dict] = {}


# ================================
# API KEY VERIFICATION
# ================================

API_KEY_HEADER = APIKeyHeader(name="xi-api-key", auto_error=False)


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """Verify API key"""
    if not API_KEYS or API_KEYS == ['']:
        return None
    
    if not api_key or api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return api_key


# ================================
# FASTAPI APP SETUP
# ================================

app = FastAPI(
    title="AI Voice Call System - ElevenLabs Compatible",
    description="Self-hosted voice AI with agent management, webhooks, and dynamic variables",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================
# HELPER FUNCTIONS
# ================================

async def end_call_tool(call_sid: str, reason: str = "user_goodbye") -> dict:
    """End the active call"""
    _logger.info(f"📞 END_CALL: call_sid={call_sid}, reason={reason}")

    try:
        await asyncio.sleep(1.5)
        call = twilio_client.calls(call_sid).update(status="completed")
        await manager.disconnect(call_sid)

        return {
            "success": True,
            "message": f"Call ended: {reason}",
            "call_sid": call_sid
        }
    except Exception as e:
        _logger.error(f"❌ Failed to end call: {e}")
        return {"success": False, "error": str(e)}


async def transfer_call_tool(call_sid: str, department: str = "sales") -> dict:
    """Transfer call to human agent"""
    _logger.info(f"📞 TRANSFER_CALL: call_sid={call_sid}, dept={department}")

    DEPARTMENT_NUMBERS = {
        "sales": os.getenv("SALES_PHONE_NUMBER", "+918107061392"),
        "support": os.getenv("SUPPORT_PHONE_NUMBER", "+918107061392"),
        "technical": os.getenv("TECH_PHONE_NUMBER", "+918107061392"),
    }

    try:
        transfer_number = DEPARTMENT_NUMBERS.get(department, DEPARTMENT_NUMBERS["sales"])

        conn = manager.get(call_sid)
        if not conn:
            return {"success": False, "error": "Connection not found"}

        _logger.info("⏳ Waiting for transfer message to be spoken...")
        await asyncio.sleep(3.0)

        conn.interrupt_requested = True

        while not conn.tts_queue.empty():
            try:
                conn.tts_queue.get_nowait()
                conn.tts_queue.task_done()
            except:
                break

        try:
            if conn.stream_sid:
                await conn.ws.send_json({
                    "event": "clear",
                    "streamSid": conn.stream_sid
                })
        except:
            pass

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial>{transfer_number}</Dial>
</Response>"""

        twilio_client.calls(call_sid).update(twiml=twiml)

        _logger.info(f"✅ Transfer completed to {department} ({transfer_number})")

        return {
            "success": True,
            "transfer_to": transfer_number,
            "department": department,
            "message": f"Transferred to {department}"
        }

    except Exception as e:
        _logger.error(f"❌ Transfer failed: {e}")
        return {"success": False, "error": str(e)}


async def call_webhook_tool(webhook_url: str, tool_name: str, parameters: dict, call_context: dict) -> dict:
    """Call external webhook tool"""
    try:
        payload = {
            "tool_name": tool_name,
            "parameters": parameters,
            "call_context": call_context,
            "timestamp": dt.utcnow().isoformat()
        }
        
        _logger.info(f"🔧 Calling webhook tool: {tool_name} at {webhook_url}")
        
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                _logger.info(f"✅ Webhook tool response: {result}")
                return {
                    "success": True,
                    "tool_name": tool_name,
                    "response": result.get("response", result),
                    "data": result.get("data", {}),
                    "message": result.get("message", "")
                }
            else:
                _logger.error(f"❌ Webhook returned status {response.status_code}")
                return {
                    "success": False,
                    "error": f"Webhook returned status {response.status_code}",
                    "tool_name": tool_name
                }
                
    except asyncio.TimeoutError:
        _logger.error(f"❌ Webhook timeout for {tool_name}")
        return {
            "success": False,
            "error": "Tool request timed out",
            "tool_name": tool_name
        }
    except Exception as e:
        _logger.error(f"❌ Webhook error for {tool_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "tool_name": tool_name
        }


async def execute_detected_tool(call_sid: str, tool_data: dict) -> dict:
    """Execute a tool detected from LLM response"""
    tool_name = tool_data["tool"]
    params = tool_data.get("params", {})

    _logger.info(f"🔧 Executing LLM-requested tool: {tool_name} with params: {params}")

    if tool_name == "end_call":
        result = await end_call_tool(call_sid, **params)
    elif tool_name == "transfer_call":
        result = await transfer_call_tool(call_sid, **params)
    else:
        conn = manager.get(call_sid)
        if not conn or not conn.agent_id:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        db = SessionLocal()
        try:
            tool = db.query(AgentTool).filter(
                AgentTool.agent_id == conn.agent_id,
                AgentTool.tool_name == tool_name,
                AgentTool.is_active == True
            ).first()
            
            if not tool or not tool.webhook_url:
                return {"success": False, "error": f"Unknown or inactive tool: {tool_name}"}
            
            call_context = {
                "call_sid": call_sid,
                "agent_id": conn.agent_id,
                "conversation_id": conn.conversation_id,
                "phone_number": None,
                "dynamic_variables": conn.dynamic_variables or {}
            }
            
            result = await call_webhook_tool(
                webhook_url=tool.webhook_url,
                tool_name=tool_name,
                parameters=params,
                call_context=call_context
            )
            
            webhooks = db.query(WebhookConfig).filter(
                WebhookConfig.agent_id == conn.agent_id,
                WebhookConfig.is_active == True
            ).all()
            
            for webhook in webhooks:
                if "tool.called" in webhook.events:
                    await send_webhook(
                        webhook.webhook_url,
                        "tool.called",
                        {
                            "call_sid": call_sid,
                            "agent_id": conn.agent_id,
                            "tool_name": tool_name,
                            "parameters": params,
                            "result": result,
                            "timestamp": dt.utcnow().isoformat()
                        }
                    )
            
        finally:
            db.close()

    return result


async def query_rag_streaming(
    question: str,
    history: Optional[list] = None,
    top_k: int = TOP_K,
    call_sid: Optional[str] = None
):
    """Query RAG with streaming response"""
    if history is None:
        history = []

    from datetime import datetime
    import pytz
    ny_tz = pytz.timezone('America/New_York')
    current_date = datetime.now(ny_tz).strftime("%A, %B %d, %Y")
    
    conn = manager.get(call_sid) if call_sid else None
    agent_prompt = None
    dynamic_vars = {}
    model_to_use = OLLAMA_MODEL
    
    model_source = "env_default"
    
    if conn and conn.agent_config:
        agent_prompt = conn.agent_config.get("system_prompt")
        dynamic_vars = conn.dynamic_variables or {}
        _logger.info(f"✅ Using agent prompt with {len(dynamic_vars)} dynamic variables")
        
        if conn.custom_model and conn.custom_model.strip():
            model_to_use = conn.custom_model
            model_source = "api_override"
        elif conn.agent_config.get("model_name"):
            model_to_use = conn.agent_config["model_name"]
            model_source = "agent_config"
    
    _logger.info(f"🤖 Model: {model_to_use} (source: {model_source})")

    loop = asyncio.get_running_loop()

    def _embed_and_query():
        import torch
        with torch.no_grad():
            query_embedding = embedder.encode(
                [question],
                device=DEVICE,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=1
            )[0].tolist()

            return collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2
            )

    results = await loop.run_in_executor(None, _embed_and_query)

    raw_docs = results.get("documents", [[]])[0] if results else []
    distances = results.get("distances", [[]])[0] if results else []

    relevant_chunks = []
    for doc, dist in zip(raw_docs, distances):
        if dist <= 1.3:
            relevant_chunks.append(doc)

    context_text = "\n".join(relevant_chunks[:3])

    history_text = ""
    if history and len(history) > 0:
        recent_history = history[-6:]
        history_lines = []
        for h in recent_history:
            history_lines.append(f"User: {h['user']}\nAssistant: {h['assistant']}")
        history_text = "\n".join(history_lines)

    if agent_prompt:
        vars_section = ""
        if dynamic_vars:
            vars_lines = []
            for key, value in dynamic_vars.items():
                if value and str(value).strip():
                    vars_lines.append(f"- **{key}**: {value}")
            if vars_lines:
                vars_section = "\n\n## Lead/Customer Information:\n" + "\n".join(vars_lines)
        call_context = ""
        if conn:
            call_context = f"""
        ## CALL CONTEXT (VERY IMPORTANT)
        You are on a LIVE PHONE CALL with a real person.
        - DO NOT include stage directions or markdown
        - Speak briefly and naturally
        Current call phase: {conn.call_phase}
        Detected user intent: {conn.last_intent}
        """

        prompt = f"""{agent_prompt}

    {call_context}
    
## Current Date (America/New_York):
Today is {current_date}.{vars_section}

## Knowledge Base Context:
{context_text if context_text.strip() else "No specific context found."}

## current conversation history:
{history_text if history_text else ""}

## User's Current Question:
{question}"""
    else:
        prompt = f"""You are MILA, a friendly voice assistant.
## Current Date:
Today is {current_date}.

## PHONE PERSONALITY:
- You're on a LIVE phone call
- Keep responses BRIEF (1-2 sentences max)
- Sound conversational, not scripted

## Knowledge Base:
{context_text if context_text else "No specific context."}

## Previous Conversation:
{history_text if history_text else "This is the start of the call."}

## What they just said:
{question}

Respond naturally and briefly:"""

    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    full_response = ""

    def _safe_put(item):
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            if queue.qsize() > 400:
                try:
                    queue.get_nowait()
                    queue.put_nowait(item)
                except:
                    pass

    def _producer():
        nonlocal full_response
        try:
            _logger.info(f"🤖 Calling Ollama with model: {model_to_use}")
            for chunk in ollama.generate(
                model=model_to_use,
                prompt=prompt,
                stream=True,
                options={
                    "temperature": 0.2,
                    "num_predict": 1200,
                    "top_k": 40,
                    "top_p": 0.9,
                    "num_ctx": 1024,
                    "num_thread": 8,
                    "repeat_penalty": 1.2,
                    "repeat_last_n": 128,
                    "num_gpu": 99,
                    "stop": ["\nUser:", "\nAssistant:", "User:"],
                }
            ):
                token = chunk.get("response")
                if token:
                    full_response += token
                    loop.call_soon_threadsafe(_safe_put, token)
            loop.call_soon_threadsafe(_safe_put, None)
            _logger.info(f"✅ Ollama generation completed: {len(full_response)} chars")
        except Exception as e:
            _logger.error(f"❌ Ollama error: {e}", exc_info=True)
            loop.call_soon_threadsafe(_safe_put, {"__error__": str(e)})

    loop.run_in_executor(None, _producer)

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, dict) and "__error__" in item:
                yield "I'm having trouble responding right now. Could you repeat that?"
                return

            yield item

    except Exception as e:
        yield "I'm having trouble answering right now. Could you repeat that?"


async def save_conversation_transcript(call_sid: str, conn):
    """Save conversation transcript to database"""
    _logger.info(f"💾 save_conversation_transcript called for {call_sid}")
    
    if not conn:
        _logger.warning(f"⚠️ No connection found for {call_sid}")
        return
    
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(
            Conversation.conversation_id == call_sid
        ).first()
        
        if conversation:
            transcript_lines = []
            for entry in conn.conversation_history:
                user_text = entry.get('user', '')
                assistant_text = entry.get('assistant', '')
                transcript_lines.append(f"User: {user_text}")
                transcript_lines.append(f"Assistant: {assistant_text}")
            
            conversation.transcript = "\n".join(transcript_lines) if transcript_lines else "[No conversation]"
            conversation.status = "completed"
            conversation.ended_at = dt.utcnow()
            
            if conversation.started_at:
                duration = (conversation.ended_at - conversation.started_at).total_seconds()
                conversation.duration_secs = int(duration)
            
            db.commit()
            _logger.info(f"✅ Saved transcript for {call_sid}")
        else:
            _logger.warning(f"⚠️ Conversation record not found in DB for {call_sid}")
    except Exception as e:
        _logger.error(f"❌ Failed to save transcript: {e}")
        db.rollback()
    finally:
        db.close()


async def handle_call_end(call_sid: str, reason: str):
    """Handle call ending"""
    conn = manager.get(call_sid)
    
    if conn:
        await save_conversation_transcript(call_sid, conn)
    
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(
            Conversation.conversation_id == call_sid
        ).first()
        
        if conversation:
            conversation.ended_reason = reason
            conversation.status = "completed"
            if not conversation.ended_at:
                conversation.ended_at = dt.utcnow()
            
            if conversation.started_at and not conversation.duration_secs:
                duration = (conversation.ended_at - conversation.started_at).total_seconds()
                conversation.duration_secs = int(duration)
            
            db.commit()
            
            webhooks = db.query(WebhookConfig).filter(
                WebhookConfig.is_active == True
            ).all()
            
            for webhook in webhooks:
                should_send = False
                if webhook.agent_id is None:
                    should_send = True
                elif conversation.agent_id and webhook.agent_id == conversation.agent_id:
                    should_send = True
                
                if should_send and ("call.ended" in webhook.events or not webhook.events):
                    await send_webhook(
                        webhook.webhook_url,
                        "call.ended",
                        {
                            "conversation_id": call_sid,
                            "agent_id": conversation.agent_id,
                            "duration_secs": conversation.duration_secs,
                            "ended_reason": reason,
                            "transcript": conversation.transcript,
                            "phone_number": conversation.phone_number,
                            "status": "completed"
                        }
                    )
            
            _logger.info(f"✅ Call ended: {call_sid} - {reason}")
        else:
            _logger.warning(f"⚠️ Conversation not found for call end: {call_sid}")
    except Exception as e:
        _logger.error(f"❌ Failed to handle call end: {e}")
    finally:
        db.close()


async def process_streaming_transcript(call_sid: str):
    """Process user transcript and generate response"""
    _logger.debug(f"🔄 process_streaming_transcript called for {call_sid}")
    
    conn = manager.get(call_sid)
    if not conn:
        _logger.debug("No connection found")
        return
    
    if conn.is_responding:
        _logger.debug("Already responding")
        return

    if conn.interrupt_requested:
        _logger.debug("⭐ Skipping - interrupt active")
        return

    now = time.time()

    # Check VAD timeout
    if conn.user_speech_detected and conn.vad_triggered_time:
        vad_duration = now - conn.vad_triggered_time
        if vad_duration > conn.vad_timeout:
            _logger.info(f"⚠️ VAD timeout cleared (duration: {vad_duration:.1f}s)")
            conn.user_speech_detected = False
            conn.speech_start_time = None
            conn.vad_triggered_time = None
            conn.vad_validated = False

    # Wait for user to finish
    if conn.last_interim_time and (now - conn.last_interim_time) < 0.5:
        _logger.debug("⸸ User still adding - waiting...")
        return

    if conn.user_speech_detected:
        _logger.debug("⸸ User still speaking - waiting...")
        return

    # Check for interim processing (for lower latency)
    if ENABLE_INTERIM_PROCESSING and conn.stt_transcript_buffer:
        buffer_len = len(conn.stt_transcript_buffer.strip())
        
        # Allow interim processing if:
        # 1. Buffer has minimum length
        # 2. Not already responding
        # 3. Either final result OR interim result with min length
        if buffer_len >= INTERIM_MIN_LENGTH:
            _logger.info(f"📊 Interim processing enabled: '{conn.stt_transcript_buffer.strip()[:50]}...'")
            # Continue to processing below
        else:
            _logger.debug(f"⸸ Interim buffer too short: {buffer_len} < {INTERIM_MIN_LENGTH}")
            return
    else:
        # Original behavior: Must have final result
        if not conn.stt_is_final:
            _logger.debug("⸸ Waiting for FINAL result...")
            return

    if not conn.stt_transcript_buffer or len(conn.stt_transcript_buffer.strip()) < 3:
        _logger.debug("⸸ Buffer empty")
        return

    # Check silence threshold
    if conn.last_speech_time is None:
        _logger.debug("⸸ No speech time recorded")
        return

    silence_elapsed = now - conn.last_speech_time

    # For interim processing: use shorter threshold
    threshold = 0.05 if (ENABLE_INTERIM_PROCESSING and not conn.stt_is_final) else SILENCE_THRESHOLD_SEC
    
    if silence_elapsed < threshold:
        _logger.debug("⸸ Waiting for silence: %.2fs / %.1fs",
                      silence_elapsed, threshold)
        return

    # Mark as responding early
    conn.is_responding = True

    await asyncio.sleep(0.05)

    final_silence = time.time() - conn.last_speech_time
    final_threshold = 0.05 if (ENABLE_INTERIM_PROCESSING and not conn.stt_is_final) else SILENCE_THRESHOLD_SEC

    if final_silence < final_threshold:
        _logger.debug("⸸ New speech detected - resetting")
        return

    if conn.last_interim_time and (time.time() - conn.last_interim_time) < 0.3:
        _logger.debug("⸸ New interim detected - waiting")
        return

    # ALL CHECKS PASSED
    processing_mode = "INTERIM" if (ENABLE_INTERIM_PROCESSING and not conn.stt_is_final) else "FINAL"
    _logger.info("✅ %.1fs silence threshold met (%s mode)", final_threshold, processing_mode)

    try:
        text = conn.stt_transcript_buffer.strip()

        intent = detect_intent(text)
        conn.last_intent = intent

        _logger.info(f"🎯 Detected intent: {intent} | text='{text}'")

        if intent == "GOODBYE":
            conn.stt_transcript_buffer = ""
            conn.stt_is_final = False
            conn.last_interim_text = ""
            
            conn.conversation_history.append({
                "user": text,
                "assistant": "Thanks for your time. Have a great day.",
                "timestamp": time.time()
            })
            
            await speak_text_streaming(call_sid, "Thanks for your time. Have a great day.")
            await end_call_tool(call_sid, "user_goodbye")
            return

        # Update call phase
        if conn.call_phase == "CALL_START":
            conn.call_phase = "DISCOVERY"
        elif conn.call_phase == "DISCOVERY":
            if len(conn.conversation_history) >= 2:
                conn.call_phase = "ACTIVE"

        if conn.interrupt_requested:
            _logger.debug("⭐ Interrupt detected - aborting")
            conn.stt_transcript_buffer = ""
            conn.stt_is_final = False
            conn.last_interim_text = ""
            return

        # Handle pending action
        if conn.pending_action:
            _logger.info("Pending action detected")
            confirmation = detect_confirmation_response(text)

            if confirmation == "yes":
                _logger.info("User confirmed action")
                result = await execute_detected_tool(call_sid, conn.pending_action)
                conn.pending_action = None
                conn.stt_transcript_buffer = ""
                conn.stt_is_final = False
                conn.last_interim_text = ""
                return
            elif confirmation == "no":
                await speak_text_streaming(call_sid, "Understood, cancelled. How else can I help?")
                conn.pending_action = None
                conn.stt_transcript_buffer = ""
                conn.stt_is_final = False
                conn.last_interim_text = ""
                return
            else:
                word_count = len(text.split())
                if word_count > 5:
                    _logger.info("User changed topic")
                    conn.pending_action = None
                else:
                    await speak_text_streaming(call_sid, "Could you please confirm yes or no?")
                    conn.stt_transcript_buffer = ""
                    conn.stt_is_final = False
                    conn.last_interim_text = ""
                    return

        # Clear buffer
        conn.stt_transcript_buffer = ""
        conn.stt_is_final = False
        conn.last_interim_text = ""

        if not text or len(text) < 3:
            _logger.warning(f"⚠️ Text too short: '{text}'")
            conn.is_responding = False
            return

        _logger.info(f"📝 USER INPUT: '{text}'")

        t_start = time.time()

        response_buffer = ""
        sentence_buffer = ""
        sentence_count = 0
        MAX_SENTENCES = 10

        async for token in query_rag_streaming(text, conn.conversation_history, call_sid=call_sid):
            if conn.interrupt_requested:
                _logger.info("⭐ Generation interrupted")
                break

            token = re.sub(r'\[(?:TOOL|CONFIRM_TOOL):[^\]]+\]', '', token)

            response_buffer += token
            sentence_buffer += token

            if sentence_buffer.rstrip().endswith(('.', '?', '!')):
                sentence = sentence_buffer.strip()

                if sentence:
                    clean_sentence = clean_markdown_for_tts(sentence)
                    sentence_count += 1
                    _logger.info("🎯 Sentence %d: '%s'",
                                 sentence_count, clean_sentence)

                    try:
                        await asyncio.wait_for(conn.tts_queue.put(clean_sentence), timeout=2.0)
                    except asyncio.TimeoutError:
                        if conn.interrupt_requested:
                            break
                    except Exception as e:
                        if conn.interrupt_requested:
                            break

                sentence_buffer = ""

                if sentence_count >= MAX_SENTENCES:
                    break

        if not conn.interrupt_requested and sentence_buffer.strip():
            final_sentence = sentence_buffer.strip()
            if final_sentence and not re.match(r'^\s*\[\w+:[^\]]*\]\s*$', final_sentence):
                clean_final = clean_markdown_for_tts(final_sentence)
                _logger.info("🎯 Final: '%s'", clean_final)
                try:
                    await asyncio.wait_for(conn.tts_queue.put(clean_final), timeout=2.0)
                except asyncio.TimeoutError:
                    _logger.warning("TTS queue full")
                except Exception as e:
                    _logger.error(f"Error queuing final: {e}")

        cleaned_response, tool_data = parse_llm_response(response_buffer)
        
        if not conn.interrupt_requested and response_buffer.strip():
            conn.conversation_history.append({
                "user": text,
                "assistant": cleaned_response,
                "timestamp": time.time()
            })
            _logger.info(f"✅ Added to conversation_history")

            if len(conn.conversation_history) > 10:
                conn.conversation_history = conn.conversation_history[-10:]

        if tool_data:
            _logger.info("🧠 Tool detected: %s", tool_data.get('tool'))

            if tool_data.get("requires_confirmation"):
                conn.pending_action = tool_data
            else:
                _logger.info("⚡ Executing tool immediately...")
                tool_result = await execute_detected_tool(call_sid, tool_data)
                _logger.info(f"🦾 Tool result: {tool_result}")

        _logger.info("⏳ Waiting for TTS...")
        max_wait = 30.0
        wait_start = time.time()
        while not conn.tts_queue.empty() and (time.time() - wait_start) < max_wait:
            await asyncio.sleep(0.1)
        _logger.info("✅ TTS completed")

        t_end = time.time()
        _logger.info("✅ TOTAL TIME: %.1fms", (t_end - t_start) * 1000)

    except Exception as e:
        _logger.error(f"❌ ERROR: {e}")
    finally:
        conn.is_responding = False
        if conn.interrupt_requested:
            conn.interrupt_requested = False


# ================================
# REST API ENDPOINTS
# ================================

@app.post("/v1/convai/agents", tags=["Agent Management"])
async def create_agent(
    agent: AgentCreate, 
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Create a new agent"""
    try:
        agent_id = generate_agent_id()
        
        db_agent = Agent(
            agent_id=agent_id,
            name=agent.name,
            system_prompt=agent.system_prompt,
            first_message=agent.first_message,
            voice_provider=agent.voice_provider,
            voice_id=agent.voice_id,
            model_provider=agent.model_provider,
            model_name=agent.model_name,
            interrupt_enabled=agent.interrupt_enabled,
            silence_threshold_sec=agent.silence_threshold_sec
        )
        
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        
        _logger.info(f"✅ Created agent: {agent_id} - {agent.name}")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "name": agent.name,
            "created_at": db_agent.created_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        _logger.error(f"❌ Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/convai/agents/{agent_id}", tags=["Agent Management"])
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Get agent configuration"""
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "system_prompt": agent.system_prompt,
        "first_message": agent.first_message,
        "voice_provider": agent.voice_provider,
        "voice_id": agent.voice_id,
        "model_provider": agent.model_provider,
        "model_name": agent.model_name,
        "interrupt_enabled": agent.interrupt_enabled,
        "silence_threshold_sec": agent.silence_threshold_sec,
        "is_active": agent.is_active,
        "created_at": agent.created_at.isoformat(),
        "updated_at": agent.updated_at.isoformat()
    }


@app.get("/v1/convai/agents", tags=["Agent Management"])
async def list_agents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all agents"""
    agents = db.query(Agent).filter(Agent.is_active == True).offset(skip).limit(limit).all()
    
    return {
        "agents": [
            {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "voice_id": agent.voice_id,
                "model_name": agent.model_name,
                "created_at": agent.created_at.isoformat()
            }
            for agent in agents
        ],
        "total": len(agents)
    }


@app.patch("/v1/convai/agents/{agent_id}", tags=["Agent Management"])
async def update_agent(
    agent_id: str,
    updates: AgentUpdate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Update agent configuration"""
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)
    
    agent.updated_at = dt.utcnow()
    db.commit()
    db.refresh(agent)
    
    _logger.info(f"✅ Updated agent: {agent_id}")
    
    return {
        "success": True,
        "agent_id": agent_id,
        "updated_fields": list(update_data.keys())
    }


@app.delete("/v1/convai/agents/{agent_id}", tags=["Agent Management"])
async def delete_agent(
    agent_id: str, 
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Delete (deactivate) agent"""
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.is_active = False
    db.commit()
    
    _logger.info(f"✅ Deleted agent: {agent_id}")
    
    return {"success": True, "message": "Agent deleted"}


@app.post("/v1/convai/twilio/outbound-call", tags=["Call Operations"])
async def initiate_outbound_call(
    request: OutboundCallRequest,
    db: Session = Depends(get_db)
):
    """Initiate outbound call"""
    try:
        agent = db.query(Agent).filter(
            Agent.agent_id == request.agent_id,
            Agent.is_active == True
        ).first()
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {request.agent_id}")
        
        client_data = request.conversation_initiation_client_data or {}
        dynamic_variables = client_data.get("dynamic_variables", {})
        config_override = client_data.get("conversation_config_override", {})
        
        custom_voice_id = config_override.get("tts", {}).get("voice_id")
        custom_model = config_override.get("agent", {}).get("prompt", {}).get("llm")
        custom_first_message = request.first_message or config_override.get("agent", {}).get("first_message")

        _logger.info(f"📞 Initiating call to {request.to_number}")
        
        phone_number_to_use = TWILIO_PHONE_NUMBER
        
        if request.agent_phone_number_id:
            phone_record = db.query(PhoneNumber).filter(
                PhoneNumber.id == request.agent_phone_number_id,
                PhoneNumber.is_active == True
            ).first()
            if phone_record:
                phone_number_to_use = phone_record.phone_number
        
        webhook_url = f"{PUBLIC_URL.rstrip('/')}/voice/outbound"
        status_callback_url = f"{PUBLIC_URL.rstrip('/')}/voice/status"
        
        call = twilio_client.calls.create(
            to=request.to_number,
            from_=phone_number_to_use,
            url=webhook_url,
            method="POST",
            status_callback=status_callback_url,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST"
        )
        
        call_sid = call.sid
        conversation_id = call_sid
        
        pending_call_data[call_sid] = {
            "agent_id": request.agent_id,
            "dynamic_variables": dynamic_variables,
            "custom_voice_id": custom_voice_id,
            "custom_model": custom_model,
            "custom_first_message": custom_first_message,
            "to_number": request.to_number,
            "enable_recording": request.enable_recording,
            "direction": "outbound"
        }
        
        conversation = Conversation(
            conversation_id=conversation_id,
            agent_id=request.agent_id,
            phone_number=request.to_number,
            status="initiated",
            dynamic_variables=dynamic_variables,
            call_metadata={"overrides": config_override, "custom_first_message": custom_first_message}
        )
        db.add(conversation)
        db.commit()
        
        _logger.info(f"✅ Call initiated: {conversation_id}")
        
        return {
            "conversation_id": conversation_id,
            "agent_id": request.agent_id,
            "status": "initiated",
            "phone_number": request.to_number,
            "first_message": custom_first_message or agent.first_message  
        }
        
    except HTTPException:
        raise
    except Exception as e:
        _logger.error(f"❌ Call initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/convai/conversations/{conversation_id}", tags=["Conversations"])
async def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Get conversation details"""
    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        "conversation_id": conversation.conversation_id,
        "agent_id": conversation.agent_id,
        "status": conversation.status,
        "transcript": conversation.transcript,
        "started_at": conversation.started_at.isoformat() if conversation.started_at else None,
        "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "metadata": {
            "call_duration_secs": conversation.duration_secs,
            "termination_reason": conversation.ended_reason,
            "phone_number": conversation.phone_number
        },
        "dynamic_variables": conversation.dynamic_variables,
        "call_metadata": conversation.call_metadata
    }


@app.get("/v1/convai/conversations", tags=["Conversations"])
async def list_conversations(
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    direction: Optional[str] = None,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """List conversations with optional filtering"""
    query = db.query(Conversation)
    
    if agent_id:
        query = query.filter(Conversation.agent_id == agent_id)
    
    if status:
        query = query.filter(Conversation.status == status)
    
    if direction:
        # Direction is stored in call_metadata
        pass  # Filter by direction if stored in metadata
    
    conversations = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "conversations": [
            {
                "conversation_id": c.conversation_id,
                "agent_id": c.agent_id,
                "status": c.status,
                "transcript": c.transcript[:100] + "..." if c.transcript and len(c.transcript) > 100 else c.transcript,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "phone_number": c.phone_number
            }
            for c in conversations
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@app.post("/voice/outbound")
@app.get("/voice/outbound")
async def voice_outbound(request: Request):
    """Twilio voice webhook for outbound calls"""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    
    call_data = pending_call_data.get(call_sid, {})
    enable_recording = call_data.get("enable_recording", False)
    
    response = VoiceResponse()
    
    if enable_recording:
        response.record(
            recording_status_callback=f"{PUBLIC_URL}/recording-callback",
            recording_status_callback_method="POST",
            recording_status_callback_event="completed"
        )
        _logger.info(f"🎙️ Recording enabled for call: {call_sid}")
    
    response.say(" ")
    response.pause(length=0)

    connect = Connect()
    from utils import public_ws_host
    connect.stream(url=f"wss://{public_ws_host()}/media-stream")
    response.append(connect)

    return Response(content=str(response), media_type="application/xml")


@app.websocket("/media-stream")
async def media_ws(websocket: WebSocket):
    """WebSocket for media streaming"""
    try:
        await websocket.accept()
    except RuntimeError as e:
        return

    async def send_heartbeat():
        while True:
            try:
                await asyncio.sleep(5)
                if websocket.client_state.name == "CONNECTED":
                    await websocket.send_json({"event": "heartbeat"})
            except Exception as e:
                break

    heartbeat_task = asyncio.create_task(send_heartbeat())
    current_call_sid: Optional[str] = None
    processing_task: Optional[asyncio.Task] = None

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except RuntimeError as e:
                break
            except Exception as e:
                break

            event = data.get("event")

            if event == "start":
                start_info = data.get("start", {})
                current_call_sid = start_info.get("callSid")
                stream_sid = start_info.get("streamSid")

                if not current_call_sid:
                    break
                
                _logger.info(f"🔗 WebSocket connected for call_sid: {current_call_sid}")
                await manager.connect(current_call_sid, websocket)
                conn = manager.get(current_call_sid)
                if conn:
                    conn.stream_sid = stream_sid
                    conn.stream_ready = True
                    conn.conversation_id = current_call_sid

                    call_data = pending_call_data.get(current_call_sid, {})
                    agent_id = call_data.get("agent_id")
                    
                    conn.dynamic_variables = call_data.get("dynamic_variables", {})
                    conn.custom_voice_id = call_data.get("custom_voice_id")
                    conn.custom_model = call_data.get("custom_model")
                    conn.custom_first_message = call_data.get("custom_first_message")
                    
                    db = SessionLocal()
                    try:
                        if agent_id:
                            agent = db.query(Agent).filter(
                                Agent.agent_id == agent_id
                            ).first()
                            
                            if agent:
                                conn.agent_id = agent_id
                                conn.agent_config = {
                                    "system_prompt": agent.system_prompt,
                                    "first_message": agent.first_message,
                                    "voice_id": agent.voice_id,
                                    "model_name": agent.model_name,
                                    "silence_threshold_sec": agent.silence_threshold_sec,
                                    "interrupt_enabled": agent.interrupt_enabled
                                }
                                
                                _logger.info(f"✅ Loaded agent: {agent_id}")

                                if call_data.get("custom_first_message"):
                                    conn.agent_config["first_message"] = call_data["custom_first_message"]
                        
                        conversation = db.query(Conversation).filter(
                            Conversation.conversation_id == current_call_sid
                        ).first()
                        
                        if conversation:
                            conversation.status = "in-progress"
                            conversation.started_at = dt.utcnow()
                            db.commit()
                            _logger.info(f"✅ Conversation status updated to 'in-progress'")
                    finally:
                        db.close()

                    # Initialize resampler
                    dummy_state = None
                    try:
                        _, dummy_state = audioop.ratecv(
                            b'\x00' * 3200, 2, 1, 16000, 8000, dummy_state
                        )
                        conn.resampler_state = dummy_state
                        conn.resampler_initialized = True
                        _logger.info("✅ Resampler pre-initialized successfully")
                    except Exception as e:
                        _logger.warning("⚠️ Resampler pre-init failed (non-critical): %s", e)
                        # This is not critical - audio will still work, just with less optimization

                    await setup_streaming_stt(current_call_sid)
                    conn.tts_task = asyncio.create_task(stream_tts_worker(current_call_sid))
                    _logger.info(f"✅ Voice pipeline started")

                await asyncio.sleep(0.1)
                
                conn = manager.get(current_call_sid)
                greeting = None
                
                if conn and conn.agent_config and conn.agent_config.get("first_message"):
                    greeting = conn.agent_config["first_message"]
                    if conn.dynamic_variables:
                        for key, value in conn.dynamic_variables.items():
                            greeting = greeting.replace(f"{{{{{key}}}}}", str(value))
                else:
                    greeting = "Hello! How can I help you today?"

                await speak_text_streaming(current_call_sid, greeting)
                
                if conn and greeting:
                    conn.conversation_history.append({
                        "user": "[Call Started]",
                        "assistant": greeting,
                        "timestamp": time.time()
                    })

            elif event == "media":
                if not current_call_sid:
                    continue

                media_data = data.get("media", {})
                payload_b64 = media_data.get("payload")

                if payload_b64:
                    _logger.info(f"📞 Received media chunk ({len(payload_b64)} bytes)")

                    try:
                        import base64
                        chunk = base64.b64decode(payload_b64)
                        conn = manager.get(current_call_sid)

                        if not conn:
                            _logger.warning("Connection not found for call_sid: %s", current_call_sid)
                            continue

                        if conn.deepgram_live:
                            try:
                                conn.deepgram_live.send(chunk)
                            except Exception as e:
                                _logger.error(f"Error sending audio to Deepgram: {e}")

                        from voice_pipeline import calculate_audio_energy, update_baseline, handle_interrupt
                        energy = calculate_audio_energy(chunk)
                        update_baseline(conn, energy)

                        now = time.time()

                        from utils import INTERRUPT_BASELINE_FACTOR, INTERRUPT_MIN_ENERGY, INTERRUPT_ENABLED, INTERRUPT_MIN_SPEECH_MS, INTERRUPT_DEBOUNCE_MS, INTERRUPT_REQUIRE_TEXT
                        energy_threshold = max(
                            conn.baseline_energy * INTERRUPT_BASELINE_FACTOR,
                            INTERRUPT_MIN_ENERGY
                        )

                        # Smart interrupt detection - responsive to user speaking while agent is speaking
                        if (INTERRUPT_ENABLED and conn.agent_config and 
                            conn.agent_config.get("interrupt_enabled", True) and 
                            conn.currently_speaking and not conn.interrupt_requested):
                            
                            # Check if user speech energy exceeds threshold
                            if energy > energy_threshold:
                                conn.speech_energy_buffer.append(energy)
                                
                                # More responsive: require fewer samples for faster detection
                                if len(conn.speech_energy_buffer) >= 2:
                                    high_energy_count = sum(1 for e in conn.speech_energy_buffer if e > energy_threshold)
                                    if high_energy_count >= 2:
                                        # Mark speech start time for minimum duration check
                                        if conn.speech_start_time is None:
                                            conn.speech_start_time = now
                                        
                                        # Check if minimum speech duration met
                                        speech_duration_ms = (now - conn.speech_start_time) * 1000
                                        if speech_duration_ms >= INTERRUPT_MIN_SPEECH_MS:
                                            # Check debounce to avoid multiple interrupts
                                            time_since_last_interrupt = (now - conn.last_interrupt_time) * 1000
                                            if time_since_last_interrupt >= INTERRUPT_DEBOUNCE_MS:
                                                # Optional: Check if we have text from user
                                                has_text = bool(conn.stt_transcript_buffer.strip()) if INTERRUPT_REQUIRE_TEXT else True
                                                
                                                if has_text:
                                                    _logger.info(f"🎯 INTERRUPT TRIGGERED: energy={energy:.0f} threshold={energy_threshold:.0f} duration={speech_duration_ms:.0f}ms buffer_samples={len(conn.speech_energy_buffer)}")
                                                    conn.last_interrupt_time = now
                                                    await handle_interrupt(current_call_sid)
                            else:
                                # Reset speech detection when energy drops
                                if conn.speech_start_time is not None:
                                    conn.speech_energy_buffer.clear()
                                    conn.speech_start_time = None

                        if not conn.currently_speaking and not conn.interrupt_requested:
                            if processing_task is None or processing_task.done():
                                processing_task = asyncio.create_task(
                                    process_streaming_transcript(current_call_sid)
                                )

                    except Exception as e:
                        _logger.error(f"Error processing media: {e}")

            elif event == "stop":
                break

    except WebSocketDisconnect:
        _logger.info(f"📞 WebSocket disconnected for call: {current_call_sid}")
    except Exception as e:
        _logger.error(f"❌ WebSocket error: {e}")
    finally:
        try:
            if processing_task and not processing_task.done():
                processing_task.cancel()
        except:
            pass

        try:
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
        except:
            pass

        if current_call_sid:
            conn = manager.get(current_call_sid)
            if conn:
                await save_conversation_transcript(current_call_sid, conn)
            
            try:
                await manager.disconnect(current_call_sid)
            except:
                pass

        try:
            await websocket.close()
        except:
            pass


@app.api_route("/", methods=["GET", "POST"])
async def index_page():
    return {
        "status": "ok",
        "message": "AI Voice Call System - ElevenLabs Compatible",
        "device": str(DEVICE),
        "features": [
            "✅ Agent management with custom configurations",
            "✅ ElevenLabs-compatible API endpoints",
            "✅ GPU-accelerated RAG and embeddings",
            "✅ Streaming STT/TTS pipeline",
            "✅ Smart voice interruption detection",
            "✅ Conversation history and transcripts",
            f"✅ {SILENCE_THRESHOLD_SEC}s silence detection"
        ]
    }


@app.get("/gpu-status")
async def gpu_status():
    """GPU status endpoint"""
    status = {
        "device": str(DEVICE),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
    }

    if torch.cuda.is_available():
        try:
            import torch as torch_module
            status.update({
                "gpu_name": torch_module.cuda.get_device_name(0),
                "gpu_count": torch_module.cuda.device_count(),
                "cuda_version": torch_module.version.cuda,
            })
        except Exception as e:
            status["gpu_error"] = str(e)

    return status


# ================================
# WEBHOOKS API
# ================================

@app.post("/v1/convai/webhooks", tags=["Webhooks"])
async def create_webhook(
    webhook_data: WebhookCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Create a webhook"""
    # Validate webhook URL
    if not webhook_data.webhook_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid webhook URL")
    
    # Validate events
    if webhook_data.events:
        for event in webhook_data.events:
            if event not in WEBHOOK_EVENTS:
                raise HTTPException(status_code=400, detail=f"Invalid event: {event}")
    
    # Verify agent exists if specified
    if webhook_data.agent_id:
        agent = db.query(Agent).filter(Agent.agent_id == webhook_data.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
    
    webhook = WebhookConfig(
        webhook_url=webhook_data.webhook_url,
        events=webhook_data.events or WEBHOOK_EVENTS,
        agent_id=webhook_data.agent_id
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    
    _logger.info(f"✅ Created webhook: {webhook.id}")
    
    return {
        "webhook_id": webhook.id,
        "webhook_url": webhook.webhook_url,
        "events": webhook.events,
        "agent_id": webhook.agent_id,
        "is_active": webhook.is_active
    }


@app.get("/v1/convai/webhooks", tags=["Webhooks"])
async def list_webhooks(
    agent_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List webhooks"""
    query = db.query(WebhookConfig).filter(WebhookConfig.is_active == True)
    
    if agent_id:
        query = query.filter(
            (WebhookConfig.agent_id == agent_id) | (WebhookConfig.agent_id == None)
        )
    
    webhooks = query.all()
    
    return {
        "webhooks": [
            {
                "webhook_id": w.id,
                "webhook_url": w.webhook_url,
                "events": w.events,
                "agent_id": w.agent_id,
                "created_at": w.created_at.isoformat()
            }
            for w in webhooks
        ],
        "total": len(webhooks)
    }


@app.delete("/v1/convai/webhooks/{webhook_id}", tags=["Webhooks"])
async def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Delete a webhook"""
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    webhook.is_active = False
    db.commit()
    
    return {"success": True, "message": "Webhook deleted"}


# ================================
# PHONE NUMBERS API
# ================================

@app.post("/v1/convai/phone-numbers", tags=["Phone Numbers"])
async def register_phone_number(
    phone_number: str,
    agent_id: Optional[str] = None,
    label: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Register a phone number"""
    import uuid
    
    # Check if phone number already exists
    existing = db.query(PhoneNumber).filter(PhoneNumber.phone_number == phone_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    # Verify agent exists if specified
    if agent_id:
        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
    
    phone = PhoneNumber(
        id=f"phone_{uuid.uuid4().hex[:16]}",
        phone_number=phone_number,
        agent_id=agent_id,
        label=label
    )
    db.add(phone)
    db.commit()
    
    _logger.info(f"✅ Registered phone number: {phone_number}")
    
    return {
        "phone_id": phone.id,
        "phone_number": phone_number,
        "agent_id": agent_id,
        "label": label,
        "is_active": True
    }


@app.get("/v1/convai/phone-numbers", tags=["Phone Numbers"])
async def list_phone_numbers(
    db: Session = Depends(get_db)
):
    """List all active phone numbers"""
    phones = db.query(PhoneNumber).filter(PhoneNumber.is_active == True).all()
    
    return {
        "phone_numbers": [
            {
                "phone_id": p.id,
                "phone_number": p.phone_number,
                "agent_id": p.agent_id,
                "label": p.label,
                "created_at": p.created_at.isoformat()
            }
            for p in phones
        ],
        "total": len(phones)
    }


@app.patch("/v1/convai/phone-numbers/{phone_id}", tags=["Phone Numbers"])
async def update_phone_number(
    phone_id: str,
    agent_id: Optional[str] = None,
    label: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Update phone number configuration"""
    phone = db.query(PhoneNumber).filter(PhoneNumber.id == phone_id).first()
    
    if not phone:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    if agent_id is not None:
        if agent_id:  # Not empty string
            agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
        phone.agent_id = agent_id if agent_id else None
    
    if label is not None:
        phone.label = label
    
    db.commit()
    
    return {"success": True, "phone_number_id": phone_id}


@app.delete("/v1/convai/phone-numbers/{phone_id}", tags=["Phone Numbers"])
async def delete_phone_number(
    phone_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Delete a phone number"""
    phone = db.query(PhoneNumber).filter(PhoneNumber.id == phone_id).first()
    
    if not phone:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    phone.is_active = False
    db.commit()
    
    return {"success": True, "message": "Phone number deleted"}


# ================================
# KNOWLEDGE BASE PER AGENT API
# ================================

@app.post("/v1/convai/agents/{agent_id}/knowledge-base", tags=["Knowledge Base"])
async def add_knowledge(
    agent_id: str,
    content: str,
    metadata: Optional[Dict] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Add knowledge to agent's knowledge base"""
    import uuid
    import torch
    
    # Verify agent exists
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    doc_id = f"doc_{uuid.uuid4().hex[:16]}"
    
    # Add to database
    kb = KnowledgeBase(
        agent_id=agent_id,
        document_id=doc_id,
        content=content,
        kb_metadata=metadata
    )
    db.add(kb)
    db.commit()
    
    # Add to ChromaDB with agent prefix
    chunks = _chunk_text(content, CHUNK_SIZE, overlap=50)
    
    with torch.no_grad():
        embeddings = embedder.encode(
            chunks, 
            device=DEVICE, 
            convert_to_numpy=True,
            normalize_embeddings=True
        ).tolist()
    
    # Use agent-specific collection
    agent_collection = chroma_client.get_or_create_collection(f"agent_{agent_id}")
    
    agent_collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        metadatas=[{"agent_id": agent_id, "doc_id": doc_id} for _ in chunks]
    )
    
    _logger.info(f"✅ Added knowledge to agent {agent_id}: {len(chunks)} chunks")
    
    return {
        "document_id": doc_id,
        "agent_id": agent_id,
        "chunks_created": len(chunks)
    }


@app.get("/v1/convai/agents/{agent_id}/knowledge-base", tags=["Knowledge Base"])
async def list_agent_knowledge(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """List knowledge base documents for an agent"""
    # Verify agent exists
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    documents = db.query(KnowledgeBase).filter(
        KnowledgeBase.agent_id == agent_id
    ).all()
    
    return {
        "agent_id": agent_id,
        "documents": [
            {
                "document_id": doc.document_id,
                "content_preview": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                "metadata": doc.kb_metadata,
                "created_at": doc.created_at.isoformat()
            }
            for doc in documents
        ],
        "total": len(documents)
    }


@app.delete("/v1/convai/agents/{agent_id}/knowledge-base/{document_id}", tags=["Knowledge Base"])
async def delete_agent_knowledge(
    agent_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Delete a knowledge base document"""
    doc = db.query(KnowledgeBase).filter(
        KnowledgeBase.agent_id == agent_id,
        KnowledgeBase.document_id == document_id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Remove from database
    db.delete(doc)
    db.commit()
    
    # Remove from ChromaDB
    try:
        agent_collection = chroma_client.get_or_create_collection(f"agent_{agent_id}")
        # Get all IDs that start with this document_id
        results = agent_collection.get(where={"doc_id": document_id})
        if results and results.get("ids"):
            agent_collection.delete(ids=results["ids"])
    except Exception as e:
        _logger.warning(f"⚠️ Could not delete from ChromaDB: {e}")
    
    return {"success": True, "message": "Document deleted"}


# ================================
# CUSTOM TOOLS PER AGENT API
# ================================

@app.post("/v1/convai/agents/{agent_id}/tools", tags=["Tools"])
async def add_agent_tool(
    agent_id: str,
    tool_data: ToolCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Add custom tool to agent
    
    Example request body:
    ```json
    {
        "tool_name": "weather",
        "description": "Get weather information for a location",
        "webhook_url": "https://your-api.com/weather",
        "parameters": {
            "location": {
                "type": "string",
                "required": true,
                "description": "City name"
            }
        }
    }
    ```
    """
    # Verify agent exists
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    tool = AgentTool(
        agent_id=agent_id,
        tool_name=tool_data.tool_name,
        description=tool_data.description,
        webhook_url=tool_data.webhook_url,
        parameters=tool_data.parameters or {}
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    
    _logger.info(f"✅ Added tool '{tool_data.tool_name}' to agent {agent_id}")
    
    return {
        "success": True,
        "tool_id": tool.id,
        "tool_name": tool_data.tool_name,
        "agent_id": agent_id,
        "webhook_url": tool_data.webhook_url
    }


@app.get("/v1/convai/agents/{agent_id}/tools", tags=["Tools"])
async def list_agent_tools(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """List custom tools for an agent"""
    tools = db.query(AgentTool).filter(
        AgentTool.agent_id == agent_id,
        AgentTool.is_active == True
    ).all()
    
    return {
        "agent_id": agent_id,
        "tools": [
            {
                "id": t.id,
                "tool_name": t.tool_name,
                "description": t.description,
                "webhook_url": t.webhook_url,
                "parameters": t.parameters,
                "created_at": t.created_at.isoformat()
            }
            for t in tools
        ]
    }


@app.delete("/v1/convai/agents/{agent_id}/tools/{tool_id}", tags=["Tools"])
async def delete_agent_tool(
    agent_id: str,
    tool_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Delete a custom tool"""
    tool = db.query(AgentTool).filter(
        AgentTool.id == tool_id,
        AgentTool.agent_id == agent_id
    ).first()
    
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    tool.is_active = False
    db.commit()
    
    return {"success": True, "message": "Tool deleted"}


# ================================
# CALL RECORDING API
# ================================

@app.post("/recording-callback", tags=["Recording"])
async def recording_callback(request: Request):
    """Handle recording completion from Twilio"""
    form = await request.form()
    call_sid = form.get("CallSid")
    recording_url = form.get("RecordingUrl")
    recording_sid = form.get("RecordingSid")
    recording_duration = form.get("RecordingDuration")
    
    _logger.info(f"🎙️ Recording completed: {call_sid} - {recording_url}")
    
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(
            Conversation.conversation_id == call_sid
        ).first()
        
        if conversation:
            conversation.recording_url = recording_url
            # Store additional recording metadata
            if conversation.call_metadata:
                conversation.call_metadata["recording_sid"] = recording_sid
                conversation.call_metadata["recording_duration"] = recording_duration
            else:
                conversation.call_metadata = {
                    "recording_sid": recording_sid,
                    "recording_duration": recording_duration
                }
            db.commit()
            _logger.info(f"✅ Recording URL saved for {call_sid}")
    except Exception as e:
        _logger.error(f"❌ Failed to save recording URL: {e}")
    finally:
        db.close()
    
    return PlainTextResponse("OK")


@app.get("/v1/convai/conversations/{conversation_id}/recording", tags=["Recording"])
async def get_recording(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """Get recording URL for a conversation"""
    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if not conversation.recording_url:
        raise HTTPException(status_code=404, detail="No recording available")
    
    return {
        "conversation_id": conversation_id,
        "recording_url": conversation.recording_url,
        "recording_metadata": conversation.call_metadata
    }


# ================================
# SIGNED URL FOR WIDGETS (JWT)
# ================================

@app.get("/v1/convai/conversation/get-signed-url", tags=["Widgets"])
async def get_signed_url(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Generate signed URL for embedding widget"""
    import jwt
    from datetime import timedelta
    
    # Verify agent exists
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    payload = {
        "agent_id": agent_id,
        "exp": dt.utcnow() + timedelta(hours=24),
        "iat": dt.utcnow()
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    
    return {
        "signed_url": f"{PUBLIC_URL}/widget?token={token}",
        "expires_in": 86400,  # 24 hours in seconds
        "agent_id": agent_id
    }


@app.get("/widget", tags=["Widgets"])
async def widget_page(
    token: str,
    db: Session = Depends(get_db)
):
    """Widget endpoint that validates JWT token"""
    import jwt
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        agent_id = payload.get("agent_id")
        
        # Verify agent exists
        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        return {
            "valid": True,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "message": "Widget authentication successful"
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/test-end-call")
async def test_end_call(request: Request):
    """Test end call tool"""
    try:
        data = await request.json()
        call_sid = data.get("call_sid", "test_call_123")
        reason = data.get("reason", "test")

        result = await end_call_tool(call_sid, reason)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/test-transfer")
async def test_transfer(request: Request):
    """Test transfer tool"""
    try:
        data = await request.json()
        call_sid = data.get("call_sid", "test_call_123")
        department = data.get("department", "sales")

        result = await transfer_call_tool(call_sid, department)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/tools/status")
async def tools_status():
    """Check tool configuration"""
    return {
        "tools_available": ["end_call", "transfer_call"],
        "departments": {
            "sales": os.getenv("SALES_PHONE_NUMBER", "NOT_SET"),
            "support": os.getenv("SUPPORT_PHONE_NUMBER", "NOT_SET"),
            "technical": os.getenv("TECH_PHONE_NUMBER", "NOT_SET"),
        },
        "confirmation_system": "enabled",
        "transfer_requires_confirmation": True,
        "end_call_requires_confirmation": False,
        "silence_threshold_sec": SILENCE_THRESHOLD_SEC,
        "utterance_end_ms": UTTERANCE_END_MS
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
