# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import summarize

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

@app.get("/")
async def root():
    return {"ok": True, "message": "FastAPI YouTube summarizer + chat"}
