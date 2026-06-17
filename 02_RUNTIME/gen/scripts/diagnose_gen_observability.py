from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Iterable


EXPECTED_TABLES = {
    "routing_decisions": [
        "hook_event",
        "tool_name",
        "suggested_llm",
        "actual_llm",
        "pretool_routing_source",
        "routing_reconciliation",
        "prompt_intent",
        "prompt_scope",
        "intent_tool_coherence",
    ],
    "task_outcomes": [
        "tool_used",
        "tokens_used",
        "prompt_intent",
        "prompt_scope",
        "active_llm",
        "suggested_llm",
    ],
    "delegation_log": [
        "provider",
        "model",
        "success",
        "latency_ms",
        "failure_reason",
        "fallback_triggered",
        "resolved_by",
    ],
    "budget_states": [
        "agent_role",
        "tokens_used",
        "external_calls",
        "handoffs",
        "wall_time_seconds",
        "stopped",
        "stopped_reason",
    ],
    "cost_accuracy": [
        "model",
        "estimated_cost_usd",
        "actual_cost_usd",
        "accuracy_pct",
        "flagged",
    ],
}


def fetchall_dict(cur: sqlite3.Cursor, sql: str) -> list[dict]:
    cur.execute(sql)
    cols = [d[0] for d in cur.description or []]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def table_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    )
    return cur.fetchone() is not None


def first_value(rows: Iterable[dict], key: str, default=0):
    rows = list(rows)
    if not rows:
        return default
    value = rows[0].get(key)
    return default if value is None else value


