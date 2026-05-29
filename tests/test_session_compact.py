"""Tests for session handoff persistence."""

import json
import importlib.util
import os
import tempfile
from pathlib import Path


def _load_session_compact(repo: Path):
    path = repo / "02_RUNTIME" / "orchestrator" / "session_compact.py"
    spec = importlib.util.spec_from_file_location("session_compact_test", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod._REPO = repo
    mod._HANDOFFS = repo / "12_HANDOFFS" / "sessions"
    mod._LATEST = repo / ".agents" / "handoffs" / "latest.json"
    mod._TEMPLATE = repo / "12_HANDOFFS" / "AGENT_HANDOFF_TEMPLATE.md"
    return mod


class TestSessionCompact:
    def test_write_handoff_creates_files(self):
        repo = Path(__file__).resolve().parents[1]
        sc = _load_session_compact(repo)
        handoff_prep = {
            "directive_summary": "Test mission complete.",
            "context_snapshot": {
                "mission_id": "CHR-TEST-COMPACT",
                "objective": "test objective",
                "autonomy_level": "L1",
                "composite_score": 82.0,
            },
            "next_session_goals": ["Run bd ready"],
            "decision": "review",
            "audit_log_ref": "CHR-TEST-COMPACT",
        }
        with tempfile.TemporaryDirectory() as td:
            tmp_repo = Path(td)
            (tmp_repo / "12_HANDOFFS").mkdir(parents=True)
            (tmp_repo / "12_HANDOFFS" / "sessions").mkdir(parents=True)
            (tmp_repo / ".agents" / "handoffs").mkdir(parents=True)
            template_src = repo / "12_HANDOFFS" / "AGENT_HANDOFF_TEMPLATE.md"
            (tmp_repo / "12_HANDOFFS" / "AGENT_HANDOFF_TEMPLATE.md").write_text(
                template_src.read_text(encoding="utf-8"), encoding="utf-8"
            )
            sc._REPO = tmp_repo
            sc._HANDOFFS = tmp_repo / "12_HANDOFFS" / "sessions"
            sc._LATEST = tmp_repo / ".agents" / "handoffs" / "latest.json"
            sc._TEMPLATE = tmp_repo / "12_HANDOFFS" / "AGENT_HANDOFF_TEMPLATE.md"
            out = sc.write_handoff(handoff_prep, mission={"mission_id": "CHR-TEST-COMPACT"})
            assert out.exists()
            latest = json.loads(sc._LATEST.read_text(encoding="utf-8"))
            assert latest["mission_id"] == "CHR-TEST-COMPACT"
            assert "CHR-TEST-COMPACT" in latest["handoff_path"]
