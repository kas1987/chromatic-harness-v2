#!/usr/bin/env python3
"""Verify mandatory agent-operations docs and cross-links are present.

Exit 0 if OK, 1 if harness onboarding docs were removed or broken.
Used in CI so nothing critical gets deleted silently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "AGENT_OPERATIONS.md",
    "AGENTS.md",
    "CLAUDE.md",
    "12_HANDOFFS/SESSION_COMPACT.md",
    "12_HANDOFFS/PRE_SESSION_INVENTORY.md",
    "docs/PRE_SESSION_AND_TOOLS.md",
    "docs/CURSOR_CONTEXT_HYGIENE.md",
    "docs/AGENT_ANTIPATTERNS.md",
    "config/pre_session/inventory.snapshot.json",
    "config/pre_session/mcp.profile.yaml",
    "scripts/generate_pre_session_inventory.py",
    "scripts/audit_mcp_context.py",
    "scripts/session_start.py",
    "scripts/session_context_report.py",
    "scripts/pre_session_common.py",
    ".claude/settings.json",
    ".cursor/rules/context-hygiene.mdc",
    ".claude/workflows/ship.js",
    ".claude/workflows/README.md",
    "scripts/sync_claude_workflows.ps1",
    "scripts/workflow_go.py",
    "scripts/workflow_git.py",
    "scripts/auto_intake.py",
    "scripts/poll_inbox.py",
    "scripts/chromatic_mcp_server.py",
    "docs/CHROMATIC_MCP_SERVER.md",
    "scripts/validate_intake_loop.py",
    "scripts/validate_instruction_governance.py",
    "scripts/validate_governance_stack.py",
    "scripts/workflow_self_heal_cycle.py",
    "scripts/daily_harness_audit.py",
    "scripts/audit_ide_parity.py",
    "scripts/audit_instruction_drift.py",
    "docs/pdr/PDR-CHV2-003_IDE_CLI_AUDIT_AND_DAILY_MONITORING.md",
    "docs/governance/IDE_CLI_PARITY_POLICY.md",
    "docs/governance/DAILY_AUDIT_RUNBOOK.md",
    "docs/beads/IDE_CLI_AUDIT_BEADS.md",
    ".cursor/rules/harness-audit.mdc",
    ".cursor/rules/karpathy-guidelines.mdc",
    "docs/governance/KARPATHY_DISCIPLINE.md",
    "scripts/validate_karpathy_discipline.py",
    "02_RUNTIME/magnets/discipline_magnet.py",
    ".vscode/tasks.json",
    ".github/workflows/harness-daily-audit.yml",
    ".claude/workflows/_budget.js",
    "scripts/run_intake_cycle.ps1",
    "scripts/run_intake_cycle.sh",
    "scripts/smoke_stack.ps1",
    "scripts/session_preflight.ps1",
    "scripts/install_automation_tasks.ps1",
    "docs/ops/HARNESS_AUTOMATION_RUNBOOK.md",
    "docs/ops/P3_AUTOMATION_BACKLOG.md",
    "07_LOGS_AND_AUDIT/intake_cycle/.gitkeep",
    "09_DEPLOYMENT/Dockerfile.console",
    "scripts/harvest_rigs.py",
    "docs/KNOWLEDGE_HARVEST.md",
    ".gitmodules",
    "02_RUNTIME/runtime-engines/manifest.json",
    "02_RUNTIME/adapters/roach-pi-loader.ts",
    "02_RUNTIME/adapters/roach_pi_guard.py",
    "scripts/roach_pi_status.py",
    "scripts/init_roach_pi_submodule.ps1",
    "docs/ROACH_PI_RUNTIME.md",
    "docs/pdr/PDR-DYNAMIC-WORKFLOW-RUNTIME-001.md",
    "docs/pdr/PDR-CHV2-001_PRE_SESSION_CONTEXT_AND_EXECUTION_FLOW_CONSOLIDATION.md",
    "00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md",
    "docs/governance/PRE_SESSION_CONTEXT_POLICY.md",
    "docs/governance/GIT_AUTONOMY_POLICY.md",
    ".cursor/rules/git-autonomy.mdc",
    "docs/governance/OPENROUTER_BROKER_POLICY.md",
    "docs/BEADS_OBJECT_MODEL.md",
    "docs/beads/ROUTER_VALIDATION_BEADS.md",
    "scripts/pre_session_manifest.py",
    "scripts/session_boot_automation.py",
    "scripts/audit_hooks.py",
    "docs/audit/HOOK_ARCHITECTURE.md",
    ".claude/settings.local.json.example",
    "scripts/run_session_boot.ps1",
    ".cursor/hooks.json",
    ".cursor/hooks/session_boot.py",
    "07_LOGS_AND_AUDIT/pre_session/.gitkeep",
    "docs/workflows/WORKFLOW_RUNTIME.md",
    "docs/workflows/DYNAMIC_WORKFLOW_SPEC.md",
    "docs/workflows/GO_MODES.md",
    "docs/workflows/PERMISSION_GATE.md",
    "docs/workflows/VERIFIER_GATE.md",
    "docs/workflows/TASK_GRAPH_SCHEMA.json",
    "docs/workflows/WORKFLOW_RUN_LOG.seed.jsonl",
    "docs/governance/ACTIVITY_LOG_AND_DUAL_BACKLOG.md",
    "scripts/log_agent_activity.py",
    "scripts/git_triage.py",
    "scripts/bd_ready_by_lane.py",
    "02_RUNTIME/activity/log.py",
    "02_RUNTIME/activity/lanes.py",
    "02_RUNTIME/activity/git_triage.py",
    "docs/workflows/GIT_CONFIDENCE_PIPELINE.md",
    "docs/workflows/TWO_LOG_AUDIT.md",
    "07_LOGS_AND_AUDIT/execution/execution.jsonl",
    "07_LOGS_AND_AUDIT/traces/traces.jsonl",
    "07_LOGS_AND_AUDIT/decisions/decision_log.jsonl",
    "docs/INTAKE_QUEUE.md",
    "01_PROTOCOLS/INTAKE/intake_queue.schema.json",
    "07_LOGS_AND_AUDIT/intake_queue.jsonl",
    "docs/WIKI_REPO_AND_PROMOTION.md",
    "docs/WIKI_REPO_RENAME.md",
    "docs/beads/WIKI_V01_BEADS.md",
    "scripts/promote_to_wiki.py",
    "scripts/sync_wiki_mirror.py",
    "config/agent_budget.yaml",
    "docs/governance/AGENT_TRANSFER_POLICY.md",
    "docs/governance/AGENT_TRANSFER_PACKET_SCHEMA.md",
    "docs/handoffs/transfer_packet.example.json",
    "07_LOGS_AND_AUDIT/budget/.gitkeep",
    "scripts/session_closeout.py",
    "scripts/spawn_successor_agent.py",
    "scripts/run_session_closeout.ps1",
    ".cursor/hooks/session_closeout.py",
    ".claude/hooks/session_closeout.sh",
    "02_RUNTIME/budget/ledger.py",
    "02_RUNTIME/budget/transfer_packet.py",
]

REQUIRED_STRINGS_IN_AGENTS = [
    "SESSION_COMPACT",
    "AGENT_OPERATIONS",
    "HARNESS_EXECUTION_FLOW",
    "bd ready",
    "bd prime",
]

REQUIRED_SNAPSHOT_KEYS = [
    "generated_at",
    "summary",
    "native_tools",
    "mcp_servers",
    "crg_manifest",
]


def main() -> int:
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        path = REPO / rel
        if not path.is_file():
            errors.append(f"Missing required file: {rel}")

    agents_md = REPO / "AGENTS.md"
    if agents_md.is_file():
        text = agents_md.read_text(encoding="utf-8")
        for needle in REQUIRED_STRINGS_IN_AGENTS:
            if needle not in text:
                errors.append(f"AGENTS.md missing required reference: {needle!r}")

    snapshot_path = REPO / "config/pre_session/inventory.snapshot.json"
    if snapshot_path.is_file():
        try:
            data = json.loads(snapshot_path.read_text(encoding="utf-8"))
            for key in REQUIRED_SNAPSHOT_KEYS:
                if key not in data:
                    errors.append(f"inventory.snapshot.json missing key: {key}")
            summary = data.get("summary", {})
            if summary.get("native_tool_count", 0) < 1:
                errors.append("inventory.snapshot.json: native_tool_count invalid")
            if summary.get("crg_resource_count", 0) < 1:
                errors.append("inventory.snapshot.json: crg_resource_count invalid")
        except json.JSONDecodeError as exc:
            errors.append(f"inventory.snapshot.json invalid JSON: {exc}")

    claude_md = REPO / "CLAUDE.md"
    if claude_md.is_file():
        text = claude_md.read_text(encoding="utf-8")
        if "AGENT_OPERATIONS" not in text:
            errors.append("CLAUDE.md missing AGENT_OPERATIONS reference")
        if "CURSOR_CONTEXT_HYGIENE" not in text and "audit_mcp_context" not in text:
            errors.append("CLAUDE.md missing MCP hygiene reference")

    ops_md = REPO / "AGENT_OPERATIONS.md"
    if ops_md.is_file():
        text = ops_md.read_text(encoding="utf-8")
        if "audit_mcp_context" not in text:
            errors.append("AGENT_OPERATIONS.md missing audit_mcp_context reference")
        if "AGENT_ANTIPATTERNS" not in text:
            errors.append("AGENT_OPERATIONS.md missing AGENT_ANTIPATTERNS reference")
        if "log_agent_activity" not in text:
            errors.append("AGENT_OPERATIONS.md missing log_agent_activity reference")

    for wf in ("ship.js", "qa.js", "close-issue.js", "go.js"):
        wf_path = REPO / ".claude/workflows" / wf
        if wf_path.is_file():
            wf_text = wf_path.read_text(encoding="utf-8").lower()
            if "label:" in wf_text and "crank" in wf_text and "do not run /crank" not in wf_text:
                errors.append(f".claude/workflows/{wf} must not invoke /crank")

    gov_script = REPO / "scripts" / "validate_instruction_governance.py"
    if gov_script.is_file():
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(gov_script)],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            errors.append(
                "validate_instruction_governance.py failed: "
                + (proc.stderr or proc.stdout)[:500]
            )

    if errors:
        print("AGENT OPERATIONS CHECK FAILED", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nRestore docs per AGENT_OPERATIONS.md before merging.",
            file=sys.stderr,
        )
        return 1

    print("Agent operations check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
