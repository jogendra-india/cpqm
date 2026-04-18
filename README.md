# CPQM — Cursor Prompt Queue Manager

A lightweight local service that lets you queue prompts to a running Cursor chat session via a browser UI. Cursor stays in a single polling loop within one chat session — processing each queued message as it arrives — so one session handles unlimited tasks without consuming extra requests.

## Quick Start

The service auto-starts on login via macOS LaunchAgent. To manage it manually:

```bash
# Start
launchctl load ~/Library/LaunchAgents/com.jogendra.cpqm.plist

# Stop
launchctl unload ~/Library/LaunchAgents/com.jogendra.cpqm.plist

# Or run directly
cd /Users/jogendra.dhaka/jllt_project/cpqm
./start.sh


restart
launchctl unload /Users/jogendra.dhaka/Library/LaunchAgents/com.jogendra.cpqm.plist && launchctl load /Users/jogendra.dhaka/Library/LaunchAgents/com.jogendra.cpqm.plist
```

Open **http://localhost:9111** in your browser.

## Usage

1. Create a Chat ID in the web UI (e.g. `10`)
2. In Cursor, start a new chat with: `CPQM_ID=10`
3. Cursor enters a polling loop — queue prompts from the web UI
4. Cursor picks them up, executes, marks consumed — all within one session
5. Click **End** in the UI when done — Cursor writes a closing summary

## Architecture

```
Browser UI (localhost:9111)
    │
    ▼
FastAPI Server (in-memory queues)
    │
    ▼
Cursor polls GET /queue/<id>/next
    → processes task
    → POST /queue/<id>/consume
    → loops
```

## API Contract

| Endpoint | Method | Description |
|---|---|---|
| `/queue/<chat_id>/next` | GET | Returns next pending message or EMPTY/END status |
| `/queue/<chat_id>` | POST | Queue a new message `{"message": "..."}` |
| `/queue/<chat_id>/consume` | POST | Move top pending message to consumed |
| `/queue/<chat_id>/end` | POST | Signal END — Cursor stops polling |
| `/queue/<chat_id>/status` | GET | Full state: pending, consumed, status |
| `/chats` | GET | List all chat IDs |
| `/chats/<chat_id>` | POST | Create a new chat ID |
| `/chats/<chat_id>` | DELETE | Remove a chat ID and all its data |

## .cursorrules Setup

See `cursorrules-snippet.md` for the rule block to add to your project's `.cursorrules` file.

## Files

```
cpqm/
  server.py              # FastAPI backend
  templates/index.html   # Browser UI
  start.sh               # Startup script (used by LaunchAgent)
  requirements.txt       # Python dependencies
  cursorrules-snippet.md # Cursor polling loop instructions
  README.md
```

## LaunchAgent

Installed at `~/Library/LaunchAgents/com.jogendra.cpqm.plist`. Runs on login, auto-restarts on crash.
