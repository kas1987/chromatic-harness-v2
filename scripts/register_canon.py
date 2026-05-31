#!/usr/bin/env python3
"""Canon registry CLI — add, list, and version entries in canon_registry.yaml.

Usage:
  python scripts/register_canon.py --list
  python scripts/register_canon.py --add <candidate-name>
  python scripts/register_canon.py --version <entry-id>
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO / "00_SOURCE_OF_TRUTH" / "canon_registry.yaml"
CANDIDATES_DIR = REPO / ".agents" / "candidates"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Minimal YAML helpers (stdlib only — no PyYAML required)
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    """Load the registry YAML into a Python dict with an 'entries' list."""
    text = path.read_text(encoding="utf-8")
    # Collect header comments
    header_lines = []
    entry_lines = []
    in_entries = False
    for line in text.splitlines():
        if line.strip().startswith("entries:"):
            in_entries = True
        if not in_entries:
            header_lines.append(line)
        else:
            entry_lines.append(line)
    entries = _parse_entries_block("\n".join(entry_lines))
    return {"_header": "\n".join(header_lines), "entries": entries}


def _parse_entries_block(block: str) -> list[dict]:
    """Parse YAML entries block into list of dicts (one level, simple values)."""
    entries: list[dict] = []
    current: dict | None = None
    for line in block.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.strip().startswith("#"):
            continue
        if stripped.startswith("entries:"):
            continue
        # New entry starts with "  - id:"
        if re.match(r"^\s{2}-\s+\w+:", stripped):
            if current is not None:
                entries.append(current)
            current = {}
            # Parse the first key on the same line
            m = re.match(r"^\s{2}-\s+(\w[\w-]*):\s*(.*)", stripped)
            if m:
                _set_entry_field(current, m.group(1), m.group(2).strip())
        elif re.match(r"^\s{4,}(\w[\w-]*):\s*(.*)", stripped) and current is not None:
            m = re.match(r"^\s{4,}(\w[\w-]*):\s*(.*)", stripped)
            if m:
                _set_entry_field(current, m.group(1), m.group(2).strip())
    if current is not None:
        entries.append(current)
    return entries


def _set_entry_field(entry: dict, key: str, raw: str) -> None:
    """Parse a scalar or list value and store it in entry."""
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if inner:
            entry[key] = [x.strip().strip('"').strip("'") for x in inner.split(",")]
        else:
            entry[key] = []
    elif raw == "null":
        entry[key] = None
    else:
        entry[key] = raw.strip('"').strip("'")


def _dump_yaml(data: dict, path: Path) -> None:
    """Serialise the registry dict back to YAML."""
    lines: list[str] = []
    if data.get("_header"):
        lines.append(data["_header"])
    lines.append("")
    lines.append("entries:")
    for entry in data["entries"]:
        first = True
        for k, v in entry.items():
            if isinstance(v, list):
                val_str = "[" + ", ".join(v) + "]"
            elif v is None:
                val_str = "null"
            else:
                val_str = f'"{v}"' if any(c in str(v) for c in ": #[]{}") else str(v)
            if first:
                lines.append(f"  - {k}: {val_str}")
                first = False
            else:
                lines.append(f"    {k}: {val_str}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Frontmatter parser (mirrors promote_to_wiki.py)
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_list(data: dict) -> int:
    entries = data["entries"]
    if not entries:
        print("Registry is empty.")
        return 0
    col_w = [20, 40, 8, 12, 12]
    header = (
        f"{'ID':<{col_w[0]}} {'TITLE':<{col_w[1]}} {'VER':<{col_w[2]}}"
        f" {'STATUS':<{col_w[3]}} {'PROMOTED_AT':<{col_w[4]}}"
    )
    print(header)
    print("-" * sum(col_w + [4]))
    for e in entries:
        eid = str(e.get("id", ""))[: col_w[0]]
        title = str(e.get("title", ""))[: col_w[1]]
        ver = str(e.get("version", ""))[: col_w[2]]
        status = str(e.get("status", ""))[: col_w[3]]
        promoted = str(e.get("promoted_at", ""))[: col_w[4]]
        print(
            f"{eid:<{col_w[0]}} {title:<{col_w[1]}} {ver:<{col_w[2]}}"
            f" {status:<{col_w[3]}} {promoted:<{col_w[4]}}"
        )
    print(f"\nTotal: {len(entries)} entries")
    return 0


def cmd_add(data: dict, name: str) -> int:
    candidate_path = CANDIDATES_DIR / f"{name}.md"
    if not candidate_path.exists():
        # Try exact file match
        matches = list(CANDIDATES_DIR.glob(f"*{name}*.md"))
        matches = [m for m in matches if m.name != "SCHEMA.md"]
        if len(matches) == 1:
            candidate_path = matches[0]
            name = candidate_path.stem
        else:
            print(f"ERROR: candidate file not found: {candidate_path}", file=sys.stderr)
            if matches:
                print(
                    f"  Possible matches: {[m.name for m in matches]}", file=sys.stderr
                )
            return 1

    text = candidate_path.read_text(encoding="utf-8", errors="replace")
    meta = _parse_frontmatter(text)

    # Determine version number (find existing entries with same base name)
    existing_ids = [e.get("id", "") for e in data["entries"]]
    version_n = 1
    for eid in existing_ids:
        m = re.match(rf"^{re.escape(name)}-v(\d+)$", str(eid))
        if m:
            version_n = max(version_n, int(m.group(1)) + 1)

    new_id = f"{name}-v{version_n}"

    # Extract first source_id from frontmatter
    raw_source_ids = meta.get("source_ids", "")
    source_bead: str | None = None
    if raw_source_ids:
        m2 = re.search(r"[\w-]+", raw_source_ids.strip("[]"))
        if m2:
            source_bead = m2.group(0)

    entry: dict = {
        "id": new_id,
        "title": meta.get("suggested_use", name.replace("-", " ").title()),
        "version": "1.0",
        "source_type": "candidate",
        "source_ref": f".agents/candidates/{candidate_path.name}",
        "source_bead": source_bead,
        "promoted_at": date.today().isoformat(),
        "promoted_by": "agent",
        "tags": [],
        "status": "active",
    }

    # Parse tags if present
    raw_tags = meta.get("tags", "")
    if raw_tags and raw_tags not in ("[]", ""):
        entry["tags"] = [
            t.strip().strip('"').strip("'")
            for t in raw_tags.strip("[]").split(",")
            if t.strip()
        ]

    data["entries"].append(entry)
    _dump_yaml(data, REGISTRY_PATH)
    print(f"Added: {new_id}  (source_bead: {source_bead})")
    return 0


def cmd_version(data: dict, entry_id: str) -> int:
    for entry in data["entries"]:
        if entry.get("id") == entry_id:
            ver_str = str(entry.get("version", "1.0"))
            try:
                parts = ver_str.split(".")
                parts[-1] = str(int(parts[-1]) + 1)
                new_ver = ".".join(parts)
            except (ValueError, IndexError):
                new_ver = ver_str + ".1"
            entry["version"] = new_ver
            _dump_yaml(data, REGISTRY_PATH)
            print(f"Bumped {entry_id}: {ver_str} → {new_ver}")
            return 0
    print(f"ERROR: entry '{entry_id}' not found", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Canon registry CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all registry entries")
    group.add_argument(
        "--add", metavar="CANDIDATE_NAME", help="Add a candidate to the registry"
    )
    group.add_argument(
        "--version", metavar="ENTRY_ID", help="Bump version of an existing entry"
    )
    args = parser.parse_args()

    if not REGISTRY_PATH.exists():
        print(f"ERROR: registry not found: {REGISTRY_PATH}", file=sys.stderr)
        return 1

    data = _load_yaml(REGISTRY_PATH)

    if args.list:
        return cmd_list(data)
    elif args.add:
        return cmd_add(data, args.add)
    elif args.version:
        return cmd_version(data, args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
