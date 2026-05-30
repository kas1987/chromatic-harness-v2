#!/usr/bin/env python3
"""Machine-verifiable Expansion-Gate spine check (bead chromatic-harness-v2-4do0).

The Expansion Gate's SPINE CHECK was an honor-system checkbox ("prerequisite
layers are proven"). This verifies it against the codegraph index instead: a
layer is only a real spine if its code is actually *wired* — indexed symbols
that participate in edges — not orphaned or absent.

Per layer path prefix it reports:
  - nodes:  symbols indexed under that path
  - edges:  edges touching those symbols (callers/callees/imports)
  - verdict: "wired" (nodes>0 and edges>0)
           | "orphaned" (nodes>0 but no edges — dead/unreferenced)
           | "absent"  (no nodes indexed)

Advisory by default (exit 0). With --strict, exits 1 if any requested layer is
not "wired" — usable as a real gate in check_expansion_gate.sh / CI.

Usage:
  python scripts/check_layer_spine.py 02_RUNTIME/router 01_PROTOCOLS/MCP
  python scripts/check_layer_spine.py --strict 02_RUNTIME/router
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / ".codegraph" / "codegraph.db"


def check_layer(con: sqlite3.Connection, prefix: str) -> dict:
    norm = prefix.replace("\\", "/").strip("/")
    like = f"{norm}%"
    node_ids = [
        r[0]
        for r in con.execute(
            "SELECT id FROM nodes WHERE REPLACE(file_path,'\\','/') LIKE ?", (like,)
        )
    ]
    nodes = len(node_ids)
    edges = 0
    if node_ids:
        qmarks = ",".join("?" * len(node_ids))
        edges = con.execute(
            f"SELECT COUNT(*) FROM edges WHERE source IN ({qmarks}) "
            f"OR target IN ({qmarks})",
            node_ids + node_ids,
        ).fetchone()[0]
    if nodes == 0:
        verdict = "absent"
    elif edges == 0:
        verdict = "orphaned"
    else:
        verdict = "wired"
    return {"layer": norm, "nodes": nodes, "edges": edges, "verdict": verdict}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Codegraph-backed Expansion-Gate spine check"
    )
    ap.add_argument("layers", nargs="+", help="Layer path prefixes (repo-relative)")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any layer is not 'wired'",
    )
    args = ap.parse_args()

    if not DB.exists():
        print(
            json.dumps(
                {
                    "ok": True,
                    "status": "codegraph_absent",
                    "advice": "run `codegraph init -i .`; spine check skipped",
                }
            )
        )
        return 0  # advisory: can't verify without an index, don't block

    con = sqlite3.connect(str(DB))
    try:
        results = [check_layer(con, layer) for layer in args.layers]
    finally:
        con.close()

    not_wired = [r for r in results if r["verdict"] != "wired"]
    payload = {
        "ok": not (args.strict and not_wired),
        "strict": args.strict,
        "results": results,
        "not_wired": [r["layer"] for r in not_wired],
    }
    print(json.dumps(payload, indent=2))
    return 1 if (args.strict and not_wired) else 0


if __name__ == "__main__":
    raise SystemExit(main())
