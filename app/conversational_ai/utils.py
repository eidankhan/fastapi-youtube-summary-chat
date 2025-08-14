# app/conversational_groq/utils.py
import json
import logging
from typing import List, Dict, Any, Tuple
import redis.asyncio as aioredis
from . import config

logger = logging.getLogger(__name__)

# Connect to Redis
redis_client = aioredis.Redis.from_url(config.REDIS_URL, decode_responses=True)

# Constants
MAX_HISTORY_MESSAGES = 50  # or pull from config if configurable

async def get_history(session_id: str) -> List[Dict[str, str]]:
    """Retrieve full conversation history from Redis."""
    key = f"{config.REDIS_PREFIX}{session_id}"
    str_list = await redis_client.lrange(key, 0, -1)
    history = []
    for s in str_list:
        try:
            history.append(json.loads(s))
        except Exception:
            history.append({"role": "system", "content": s})
    return history

async def save_history(session_id: str, history: List[Dict[str, str]]) -> None:
    """Save the entire conversation history to Redis."""
    key = f"{config.REDIS_PREFIX}{session_id}"
    await redis_client.delete(key)
    for msg in history:
        await redis_client.rpush(key, json.dumps(msg))
    await redis_client.expire(key, config.SESSION_TTL_SECONDS)

async def summarize_and_store(session_id: str, old_messages: List[Dict[str, str]], recent_messages: List[Dict[str, str]]) -> None:
    """
    Summarize old messages and store summary with recent messages.
    This prevents unlimited growth of the history list.
    """
    summary_text = " ".join([m["content"] for m in old_messages if m.get("content")])
    summary_msg = {"role": "system", "content": f"Summary of earlier conversation: {summary_text}"}
    new_history = [summary_msg] + recent_messages
    await save_history(session_id, new_history)

def normalize_messages(history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Ensure all messages follow the {role, content} format and are strings.
    """
    normalized = []
    for m in history:
        if "role" in m and "content" in m:
            normalized.append({
                "role": str(m["role"]).strip(),
                "content": str(m["content"]).strip()
            })
    return normalized

def extract_json_from_text(text: str) -> Tuple[Dict[str, Any], str]:
    """
    Extract the first valid JSON object from a string.
    Returns (parsed_json, raw_json_string).
    """
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end+1]
        try:
            parsed = json.loads(json_str)
            return parsed, json_str
        except json.JSONDecodeError:
            logger.warning("Invalid JSON block extracted")
    return {}, ""
