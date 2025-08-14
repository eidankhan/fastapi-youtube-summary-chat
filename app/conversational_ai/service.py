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
from . import config
import redis.asyncio as aioredis
from tiktoken import get_encoding, encoding_for_model

enc = get_encoding("cl100k_base")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Redis
redis_client = aioredis.Redis.from_url(config.REDIS_URL, decode_responses=True)

# Choose AI Provider
if config.PROVIDER == "groq":
    from openai import OpenAI as GroqClient
    ai_client = GroqClient(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)
    MODEL_NAME = config.GROQ_MODEL
elif config.PROVIDER == "openai":
    import openai
    openai.api_key = config.OPENAI_API_KEY
    ai_client = openai
    MODEL_NAME = config.OPENAI_MODEL
else:
    raise ValueError(f"Unsupported AI_PROVIDER: {config.PROVIDER}")


def make_session_key(session_id: str) -> str:
    return f"{config.REDIS_PREFIX}{session_id}"


async def create_session_if_missing(session_id: Optional[str] = None) -> str:
    if not session_id:
        session_id = str(uuid.uuid4())

    key = make_session_key(session_id)
    exists = await redis_client.exists(key)

    if not exists:
        await redis_client.hset(f"{key}:meta", mapping={"created_at": str(asyncio.get_event_loop().time())})
        await redis_client.expire(f"{key}:meta", config.SESSION_TTL_SECONDS)
        await redis_client.rpush(key, json.dumps({"role": "system", "content": ""}))
        await redis_client.expire(key, config.SESSION_TTL_SECONDS)
        await redis_client.lpop(key)
    else:
        await redis_client.expire(key, config.SESSION_TTL_SECONDS)
        await redis_client.expire(f"{key}:meta", config.SESSION_TTL_SECONDS)

    return session_id


async def append_message(session_id: str, role: str, content: str) -> None:
    key = make_session_key(session_id)
    await redis_client.rpush(key, json.dumps({"role": role, "content": content}))
    await redis_client.expire(key, config.SESSION_TTL_SECONDS)
    await redis_client.expire(f"{key}:meta", config.SESSION_TTL_SECONDS)

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
    """Calls either Groq or OpenAI depending on PROVIDER"""
    def sync_call():
        if config.PROVIDER == "groq":
            return ai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=temperature,
            )
        elif config.PROVIDER == "openai":
            return ai_client.chat.completions.create(
                model=MODEL_NAME,
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
    # Ensure session exists
    session_id = await create_session_if_missing(session_id)

    # Get previous history or use override
    history = history_override or await get_history_async(
        session_id, limit=MAX_HISTORY_MESSAGES
    )

    # Normalize history format
    messages = normalize_messages(history)

    # Prepare system prompt
    system_prompt = (
        "You are a helpful assistant. Use the provided context when relevant.\n\n"
        "Respond ONLY in valid JSON with keys:\n"
        "  'answer' (string)\n"
        "  'suggestions' (array of exactly 3 strings)\n"
    )
    messages.append({"role": "system", "content": system_prompt})

    # Prepare safe context
    context = await safe_context(context)

    # Decide on user content based on action
    if action == "qa":
        user_content = f"Context:\n{context}\n\nQuestion:\n{question}"
    elif action == "summary":
        user_content = f"Summarize the following content:\n\n{context}"
    elif action == "expand":
        user_content = f"Expand and explain the following content:\n\n{context}"
    else:
        user_content = question or context

    # Append user message
    messages.append({"role": "user", "content": user_content})

    # Final trim before API call
    messages = trim_for_token_limit(messages, config.PROVIDER)

    # Call AI model
    completion = await call_model(messages)

    # Extract assistant response safely
    try:
        assistant_text = completion.choices[0].message.content
    except Exception as e:
        logger.error("Unexpected model response: %s", e)
        raise RuntimeError("Model returned unexpected structure") from e

    # Try parsing JSON response
    try:
        parsed, _ = extract_json_from_text(assistant_text)
        answer = parsed.get("answer", "").strip()
        suggestions = [str(s).strip() for s in parsed.get("suggestions", [])][:3]
    except Exception:
        # If JSON parsing fails, return raw text
        answer = assistant_text.strip()
        suggestions = []

    # Save conversation
    await append_message(session_id, "user", user_content)
    await append_message(session_id, "assistant", answer)

    return {
        "action": action,
        "response": answer,
        "suggestions": suggestions,
        "session_id": session_id,
    }

async def safe_context(context: str) -> str:
    token_count = len(enc.encode(context))
    trigger_limit = config.SUMMARY_TRIGGER[config.PROVIDER]

    if token_count > trigger_limit:
        logger.info("Context too long (%d tokens), summarising", token_count)
        summary = await summarize_and_store(None, [{"role": "system", "content": context}], [])
        return summary if summary else context

    return context

def trim_for_token_limit(messages: List[Dict[str, str]], provider: str) -> List[Dict[str, str]]:
    """Trim messages to fit within provider-specific token limits."""
    limit = config.TOKEN_LIMITS.get(provider, 8192)
    buffer = int(limit * 0.9)  # Keep 10% margin for safety

    # Always keep the last messages + system prompts
    while count_tokens(messages, provider) > buffer:
        # Ensure we don't delete system messages
        for i, msg in enumerate(messages):
            if msg.get("role") != "system":
                del messages[i]
                break
        else:
            # Only system messages remain, break out
            break

    return messages



def count_tokens(messages: List[Dict[str, str]], provider: str) -> int:
    """Count tokens in the messages list using tiktoken for accuracy."""
    # Select encoding based on provider
    if provider == "openai":
        enc = encoding_for_model(config.OPENAI_MODEL)
    else:
        # Groq models use OpenAI-compatible tokenization
        enc = get_encoding("cl100k_base")

    total_tokens = 0
    for msg in messages:
        total_tokens += len(enc.encode(msg.get("content", "")))
    return total_tokens
