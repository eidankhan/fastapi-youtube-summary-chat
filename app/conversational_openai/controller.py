# controller.py
from fastapi import APIRouter, HTTPException, status
import logging
from . import schema, service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/api/conversational", tags=["conversational"])

@router.post("/chat", response_model=schema.ChatResponse)
async def conv_chat_endpoint(request: schema.ChatRequest):
    try:
        result = await service.ask(
            session_id=request.session_id,
            action=request.action,
            context=request.context,
            question=request.question,
            history_override=None
        )
    except Exception as e:
        logger.exception("Conversation call failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return schema.ChatResponse(
        action=result["action"],
        response=result["response"],
        suggestions=result["suggestions"],
        session_id=result.get("session_id"),
    )

@router.post("/clear", status_code=204)
async def clear_session(session_id: str):
    key = service.make_session_key(session_id)
    await service.redis_client.delete(key)
    await service.redis_client.delete(f"{key}:meta")
    return None
