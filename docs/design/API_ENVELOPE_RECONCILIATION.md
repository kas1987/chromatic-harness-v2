# API Envelope Reconciliation — Design Note

**Status: DESIGN ONLY — NEEDS-APPROVAL before any code changes**
**Date: 2026-06-16**
**Scope: 05_FRONTEND_CONSOLE/src/lib/api.ts vs 02_RUNTIME/api/main.py**

---

## 1. The Precise Mismatch

### 1a. Envelope mismatch: `{status, data}` vs bare object

**Frontend assumption (`api.ts` lines 88-89):**

```typescript
const data = await res.json();
return data.data;   // expects envelope { ..., data: T }
```

`apiCall<T>` always unwraps `.data` from the JSON response. Every exported
function (`getMissions`, `getMission`, `createMission`, `getBeads`, etc.) flows
through this path.

**FastAPI reality (`main.py`):**

FastAPI returns bare Pydantic model serializations with no envelope. Examples:

| Endpoint | FastAPI response shape | File:line |
|---|---|---|
| `GET /missions` | `[ { mission_id, objective, ... } ]` | main.py:254-258, models.py:16-25 |
| `GET /missions/{id}` | `{ mission_id, objective, ... }` | main.py:261-267 |
| `POST /missions` | `{ mission_id, objective, ... }` | main.py:222-251 |
| `GET /beads` | `[ { bead_id, title, ... } ]` | main.py:480-484 |
| `GET /agents` | `[ { agent_id, ... } ]` | main.py:538-542 |
| `GET /agents/meta/level-thresholds` | `{ "data": { 0: {...}, 1: {...} } }` | main.py:610-612 |

The one exception is `GET /agents/meta/level-thresholds` (main.py:612), which
wraps its payload under `"data"` but omits a `"status"` field. This is an
accidental partial compliance with what the frontend expects.

**Consequence:** Every call to `apiCall<T>` returns `undefined` in practice
because `res.json().data` is `undefined` on a bare-object response. Console
panels (missions list, beads list, agents panel) receive `undefined` and render
empty.

**Health endpoint note:** `GET /health` returns `{ status, version }` (main.py:100-101).
`apiCall` unwraps `.data` from that too, yielding `undefined`. `getHealthStatus`
then catches and returns `{ status: "unavailable" }`.

### 1b. Missing `/gates` endpoint

**Frontend call (`api.ts` lines 108-110):**

```typescript
export async function getMissionGates(id: string): Promise<GateResult[]> {
  return apiCall("GET", `/missions/${id}/gates`);
}
```

**FastAPI:** There is no `GET /missions/{mission_id}/gates` route in
`02_RUNTIME/api/main.py`. The only mission sub-routes present are:

- `POST /missions/{mission_id}/events` (main.py:270)
- `GET /missions/{mission_id}/events` (main.py:294)
- `GET /missions/{mission_id}/analytics` (main.py:315)
- `POST /missions/{mission_id}/synthesize` (main.py:398)

`getMissionGates` is called by `getMissionEvents` (api.ts:137), which is wrapped
in a try/catch that silently swallows the 404 (api.ts:159). The Magnet Events
panel always renders empty as a result.

### 1c. Routing split: `:3030` vs `:8787`

`apiCall` routes all calls to `API_BASE` (default `:3030`, the Next.js host),
not `PYTHON_API_BASE` (`:8787`, FastAPI). There is no Next.js API route layer
currently implementing `/missions`, `/beads`, `/agents`, or `/health`. These
calls 404 on the Next host before they even reach the envelope issue.

By contrast, `getMissionAnalytics` (api.ts:245) and `getMissionEventsRange`
(api.ts:283) bypass `apiCall` and hit `:8787` directly via raw `fetch`,
expecting bare JSON. Those callsites are currently correct relative to what
FastAPI returns and must not be broken.

---

## 2. Reconciliation Options

### Option A: Add `{status, data}` envelope + `/gates` endpoint to FastAPI

Wrap every FastAPI response in `{ "status": "ok", "data": <payload> }` and add
`GET /missions/{mission_id}/gates`.

**Pros:**
- `api.ts` stays unchanged (protected file — hard requirement for sub-agents).
- Makes the API contract explicit; envelope is a common REST pattern that
  co-locates success/error shape.
- One-time FastAPI change fixes all panels simultaneously.

