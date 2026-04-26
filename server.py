"""
Cursor Prompt Queue Manager (CPQM)

A lightweight local server that maintains in-memory message queues per Chat ID.
Cursor polls these queues within a single chat session, processing tasks sequentially
without consuming additional requests.
"""

import logging
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("cpqm")

app = FastAPI(title="Cursor Prompt Queue Manager")

TEMPLATES_DIR = Path(__file__).parent / "templates"

# ── In-memory state ──────────────────────────────────────────────

pending: dict[str, list[dict]] = defaultdict(list)
consumed: dict[str, list[dict]] = defaultdict(list)
status: dict[str, str] = {}
known_chat_ids: list[str] = []
next_message_id: dict[str, int] = defaultdict(lambda: 1)


class QueueMessageBody(BaseModel):
    message: str


# ── Helper functions ─────────────────────────────────────────────

def _ensure_chat(chat_id: str):
    """Ensures chat_id exists in known chats with default status."""
    if chat_id not in known_chat_ids:
        # New chats are shown at the top of the UI list.
        known_chat_ids.insert(0, chat_id)
    if chat_id not in status:
        status[chat_id] = "ACTIVE"


# ── UI ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html = (TEMPLATES_DIR / "index.html").read_text()
    return HTMLResponse(content=html)


# ── Cursor-facing endpoints ──────────────────────────────────────

@app.get("/queue/{chat_id}/next")
async def next_message(chat_id: str):
    """
    Returns the next pending message for the given chat ID.
    Auto-creates the chat if it doesn't exist yet (so Cursor can just
    declare CPQM_ID=<n> without pre-creating via the UI).
    """
    _ensure_chat(chat_id)

    if status.get(chat_id) == "END" and not pending[chat_id]:
        return {"status": "END"}

    if pending[chat_id]:
        msg = pending[chat_id][0]
        return {
            "status": "MESSAGE",
            "text": msg["text"],
            "message_id": msg.get("id", 0),
        }

    return {"status": "Please poll after waiting for 1 minute, do not run polling in the background, keep this in sync mode only"}


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

    message_id = next_message_id[chat_id]
    next_message_id[chat_id] += 1
    msg = {
        "id": message_id,
        "text": body.message,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    pending[chat_id].append(msg)
    LOGGER.info("Chat %s queued: %s", chat_id, body.message[:80])
    return {"ok": True, "message": msg}


@app.delete("/queue/{chat_id}/message/{message_id}")
async def delete_pending_message(chat_id: str, message_id: int):
    """Removes a specific pending message by its ID."""
    for i, msg in enumerate(pending.get(chat_id, [])):
        if msg["id"] == message_id:
            removed = pending[chat_id].pop(i)
            LOGGER.info("Chat %s deleted pending msg %d: %s", chat_id, message_id, removed["text"][:80])
            return {"ok": True, "deleted": removed}
    return {"ok": False, "reason": "message not found in pending queue"}


@app.put("/queue/{chat_id}/message/{message_id}")
async def update_pending_message(chat_id: str, message_id: int, body: QueueMessageBody):
    """Updates the text for a pending message by its ID."""
    for msg in pending.get(chat_id, []):
        if msg["id"] == message_id:
            msg["text"] = body.message
            msg["queued_at"] = datetime.now(timezone.utc).isoformat()
            LOGGER.info("Chat %s updated pending msg %d", chat_id, message_id)
            return {"ok": True, "updated": msg}

    return {"ok": False, "reason": "message not found in pending queue"}


@app.put("/chats/{chat_id}/rename/{new_chat_id}")
async def rename_chat(chat_id: str, new_chat_id: str):
    """Renames a chat ID, migrating all its data."""
    if chat_id not in known_chat_ids:
        return {"ok": False, "reason": "chat not found"}
    if new_chat_id in known_chat_ids:
        return {"ok": False, "reason": "target chat ID already exists"}

    idx = known_chat_ids.index(chat_id)
    known_chat_ids[idx] = new_chat_id

    pending[new_chat_id] = pending.pop(chat_id, [])
    consumed[new_chat_id] = consumed.pop(chat_id, [])
    status[new_chat_id] = status.pop(chat_id, "ACTIVE")
    next_message_id[new_chat_id] = next_message_id.pop(chat_id, 1)

    LOGGER.info("Chat %s renamed to %s", chat_id, new_chat_id)
    return {"ok": True, "old_chat_id": chat_id, "new_chat_id": new_chat_id}


@app.post("/queue/{chat_id}/end")
async def end_chat(chat_id: str):
    """Sets the chat ID status to END."""
    _ensure_chat(chat_id)
    status[chat_id] = "END"
    LOGGER.info("Chat %s marked END", chat_id)
    return {"ok": True, "status": "END"}


@app.post("/queue/{chat_id}/reopen")
async def reopen_chat(chat_id: str):
    """Re-activates a chat that was ended by mistake."""
    _ensure_chat(chat_id)
    status[chat_id] = "ACTIVE"
    LOGGER.info("Chat %s reopened", chat_id)
    return {"ok": True, "status": "ACTIVE"}


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


@app.post("/chats/new")
async def create_random_chat():
    """Creates a chat with a random numeric ID and returns it."""
    chat_id = str(random.randint(1000, 9999))
    while chat_id in known_chat_ids:
        chat_id = str(random.randint(1000, 9999))
    _ensure_chat(chat_id)
    LOGGER.info("Chat %s created (random)", chat_id)
    return {"ok": True, "chat_id": chat_id, "status": status[chat_id]}


@app.post("/chats/{chat_id}")
async def create_chat(chat_id: str):
    """Registers a new chat ID."""
    _ensure_chat(chat_id)
    LOGGER.info("Chat %s created", chat_id)
    return {"ok": True, "chat_id": chat_id, "status": status[chat_id]}


@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Removes a chat ID and all its data entirely."""
    if chat_id in known_chat_ids:
        known_chat_ids.remove(chat_id)
    pending.pop(chat_id, None)
    consumed.pop(chat_id, None)
    next_message_id.pop(chat_id, None)
    status.pop(chat_id, None)
    return {"ok": True}


# ── Entry-point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9111, log_level="info")
