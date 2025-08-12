import os
from redis import Redis

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
SESSION_TTL_SECONDS = int(os.getenv("REDIS_TTL", 3600))  # 1 hour session TTL

# Prefix for Redis keys so we don't conflict with other parts of the app
REDIS_PREFIX = os.getenv("GROQ_REDIS_PREFIX", "groqchat")

redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# AI Model Config
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")
