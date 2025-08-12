# app/api/chat.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter()

class ChatRequest(BaseModel):
    action: str
    context: str
    question: str
    history: list = []

class ChatResponse(BaseModel):
    action: str
    response: str
    suggestions: List[str]

@router.post("/chat", response_model=ChatResponse)
async def mock_chat(request: ChatRequest):
    """
    Mocked Copilot-style chat endpoint for frontend testing without OpenAI API calls.
    """
    # This simulates what GPT would normally return
    mock_responses = {
        "summary": "This is a mock summary of the provided context.",
        "qa": "This is a mock answer to your question based on the given context.",
        "default": "This is a generic mock response for testing."
    }

    # Pick mock response based on action
    answer = mock_responses.get(request.action, mock_responses["default"])

    # Example static suggestions
    suggestions = [
        "List the top affected industries",
        "Explain the long-term economic risks",
        "Summarize in 3 bullet points"
    ]

    return ChatResponse(
        action=request.action,
        response=answer,
        suggestions=suggestions
    )
