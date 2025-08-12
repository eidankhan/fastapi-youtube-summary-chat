# service.py
import os
import json
import uuid
import logging
import asyncio
from typing import List, Dict, Any, Optional
from .utils import (
    get_history,
    save_history,
    summarize_and_store,
    MAX_HISTORY_MESSAGES,
    normalize_messages,
    extract_json_from_text,
)
from openai import OpenAI  # Groq-compatible OpenAI client
import redis.asyncio as aioredis
from . import config

# Add at the top with other imports
from tiktoken import get_encoding

TOKEN_LIMIT = 5500  # Keep below Groq's 6k TPM limit for llama3-70b-8192
SUMMARY_TRIGGER_TOKENS = 1500  # If context is this long, summarise it
enc = get_encoding("cl100k_base")  # Approx tokenizer for LLaMA-like models

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Redis client
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)

# Groq/OpenAI client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")

if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not set — service will fail when calling model")

client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)


def make_session_key(session_id: str) -> str:
    return f"{config.REDIS_PREFIX}{session_id}"


async def create_session_if_missing(session_id: Optional[str] = None) -> str:
    """
    Ensure a session exists in Redis with metadata and TTL.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    key = make_session_key(session_id)
    exists = await redis_client.exists(key)

    if not exists:
        await redis_client.hset(
            f"{key}:meta", mapping={"created_at": str(asyncio.get_event_loop().time())}
        )
        await redis_client.expire(f"{key}:meta", config.SESSION_TTL_SECONDS)
        await redis_client.rpush(key, json.dumps({"role": "system", "content": ""}))
        await redis_client.expire(key, config.SESSION_TTL_SECONDS)
        await redis_client.lpop(key)
    else:
        await redis_client.expire(key, config.SESSION_TTL_SECONDS)
        await redis_client.expire(f"{key}:meta", config.SESSION_TTL_SECONDS)

    return session_id


async def append_message(session_id: str, role: str, content: str) -> None:
    """
    Append message to history and enforce history size + summarization.
    """
    key = make_session_key(session_id)
    await redis_client.rpush(key, json.dumps({"role": role, "content": content}))
    await redis_client.expire(key, config.SESSION_TTL_SECONDS)
    await redis_client.expire(f"{key}:meta", config.SESSION_TTL_SECONDS)

    # Trim if exceeding max messages
    length = await redis_client.llen(key)
    if length > MAX_HISTORY_MESSAGES:
        old_count = length - MAX_HISTORY_MESSAGES
        old_messages = await redis_client.lrange(key, 0, old_count - 1)
        recent_messages = await redis_client.lrange(key, old_count, -1)

        try:
            old = [json.loads(m) for m in old_messages]
            recent = [json.loads(m) for m in recent_messages]
        except Exception:
            old = [{"role": "system", "content": m} for m in old_messages]
            recent = [{"role": "system", "content": m} for m in recent_messages]

        await summarize_and_store(session_id, old, recent)


async def get_history_async(session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get conversation history from Redis.
    """
    key = make_session_key(session_id)
    if limit:
        str_list = await redis_client.lrange(key, max(0, -limit), -1)
    else:
        str_list = await redis_client.lrange(key, 0, -1)

    history = []
    for s in str_list:
        try:
            history.append(json.loads(s))
        except Exception:
            history.append({"role": "system", "content": s})
    return history


async def call_model(messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
    """
    Call Groq API in a thread to avoid blocking.
    """
    def sync_call():
        return client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
        )

    return await asyncio.to_thread(sync_call)


async def ask(
    session_id: Optional[str],
    action: str,
    context: str,
    question: str,
    history_override: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Main conversation entrypoint.
    """
    session_id = await create_session_if_missing(session_id)
    history = history_override or await get_history_async(session_id, limit=MAX_HISTORY_MESSAGES)

    messages = normalize_messages(history)
    # Trim early in case stored history is large
    messages = await trim_for_token_limit(messages)

    system_prompt = (
        "You are a helpful assistant. Use the provided context when relevant.\n\n"
        "Respond ONLY in valid JSON with keys:\n"
        "  'answer' (string) — the main reply\n"
        "  'suggestions' (array of strings) — exactly 3 short follow-up ideas.\n"
    )
    messages.append({"role": "system", "content": system_prompt})

    # Summarise context if it's huge
    context = await safe_context(context)

    if action == "qa":
        user_content = f"Context:\n{context}\n\nQuestion:\n{question}"
    elif action == "summary":
        user_content = f"Summarize the following content:\n\n{context}"
    elif action == "expand":
        user_content = f"Expand and explain the following content:\n\n{context}"
    else:
        user_content = question or context

    messages.append({"role": "user", "content": user_content})

    logger.info("Calling model for session %s with %d messages", session_id, len(messages))

    # Final safety trim for token budget
    messages = await trim_for_token_limit(messages)

    completion = await call_model(messages)

    try:
        assistant_text = completion.choices[0].message.content
    except Exception as e:
        logger.error("Unexpected model response: %s", e)
        raise RuntimeError("Model returned unexpected structure") from e

    logger.debug("Raw model reply: %s", assistant_text[:1000])

    try:
        parsed, _ = extract_json_from_text(assistant_text)
        answer = parsed.get("answer", "").strip()
        suggestions = [str(s).strip() for s in parsed.get("suggestions", [])][:3]
    except Exception as e:
        logger.warning("Failed to parse JSON from model output: %s", e)
        answer = assistant_text.strip()
        suggestions = []

    await append_message(session_id, "user", user_content)
    await append_message(session_id, "assistant", answer)

    return {
        "action": action,
        "response": answer,
        "suggestions": suggestions,
        "session_id": session_id,
    }

async def safe_context(context: str) -> str:
    """Summarise context if it's too long."""
    token_count = len(enc.encode(context))
    if token_count > SUMMARY_TRIGGER_TOKENS:
        logger.info("Context too long (%d tokens), summarising before sending", token_count)
        summary = await summarize_and_store(None, [{"role": "system", "content": context}], [])
        return summary if summary else context
    return context

async def trim_for_token_limit(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Ensure total messages fit in TOKEN_LIMIT."""
    while True:
        total_tokens = sum(len(enc.encode(m.get("content", ""))) for m in messages)
        if total_tokens <= TOKEN_LIMIT:
            break
        # Remove earliest non-system message
        for i, msg in enumerate(messages):
            if msg.get("role") != "system":
                messages.pop(i)
                break
    return messages