**Cons:**
- Touches `02_RUNTIME` — requires human approval per project rules.
- Every endpoint changes response shape; the two raw-`fetch` callsites in
  `api.ts` (analytics at line 245, events at line 283) hit `:8787` and expect
  bare JSON. Wrapping those endpoints would break those callers unless `api.ts`
  is updated simultaneously — but `api.ts` is a protected file.
- `GET /agents/meta/level-thresholds` (main.py:612) already returns
  `{ "data": ... }` without `"status"`; uniform wrapping must also fix this or
  it will double-nest.
- Requires removing or changing `response_model` annotations on all affected
  endpoints so FastAPI does not validate the wrapper against the Pydantic model.

**Recommended scope guard:** Leave `GET /missions/{mission_id}/analytics` and
`GET /missions/{mission_id}/events` unwrapped until the raw-`fetch` callsites
in `api.ts` can be updated in a coordinated change.

### Option B: Change `apiCall` to stop unwrapping `.data`, add frontend gates fallback

Change `apiCall<T>` (api.ts:89) to return `res.json()` directly, and handle
the gates 404 as a frontend stub.

**Pros:**
- Zero runtime changes; no impact to `02_RUNTIME`.
- Smallest blast radius — one-line fix to one function corrects all panels.
- The gates fallback (return `[]`) is already implemented implicitly via the
  try/catch at api.ts:159.

**Cons:**
- `api.ts` is explicitly listed as off-limits for sub-agents and protected by
  hard rules for this session.
- `GET /agents/meta/level-thresholds` returns `{ "data": ... }` (main.py:612);
  after removing the generic unwrap, `getLevelThresholds` would need a
  call-specific unwrap or main.py:612 would need to change to return the map
  bare — either way requires a targeted edit.
- Does not add a real `/gates` endpoint; gates data remains unavailable unless
  a backend implementation is later added.

---

## 3. Recommendation

**Recommended: Option A (add envelope + `/gates` to FastAPI), scoped narrowly.**

1. `api.ts` is a protected file and cannot be changed by sub-agents; Option B
   is not executable at the tooling level regardless of merit.
2. The envelope pattern is the correct architectural fix — it matches the shape
   the frontend was already written to expect and co-locates `status` with
   `data` for consistent error handling.
3. The `/gates` endpoint is a genuine functional gap: it has a named export, a
   TypeScript type (`GateResult[]`), and a UI consumer. A stub endpoint
   returning `[]` unblocks rendering without requiring DB schema changes.

**Scoping guard:** `GET /missions/{mission_id}/analytics` and
`GET /missions/{mission_id}/events` must remain bare until the raw-`fetch`
callsites in `api.ts` are updated in a coordinated change (requires human
approval on the protected file).

---

## 4. Ordered Change List (Option A) — NEEDS-APPROVAL

All changes are in `02_RUNTIME/api/main.py` unless noted.

**Step 1 — Add envelope helper** (insert after imports, before `@asynccontextmanager`):
```python
def _ok(payload):
    """Wrap a response payload in the standard {status, data} envelope."""
    return {"status": "ok", "data": payload}
```

**Step 2 — Wrap `GET /health`** (main.py:100-101):
```python
@app.get("/health")
async def health():
    return _ok({"status": "ok", "version": "2.0.0"})
```

**Step 3 — Wrap `POST /missions`** (main.py:222-251):
- Change `response_model=MissionResponse` to `response_model=dict`.
- Change final `return MissionResponse(**data)` to `return _ok(data)`.

**Step 4 — Wrap `GET /missions`** (main.py:254-258):
- Change `response_model=list[MissionResponse]` to `response_model=dict`.
- Change return to `return _ok([json.loads(r[0]) for r in rows])`.

**Step 5 — Wrap `GET /missions/{mission_id}`** (main.py:261-267):
- Change `response_model=MissionResponse` to `response_model=dict`.
- Change return to `return _ok(json.loads(row[0]))`.

**Step 6 — Add `GET /missions/{mission_id}/gates`** (insert after step 5):
```python
@app.get("/missions/{mission_id}/gates")
async def get_mission_gates(
    mission_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Gates stub: returns empty list until gate engine is wired to DB."""
    async with db.execute(
        "SELECT mission_id FROM missions WHERE mission_id = ?", (mission_id,)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Mission not found")
    return _ok([])
```

**Step 7 — Wrap `POST /missions/{mission_id}/synthesize`** (main.py:398-455):
- Change `response_model=AgentLeadResponse` to `response_model=dict`.
- Change `return AgentLeadResponse(...)` to `return _ok(AgentLeadResponse(...).model_dump())`.

