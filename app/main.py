# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import summarize
from app.routes import copilot_chat
from app.routes import chat_endpoint
from app.routes import mock_chat
from app.routes import groq_chat
from app.conversational_groq import controller
from app.conversational_openai import controller as openai_controller     
from app.conversational_ai import controller as conv_controller



app = FastAPI(title="YouTube Transcript Summarizer + Chat")

# CORS middleware — allows requests from browser extensions (your Chrome ext)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # You can restrict this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(summarize.router, prefix="/api")
app.include_router(copilot_chat.router, prefix="/api")
app.include_router(chat_endpoint.router, prefix="/assistant")
app.include_router(mock_chat.router, prefix="/mock")
app.include_router(groq_chat.router, prefix="/api")
app.include_router(controller.router)
app.include_router(openai_controller.router)
app.include_router(conv_controller.router)

@app.get("/")
async def root():
    return {"ok": True, "message": "FastAPI YouTube summarizer + chat"}
