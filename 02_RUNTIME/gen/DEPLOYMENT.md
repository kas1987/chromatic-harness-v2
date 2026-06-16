# Gen Deployment Guide

## Prerequisites

- [Fly.io account](https://fly.io)
- [Fly CLI installed](https://fly.io/docs/hands-on/install-flyctl/)
- Docker (optional, for local testing)

## Deployment Steps

### 1. Authenticate with Fly

```bash
fly auth login
```

### 2. Create Fly Application

If you haven't already created the app:

```bash
cd gen
fly launch --no-deploy
```

This creates:
- A Fly app named `gen-orchestrator` (or your choice)
- `fly.toml` configuration file

### 3. Set Environment Secrets

```bash
fly secrets set GEN_TOKEN=your-very-secure-random-token
fly secrets set DATABASE_PATH=/var/lib/gen/gen.db
fly secrets set NODE_ENV=production
```

Generate a secure token:
```bash
openssl rand -hex 32
```

### 4. Deploy

```bash
fly deploy
```

Watch deployment progress:
```bash
fly logs
```

### 5. Verify Deployment

Test the health endpoint:
```bash
curl https://gen-orchestrator.fly.dev/health
```

Test with authentication:
```bash
curl -H "Authorization: Bearer your-token" \
  https://gen-orchestrator.fly.dev/health
```

### 6. Configure Claude Integration

In your Claude Code `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": {
      "url": "https://gen-orchestrator.fly.dev/hooks/pretool",
      "timeout_ms": 5000,
      "fail_open": true
    }
  }
}
```

## Monitoring

### View Logs

```bash
fly logs -a gen-orchestrator
```

### Check Status

```bash
fly status -a gen-orchestrator
```

### View Metrics

```bash
fly metrics -a gen-orchestrator
```

## Database

### Persistent Volume

Gen uses a persistent volume to store the SQLite database:

```bash
# View volumes
fly volumes list -a gen-orchestrator

# Inspect database
fly ssh console -a gen-orchestrator
# Inside console:
sqlite3 /var/lib/gen/gen.db ".tables"
```

### Backup

Export events for backup:

```bash
fly ssh console -a gen-orchestrator
sqlite3 /var/lib/gen/gen.db "SELECT * FROM pretool_events;" > events-backup.csv
exit
```

## Scaling

### Increase Resources

```bash
fly scale memory 256 -a gen-orchestrator
fly scale count 2 -a gen-orchestrator
```

### Regional Deployment

Change `primary_region` in `fly.toml`:

```toml
primary_region = "sfo"  # San Francisco
# or
primary_region = "jnb"  # Johannesburg
```

Then redeploy:
```bash
fly deploy
```

## Troubleshooting

### Health Check Failing

Ensure:
1. Server is listening on port 3000
2. `/health` endpoint is accessible without auth
3. Database is initialized

```bash
fly logs -a gen-orchestrator | grep health
```

### Authentication Errors

Verify the token:
```bash
TOKEN=$(fly secrets list -a gen-orchestrator | grep GEN_TOKEN | awk '{print $2}')
curl -H "Authorization: Bearer $TOKEN" https://gen-orchestrator.fly.dev/health
```

### Database Errors

Check database file exists and is writable:
```bash
fly ssh console -a gen-orchestrator
ls -la /var/lib/gen/
```

## Production Checklist

- [ ] GEN_TOKEN is set to a strong random value
- [ ] Health check is passing
- [ ] Logs are being captured
- [ ] Database is on persistent volume
- [ ] Claude integration is configured
- [ ] Backup strategy is in place
- [ ] Monitoring alerts are configured

## Rollback

If deployment has issues, rollback to previous version:

```bash
fly releases -a gen-orchestrator
fly releases rollback <version> -a gen-orchestrator
```

## Support

For issues:
1. Check logs: `fly logs -a gen-orchestrator`
2. Verify config: `fly config show`
3. Test locally: `npm run dev`
