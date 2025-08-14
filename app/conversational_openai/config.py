# config.py
import os
from redis import Redis

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
SESSION_TTL_SECONDS = int(os.getenv("REDIS_TTL", 3600))  # 1 hour

# Prefix for Redis keys
REDIS_PREFIX = os.getenv("OPENAI_REDIS_PREFIX", "openaichat")

redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)

# OpenAI API Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
