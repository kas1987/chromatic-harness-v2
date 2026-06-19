# LOGHOUSE Server
**Full-featured audit report dashboard and API for Claude Code operations monitoring**

## Overview

LOGHOUSE is a web-based dashboard and REST API server that provides real-time visualization of Claude Code audit data, correlations, SWOT analysis, and action plan tracking.

**Features:**
- 📊 Real-time dashboard with metrics and alerts
- 🔍 Browse audit history and search functionality
- 🔗 Git correlation viewer (match commits to audit spikes)
- 💼 SWOT analysis explorer
- 🎯 Action plan tracker with progress monitoring
- 🚨 Anomaly detection and alert management
- 📤 Export data (JSON/CSV)
- 🔌 REST API for programmatic access

## Getting Started

### Prerequisites
- Node.js 16+ (download from [nodejs.org](https://nodejs.org))
- npm (comes with Node.js)

### Quick Start

**Option 1: Automated (Recommended)**

```bash
# Linux/Mac
./start-loghouse.sh

# Windows (double-click)
start-loghouse.bat
```

**Option 2: Manual**

```bash
cd LOGHOUSE_SERVER

# Install server dependencies
npm install

# Install & build client
cd client
npm install
npm run build
cd ..

# Start server
PORT=3333 node index.js
```

### Access the Server
- **Dashboard:** http://localhost:3333
- **API:** http://localhost:3333/api
- **Health:** http://localhost:3333/api/health

## Architecture

### Backend (Express.js)
- `index.js` — Main server and routing
- `data-loader.js` — LOGHOUSE file reader and parser
- `routes/api.js` — REST API endpoints
- `routes/health.js` — Server health checks

### Frontend (React)
- `App.jsx` — Main navigation and layout
- `pages/Dashboard.jsx` — Overview metrics
- `pages/AuditHistory.jsx` — Browse and search audits
- `pages/Correlations.jsx` — Git commit correlation
- `pages/SWOT.jsx` — SWOT analysis explorer
- `pages/ActionPlan.jsx` — Action tracking
- `pages/Alerts.jsx` — Anomaly alerts and thresholds

## API Endpoints

### Audit Reports
```
GET /api/audits/reports              — List all audit reports
GET /api/audits/latest               — Get latest audit
GET /api/audits/by-date/:date        — Get audit by date (YYYY-MM-DD)
GET /api/audits/search?q=:term       — Search reports
GET /api/audits/export/:format       — Export (json or csv)
```

### Analysis
```
GET /api/audits/correlations         — List correlation reports
GET /api/audits/swot                 — List SWOT analyses
GET /api/audits/git-correlation/:date — Get git commits for date
```

### Health
```
GET /api/health                      — Server and LOGHOUSE health
GET /api                             — Server info and endpoints
```

## Configuration

### Port
Set via environment variable:
```bash
PORT=3333 node index.js
```

### Data Location
LOGHOUSE automatically reads from:
```
chromatic-harness-v2/.artifacts/LOGHOUSE/
├── audits/
├── correlations/
├── swot/
└── schemas/
```

## Data Flow

```
audit.log (raw tool data)
    ↓
LOGHOUSE audit reports
    ├── audits/*.md (comprehensive)
    ├── correlations/*.md (git-matched)
    └── swot/*.md (strategic)
        ↓
    LOGHOUSE Server (index.js)
        ├── data-loader.js (parse markdown)
        ├── /api/audits/* (REST endpoints)
        └── /api/health (status)
            ↓
        React Dashboard (port 3333)
            ├── Dashboard
            ├── AuditHistory
            ├── Correlations
            ├── SWOT
            ├── ActionPlan
            └── Alerts
```

## Usage Examples

### View Dashboard
Open http://localhost:3333 in browser

### Query API
```bash
# Get latest audit
curl http://localhost:3333/api/audits/latest

# Search for "spike"
curl "http://localhost:3333/api/audits/search?q=spike"

# Export all reports as JSON
curl http://localhost:3333/api/audits/export/json > reports.json

# Get git commits for a date
curl http://localhost:3333/api/audits/git-correlation/2026-06-02

# Health check
curl http://localhost:3333/api/health
```

### Programmatic Access
```javascript
// JavaScript
fetch('/api/audits/latest')
  .then(r => r.json())
  .then(data => console.log(data.report));

// Python
import requests
resp = requests.get('http://localhost:3333/api/audits/latest')
print(resp.json()['report'])
```

## Troubleshooting

### Port 3333 Already in Use
Change port:
```bash
PORT=3334 node index.js
```

### React Build Missing
```bash
cd client
npm run build
cd ..
npm start
```

### Modules Not Found
```bash
npm install
cd client && npm install && cd ..
```

### Can't Access from Browser
Verify server is running:
```bash
curl http://localhost:3333/api
```

## Development

### Hot Reload (Backend)
```bash
npm install -g nodemon
nodemon index.js
```

### React Development Mode
```bash
cd client
npm start
```

## Deployment

### Production Build
```bash
cd client
npm run build
cd ..
PORT=3333 node index.js
```

### Docker (Optional)
```dockerfile
FROM node:18
WORKDIR /app
COPY . .
RUN npm install && cd client && npm install && npm run build && cd ..
EXPOSE 3333
CMD ["node", "index.js"]
```

## Performance

- **Memory:** ~50-100 MB (Node + React)
- **CPU:** Minimal (report serving, not compute)
- **Startup Time:** ~3-5 seconds
- **API Latency:** <100ms for most queries
- **Cache:** 60-second report cache to reduce file I/O

## Security

**Current:** Local-only access via http://localhost:3333

**For Network/Cloud Access:**
1. Add authentication (JWT/API key)
2. Use HTTPS/TLS
3. Implement CORS restrictions
4. Run behind reverse proxy (nginx, Caddy)
5. Set firewall rules

## Monitoring

### Health Endpoint
Check every 5 minutes:
```bash
curl http://localhost:3333/api/health | jq .status
```

### Alert Thresholds
Configure via **Alerts** page in dashboard:
- Daily tools threshold
- Peak hour threshold
- Sustained rate threshold
- Task tracking minimum
- Agent usage minimum

## Integration

### Slack Alerts (Future)
Webhook notifications for threshold violations

### GitHub Integration (Future)
Automatic PR correlation and link generation

### CI/CD Hooks (Future)
Trigger reports on deployment or test completion

## Support

### Logs
- Server: Console output
- API errors: Returned in response
- Client errors: Browser console (F12)

### Debugging
```bash
DEBUG=* node index.js  # Verbose output
```

## License
MIT

---

**LOGHOUSE Server v1.0** | Port 3333 | Local Access Only

Last Updated: 2026-06-19
