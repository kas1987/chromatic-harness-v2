#!/usr/bin/env python3
"""Generate a standardized Chromatic review resolution comment body.

This script prints the body. Pipe it into gh CLI if desired:
  python scripts/post_review_resolution.py --finding RF-1 --task NW-1 --agent Sentinel --status Resolved --files src/a.py --validation "pytest" | gh pr comment 42 --body-file -
"""
from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finding", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--status", default="Resolved")
    parser.add_argument("--confidence", default="unknown")
    parser.add_argument("--change", default="Scoped review finding addressed.")
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--validation", nargs="*", default=[])
    args = parser.parse_args()

    files = "\n".join(f"- `{f}`" for f in args.files) or "- None recorded"
    validation = "\n".join(f"- `{v}`" for v in args.validation) or "- Manual review required"
    body = f"""## Chromatic Review Resolution

**Finding:** {args.finding}  
**Queue Item:** {args.task}  
**Status:** {args.status}  
**Agent:** {args.agent}  
**Confidence:** {args.confidence}  

### Change made
{args.change}

### Validation
{validation}

### Files changed
{files}

### Notes
Patch was kept scoped to the review finding and governed by Chromatic Review Intake rules.
"""
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
