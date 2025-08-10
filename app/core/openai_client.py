# app/core/openai_client.py
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

async def chat_with_context(messages, transcript: str = None):
    system_msg = (
        "You are an assistant that knows the content of a YouTube transcript provided by the user. "
        "When answering, ground responses in the transcript if relevant."
    )

    prompt_messages = [{"role": "system", "content": system_msg}]
    if transcript:
        prompt_messages.append({"role": "system", "content": f"Transcript:\n{transcript}"})
    prompt_messages.extend(messages)

    resp = client.chat.completions.create(
        model=MODEL,
        messages=prompt_messages,
        max_tokens=400,
        temperature=0.7,
    )

    return {
        "content": resp.choices[0].message.content.strip(),
        "raw": resp,
    }