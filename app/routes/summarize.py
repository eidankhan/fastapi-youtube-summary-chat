# app/routes/summarize.py
from fastapi import APIRouter, HTTPException
from app.schemas import SummarizeRequest, SummarizeResponse
from app.core.openai_client import create_summary

router = APIRouter()

@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_endpoint(req: SummarizeRequest):
    if not req.transcript or len(req.transcript.strip()) < 20:
        raise HTTPException(status_code=400, detail="Transcript too short")
    summary = await create_summary(req.transcript, max_tokens=req.max_tokens)
    return SummarizeResponse(summary=summary)
