from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    action: str
    context: str
    question: str
    session_id: Optional[str] = None  # ✅ Make optional
    history: Optional[list] = []      # Or remove if unused

class ChatResponse(BaseModel):
    action: str
    response: str
    suggestions: List[str]
    session_id: Optional[str] = None
