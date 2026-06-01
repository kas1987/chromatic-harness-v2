#!/usr/bin/env python3
"""Tamper-evident log integrity checker (GH #85 / chromatic-harness-v2-snjm).

Implements SHA-256 hash chaining over audit log files.  Each log entry is
hashed individually; the chain hash is computed as:

    chain_hash[n] = SHA-256(chain_hash[n-1] + entry_hash[n])

The genesis entry uses a zero-padded prior hash ("0" * 64).

Usage:
    python scripts/log_integrity_check.py            # verify all targets
    python scripts/log_integrity_check.py --build    # rebuild chain manifest
    python scripts/log_integrity_check.py --json     # print full JSON result
    python scripts/log_integrity_check.py --target telemetry  # one file only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "security"
MANIFEST_PATH = ARTIFACT_DIR / "log_integrity_latest.json"

# Log files to cover with hash chains
LOG_TARGETS: dict[str, Path] = {
    "telemetry": REPO / "05_REPORTS" / "telemetry.jsonl",
    "token_governance": REPO / "07_LOGS_AND_AUDIT" / "token_governance" / "history.jsonl",
    "drift_history": REPO / "07_LOGS_AND_AUDIT" / "drift" / "history.jsonl",
}

GENESIS_HASH = "0" * 64


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry_bytes(raw_line: str) -> bytes:
    """Canonical representation of a JSONL line for hashing.

    Re-encodes as sorted-key JSON so whitespace differences don't matter.
    Falls back to the raw line if the entry is not valid JSON.
    """
    try:
        obj = json.loads(raw_line)
        return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (json.JSONDecodeError, TypeError):
        return raw_line.encode("utf-8")


def _iter_lines(path: Path) -> Iterator[str]:
    """Yield non-empty lines from a JSONL file; tolerate missing file."""
    if not path.exists():
        return
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.rstrip("\n")
            if stripped:
                yield stripped


def build_chain(path: Path) -> dict:
    """Build a SHA-256 hash chain over a JSONL file.

    Returns a chain descriptor with:
      - entry_count: number of entries hashed
      - chain_hash:  final cumulative hash
      - entries:     list of per-entry hashes (omitted when >500 entries for size)
    """
    prior = GENESIS_HASH
    entries: list[dict] = []
    count = 0
    for raw in _iter_lines(path):
        count += 1
        entry_hash = _sha256(_entry_bytes(raw))
        chain_hash = _sha256((prior + entry_hash).encode("utf-8"))
        entries.append({"index": count, "entry_hash": entry_hash, "chain_hash": chain_hash})
        prior = chain_hash

    return {
        "file": str(path.relative_to(REPO)).replace("\\", "/"),
        "entry_count": count,
        "chain_hash": prior if count > 0 else GENESIS_HASH,
        "genesis_hash": GENESIS_HASH,
        # Omit per-entry detail for very large logs to keep the manifest compact
        "entries": entries if count <= 500 else [],
        "entries_stored": count <= 500,
    }


def verify_chain(path: Path, stored: dict) -> dict:
    """Verify that the current file matches a previously stored chain descriptor.

    Returns a verification record with status 'ok', 'tampered', 'missing', or 'no_baseline'.
    """
    if not stored:
        return {"status": "no_baseline", "file": str(path.relative_to(REPO)).replace("\\", "/")}

    if not path.exists():
        return {"status": "missing", "file": stored.get("file", "?")}

    current = build_chain(path)

    if current["chain_hash"] == stored["chain_hash"] and current["entry_count"] == stored["entry_count"]:
        return {
            "status": "ok",
            "file": stored.get("file", "?"),
            "entry_count": current["entry_count"],
            "chain_hash": current["chain_hash"],
        }

    return {
        "status": "tampered",
        "file": stored.get("file", "?"),
        "expected_chain_hash": stored["chain_hash"],
        "actual_chain_hash": current["chain_hash"],
        "expected_entry_count": stored["entry_count"],
        "actual_entry_count": current["entry_count"],
    }


def load_manifest() -> dict:
    """Load existing manifest from disk; return empty dict on missing/corrupt."""
    try:
        if MANIFEST_PATH.exists():
            data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def save_manifest(manifest: dict) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def run_build() -> dict:
    """Build (or rebuild) the full chain manifest from all log targets."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    chains: dict[str, dict] = {}
    for name, path in LOG_TARGETS.items():
        chains[name] = build_chain(path)

    manifest = {
        "schema_version": 1,
        "built_at": ts,
        "targets": chains,
    }
    save_manifest(manifest)
    return manifest


