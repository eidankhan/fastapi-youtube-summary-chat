from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI
import os
import json

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class ChatRequest(BaseModel):
    action: str
    context: str
    question: str
    history: list = []

class ChatResponse(BaseModel):
    action: str
    response: str
    suggestions: list

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    A Copilot-style chat endpoint that returns both an answer and 3 follow-up suggestions.
    """
    messages = []

    # Add history if provided
    if request.history:
        messages.extend(request.history)

    # Add system and user messages
    messages.append({
        "role": "system",
        "content": (
            f"You are a helpful assistant. You have the following context:\n"
            f"{request.context}\n\n"
            "When responding:\n"
            "1. Provide a clear and helpful answer to the question.\n"
            "2. Also propose 3 short, relevant follow-up questions.\n"
            "3. Return your response as valid JSON with keys: 'answer' and 'suggestions'.\n"
            "4. 'suggestions' must be an array of strings."
        )
    })
    messages.append({"role": "user", "content": request.question})

    # Single OpenAI API call
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7
    )

    # Parse JSON output
    try:
        result = json.loads(completion.choices[0].message.content)
    except json.JSONDecodeError:
        # Fallback if output isn't JSON
        result = {
            "answer": completion.choices[0].message.content.strip(),
            "suggestions": []
        }

    return {
        "action": request.action,
        "response": result.get("answer", ""),
        "suggestions": result.get("suggestions", [])[:3]
    }
