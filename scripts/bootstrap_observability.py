#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
from common_harness import write_json,utc_now

def touch(path, content):
    if not path.exists(): path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding='utf-8')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root', default='.'); args=ap.parse_args(); root=Path(args.repo_root).resolve()
    for d in ['00_META/observability','00_META/queues','.chromatic/locks','00_META/observability/reports']: (root/d).mkdir(parents=True, exist_ok=True)
    write_json(root/'.chromatic/session_state.json', {'initialized_at':utc_now(),'repo':root.name,'status':'active'}); write_json(root/'.chromatic/active_writers.json', {'updated_at':utc_now(),'claims':{}}); touch(root/'00_META/observability/ERROR_LOG.jsonl',''); touch(root/'00_META/queues/ERROR_REMEDIATION_QUEUE.md','# Error Remediation Queue\n\n| ID | Status | Priority | Source Event | Category | Severity | Suggested Owner | Task | Definition of Done |\n|---|---|---:|---|---|---|---|---|---|\n')
    subprocess.run([sys.executable, str(root/'scripts/log_harness_event.py'),'--repo-root',str(root),'--event-type','info','--severity','info','--category','manual_note','--status','resolved','--surface','manual','--raw-excerpt','Observability bootstrap completed.'], check=False)
    print('Chromatic Harness observability initialized at '+str(root))
if __name__=='__main__': main()
