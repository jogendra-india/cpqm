# CPQM — .cursorrules Snippet

Copy the block below into your project's `.cursorrules` file (or equivalent rule
file) to enable the CPQM polling loop inside Cursor.

---

```
## CPQM Polling Loop

When a chat message begins with `CPQM_ID=<N>` (where N is any integer or string),
you MUST follow this protocol for the entire chat session:

### Setup
- Extract the CPQM_ID value from the first message.
- The CPQM service runs at http://localhost:9111

### Polling Loop
1. Call `GET http://localhost:9111/queue/<CPQM_ID>/next`

2. Inspect the `status` field in the JSON response:

   a. **status = "END"**
      - Stop polling immediately.
      - Write a structured closing summary listing every task you completed
        in this session (task text + outcome).
      - End the session.

   b. **status = "EMPTY"**
      - Wait approximately 3 seconds.
      - Go back to step 1.

   c. **status = "MESSAGE"**
      - Read the `text` field — this is the task/prompt to execute.
      - Acknowledge the task: print "📥 Received task: <text>"
      - Execute the task fully using all available tools.
      - After completing the task, call
        `POST http://localhost:9111/queue/<CPQM_ID>/consume`
        to mark it as consumed.
      - Print "✅ Completed and consumed task: <text>"
      - Go back to step 1 immediately.

### Rules
- NEVER open a new chat or start a new request. All tasks are processed as
  continuations within this single open session.
- Always poll again immediately after consuming a message (do not wait).
- Only wait 3 seconds when the queue is EMPTY.
- If the task is ambiguous, do your best interpretation — do not ask
  clarifying questions (the user will queue follow-ups if needed).
- Keep a running tally of completed tasks for the final summary.
```

---

## How to use

1. Start the CPQM server (it auto-starts on boot if you installed the LaunchAgent):
   ```bash
   cd /Users/jogendra.dhaka/jllt_project/cpqm
   python server.py
   ```

2. Open the UI at **http://localhost:9111** and create a Chat ID (e.g. `10`).

3. In Cursor, start a new chat with this first message:
   ```
   CPQM_ID=10
   ```

4. Cursor enters the polling loop. Queue prompts from the web UI — Cursor picks
   them up, executes them, and marks them consumed. All within one session.

5. When done, click **End** in the UI. Cursor detects the END signal and writes
   a closing summary.
