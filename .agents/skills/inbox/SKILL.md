---
name: inbox
description: 'Unified inbox check: Agent Mail MCP (agent coordination) + Chromatic Intake Harness (file/email/GitHub ingestion pipeline). Triggers: "inbox", "check mail", "any messages", "show inbox", "pending messages", "who needs help", "check intake", "what is in the queue".'
metadata:
  tier: solo
  dependencies: []
---

# Inbox Skill

> **Quick Ref:** Unified view of two inbox systems — Agent Mail (agent coordination) + Chromatic Intake Harness (file/email/GitHub pipeline).

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

## Two Inbox Systems

| System | What it contains | Check via |
|--------|-----------------|-----------|
| **Agent Mail MCP** | Agent-to-agent messages, HELP_REQUESTs, completions | `mcp__mcp-agent-mail__*` tools or `localhost:8765` |
| **Chromatic Intake Harness** | Gmail, GitHub notifications, local file drops, routed work items | SQLite DB + intake folders at `$CHROMATIC_INBOX_ROOT` |

Run both checks every time unless the user specifies `--agent-mail` or `--intake` to isolate one system.

## Invocation

```bash
/inbox                  # Both systems, snapshot
/inbox --watch          # Both systems, continuous polling (30s)
/inbox --agent-mail     # Agent Mail only
/inbox --intake         # Chromatic Intake Harness only
```

---

## Execution Steps

### Step 1: Check Agent Mail

#### 1a — Probe availability

```bash
curl -s http://localhost:8765/health 2>/dev/null && echo "Agent Mail HTTP: UP" || echo "Agent Mail: not running"
# If MCP tools present: look for mcp__mcp-agent-mail__fetch_inbox
```

#### 1b — Determine agent identity

```bash
AGENT_NAME="${OLYMPUS_DEMIGOD_ID:-${AGENT_NAME:-${USER:-local}-$(hostname -s 2>/dev/null)}}"
PROJECT_KEY=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
```

#### 1c — Fetch inbox (MCP method, preferred)

```
Tool: mcp__mcp-agent-mail__fetch_inbox
Parameters:
  project_key: "<PROJECT_KEY>"
  agent_name: "<AGENT_NAME>"
```

Categorize results:
- **Pending** — messages without acknowledgement
- **HELP_REQUEST** — subject contains "HELP_REQUEST" (prioritize these — blocked agent)
- **Completions** — subject is "OFFERING_READY", "DONE", or "COMPLETED"

#### 1d — Search for unresolved HELP_REQUESTs

```
Tool: mcp__mcp-agent-mail__search_messages
Parameters:
  project_key: "<PROJECT_KEY>"
  query: "HELP_REQUEST"
```

Filter to threads that have no HELP_RESPONSE reply.

#### 1e — Recent completions

```
Tool: mcp__mcp-agent-mail__search_messages
Parameters:
  project_key: "<PROJECT_KEY>"
  query: "OFFERING_READY OR DONE OR COMPLETED"
```

---

### Step 2: Check Chromatic Intake Harness

#### 2a — Locate the harness root

```bash
# Env var (set in chromatic sessions)
INBOX_ROOT="${CHROMATIC_INBOX_ROOT:-}"

# Fallback: find the data root
if [ -z "$INBOX_ROOT" ]; then
  INBOX_ROOT=$(find "C:/chromatic-inbox-harness-data" "C:/Repos/Poly-Chromatic/chromatic-inbox-harness-data" \
    /mnt/c/chromatic-inbox-harness-data \
    -maxdepth 0 -type d 2>/dev/null | head -1)
fi

# Last resort: check if there's an active DB anywhere
if [ -z "$INBOX_ROOT" ]; then
  DB_PATH=$(find "C:/chromatic-inbox-harness-data" "$HOME/chromatic-inbox-harness-data" \
    -name "chromatic_inbox.sqlite" 2>/dev/null | head -1)
  INBOX_ROOT=$(dirname "$DB_PATH" 2>/dev/null | xargs dirname 2>/dev/null || echo "")
fi

echo "Inbox root: ${INBOX_ROOT:-NOT FOUND}"
```

#### 2b — Count items in intake folders

```bash
if [ -n "$INBOX_ROOT" ]; then
  for folder in "00_INTAKE/gmail" "00_INTAKE/github" "00_INTAKE/uploads" "00_INTAKE/audio"; do
    count=$(ls "$INBOX_ROOT/$folder/" 2>/dev/null | wc -l)
    echo "$folder: $count items"
  done
fi
```

#### 2c — Query the SQLite queue

```bash
DB="${INBOX_ROOT}/db/chromatic_inbox.sqlite"
if [ -f "$DB" ]; then
  python3 - <<'PYEOF'
import sqlite3, os, sys

db = os.environ.get("DB_PATH", "")
if not db:
    # Try to resolve from INBOX_ROOT
    root = os.environ.get("CHROMATIC_INBOX_ROOT", "")
    db = f"{root}/db/chromatic_inbox.sqlite" if root else ""

if not db or not os.path.exists(db):
    print("DB not found")
    sys.exit(0)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

# Queue summary by status
print("\n=== Queue Items by Status ===")
for row in conn.execute("SELECT status, COUNT(*) as n FROM queue_items GROUP BY status ORDER BY n DESC"):
    print(f"  {row['status']}: {row['n']}")

# Recent unprocessed items
print("\n=== Pending Queue Items (last 10) ===")
for row in conn.execute("""
    SELECT id, source, subject, priority, status, created_at
    FROM queue_items
    WHERE status IN ('pending', 'new', 'retry')
    ORDER BY priority DESC, created_at DESC
    LIMIT 10
"""):
    print(f"  [{row['priority']}] {row['source']} — {row['subject'][:60]} ({row['status']})")

# Recent routed items
print("\n=== Recently Routed (last 5) ===")
for row in conn.execute("""
    SELECT id, source, subject, route, created_at
    FROM queue_items
    WHERE status = 'routed'
    ORDER BY created_at DESC
    LIMIT 5
"""):
    print(f"  {row['source']} → {row['route']}: {row['subject'][:50]}")

conn.close()
PYEOF
fi
```

