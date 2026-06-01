#!/usr/bin/env python3
"""
Portable closed-bead window query wrapper for bd workflows.

Reads .beads/issues.jsonl (the passive export that bd writes) and returns
closed beads without relying on unsupported bd list flags.

Usage:
    python bd_closed_window.py [--days N] [--status STATUS]

Examples:
    python bd_closed_window.py --days 30
    python bd_closed_window.py --status closed --days 7
"""

import json
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path


def get_closed_window(days=7, status="closed", project_root=None):
    """
    Query closed beads from the last N days.

    Args:
        days: Number of days to look back (default 7)
        status: Status filter (default 'closed')
        project_root: Path to project root (default: current directory)

    Returns:
        List of bead objects matching the filter
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)

    beads_file = project_root / ".beads" / "issues.jsonl"

    if not beads_file.exists():
        raise FileNotFoundError(f"Beads file not found: {beads_file}")

    # Calculate cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    cutoff_iso = cutoff_date.isoformat() + "Z"

    results = []

    # Read and filter JSONL
    with open(beads_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                bead = json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines
                continue

            # Filter by status
            if bead.get("status") != status:
                continue

            # Filter by date: use closed_at if available, otherwise updated_at
            timestamp_str = bead.get("closed_at") or bead.get("updated_at")
            if not timestamp_str:
                continue

            # Parse ISO 8601 timestamp
            try:
                # Remove timezone info for comparison
                if timestamp_str.endswith("Z"):
                    timestamp_str = timestamp_str[:-1]
                elif "+" in timestamp_str:
                    timestamp_str = timestamp_str.split("+")[0]
                elif timestamp_str.count("-") > 2:  # Has timezone offset
                    timestamp_str = timestamp_str.rsplit("-", 1)[0]

                timestamp = datetime.fromisoformat(timestamp_str)
            except (ValueError, AttributeError):
                continue

            # Check if within window
            if timestamp >= cutoff_date:
                results.append(
                    {
                        "id": bead.get("id"),
                        "title": bead.get("title"),
                        "status": bead.get("status"),
                        "closed_at": bead.get("closed_at"),
                        "updated_at": bead.get("updated_at"),
                    }
                )

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Query closed beads from bd workflow history"
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Number of days to look back (default: 7)"
    )
    parser.add_argument(
        "--status", type=str, default="closed", help="Status filter (default: closed)"
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args()

    try:
        results = get_closed_window(
            days=args.days, status=args.status, project_root=args.project_root
        )
        # Output as JSON array
        print(json.dumps(results, indent=2))
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
