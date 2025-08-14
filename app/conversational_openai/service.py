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
import openai
import redis.asyncio as aioredis
from . import config
from tiktoken import get_encoding

TOKEN_LIMIT = 5500
SUMMARY_TRIGGER_TOKENS = 1500
enc = get_encoding("cl100k_base")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

redis_client = aioredis.Redis.from_url(config.REDIS_URL, decode_responses=True)

openai.api_key = config.OPENAI_API_KEY
OPENAI_MODEL = config.OPENAI_MODEL

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
    def sync_call():
        return openai.chat.completions.create(
            model=OPENAI_MODEL,
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
    session_id = await create_session_if_missing(session_id)
    history = history_override or await get_history_async(session_id, limit=MAX_HISTORY_MESSAGES)

    messages = normalize_messages(history)
    messages = await trim_for_token_limit(messages)

    system_prompt = (
        "You are a helpful assistant. Use the provided context when relevant.\n\n"
        "Respond ONLY in valid JSON with keys:\n"
        "  'answer' (string)\n"
        "  'suggestions' (array of exactly 3 strings)\n"
    )
    messages.append({"role": "system", "content": system_prompt})
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
    messages = await trim_for_token_limit(messages)

    completion = await call_model(messages)

    try:
        assistant_text = completion.choices[0].message.content
    except Exception as e:
        logger.error("Unexpected model response: %s", e)
        raise RuntimeError("Model returned unexpected structure") from e

    try:
        parsed, _ = extract_json_from_text(assistant_text)
        answer = parsed.get("answer", "").strip()
        suggestions = [str(s).strip() for s in parsed.get("suggestions", [])][:3]
    except Exception:
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
    token_count = len(enc.encode(context))
    if token_count > SUMMARY_TRIGGER_TOKENS:
        logger.info("Context too long (%d tokens), summarising", token_count)
        summary = await summarize_and_store(None, [{"role": "system", "content": context}], [])
        return summary if summary else context
    return context

async def trim_for_token_limit(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    while True:
        total_tokens = sum(len(enc.encode(m.get("content", ""))) for m in messages)
        if total_tokens <= TOKEN_LIMIT:
            break
        for i, msg in enumerate(messages):
            if msg.get("role") != "system":
                messages.pop(i)
                break
    return messages