#### 2d — Check routed folders

```bash
if [ -n "$INBOX_ROOT" ]; then
  echo "\n=== Routed Work Items ==="
  for folder in "02_ROUTED/code-review" "02_ROUTED/architecture" "02_ROUTED/urgent" "02_ROUTED/unknown"; do
    count=$(ls "$INBOX_ROOT/$folder/" 2>/dev/null | wc -l)
    [ "$count" -gt 0 ] && echo "  $folder: $count items"
  done
fi
```

#### 2e — Check harness API health (if running)

```bash
# The harness exposes a FastAPI server when active
curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool 2>/dev/null \
  || curl -s http://localhost:8001/health 2>/dev/null \
  || echo "Harness API: not running (normal if not in active session)"
```

---

### Step 3: Unified Summary Display

Present a single combined view:

```
━━━ INBOX SNAPSHOT ━━━━━━━━━━━━━━━━━━━━━
Agent Mail:      [UP/DOWN] N pending | N HELP_REQUESTs | N completions
Intake Harness:  [FOUND/NOT FOUND]
  Gmail:    N items    GitHub: N items    Uploads: N items
  Queue:    N pending  N routed           N complete
  Urgent:   N items in 02_ROUTED/urgent

HELP_REQUESTs (act immediately):
  • [worker-2] schema migration blocked

Pending Intake:
  • [priority:high] github — PR review requested kas1987/04-Prism#5
  • [priority:med]  gmail  — CI failure on fusion-computer

Routed (ready to action):
  • code-review: 3 items
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### Step 4: Action Recommendations

After displaying the snapshot, always recommend the next action:

- If HELP_REQUESTs exist → "Worker X is blocked — respond before proceeding"
- If `02_ROUTED/urgent` has items → "N urgent items need immediate action"
- If `00_INTAKE/github` has items → "Run GitHub notification router to process PRs/CI failures: `python 01_INTAKE/github_notification_router.py`"
- If `00_INTAKE/gmail` has items → "Gmail items waiting — Gmail ingestion service needed (bd show ci-x0k)"
- If queue has pending but no intake items → "Items stalled in queue — check `03_DB/` or run `bd show` on intake issues"

---

## Watch Mode

Read `references/watch-mode.md` for polling loop setup. In watch mode, poll both systems every 30 seconds and alert on:
- New HELP_REQUESTs (Agent Mail)
- New items in `00_INTAKE/github` or `00_INTAKE/uploads`
- Queue items moving to `urgent`

---

## Key Rules

- **HELP_REQUESTs always first** — blocked agents waste resources
- **Urgent intake always second** — `02_ROUTED/urgent` items are time-sensitive
- **Never assume harness is running** — it may not be; report what you find, don't error out
- **If harness root not found** — note it and still check Agent Mail
- **GitHub items in intake** — the router is `01_INTAKE/github_notification_router.py`; check bd issue `ci-98r` for status

---

## Harness Intake Folder Schema

```
$CHROMATIC_INBOX_ROOT/
  00_INTAKE/
    gmail/          # Raw Gmail messages (.eml or .json)
    github/         # GitHub notification payloads
    uploads/        # Local file drops (PDFs, images, audio)
    screenshots/    # Screen captures
    audio/          # Voice memos
  01_PROCESSING/    # In-flight items
  02_ROUTED/
    code-review/    # PRs, patches
    architecture/   # Design docs
    financial/      # Billing, invoices
    images/         # Image processing
    urgent/         # High-priority, any source
    unknown/        # Unrouted items
  03_COMPLETE/      # Finished
  04_AUDIT/         # Audit trail
  05_MEMORY/        # Knowledge extracts
  db/
    chromatic_inbox.sqlite   # Queue items, routing log
```

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| "Agent Mail not running" | MCP server down | Start: check MCP config or run `localhost:8765` server |
| "Inbox root NOT FOUND" | `$CHROMATIC_INBOX_ROOT` not set, data not at expected path | Set env var or run `scripts/init_local_inbox.py --root <path>` |
| Empty queue despite intake files | Router not run yet | Run `01_INTAKE/github_notification_router.py` or Gmail ingestor |
| Watch mode exits immediately | Polling error | Check each system individually first |
| Harness API 404/down | Not in active harness session | Normal — skip API check, use SQLite directly |

---

## See Also

- `skills/swarm/SKILL.md` — Spawns workers that send to Agent Mail inbox
- `skills/crank/SKILL.md` — Distributed mode uses Agent Mail for coordination
- `skills/handoff/SKILL.md` — HELP_REQUESTs trigger handoffs
- `skills/status/SKILL.md` — Dashboard includes pending inbox messages
- **Harness intake router:** `01_INTAKE/github_notification_router.py`
- **Harness DB schema:** `03_DB/schema.sql`
- **Init harness:** `scripts/init_local_inbox.py --root <path>`
- **Beads issues tracking intake features:** ci-98r (GitHub router), ci-x0k (Gmail), ci-027 (file watcher)