def analyze_database(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    present_tables = {
        row["name"] for row in fetchall_dict(cur, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    }

    report: dict = {
        "database": str(db_path),
        "tables_present": sorted(present_tables),
        "row_counts": {},
        "schema_gaps": {},
        "usage": {},
        "offload_surfaces": {
            "whole_task": [
                {
                    "surface": "/api/delegate",
                    "when": "code or dispatch work with clear prompt boundaries",
                    "mode": "queue whole request, execute on selected provider, return final response with fallback chain",
                },
                {
                    "surface": "Hop middleware (local async / remote_mcp)",
                    "when": "opt-in prompts that should be fully rerouted to a destination skill or MCP",
                    "mode": "fire-and-forget dispatch with channel or remote MCP delivery; original request continues fail-open",
                },
            ],
            "interject_after_completion": [
                {
                    "surface": "session dispatch updates on /hooks/user-prompt",
                    "when": "a delegated task finishes and should add a status block back into the next user turn",
                    "mode": "pending updates are drained into the next prompt preamble",
                }
            ],
            "granular_delegation": [
                {
                    "surface": "pretool suggested_llm + session intent cache",
                    "when": "tool-by-tool provider steering is enough",
                    "mode": "keep main agent in control, only redirect model choice or next provider",
                }
            ],
        },
        "recommendations": [],
    }

    for table in EXPECTED_TABLES:
        if exists(cur, table):
            count = first_value(fetchall_dict(cur, f"SELECT COUNT(*) AS c FROM {table}"), "c")
            report["row_counts"][table] = count
            cols = table_columns(cur, table)
            missing = sorted(set(EXPECTED_TABLES[table]) - cols)
            if missing:
                report["schema_gaps"][table] = missing
        else:
            report["row_counts"][table] = None
            report["schema_gaps"][table] = sorted(EXPECTED_TABLES[table])

    if exists(cur, "task_outcomes"):
        report["usage"]["task_outcomes_by_tool"] = fetchall_dict(
            cur,
            """
            SELECT tool_used, COUNT(*) AS calls,
                   SUM(CASE WHEN succeeded = 1 THEN 1 ELSE 0 END) AS successes,
                   SUM(tokens_used) AS tokens
            FROM task_outcomes
            GROUP BY tool_used
            ORDER BY calls DESC, tool_used ASC
            LIMIT 25
            """,
        )

    if exists(cur, "routing_decisions"):
        report["usage"]["routing_by_tool"] = fetchall_dict(
            cur,
            """
            SELECT tool_name, COUNT(*) AS decisions,
                   SUM(CASE WHEN routing_reconciliation = 'match' THEN 1 ELSE 0 END) AS matches,
                   SUM(CASE WHEN routing_reconciliation = 'mismatch' THEN 1 ELSE 0 END) AS mismatches
            FROM routing_decisions
            GROUP BY tool_name
            ORDER BY decisions DESC, tool_name ASC
            LIMIT 25
            """,
        )
        report["usage"]["routing_provider_pairs"] = fetchall_dict(
            cur,
            """
            SELECT suggested_llm, actual_llm, COUNT(*) AS runs
            FROM routing_decisions
            GROUP BY suggested_llm, actual_llm
            ORDER BY runs DESC
            LIMIT 25
            """,
        )

    if exists(cur, "delegation_log"):
        report["usage"]["delegations_by_provider"] = fetchall_dict(
            cur,
            """
            SELECT provider,
                   COUNT(*) AS attempts,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS successes,
                   AVG(latency_ms) AS avg_latency_ms,
                   SUM(CASE WHEN fallback_triggered = 1 THEN 1 ELSE 0 END) AS fallback_triggers
            FROM delegation_log
            GROUP BY provider
            ORDER BY attempts DESC, provider ASC
            """,
        )
        report["usage"]["delegation_gateway_summary"] = {
            "correlation_note": (
                "Rows sharing the same trace_id are attempts for one POST /api/delegate job; "
                "pair with client sessionId via optional request body fields (see MODEL-DISPATCH-GATEWAY.md)."
            ),
            "window": "created_at > datetime('now', '-1 day') (SQLite)",
            "attempts_last_24h": first_value(
                fetchall_dict(
                    cur,
                    """
                    SELECT COUNT(*) AS c FROM delegation_log
                    WHERE created_at > datetime('now', '-1 day')
                    """,
                ),
                "c",
                0,
            ),
            "successes_last_24h": first_value(
                fetchall_dict(
                    cur,
                    """
                    SELECT COUNT(*) AS c FROM delegation_log
                    WHERE created_at > datetime('now', '-1 day') AND success = 1
                    """,
                ),
                "c",
                0,
            ),
            "failures_by_reason_last_24h": fetchall_dict(
                cur,
                """
                SELECT COALESCE(failure_reason, '(null)') AS failure_reason, COUNT(*) AS cnt
                FROM delegation_log
                WHERE created_at > datetime('now', '-1 day') AND success = 0
                GROUP BY failure_reason
                ORDER BY cnt DESC
                LIMIT 20
                """,
            ),
            "distinct_traces_last_24h": first_value(
                fetchall_dict(
                    cur,
                    """
                    SELECT COUNT(DISTINCT trace_id) AS c FROM delegation_log
                    WHERE created_at > datetime('now', '-1 day')
                    """,
                ),
                "c",
                0,
            ),
            "top_fallback_notes_last_24h": fetchall_dict(
                cur,
                """
                SELECT fallback_note, COUNT(*) AS cnt
                FROM delegation_log
                WHERE created_at > datetime('now', '-1 day')
                  AND fallback_note IS NOT NULL AND fallback_note != ''
                GROUP BY fallback_note
                ORDER BY cnt DESC
                LIMIT 10
                """,
            ),
        }

    if exists(cur, "budget_states"):
        report["usage"]["budget_state_summary"] = fetchall_dict(
            cur,
            """
            SELECT agent_role,
                   COUNT(*) AS active_tasks,
                   SUM(tokens_used) AS tokens,
                   SUM(external_calls) AS external_calls,
                   SUM(handoffs) AS handoffs,
                   SUM(CASE WHEN stopped = 1 THEN 1 ELSE 0 END) AS stopped_tasks
            FROM budget_states
            GROUP BY agent_role
            ORDER BY active_tasks DESC, agent_role ASC
            """,
        )

    if exists(cur, "cost_accuracy"):
        report["usage"]["cost_accuracy"] = fetchall_dict(
            cur,
            """
            SELECT model,
                   COUNT(*) AS samples,
                   AVG(accuracy_pct) AS avg_accuracy_pct,
                   SUM(CASE WHEN flagged = 1 THEN 1 ELSE 0 END) AS flagged
            FROM cost_accuracy
            GROUP BY model
            ORDER BY samples DESC, model ASC
            """,
        )

    task_cols = set(table_columns(cur, "task_outcomes")) if exists(cur, "task_outcomes") else set()
    if "active_llm" not in task_cols or "suggested_llm" not in task_cols:
        report["recommendations"].append(
            "Run the current Gen app startup or a dedicated migration path so task_outcomes gets prompt_intent/prompt_scope/active_llm/suggested_llm columns. Without them, LLM/provider usage by tool cannot be diagnosed from SQLite."
        )
    if not exists(cur, "routing_decisions"):
        report["recommendations"].append(
            "Initialize RoutingDecisionLog in the active Gen process and verify pretool/posttool traffic is hitting the current database. routing_decisions is the primary table for tool frequency, suggested-vs-actual provider usage, and MCP-adjacent routing analytics."
        )
    if exists(cur, "delegation_log") and report["row_counts"].get("delegation_log", 0) == 0:
        report["recommendations"].append(
            "No delegation attempts are recorded yet. Mount Gen with /api/delegate enabled and call POST /api/delegate from dispatch.html or scripts; see docs/architecture/MODEL-DISPATCH-GATEWAY.md."
        )
    if exists(cur, "budget_states"):
        stopped = report["usage"].get("budget_state_summary", [])
        total_tokens = sum((row.get("tokens") or 0) for row in stopped if isinstance(row, dict))
        if total_tokens == 0:
            report["recommendations"].append(
                "Token accounting is effectively empty in budget_states. Posttool clients are not consistently returning token counts, so cost/token dashboards will under-report usage."
            )
    if not exists(cur, "cost_accuracy"):
        report["recommendations"].append(
            "cost_accuracy tracker code exists but its table is absent in the live DB. Actual-vs-estimated cost accuracy is not being recorded today."
        )

    conn.close()
    return report


def print_human(report: dict) -> None:
    print("== Gen Observability Diagnostics ==")
    print(f"DB: {report['database']}")
    if report.get("daily_gateway_only"):
        dg = report["usage"].get("delegation_gateway_summary")
        print()
        print("-- delegation_gateway_summary (last 24h) --")
        if isinstance(dg, dict):
            for k, v in dg.items():
                print(f"{k}: {v}")
        return
    print()
    print("-- Tables / row counts --")
    for name, count in report["row_counts"].items():
        print(f"{name}: {count}")
    print()
    print("-- Schema gaps --")
    for table, missing in report["schema_gaps"].items():
        if missing:
            print(f"{table}: missing {', '.join(missing)}")
    print()
    print("-- Usage snapshots --")
    for section, rows in report["usage"].items():
        print(f"[{section}]")
        if rows is None or rows == [] or rows == {}:
            print("  <empty>")
            continue
        if isinstance(rows, dict):
            for k, v in rows.items():
                print(f"  {k}: {v}")
            continue
        for row in rows[:10]:
            print(f"  {row}")
    print()
    print("-- Offload surfaces --")
    for category, items in report["offload_surfaces"].items():
        print(f"[{category}]")
        for item in items:
            print(f"  - {item['surface']}: {item['when']} -> {item['mode']}")
    print()
    print("-- Recommendations --")
    for rec in report["recommendations"]:
        print(f"- {rec}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose Gen observability, routing, token, and delegation coverage")
    parser.add_argument("--db", default="gen.db", help="Path to Gen SQLite database (default: ./gen.db)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable output")
    parser.add_argument(
        "--daily-delegate",
        action="store_true",
        help="Print only delegation_gateway_summary (last 24h) for quick ops review",
    )
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    report = analyze_database(db_path)
    if args.daily_delegate:
        report["daily_gateway_only"] = True
        report["usage"] = {"delegation_gateway_summary": report["usage"].get("delegation_gateway_summary", {})}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
