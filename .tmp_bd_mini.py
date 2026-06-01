import json
import re
import pathlib

raw = pathlib.Path(".tmp_bd_payload.json").read_text(encoding="utf-8")
obj = None
try:
    obj = json.loads(raw)
except Exception:
    rows = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    obj = rows


def unwrap(x):
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        for k in [
            "items",
            "results",
            "data",
            "ready",
            "tasks",
            "issues",
            "tickets",
            "nodes",
        ]:
            if isinstance(x.get(k), list):
                return x[k]
        for v in x.values():
            if isinstance(v, list):
                return v
    return []


items = unwrap(obj)


def g(d, ks):
    for k in ks:
        if isinstance(d, dict) and d.get(k) is not None:
            return d.get(k)
    return ""


norm = []
for i, it in enumerate(items):
    if isinstance(it, dict):
        norm.append(
            {
                "i": i,
                "id": str(g(it, ["id", "key", "issue_id", "ticket", "uid", "number"])),
                "title": str(
                    g(it, ["title", "summary", "name", "text", "description"])
                ),
                "status": str(g(it, ["status", "state", "workflow_state"])),
            }
        )
    else:
        s = str(it)
        norm.append({"i": i, "id": s, "title": s, "status": ""})

total = len(norm)
ready = sum(1 for x in norm if re.search(r"\bready\b", x["status"], re.I)) or (
    total if total else 0
)
open_ = sum(
    1
    for x in norm
    if not re.search(
        r"\b(closed|done|resolved|cancelled|canceled)\b", x["status"], re.I
    )
) or (total if total else 0)
flagged = set()
groups = []


def add(n, idx):
    idx = [i for i in idx if 0 <= i < total]
    if not idx:
        return
    for i in idx:
        flagged.add(i)
    ex = []
    for i in idx[:1]:
        ex.append({"id": norm[i]["id"], "title": norm[i]["title"][:80]})
    groups.append({"pattern": n, "count": len(idx), "examples": ex})


add(
    "malformed_id_format",
    [
        x["i"]
        for x in norm
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]*-\d+$", x["id"] or "")
    ],
)
add(
    "temp_or_import_artifact",
    [
        x["i"]
        for x in norm
        if re.search(
            r"(tmp|temp|import|dummy|sample|test|wip|backup|copy of)",
            (x["id"] + " " + x["title"]).lower(),
        )
    ],
)
add(
    "non_actionable_title",
    [
        x["i"]
        for x in norm
        if len(x["title"].strip()) < 4
        or x["title"].strip().lower()
        in {"tbd", "todo", "misc", "n/a", "none", "placeholder"}
    ],
)
from collections import defaultdict

b = defaultdict(list)
for x in norm:
    t = " ".join(x["title"].lower().split())
    if t:
        b[t].append(x["i"])
for t, idx in b.items():
    if len(idx) > 1:
        add("duplicate_title::" + t[:24], idx)
p = defaultdict(list)
for x in norm:
    m = re.match(r"^([A-Za-z][A-Za-z0-9_]*)-", x["id"] or "")
    if m:
        p[m.group(1).lower()].append(x["i"])
for k, idx in sorted(p.items(), key=lambda kv: len(kv[1]), reverse=True)[:5]:
    if len(idx) >= 3:
        add("duplicate_prefix::" + k, idx)
add(
    "file_or_path_artifact_in_title",
    [
        x["i"]
        for x in norm
        if re.search(r"(\.csv|\.json|\.xlsx|\.sql|/|\\\\)", x["title"].lower())
    ],
)
groups = sorted(groups, key=lambda z: z["count"], reverse=True)[:10]
out = {
    "total_items": total,
    "open_items_estimate": open_,
    "ready_items_estimate": ready,
    "estimated_polluted_count": len(flagged),
    "top_pattern_groups": groups,
}
print(json.dumps(out, separators=(",", ":")))
