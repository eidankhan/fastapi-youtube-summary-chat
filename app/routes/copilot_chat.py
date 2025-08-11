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
    Copilot-style chat endpoint that returns both an answer and 3 tailored follow-up suggestions.
    """
    # Action-specific instructions
    action_instructions = {
        "summary": "Provide a concise summary. Then suggest 3 follow-up prompts such as expanding details, listing pros & cons, or explaining technical terms.",
        "expand": "Provide an in-depth expansion of the topic. Then suggest 3 follow-up prompts such as summarizing it, giving real-world examples, or highlighting key stats.",
        "qa": "Answer the question clearly and accurately. Then suggest 3 follow-up prompts such as asking for more detail, related topics, or hypothetical scenarios."
    }

    system_prompt = (
        f"You are a helpful assistant. You have the following context:\n"
        f"{request.context}\n\n"
        f"When responding to the user action '{request.action}':\n"
        f"{action_instructions.get(request.action, '')}\n\n"
        "Return your response in JSON format with keys: 'answer' and 'suggestions'.\n"
        "'suggestions' must be an array of 3 short, relevant follow-up questions or actions."
    )

    messages = []

    # Add history if any
    if request.history:
        messages.extend(request.history)

    # Add system and user content
    messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": request.question})

    # One API call to get both answer & suggestions
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7
    )

    # Parse as JSON
    try:
        result = json.loads(completion.choices[0].message.content)
    except json.JSONDecodeError:
        result = {
            "answer": completion.choices[0].message.content.strip(),
            "suggestions": []
        }

    return {
        "action": request.action,
        "response": result.get("answer", ""),
        "suggestions": result.get("suggestions", [])[:3]
    }
