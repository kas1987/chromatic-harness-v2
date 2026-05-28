# Chromatic Harness v2 Deployment Guide

**Complete Option C System: Frontend + Backend + Safety**

## Quick Start (5 minutes)

### Prerequisites

- Node.js 18+ (for frontend)
- TypeScript 5+ (for backend)
- Git + GitHub CLI

### 1. Start Backend (Console Server + Magnets)

```bash
cd chromatic-harness-v2/02_RUNTIME
npx ts-node console-api/console-server.ts &
# Server running on http://localhost:3030
```

**Verifies:**
- ✓ Mission store initialized
- ✓ CMP gates ready
- ✓ Beads queue active
- ✓ Agent endpoints available

### 2. Start Frontend (React Dashboard)

```bash
cd chromatic-harness-v2/05_FRONTEND_CONSOLE
npm run dev
# Dashboard running on http://localhost:3000
```

**Opens:**
- http://localhost:3000 → Chromatic Harness Console
- 4-panel dashboard with mission board
- Agent trust profiles
- Magnet event streams
- Beads queue

### 3. Test the Pipeline

**Create a mission via dashboard:**

```
Objective: Add authentication middleware to API routes
Click GO
```

**Observe:**
1. Mission appears in left panel
2. Click mission → Magnet Event Stream updates
3. Confidence bar shows requirement
4. Beads queue populates with findings

## Complete Architecture

```
┌─────────────────────────────────────────────────┐
│          React Dashboard (port 3000)            │
│  ├─ Mission Board                               │
│  ├─ Magnet Events                               │
│  ├─ Agent Profiles                              │
│  └─ Beads Queue                                 │
└────────────┬────────────────────────────────────┘
             │ HTTP (fetch 5s polling)
             ↓
┌─────────────────────────────────────────────────┐
│   Console REST API (port 3030)                  │
│  ├─ POST /missions (create + intake gate)       │
│  ├─ GET /missions (list all)                    │
│  ├─ GET /missions/:id/gates                     │
│  ├─ GET /missions/:id/magnets                   │
│  ├─ GET /beads                                  │
│  ├─ GET /agents (trust profiles)                │
│  └─ GET /health                                 │
└────────────┬────────────────────────────────────┘
             │
      ┌──────┼──────┬──────┐
      ↓      ↓      ↓      ↓
   ┌──────────────────────────────┐
   │  Chromatic Harness Core      │
   ├──────────────────────────────┤
   │ CMP Governance Gates         │
   │ ├─ IntentGate                │
   │ ├─ ScopeGate                 │
   │ └─ ConfidenceGate            │
   │                              │
   │ Magnets Observability        │
   │ ├─ ExecutionMagnet           │
   │ ├─ CostMagnet                │
   │ ├─ ConfidenceMagnet          │
   │ └─ MagnetSynthesis           │
   │                              │
   │ Beads Intake                 │
   │ └─ Actions/Alerts/Learnings  │
   │                              │
   │ Sandbox Lab Safety           │
   │ └─ L0-L5 Trust Progression   │
   │                              │
   │ Runtime Adapters             │
   │ └─ roach-pi (+ custom)       │
   └──────────────────────────────┘
```

## Detailed Usage

### Create a Mission

**Via Dashboard:**
```
1. Type objective in input
2. Hit ENTER or click GO
3. Mission appears in left panel within 5 seconds
```

**Via API (curl):**
```bash
curl -X POST http://localhost:3030/missions \
  -H "Content-Type: application/json" \
  -d '{
    "packet": {
      "mission_id": "auth-middleware-01",
      "intent": "Add auth middleware to API",
      "scope": ["src/api/**/*"],
      "confidence_required": 0.75,
      "required_gates": ["intent", "scope"]
    }
  }'
```

### Monitor Execution

**Dashboard:**
- Select mission → Magnet Event Stream shows tool calls, retries, anomalies
- Confidence bar = required confidence for gate
- Stop conditions shown below confidence

**API:**
```bash
# Get mission details
curl http://localhost:3030/missions/auth-middleware-01

# Get magnet reports
curl http://localhost:3030/missions/auth-middleware-01/magnets

# Get gate decisions
curl http://localhost:3030/missions/auth-middleware-01/gates
```

### Review Beads

**Dashboard:** Beads Queue panel (bottom right)
- p0 (red) = critical alerts
- p1 (orange) = high priority findings
- p2 (blue) = medium priority
- p3 (gray) = low priority

**API:**
```bash
# Get all beads
curl http://localhost:3030/beads

# Update bead status
curl -X PATCH http://localhost:3030/beads/bead-id-123 \
  -H "Content-Type: application/json" \
  -d '{"status": "done"}'
```

