
# YouTube Transcript Summarizer API (FastAPI + Docker + OpenAI)

## 📌 Overview
This project is a **containerized FastAPI application** that:
- Accepts a YouTube transcript and returns a concise AI-generated summary.
- Is modular, allowing future extension (e.g., AI chat feature).
- Uses **OpenAI's GPT models** for summarization.
- Runs fully in **Docker** with optional **Redis** support for chat sessions.

Built with:
- **FastAPI** for modern async API handling
- **OpenAI Python SDK v1.x** for AI integration
- **Docker** + **Docker Compose** for environment consistency
- **Pydantic** for request/response validation

---
## 📂 Project Structure

```
fastapi-youtube-summary-chat/
├── app/
│   ├── **init**.py
│   ├── main.py                 # FastAPI entry point
│   ├── core/
│   │   ├── **init**.py
│   │   └── openai_client.py    # OpenAI API integration logic
│   ├── routes/
│   │   ├── **init**.py
│   │   └── summarize.py        # /summarize endpoint
│   ├── schemas.py              # Request/response Pydantic models
├── Dockerfile                  # Container build instructions
├── docker-compose.yml          # Multi-service orchestration (app + redis)
├── requirements.txt            # Python dependencies
├── .env.example                # Example environment variables (safe to share)
├── .env                        # Actual environment variables (private)
└── README.md                   # Project documentation
````

## 🚀 Step-by-Step Guide

### **1. Prerequisites**
- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed.
- An [OpenAI API Key](https://platform.openai.com/account/api-keys).

---

### **2. Clone the Project**
```bash
git clone https://github.com/your-username/fastapi-youtube-summary-chat.git
cd fastapi-youtube-summary-chat
````

---

### **3. Setup Environment Variables**

1. Copy the example `.env` file:

   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and fill in:

   ```env
   OPENAI_API_KEY=sk-your-openai-key
   OPENAI_MODEL=gpt-4o-mini
   REDIS_URL=redis://redis:6379/0
   ```

**Why two files?**

* `.env.example` → Safe template for collaborators.
* `.env` → Your private API keys and config.

---

### **4. Build and Run with Docker Compose**

```bash
docker compose up --build
```

* `--build` ensures the image is rebuilt from the `Dockerfile`.
* Runs the **FastAPI app** on port `8000` and **Redis** on `6379`.

---

### **5. Verify the API**

Open your browser at:

```
http://localhost:8000/
```

You should see:

```json
{"ok": true, "message": "FastAPI YouTube summarizer + chat"}
```

For API docs (Swagger UI):

```
http://localhost:8000/docs
```

---

### **6. `/summarize` Endpoint Implementation**

#### **Route: `app/routes/summarize.py`**

```python
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
```

#### **OpenAI Client: `app/core/openai_client.py` (v1.x API)**

```python
import os
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is required")

client = OpenAI(api_key=OPENAI_API_KEY)

async def create_summary(transcript: str, max_tokens: int = 300) -> str:
    prompt = (
        "You are a helpful assistant. Read the following YouTube transcript and provide a concise, clear summary "
        "(3-6 sentences). Highlight main points, key conclusions, and any action items if present.\n\n"
        f"Transcript:\n{transcript}\n\nSummary:"
    )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()
```

### **7. Test the `/summarize` Endpoint**

```bash
curl -X POST http://localhost:8000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"transcript": "This is a test transcript about the history of Python and why it is loved."}'
```

**Expected Response:**

```json
{"summary": "Python is popular due to its simplicity, readability, and wide applicability..."}
```
