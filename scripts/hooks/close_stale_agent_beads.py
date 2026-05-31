import datetime
import json
import shutil
import subprocess
import sys

STALE_MINUTES = 60


def _find_bd():
    for name in ("bd.cmd", "bd.exe", "bd"):
        found = shutil.which(name)
        if found:
            return found
    return None


BD = _find_bd()
if BD is None:
    sys.exit(0)  # fail-open: bd not installed, skip sweep

result = subprocess.run(
    [BD, "list", "--status", "in_progress", "--limit", "0"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    shell=False,
)

ids = [
    line.strip().split()[1]
    for line in result.stdout.splitlines()
    if "[agent]" in line and len(line.strip().split()) >= 2
]


def _is_stale(bead_id):
    """Return True if the bead is old enough to be swept (>STALE_MINUTES) or has no started_at."""
    try:
        show_result = subprocess.run(
            [BD, "show", bead_id, "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        data = json.loads(show_result.stdout)
        # bd show --json returns an array
        if isinstance(data, list):
            data = data[0] if data else {}
        started_at = data.get("started_at")
        if not started_at:
            return True  # no timestamp → treat as stale
        parsed = datetime.datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        return (now - parsed).total_seconds() > STALE_MINUTES * 60
    except Exception:
        return True  # fail-open: if we can't determine age, treat as stale


stale_ids = [bid for bid in ids if _is_stale(bid)]

if not stale_ids:
    sys.exit(0)

try:
    subprocess.run(
        [BD, "close"] + stale_ids + ["--reason", "session-end sweep", "--quiet"],
        check=False,
        shell=False,
    )
except Exception:
    pass  # fail-open: bd failure must never break SessionEnd
