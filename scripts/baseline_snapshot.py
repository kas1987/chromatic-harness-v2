"""Baseline snapshot CLI — collect all KPIs, write snapshots, diff over time.

Usage:
    python scripts/baseline_snapshot.py               # print current values as ASCII table
    python scripts/baseline_snapshot.py --write        # write snapshot to 05_REPORTS/baselines/
    python scripts/baseline_snapshot.py --diff         # compare today vs most recent prior snapshot
    python scripts/baseline_snapshot.py --write --diff # write + diff
"""

import argparse
import importlib
import json
import pathlib
import sys
from datetime import date

COLLECTORS_DIR = pathlib.Path(__file__).parent / "kpi_collectors"
BASELINES_DIR = pathlib.Path(__file__).parent.parent / "05_REPORTS" / "baselines"

COLLECTOR_MODULES = [
    "cache_hit_rate",
    "router_ratio",
    "learning_application_rate",
    "context_budget_adherence",
    "mcp_count",
    "terminal_use",
    "pattern_count",
]


def run_collectors():
    """Import and run each collector; return dict of name -> result."""
    results = {}
    sys.path.insert(0, str(COLLECTORS_DIR.parent))
    for name in COLLECTOR_MODULES:
        try:
            mod = importlib.import_module(f"kpi_collectors.{name}")
            result = mod.collect()
        except Exception as exc:
            result = {"status": "error", "error": str(exc)}
        results[name] = result
    return results


def flatten_snapshot(results):
    """Flatten collector results into a single dict for snapshot storage."""
    flat = {}
    for collector, data in results.items():
        status = data.get("status", "unknown")
        flat[f"{collector}__status"] = status
        for k, v in data.items():
            if k == "status":
                continue
            flat[f"{collector}__{k}"] = v
    return flat


def print_table(results):
    """Print collector results as a human-readable ASCII table."""
    col_w = 32
    val_w = 48
    sep = "+" + "-" * (col_w + 2) + "+" + "-" * (val_w + 2) + "+"
    header = f"| {'Metric':<{col_w}} | {'Value':<{val_w}} |"
    print(sep)
    print(header)
    print(sep)
    for collector, data in results.items():
        status = data.get("status", "unknown")
        if status == "not_instrumented":
            val_str = "(not instrumented)"
        elif status == "error":
            val_str = f"ERROR: {data.get('error', '')}"
        else:
            # Print key=value pairs except status
            parts = [f"{k}={v}" for k, v in data.items() if k != "status"]
            val_str = "  ".join(parts) if parts else "ok"
        # Truncate if needed
        if len(val_str) > val_w:
            val_str = val_str[: val_w - 3] + "..."
        print(f"| {collector:<{col_w}} | {val_str:<{val_w}} |")
    print(sep)


def write_snapshot(flat, today_str):
    """Write snapshot to 05_REPORTS/baselines/YYYY-MM-DD.json."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BASELINES_DIR / f"{today_str}.json"
    payload = {"date": today_str, "metrics": flat}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def load_prior_snapshot(today_str):
    """Find and load the most recent snapshot before today."""
    if not BASELINES_DIR.exists():
        return None, None
    candidates = sorted(BASELINES_DIR.glob("????-??-??.json"))
    prior = [p for p in candidates if p.stem < today_str]
    if not prior:
        return None, None
    latest = prior[-1]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        return latest.stem, data.get("metrics", {})
    except Exception:
        return None, None


def print_diff(today_flat, prior_flat, prior_date):
    """Print a human-readable diff table between today and prior snapshot."""
    all_keys = sorted(set(list(today_flat.keys()) + list(prior_flat.keys())))
    col_w = 36
    v_w = 18
    sep = (
        "+"
        + "-" * (col_w + 2)
        + "+"
        + "-" * (v_w + 2)
        + "+"
        + "-" * (v_w + 2)
        + "+"
        + "-" * (v_w + 2)
        + "+"
    )
    header = f"| {'Metric':<{col_w}} | {'Before (' + prior_date + ')':<{v_w}} | {'After (today)':<{v_w}} | {'Delta':<{v_w}} |"
    print(f"\nDiff vs {prior_date}:")
    print(sep)
    print(header)
    print(sep)
    changed = 0
    for key in all_keys:
        before = prior_flat.get(key, "(absent)")
        after = today_flat.get(key, "(absent)")
        if before == after:
            continue
        changed += 1
        # Compute delta for numeric values
        delta = ""
        try:
            delta = str(round(float(after) - float(before), 3))
        except (TypeError, ValueError):
            delta = "changed"

        def _fmt(v):
            s = str(v)
            return s[: v_w - 3] + "..." if len(s) > v_w else s

        print(
            f"| {key:<{col_w}} | {_fmt(before):<{v_w}} | {_fmt(after):<{v_w}} | {delta:<{v_w}} |"
        )
    print(sep)
    if changed == 0:
        print("  (no changes detected)")
    else:
        print(f"  {changed} field(s) changed.")


def main():
    parser = argparse.ArgumentParser(description="Baseline KPI snapshot tool")
    parser.add_argument(
        "--write", action="store_true", help="Write snapshot to baselines dir"
    )
    parser.add_argument(
        "--diff", action="store_true", help="Diff today vs most recent prior snapshot"
    )
    args = parser.parse_args()

    today_str = date.today().isoformat()
    results = run_collectors()

    print_table(results)

    flat = flatten_snapshot(results)

    if args.write:
        out_path = write_snapshot(flat, today_str)
        print(f"\nSnapshot written to: {out_path}")

    if args.diff:
        # If --diff but not --write, still need today's flat data for comparison
        # (may or may not have been written)
        prior_date, prior_flat = load_prior_snapshot(today_str)
        if prior_flat is None:
            print("\nNo prior snapshot found to diff against.")
        else:
            print_diff(flat, prior_flat, prior_date)


if __name__ == "__main__":
    main()
