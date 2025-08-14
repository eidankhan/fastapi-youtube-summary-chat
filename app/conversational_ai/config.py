# config.py
import os
from redis import Redis

# Provider selection: "groq" or "openai"
PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()

# Redis config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
SESSION_TTL_SECONDS = int(os.getenv("REDIS_TTL", 3600))

REDIS_PREFIX = os.getenv("REDIS_PREFIX", "aichat")

redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)

# Groq config
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")

# OpenAI config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Token limits per provider
TOKEN_LIMITS = {
    "openai": int(os.getenv("OPENAI_TOKEN_LIMIT", 128000)),  # gpt-4o family
    "groq": int(os.getenv("GROQ_TOKEN_LIMIT", 6000)),        # llama3-70b
}

# Summarization trigger per provider
SUMMARY_TRIGGER = {
    "openai": int(os.getenv("OPENAI_SUMMARY_TRIGGER", 110000)),
    "groq": int(os.getenv("GROQ_SUMMARY_TRIGGER", 5000)),
}

# Retry config
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
