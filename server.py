"""
Cursor Prompt Queue Manager (CPQM)

A lightweight local server that maintains in-memory message queues per Chat ID.
Cursor polls these queues within a single chat session, processing tasks sequentially
without consuming additional requests.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("cpqm")

app = FastAPI(title="Cursor Prompt Queue Manager")
templates = Jinja2Templates(directory="templates")

# ── In-memory state ──────────────────────────────────────────────

# pending[chat_id] = [ { "text": ..., "queued_at": ... }, ... ]
pending: dict[str, list[dict]] = defaultdict(list)

# consumed[chat_id] = [ { "text": ..., "queued_at": ..., "consumed_at": ... }, ... ]
consumed: dict[str, list[dict]] = defaultdict(list)

# status[chat_id] = "ACTIVE" | "END"
status: dict[str, str] = {}

# Track all known chat IDs in creation order
known_chat_ids: list[str] = []


class QueueMessageBody(BaseModel):
    message: str


# ── UI ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Cursor-facing endpoints ──────────────────────────────────────

@app.get("/queue/{chat_id}/next")
async def next_message(chat_id: str):
    """
    Returns the next pending message for the given chat ID.
    - {status: "END"}     → chat has been terminated
    - {status: "MESSAGE", text: "...", message_id: n} → next task
    - {status: "EMPTY"}   → nothing pending right now
    """
    if status.get(chat_id) == "END" and not pending[chat_id]:
        return {"status": "END"}

    if pending[chat_id]:
        msg = pending[chat_id][0]
        return {
            "status": "MESSAGE",
            "text": msg["text"],
            "message_id": msg.get("id", 0),
        }

    return {"status": "EMPTY"}


@app.post("/queue/{chat_id}/consume")
async def consume_message(chat_id: str):
    """Moves the top pending message to the consumed stack."""
    if not pending[chat_id]:
        return {"ok": False, "reason": "nothing to consume"}

    msg = pending[chat_id].pop(0)
    msg["consumed_at"] = datetime.now(timezone.utc).isoformat()
    consumed[chat_id].append(msg)
    LOGGER.info("Chat %s consumed: %s", chat_id, msg["text"][:80])
    return {"ok": True, "consumed": msg}


# ── UI-facing endpoints ──────────────────────────────────────────

@app.post("/queue/{chat_id}")
async def enqueue_message(chat_id: str, body: QueueMessageBody):
    """Adds a new message to the pending queue for a chat ID."""
    _ensure_chat(chat_id)

    msg = {
        "id": len(pending[chat_id]) + len(consumed[chat_id]) + 1,
        "text": body.message,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    pending[chat_id].append(msg)
    LOGGER.info("Chat %s queued: %s", chat_id, body.message[:80])
    return {"ok": True, "message": msg}


@app.post("/queue/{chat_id}/end")
async def end_chat(chat_id: str):
    """Sets the chat ID status to END."""
    _ensure_chat(chat_id)
    status[chat_id] = "END"
    LOGGER.info("Chat %s marked END", chat_id)
    return {"ok": True, "status": "END"}


@app.get("/queue/{chat_id}/status")
async def chat_status(chat_id: str):
    """Returns full state for a chat ID: pending, consumed, status flag."""
    return {
        "chat_id": chat_id,
        "status": status.get(chat_id, "ACTIVE"),
        "pending": pending.get(chat_id, []),
        "consumed": consumed.get(chat_id, []),
    }


@app.get("/chats")
async def list_chats():
    """Returns all known chat IDs and their status."""
    return [
        {"chat_id": cid, "status": status.get(cid, "ACTIVE")}
        for cid in known_chat_ids
    ]


@app.post("/chats/{chat_id}")
async def create_chat(chat_id: str):
    """Registers a new chat ID."""
    _ensure_chat(chat_id)
    return {"ok": True, "chat_id": chat_id, "status": status[chat_id]}


@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Removes a chat ID and all its data entirely."""
    if chat_id in known_chat_ids:
        known_chat_ids.remove(chat_id)
    pending.pop(chat_id, None)
    consumed.pop(chat_id, None)
    status.pop(chat_id, None)
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────

def _ensure_chat(chat_id: str):
    if chat_id not in known_chat_ids:
        known_chat_ids.append(chat_id)
    if chat_id not in status:
        status[chat_id] = "ACTIVE"


# ── Entry-point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9111, log_level="info")