def run_verify(target_filter: str | None = None) -> dict:
    """Verify current log files against the stored chain manifest.

    Returns a result dict with overall status and per-file findings.
    """
    manifest = load_manifest()
    stored_targets: dict = manifest.get("targets", {})

    findings: list[dict] = []
    tampered = 0

    targets = (
        {target_filter: LOG_TARGETS[target_filter]} if target_filter and target_filter in LOG_TARGETS else LOG_TARGETS
    )

    for name, path in targets.items():
        stored = stored_targets.get(name, {})
        result = verify_chain(path, stored)
        result["log_target"] = name
        findings.append(result)
        if result["status"] == "tampered":
            tampered += 1

    # Files not in targets but in stored manifest
    for name, stored in stored_targets.items():
        if name not in targets:
            findings.append({"log_target": name, "status": "not_checked", "note": "filtered out"})

    status = "ok" if tampered == 0 else "tampered"
    return {
        "schema_version": 1,
        "status": status,
        "tampered_count": tampered,
        "total_checked": len([f for f in findings if f["status"] != "not_checked"]),
        "findings": findings,
        "manifest_built_at": manifest.get("built_at", "no_manifest"),
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    }


def write_status_artifact(result: dict) -> Path:
    """Write verification result to the dashboard artifact location."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "last_verify": result,
                "built_at": load_manifest().get("built_at", "no_prior_build"),
                "targets": load_manifest().get("targets", {}),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    status_path = ARTIFACT_DIR / "log_integrity_latest.json"
    status_path.write_text(payload, encoding="utf-8")
    return status_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Tamper-evident log integrity checker (GH #85)")
    ap.add_argument("--build", action="store_true", help="Rebuild chain manifest from current log state")
    ap.add_argument("--json", action="store_true", help="Print full JSON result to stdout")
    ap.add_argument("--target", metavar="NAME", help=f"Verify single target: {list(LOG_TARGETS.keys())}")
    ap.add_argument("--no-artifact", action="store_true", help="Skip writing artifact file")
    args = ap.parse_args()

    if args.build:
        manifest = run_build()
        print(f"chain manifest built: {len(manifest['targets'])} targets")
        for name, chain in manifest["targets"].items():
            print(f"  {name}: {chain['entry_count']} entries -> {chain['chain_hash'][:16]}...")
        if args.json:
            print(json.dumps(manifest, indent=2))
        return 0

    # Verify mode
    result = run_verify(args.target)

    print(
        f"log integrity: {result['status'].upper()} ({result['tampered_count']} tampered / {result['total_checked']} checked)"
    )
    for f in result["findings"]:
        status_str = f["status"].upper()
        name = f.get("log_target", "?")
        count = f.get("entry_count", f.get("actual_entry_count", "?"))
        chain = (
            f.get("chain_hash", f.get("actual_chain_hash", "?"))[:16]
            if isinstance(f.get("chain_hash", f.get("actual_chain_hash")), str)
            else "?"
        )
        print(f"  [{status_str}] {name}: {count} entries, chain={chain}...")
        if f["status"] == "tampered":
            print(f"    expected: {f.get('expected_chain_hash', '')[:16]}...")
            print(f"    actual:   {f.get('actual_chain_hash', '')[:16]}...")

    if not args.no_artifact:
        artifact = write_status_artifact(result)
        print(f"  artifact:  {artifact}")

    if args.json:
        print(json.dumps(result, indent=2))

    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