### Agent Trust Profiles

**Dashboard:** Agent Trust Profiles panel
- Shows all registered agents
- Current trust level (L0-L5)
- Success rate %
- Risk score %
- Click agent for promotion history

**API:**
```bash
# List all agents
curl http://localhost:3030/agents

# Get single agent
curl http://localhost:3030/agents/openhands-001
```

## Configuration

### Environment Variables

**Frontend (.env.local):**
```
NEXT_PUBLIC_API_URL=http://localhost:3030
```

**Backend:**
- PORT: 3030 (hardcoded in ConsoleServer)
- Can be modified in console-server.ts line 32

### API Base URL

If running backend on different host:

**Frontend:**
```bash
export NEXT_PUBLIC_API_URL=http://10.0.0.5:3030
npm run dev
```

## Testing

### Unit Tests (Individual Phases)

```bash
# Phase 1: Runtime Adapter
npx ts-node 02_RUNTIME/test-phase1.ts

# Phase 3: Governance + Beads
npx ts-node 02_RUNTIME/test-phase3.ts

# Phase 4: Console API
npx ts-node 02_RUNTIME/test-phase4.ts

# Phase 5: Sandbox Lab
npx ts-node 02_RUNTIME/test-phase5.ts
```

### End-to-End Tests (Full Pipeline)

```bash
# Complete mission → gates → execution → beads flow
npx ts-node 02_RUNTIME/test-e2e.ts
```

## Troubleshooting

### Frontend can't connect to API

**Error:** "API error" badge shows red in dashboard

**Solution:**
```bash
# 1. Verify backend is running
ps aux | grep console-server

# 2. Check port is open
netstat -an | grep 3030

# 3. Check NEXT_PUBLIC_API_URL
echo $NEXT_PUBLIC_API_URL

# 4. Restart both:
pkill -f console-server
pkill -f "next dev"
# Then restart following Quick Start steps
```

### Missions not showing in dashboard

**Debug:**
```bash
# Check missions exist in API
curl http://localhost:3030/missions

# Check if polling is working (look at Network tab in DevTools)
# Should see requests every 5 seconds
```

### Agent profiles not loading

**Check:**
```bash
# Verify agent endpoints work
curl http://localhost:3030/agents

# Should return array of agents (may be empty or demo data)
```

## Performance Tuning

### Reduce API polling (battery/bandwidth)

**In src/app/page.tsx line 74-75:**
```typescript
const t = setInterval(refresh, 5000);  // Change 5000 to 10000 for 10s
```

### Increase magnet sensitivity

**In 02_RUNTIME/magnets/cost-magnet.ts:**
```typescript
const ANOMALY_THRESHOLD = 0.8;  // Lower = more alerts
```

### Reduce dashboard panel count

Edit src/app/page.tsx to remove unused panels for lighter rendering.

## Next Steps

### Phase 6.5: Real-Time Events (WebSocket)

Replace HTTP polling with WebSocket for instant magnet events:
```bash
# Frontend subscribes to mission events
ws://localhost:3030/missions/:id/events

# Server pushes magnet reports in real-time
```

### Phase 7: Mission Replay

Add historical analysis dashboard:
- Mission execution timeline
- Magnet score progression
- Gate decision history
- Performance analytics

### Phase 8: Multi-User Support

Add authentication layer:
- User login/registration
- Role-based access control (RBAC)
- Mission permission scoping
- Audit trail

## Production Deployment

### Docker

```dockerfile
# Backend
FROM node:18-alpine
WORKDIR /app
COPY 02_RUNTIME /app
RUN npm install -g ts-node typescript
EXPOSE 3030
CMD ["ts-node", "console-api/console-server.ts"]

# Frontend
FROM node:18-alpine as builder
WORKDIR /app
COPY 05_FRONTEND_CONSOLE /app
RUN npm install && npm run build

FROM node:18-alpine
COPY --from=builder /app/.next /app/.next
EXPOSE 3000
CMD ["npm", "start"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  backend:
    build: ./02_RUNTIME
    ports:
      - "3030:3030"
  frontend:
    build: ./05_FRONTEND_CONSOLE
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://backend:3030
    depends_on:
      - backend
```

## Support & Documentation

- **Architecture:** `OPTION_C_COMPLETE.md`
- **Phase Docs:** `02_RUNTIME/PHASE_*.md` (1-6)
- **API Spec:** `02_RUNTIME/console-api/console-server.ts`
- **Source of Truth:** `00_SOURCE_OF_TRUTH/CHROMATIC_HARNESS_MANIFEST.md`

---

**Chromatic Harness v2 is ready for deployment and testing.**
