# CPQM — .cursorrules Snippet

Copy the block below into your project's `.cursorrules` file (or equivalent rule
file) to enable the CPQM polling loop inside Cursor.

---

---
alwaysApply: true
---

## CPQM — Cursor Prompt Queue Manager

When the very first message in a chat is `CPQM_ID=<N>` or just `CPQM`
(case-insensitive), this entire chat session becomes a CPQM worker session.

### Setup

- If `CPQM_ID=<N>`: use N as the queue ID.
- If just `CPQM`: call `POST http://localhost:9111/chats/new`, read the
  `chat_id` from the response, and print it so the user knows which ID to
  use in the web UI.
- The queue auto-creates on first poll — no need to pre-create via the UI.

### Core Loop

Repeat forever until END is received:

1. **Poll** — `GET http://localhost:9111/queue/<ID>/next`

2. **If `status` = `"END"`** — stop. Write a structured closing summary of
   every task completed in this session (task text + what you did). Done.

3. **If `status` = `"EMPTY"`** — wait ~3 seconds, go to step 1.

4. **If `status` = `"MESSAGE"`** — you have a task. Do ALL of the following
   **in this exact order**:

   a. Print: `--- CPQM Task Received: "<text>" ---`

   b. **EXECUTE THE TASK.** The `text` field IS a user prompt. Treat it
      EXACTLY as if the user had typed it into this chat directly. That
      means: read files, write code, run commands, create plans, answer
      questions — whatever the prompt asks for. Do the FULL work, produce
      the FULL response, just as you would for any normal user message.
      DO NOT just acknowledge it. DO NOT just say "done". Actually do it.

   c. **Only after you have fully completed the work and produced your
      response**, call `POST http://localhost:9111/queue/<ID>/consume`
      to mark the task as done.

   d. Print: `--- CPQM Task Complete: "<text>" ---`

   e. Go to step 1 immediately (no wait).

### Critical Rules

- The queued message text IS the prompt. Execute it fully. If it says
  "refactor the auth module", you refactor the auth module. If it says
  "write tests for X", you write the tests. If it says "how are you",
  you answer conversationally. Treat every message exactly like a normal
  user prompt.
- NEVER consume a message before you have finished executing it.
- NEVER open a new chat or start a new request.
- NEVER just acknowledge a task without doing the work.
- Only wait when the queue is EMPTY. After completing a task, poll
  immediately.
- Keep a running tally of completed tasks for the final summary.
