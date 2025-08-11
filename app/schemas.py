# app/schemas.py
from pydantic import BaseModel
from typing import List, Optional

class SummarizeRequest(BaseModel):
    transcript: str
    max_tokens: Optional[int] = 300

class SummarizeResponse(BaseModel):
    summary: str

class ChatHistoryItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    action: str
    context: str
    question: Optional[str] = None
    history: Optional[List[ChatHistoryItem]] = []

class ChatResponse(BaseModel):
    response: str
