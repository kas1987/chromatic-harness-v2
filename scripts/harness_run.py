#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
import sys
import shlex
from pathlib import Path
from common_harness import append_jsonl,event_id,git_state,repo_root,utc_now,validate_record
from redact_secrets import redact

def main():
    ap=argparse.ArgumentParser(description='Run a command and log failed results to Harness observability.'); ap.add_argument('--repo-root'); ap.add_argument('--surface', default='terminal'); ap.add_argument('--agent', default=''); ap.add_argument('--model', default=''); ap.add_argument('--session-id', default=''); ap.add_argument('--severity-on-fail', default='medium'); ap.add_argument('--category-on-fail', default='command_failure'); ap.add_argument('--route', action='store_true'); ap.add_argument('command', nargs=argparse.REMAINDER); args=ap.parse_args()
    if not args.command: print('No command provided. Usage: python scripts/harness_run.py -- npm run build', file=sys.stderr); return 2
    cmd=args.command[1:] if args.command and args.command[0]=='--' else args.command; root=Path(args.repo_root).resolve() if args.repo_root else repo_root(); proc=subprocess.run(cmd, cwd=str(root), text=True, capture_output=True)
    if proc.stdout: print(proc.stdout, end='')
    if proc.stderr: print(proc.stderr, end='', file=sys.stderr)
    if proc.returncode!=0:
        excerpt,changed=redact((proc.stderr or proc.stdout or '')[-4000:])
        ev={'event_id':event_id(),'timestamp':utc_now(),'repo':root.name,'workspace':str(root),'source':{'surface':args.surface,'agent':args.agent,'model':args.model,'session_id':args.session_id},'event_type':'command_result','severity':args.severity_on_fail,'category':args.category_on_fail,'status':'open','command':' '.join(shlex.quote(x) for x in cmd),'exit_code':proc.returncode,'files_touched':[],'error_signature':f'command_failed_exit_{proc.returncode}','raw_excerpt':excerpt,'redacted':changed,'suspected_cause':'','action_taken':'command failure logged by harness_run.py','linked_fix':None,'linked_learning':None,'next_action':'route event for remediation','metadata':{'git':git_state(root)}}
        errs=validate_record(ev)
        if errs: print('Unable to log invalid event: '+str(errs), file=sys.stderr)
        else:
            append_jsonl(root/'00_META/observability/ERROR_LOG.jsonl', ev); print(f'\nHarness event logged: {ev["event_id"]}', file=sys.stderr)
            if args.route: subprocess.run([sys.executable, str(root/'scripts/route_event.py'),'--repo-root',str(root),'--event-id',ev['event_id']], check=False)
    return proc.returncode
if __name__=='__main__': raise SystemExit(main())