**Step 8 — Wrap `POST /beads`** (main.py:458-477):
- Change `response_model=BeadResponse` to `response_model=dict`.
- Change `return BeadResponse(**data)` to `return _ok(data)`.

**Step 9 — Wrap `GET /beads`** (main.py:480-484):
- Change `response_model=list[BeadResponse]` to `response_model=dict`.
- Change return to `return _ok([json.loads(r[0]) for r in rows])`.

**Step 10 — Wrap agent endpoints** (main.py:506-612):
For each of: `POST /agents`, `GET /agents`, `GET /agents/{agent_id}`,
`POST /agents/{agent_id}/executions`, `POST /agents/{agent_id}/promote`:
- Change `response_model` annotations to `dict`.
- Change `return _agent_data_to_response(data)` to
  `return _ok(_agent_data_to_response(data).model_dump())`.

**Step 11 — Fix `GET /agents/meta/level-thresholds`** (main.py:610-612):
- Change `return {"data": _LEVEL_THRESHOLDS}` to `return _ok(_LEVEL_THRESHOLDS)`.

**Step 12 — Leave unwrapped (coordinate separately):**
- `GET /missions/{mission_id}/analytics` (main.py:315-395)
- `GET /missions/{mission_id}/events` (main.py:294-312)
- `POST /missions/{mission_id}/events` (main.py:270-291)

These are consumed by raw `fetch` in `api.ts` without envelope unwrapping.
Changing them requires a coordinated update to the protected `api.ts` file.

---

## 5. Manual Test Plan

### 5a. curl against `:8787` (after Option A is applied)

```bash
# 1. Health -- expect { "status": "ok", "data": { "status": "ok", "version": "2.0.0" } }
curl -s http://localhost:8787/health | python -m json.tool

# 2. List missions -- expect { "status": "ok", "data": [ ... ] }
curl -s http://localhost:8787/missions | python -m json.tool

# 3. Create mission -- expect { "status": "ok", "data": { "mission_id": "CHR-...", ... } }
curl -s -X POST http://localhost:8787/missions \
  -H "Content-Type: application/json" \
  -d '{"objective":"test reconciliation","agent_role":"agent_lead","autonomy_level":"L1","confidence_required":75.0}' \
  | python -m json.tool

# 4. Gates stub -- expect { "status": "ok", "data": [] }
curl -s http://localhost:8787/missions/<mission_id>/gates | python -m json.tool

# 5. Gates 404 -- expect HTTP 404 with detail "Mission not found"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8787/missions/FAKE-0000/gates

# 6. List beads -- expect { "status": "ok", "data": [ ... ] }
curl -s http://localhost:8787/beads | python -m json.tool

# 7. Level thresholds -- expect { "status": "ok", "data": { "0": {...}, "1": {...}, ... } }
curl -s http://localhost:8787/agents/meta/level-thresholds | python -m json.tool

# 8. Analytics (must remain bare -- do not wrap until api.ts raw fetch updated)
#    expect bare MissionAnalyticsResponse JSON with no envelope
curl -s http://localhost:8787/missions/<mission_id>/analytics | python -m json.tool

# 9. Events (must remain bare until api.ts raw fetch updated)
curl -s "http://localhost:8787/missions/<mission_id>/events" | python -m json.tool
```

### 5b. Console smoke test (browser at http://localhost:3000)

1. Open browser dev-tools Network tab.
2. Load the Command Center page.
3. Verify the Missions panel populates with a list (not empty, not an error state).
4. Verify the Beads panel lists beads.
5. Verify the Agents panel lists agent profiles.
6. Verify the Health indicator shows "ok" rather than "unavailable".
7. Click into any mission; verify the Gates sub-panel renders an empty list
   (not a network error -- empty array is the correct stub response).
8. Confirm no `TypeError: Cannot read properties of undefined (reading 'data')`
   errors appear in the browser console.
9. Quick sanity: verify theme switching still works (unrelated to this change).

---

## 6. Execution Gate

**NEEDS-APPROVAL** — this document is DESIGN ONLY. No code has been changed.

Before executing Option A a human operator must:

1. Review and approve this design note.
2. Decide whether to also update the two raw-`fetch` callsites in `api.ts`
   (analytics line 245, events line 283) so those endpoints can also be wrapped
   in the same pass.
3. Decide on `response_model` annotation strategy: remove them, change to
   `dict`, or introduce a generic `EnvelopeResponse[T]` Pydantic model.
4. Execute or delegate the ordered changes in Section 4.
5. Run the test plan in Section 5 and confirm all panels are operational before
   marking this resolved.
