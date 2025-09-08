# server.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uvicorn
import sqlite3
import time
import google.generativeai as genai
from typing import List, Optional
import uuid

# --------------- CONFIG -----------------
DB_PATH = "chats.db"
GEMINI_KEY = os.getenv("GEMINI_API_KEY")  # set this in env on host
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500").split(",")

if not GEMINI_KEY:
    print("WARNING: GEMINI_API_KEY not set. Server will still run but requests will fail.")
genai.configure(api_key=GEMINI_KEY)
MODEL_NAME = "gemini-1.5-flash"
# ----------------------------------------

app = FastAPI(title="AI Chat (with memory)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # restrict to your website domain(s) when deploying
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple DB helpers
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,        -- "user" or "assistant"
        content TEXT NOT NULL,
        created_at INTEGER NOT NULL
    );
    """)
    conn.commit()
    conn.close()

init_db()

# Request models
class ChatRequest(BaseModel):
    session_id: Optional[str] = None  # if not provided, client will get one
    text: str
    history_limit: Optional[int] = 10  # how many previous messages to include for context

class StartSessionResponse(BaseModel):
    session_id: str

# Utilities
def save_message(session_id: str, role: str, content: str):
    conn = get_conn()
    cur = conn.cursor()
    mid = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (mid, session_id, role, content, int(time.time()))
    )
    conn.commit()
    conn.close()

def get_history(session_id: str, limit: int = 10) -> List[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
        (session_id, limit * 2)  # multiply so we can keep original order after reversing
    )
    rows = cur.fetchall()
    conn.close()
    # rows come newest first — reverse to oldest-first
    items = [dict(r) for r in reversed(rows)]
    return items

# Endpoint to create a new session id
@app.post("/start-session", response_model=StartSessionResponse)
def start_session():
    sid = str(uuid.uuid4())
    # optional: init with a system message to set "assistant style"
    save_message(sid, "assistant", "Hello! I'm ready to help. Ask me anything.")
    return {"session_id": sid}

# Get history for UI (optionally used by frontend)
@app.get("/history/{session_id}")
def history(session_id: str, limit: int = 50):
    return {"messages": get_history(session_id, limit)}

# Main chat endpoint
@app.post("/chat")
def chat(payload: ChatRequest):
    session_id = payload.session_id or str(uuid.uuid4())

    # If new session, create an initial assistant message for continuity
    # But we only create on the fly if session_id had no messages yet
    history = get_history(session_id, limit=payload.history_limit or 10)
    if len(history) == 0:
        save_message(session_id, "assistant", "Hello! I'm ready to help. Ask me anything.")
        history = get_history(session_id, limit=payload.history_limit or 10)

    # Save user message
    save_message(session_id, "user", payload.text)

    # Build a compact prompt from last messages for context-aware replies.
    # Gemini can be given a single text prompt; we create a short chat transcript.
    # Keep to a reasonable length: include last N messages (both user and assistant).
    convo = get_history(session_id, limit=payload.history_limit)
    prompt_lines = []
    for m in convo:
        role = m["role"]
        content = m["content"].strip()
        if role == "user":
            prompt_lines.append(f"User: {content}")
        else:
            prompt_lines.append(f"Assistant: {content}")
    # add the new user message at the end to ensure it's included
    prompt_lines.append(f"User: {payload.text}")
    prompt = "\n".join(prompt_lines) + "\nAssistant:"

    # Call Gemini
    try:
        # Use the model.generate_content API with a text prompt
        response = genai.create_text(
            model=MODEL_NAME,
            prompt=prompt,
            max_output_tokens=512
        )
        # response.text may vary; use the library returned field
        ai_text = response.text if hasattr(response, "text") else str(response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model error: {e}")

    # Save assistant message
    save_message(session_id, "assistant", ai_text)

    return {"session_id": session_id, "reply": ai_text}
