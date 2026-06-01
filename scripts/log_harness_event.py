#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path
from common_harness import append_jsonl,event_id,git_state,repo_root,utc_now,validate_record
from redact_secrets import redact

def main():
    ap=argparse.ArgumentParser(description='Append a Chromatic Harness event to ERROR_LOG.jsonl')
    ap.add_argument('--repo-root'); ap.add_argument('--repo'); ap.add_argument('--event-id'); ap.add_argument('--event-type', default='error'); ap.add_argument('--severity', default='medium'); ap.add_argument('--category', default='unknown'); ap.add_argument('--status', default='open'); ap.add_argument('--surface', default='terminal'); ap.add_argument('--ide'); ap.add_argument('--agent'); ap.add_argument('--model'); ap.add_argument('--session-id'); ap.add_argument('--command'); ap.add_argument('--exit-code', type=int); ap.add_argument('--files-touched'); ap.add_argument('--error-signature'); ap.add_argument('--raw-excerpt'); ap.add_argument('--suspected-cause'); ap.add_argument('--action-taken'); ap.add_argument('--linked-fix'); ap.add_argument('--linked-learning'); ap.add_argument('--next-action'); ap.add_argument('--log-path', default='00_META/observability/ERROR_LOG.jsonl'); ap.add_argument('--route', action='store_true'); ap.add_argument('--include-git', action='store_true')
    args=ap.parse_args(); root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); raw,changed=redact(args.raw_excerpt or '')
    ev={'event_id':args.event_id or event_id(),'timestamp':utc_now(),'repo':args.repo or root.name,'workspace':str(root),'source':{'surface':args.surface,'ide':args.ide or '','agent':args.agent or '','model':args.model or '','session_id':args.session_id or os.environ.get('CHROMATIC_SESSION_ID','')},'event_type':args.event_type,'severity':args.severity,'category':args.category,'command':args.command or '','exit_code':args.exit_code,'files_touched':[f for f in (args.files_touched or '').split(',') if f],'error_signature':args.error_signature or '','raw_excerpt':raw,'redacted':changed,'suspected_cause':args.suspected_cause or '','action_taken':args.action_taken or '','status':args.status,'linked_fix':args.linked_fix,'linked_learning':args.linked_learning,'next_action':args.next_action or '','metadata':{'host':socket.gethostname(),'git':git_state(root) if args.include_git else {}}}
    errs=validate_record(ev)
    if errs:
        print('Invalid event:\n- '+'\n- '.join(errs), file=sys.stderr); return 2
    path=Path(args.log_path); path=path if path.is_absolute() else root/path; append_jsonl(path, ev); print(ev['event_id'])
    if args.route: subprocess.run([sys.executable, str(root/'scripts/route_event.py'), '--event-id', ev['event_id'], '--repo-root', str(root)], check=False)
    return 0
if __name__=='__main__': raise SystemExit(main())
