import os
import json
import re
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()

# Groq API client
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
)

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")

class ChatRequest(BaseModel):
    action: str
    context: str
    question: str
    history: list = []

class ChatResponse(BaseModel):
    action: str
    response: str
    suggestions: list

@router.post("/chat-groq", response_model=ChatResponse)
async def chat_groq_endpoint(request: ChatRequest):
    """
    A Copilot-style chat endpoint using Groq API.
    Returns both an answer and 3 follow-up suggestions.
    """

    messages = []
    if request.history:
        messages.extend(request.history)

    messages.append({
        "role": "system",
        "content": (
            f"You are a helpful assistant. You have the following context:\n"
            f"{request.context}\n\n"
            "When responding:\n"
            "1. Provide a clear and helpful answer to the question.\n"
            "2. Also propose 3 short, relevant follow-up questions.\n"
            "3. Return your response as valid JSON with keys: 'answer' and 'suggestions'.\n"
            "4. 'suggestions' must be an array of strings.\n"
            "5. Return ONLY the JSON. Do not include any extra commentary or explanation."
        )
    })
    messages.append({"role": "user", "content": request.question})

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.7
    )

    raw_content = completion.choices[0].message.content
    logger.info(f"Raw Groq API response: {raw_content}")

    # Try to extract JSON
    try:
        match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if match:
            json_str = match.group(0)
            result = json.loads(json_str)
            logger.info(f"Parsed JSON result: {result}")
        else:
            raise json.JSONDecodeError("No JSON found", raw_content, 0)

    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON, falling back to plain text.")
        result = {
            "answer": raw_content.strip(),
            "suggestions": []
        }

    return {
        "action": request.action,
        "response": result.get("answer", ""),
        "suggestions": result.get("suggestions", [])[:3]
    }
