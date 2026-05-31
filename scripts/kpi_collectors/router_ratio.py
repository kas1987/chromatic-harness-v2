#!/usr/bin/env python3
"""
KPI Stub: Router local-vs-cloud ratio
Target: reads router/ledger logs, computes local_calls / cloud_calls.

Instrumentation needed:
  - 07_LOGS_AND_AUDIT/budget/ledger.jsonl rows already have provider field.
  - Local providers: ollama, local, llama*, phi*, mistral* (T0/T1).
  - Cloud providers: anthropic, openai, gemini, openrouter, native_claude (T2-T4).
  - Map each ledger row's provider to local vs cloud, then compute ratio.

Current blocker: 49% of ledger rows have unknown provider — fix unknown_pct first.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH = ROOT / "07_LOGS_AND_AUDIT" / "budget" / "ledger.jsonl"

LOCAL_PROVIDERS = {
    "ollama",
    "local",
    "llama",
    "phi",
    "mistral",
    "lm_studio",
    "llamacpp",
}


def _is_local(provider: str) -> bool:
    p = (provider or "").lower()
    return any(p.startswith(lp) for lp in LOCAL_PROVIDERS)


def collect():
    try:
        lines = [
            l.strip()
            for l in LEDGER_PATH.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        local_count = cloud_count = unknown_count = 0
        for line in lines:
            try:
                row = json.loads(line)
            except Exception:
                continue
            prov = row.get("provider", "")
            if not prov or prov == "unknown":
                unknown_count += 1
            elif _is_local(prov):
                local_count += 1
            else:
                cloud_count += 1
        total = local_count + cloud_count
        if total == 0:
            return {
                "kpi": "router_local_vs_cloud_ratio",
                "value": None,
                "status": "not_instrumented",
                "note": f"No local/cloud provider labels found; {unknown_count} rows have unknown provider",
            }
        ratio = round(local_count / total, 4)
        return {
            "kpi": "router_local_vs_cloud_ratio",
            "value": ratio,
            "status": "ok",
            "note": f"local={local_count} cloud={cloud_count} unknown={unknown_count} ratio={ratio:.1%}",
        }
    except FileNotFoundError:
        return {
            "kpi": "router_local_vs_cloud_ratio",
            "value": None,
            "status": "not_instrumented",
            "note": "ledger.jsonl not found",
        }
    except Exception as e:
        return {
            "kpi": "router_local_vs_cloud_ratio",
            "value": None,
            "status": "error",
            "note": str(e),
        }


if __name__ == "__main__":
    print(json.dumps(collect()))
