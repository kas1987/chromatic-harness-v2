# Local Service Security (GH #87)

## Overview

Several AI/ML services run locally on the development machine.  This document
captures their authentication posture, network exposure, and secure configuration
defaults.  **All auditing is read-only** — this document and `scripts/service_auth_audit.py`
never modify service configs.

## Services in Scope

| Service    | Default Port(s)      | Default Bind   | Has Auth by Default |
|------------|----------------------|----------------|---------------------|
| Ollama     | 11434                | 127.0.0.1      | No (localhost trust)|
| Neo4j HTTP | 7474                 | 127.0.0.1      | No (Community Ed.)  |
| Neo4j Bolt | 7687                 | 127.0.0.1      | No (Community Ed.)  |
| ChromaDB   | 8000                 | 127.0.0.1      | No                  |
| ComfyUI    | 8188                 | 127.0.0.1      | No                  |

## Risk Classification

| Bind Address | Auth Enabled | Risk Level  |
|--------------|--------------|-------------|
| 0.0.0.0      | Any          | CRITICAL    |
| 127.0.0.1    | No           | LOW         |
| 127.0.0.1    | Yes          | OK          |
| Not running  | N/A          | OK          |

## Per-Service Hardening

### Ollama (port 11434)

**Default behavior:** Binds to `127.0.0.1` — safe by default.

**Risk:** Setting `OLLAMA_HOST=0.0.0.0` exposes the API to the local network
with no authentication, allowing any host to run models and exfiltrate data.

**Secure configuration:**
```bash
# Do NOT set:
# OLLAMA_HOST=0.0.0.0

# Safe (explicit):
OLLAMA_HOST=127.0.0.1 ollama serve
```

**Validation:**
```bash
# Should NOT return a connection from a remote IP:
curl http://127.0.0.1:11434/api/tags
```

### Neo4j (ports 7474, 7687)

**Default behavior:** Community Edition defaults vary by version; some installs
default to `neo4j`/`neo4j` credentials requiring a password change on first login.

**Risk:** If password was never changed or auth is disabled in `neo4j.conf`, the
database is accessible to any process on the machine.

**Secure configuration:**
```properties
# neo4j.conf
dbms.connector.http.listen_address=127.0.0.1:7474
dbms.connector.bolt.listen_address=127.0.0.1:7687
dbms.security.auth_enabled=true
```

**Validation:**
```bash
# Should require credentials:
curl -u neo4j:neo4j http://localhost:7474/db/neo4j/tx
```

### ChromaDB (port 8000)

**Default behavior:** No authentication.  Binds to `0.0.0.0` by default in some
versions.

**Risk:** Vector store data (embeddings, metadata, document content) is accessible
without credentials.

**Secure configuration:**
```bash
# Always pass --host:
chroma run --host 127.0.0.1 --port 8000

# Or set env var:
CHROMA_SERVER_HOST=127.0.0.1
```

**Validation:**
```bash
curl http://127.0.0.1:8000/api/v1/heartbeat
# Verify bind in netstat:
netstat -an | grep 8000
```

### ComfyUI (port 8188)

**Default behavior:** No authentication.  Some startup scripts pass `--listen 0.0.0.0`.

**Risk:** Full workflow execution interface exposed to the network; an attacker
could load malicious custom nodes or exfiltrate generated images.

**Secure configuration:**
```bash
# Restrict to localhost:
python main.py --listen 127.0.0.1 --port 8188

# Never use:
# python main.py --listen 0.0.0.0
```

## Running the Audit

```bash
# Full audit with artifact write:
python scripts/service_auth_audit.py

# JSON output:
python scripts/service_auth_audit.py --json

# Save artifact only:
python scripts/service_auth_audit.py --save
```

Artifacts written to: `07_LOGS_AND_AUDIT/security/service_auth_latest.json`

Exit code 1 if any service has CRITICAL risk (bound to 0.0.0.0).

## Validation Checklist

- [ ] Run `python scripts/service_auth_audit.py` — overall risk is OK or LOW
- [ ] No service shows `listen_address: 0.0.0.0` in the audit output
- [ ] Ollama: `OLLAMA_HOST` env var is unset or explicitly `127.0.0.1`
- [ ] Neo4j: `neo4j.conf` has `listen_address=127.0.0.1` for both connectors
- [ ] ChromaDB: started with `--host 127.0.0.1` or equivalent env var
- [ ] ComfyUI: started with `--listen 127.0.0.1`
- [ ] Windows Firewall inbound rules block external access to ports 7474, 7687, 8000, 8188, 11434

## Artifact Schema

`07_LOGS_AND_AUDIT/security/service_auth_latest.json`:

```json
{
  "schema_version": 1,
  "timestamp": "20260601T120000Z",
  "overall_risk": "ok",
  "services_running": 0,
  "critical_count": 0,
  "findings": [
    {
      "service": "ollama",
      "port": 11434,
      "running": false,
      "listen_address": null,
      "risk": "ok",
      "recommendation": "No action required."
    }
  ]
}
```
