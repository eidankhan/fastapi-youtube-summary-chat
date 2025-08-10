# app/schemas.py
from pydantic import BaseModel
from typing import Optional

class SummarizeRequest(BaseModel):
    transcript: str
    max_tokens: Optional[int] = 300

class SummarizeResponse(BaseModel):
    summary: str