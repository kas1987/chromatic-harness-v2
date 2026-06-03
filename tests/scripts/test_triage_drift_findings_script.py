"""Additional tests for scripts/triage_drift_findings.py.

Focuses on edge cases not covered by tests/test_triage_drift_findings.py:
fingerprinting, state persistence, markdown parsing, priority logic, dry-run.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_RUNTIME = Path(__file__).resolve().parents[2] / "02_RUNTIME"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

import triage_drift_findings as triage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_evolve(root: Path) -> Path:
    evolve = root / ".agents" / "evolve"
    evolve.mkdir(parents=True, exist_ok=True)
    return evolve


# ---------------------------------------------------------------------------
# DriftItem + fingerprinting
# ---------------------------------------------------------------------------


class TestFingerprint:
    def test_same_inputs_same_fingerprint(self):
        item = triage.DriftItem(
            source="a/b.jsonl",
            category="drift",
            file="foo.py",
            line=10,
            detail="something broken",
        )
        assert triage._fingerprint(item) == triage._fingerprint(item)

    def test_different_detail_different_fingerprint(self):
        base = triage.DriftItem(source="s", category="c", file="f", line=1, detail="A")
        changed = triage.DriftItem(source="s", category="c", file="f", line=1, detail="B")
        assert triage._fingerprint(base) != triage._fingerprint(changed)

    def test_none_line_in_fingerprint(self):
        item = triage.DriftItem(source="s", category="c", file="f", line=None, detail="d")
        fp = triage._fingerprint(item)
        assert len(fp) == 40  # sha1 hex digest length

    def test_fingerprint_is_sha1_of_pipe_joined(self):
        item = triage.DriftItem(source="s", category="c", file="f", line=5, detail="d")
        raw = "|".join(["s", "c", "f", "5", "d"])
        expected = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        assert triage._fingerprint(item) == expected


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------


class TestPriorityFor:
    def test_critical_keyword_gives_priority_1(self):
        item = triage.DriftItem(source="s", category="critical_fail", file="f", line=None, detail="x")
        assert triage._priority_for(item) == "1"

    def test_security_keyword_gives_priority_1(self):
        item = triage.DriftItem(source="s", category="drift", file="f", line=None, detail="security issue")
        assert triage._priority_for(item) == "1"

    def test_error_keyword_gives_priority_2(self):
        item = triage.DriftItem(source="s", category="drift", file="f", line=None, detail="error in config")
        assert triage._priority_for(item) == "2"

    def test_missing_keyword_gives_priority_2(self):
        item = triage.DriftItem(source="s", category="drift", file="f", line=None, detail="missing value")
        assert triage._priority_for(item) == "2"

    def test_broken_keyword_gives_priority_2(self):
        item = triage.DriftItem(source="s", category="drift", file="f", line=None, detail="broken link")
        assert triage._priority_for(item) == "2"

    def test_unknown_detail_gives_priority_3(self):
        item = triage.DriftItem(source="s", category="drift", file="f", line=None, detail="style inconsistency")
        assert triage._priority_for(item) == "3"


# ---------------------------------------------------------------------------
# Title / Description
# ---------------------------------------------------------------------------


class TestTitleFor:
    def test_includes_category(self):
        item = triage.DriftItem(source="s", category="mycat", file="unknown", line=None, detail="d")
        assert "mycat" in triage._title_for(item)

    def test_includes_file_when_not_unknown(self):
        item = triage.DriftItem(source="s", category="c", file="src/main.py", line=None, detail="d")
        assert "src/main.py" in triage._title_for(item)

    def test_omits_unknown_file(self):
        item = triage.DriftItem(source="s", category="c", file="unknown", line=None, detail="d")
        assert "unknown" not in triage._title_for(item)

    def test_max_length_120(self):
        item = triage.DriftItem(source="s", category="c" * 100, file="f" * 100, line=None, detail="d")
        assert len(triage._title_for(item)) <= 120


class TestDescriptionFor:
    def test_contains_all_fields(self):
        item = triage.DriftItem(source="src.jsonl", category="cat", file="foo.py", line=7, detail="the detail")
        desc = triage._description_for(item)
        assert "src.jsonl" in desc
        assert "cat" in desc
        assert "foo.py" in desc
        assert "7" in desc
        assert "the detail" in desc

    def test_no_line_omits_colon_number(self):
        item = triage.DriftItem(source="s", category="c", file="foo.py", line=None, detail="d")
        desc = triage._description_for(item)
        # Should not have ":None" or "foo.py:None"
        assert ":None" not in desc


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


class TestState:
    def test_load_missing_state_returns_empty_set(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        assert triage._load_state(path) == set()

    def test_save_and_reload_roundtrip(self, tmp_path):
        path = tmp_path / "state.json"
        fps = {"abc123", "def456"}
        triage._save_state(path, fps)
        loaded = triage._load_state(path)
        assert loaded == fps

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "state.json"
        triage._save_state(path, {"fp1"})
        assert path.is_file()

    def test_load_corrupt_json_returns_empty(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("NOT JSON", encoding="utf-8")
        assert triage._load_state(path) == set()

    def test_load_wrong_schema_returns_empty(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"created_fingerprints": "not a list"}), encoding="utf-8")
        assert triage._load_state(path) == set()


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------


class TestReadMarkdown:
    def test_reads_bullet_items(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        md = tmp_path / "report.md"
        md.write_text("# Header\n- first item\n- second item\nskip this\n", encoding="utf-8")
        items = triage._read_markdown(md)
        assert len(items) == 2
        assert items[0].detail == "first item"
        assert items[0].category == "drift_report"
        assert items[1].detail == "second item"

    def test_skips_non_bullet_lines(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        md = tmp_path / "report.md"
        # The code strips each line before checking startswith("- "),
        # so "  - indented" is also treated as a bullet after strip.
        # Non-bullet content: headers (#), plain text, etc.
        md.write_text("# Title\nPlain text\nno dash here\n- valid\n", encoding="utf-8")
        items = triage._read_markdown(md)
        assert len(items) == 1
        assert items[0].detail == "valid"


# ---------------------------------------------------------------------------
# JSONL parsing edge cases
# ---------------------------------------------------------------------------


class TestReadJsonl:
    def test_skips_blank_lines(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        p = tmp_path / "f.jsonl"
        p.write_text(
            "\n\n" + json.dumps({"detail": "real item", "category": "c", "file": "f"}) + "\n\n", encoding="utf-8"
        )
        items = triage._read_jsonl(p)
        assert len(items) == 1

    def test_skips_invalid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        p = tmp_path / "f.jsonl"
        p.write_text("NOT JSON\n" + json.dumps({"detail": "ok", "category": "c", "file": "f"}) + "\n", encoding="utf-8")
        items = triage._read_jsonl(p)
        assert len(items) == 1

    def test_skips_rows_without_detail(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        p = tmp_path / "f.jsonl"
        p.write_text(json.dumps({"category": "c", "file": "f"}) + "\n", encoding="utf-8")
        items = triage._read_jsonl(p)
        assert len(items) == 0

    def test_uses_message_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        p = tmp_path / "f.jsonl"
        p.write_text(json.dumps({"message": "msg fallback", "category": "c", "file": "f"}) + "\n", encoding="utf-8")
        items = triage._read_jsonl(p)
        assert len(items) == 1
        assert items[0].detail == "msg fallback"

    def test_integer_line_number_parsed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        p = tmp_path / "f.jsonl"
        p.write_text(json.dumps({"detail": "d", "category": "c", "file": "f", "line": 99}) + "\n", encoding="utf-8")
        items = triage._read_jsonl(p)
        assert items[0].line == 99


# ---------------------------------------------------------------------------
# load_drift_items
# ---------------------------------------------------------------------------


class TestLoadDriftItems:
    def test_empty_evolve_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        _make_evolve(tmp_path)
        assert triage.load_drift_items(tmp_path) == []

    def test_deduplicates_within_same_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        evolve = _make_evolve(tmp_path)
        # The fingerprint includes source path, so same content in different files
        # is NOT deduplicated (different source). Same content in same file (two
        # jsonl lines) would be deduplicated because load reads each file once.
        # Within one file, the same logical record appears once → 1 item.
        row = {"detail": "dup detail", "category": "c", "file": "f"}
        latest = evolve / "drift-findings-latest.jsonl"
        latest.write_text(json.dumps(row) + "\n", encoding="utf-8")
        items = triage.load_drift_items(tmp_path)
        assert len(items) == 1

    def test_missing_evolve_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        result = triage.load_drift_items(tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# triage() dry-run
# ---------------------------------------------------------------------------


class TestTriageDryRun:
    def test_dry_run_does_not_call_bd(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        evolve = _make_evolve(tmp_path)
        (evolve / "drift-findings-latest.jsonl").write_text(
            json.dumps({"detail": "something", "category": "drift", "file": "x.py"}) + "\n",
            encoding="utf-8",
        )
        calls: list = []
        monkeypatch.setattr(triage, "_run_bd", lambda *a, **kw: calls.append(a) or (0, ""))
        state = tmp_path / "state.json"
        result = triage.triage(root=tmp_path, write=False, max_items=10, state_path=state)
        assert calls == []
        assert result["created_count"] == 0
        assert result["pending_count"] == 1

    def test_write_mode_respects_max_items(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        evolve = _make_evolve(tmp_path)
        rows = [json.dumps({"detail": f"item {i}", "category": "c", "file": f"f{i}.py"}) for i in range(5)]
        (evolve / "drift-findings-latest.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
        monkeypatch.setattr(triage, "_run_bd", lambda *a, **kw: (0, "Created issue: x-1"))
        state = tmp_path / "state.json"
        result = triage.triage(root=tmp_path, write=True, max_items=2, state_path=state)
        assert result["created_count"] == 2
        assert result["planned_count"] == 2

    def test_already_known_fingerprints_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        evolve = _make_evolve(tmp_path)
        row = {"detail": "known item", "category": "c", "file": "f"}
        (evolve / "drift-findings-latest.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        # Pre-populate state with the fingerprint
        items = triage._read_jsonl(evolve / "drift-findings-latest.jsonl")
        fp = triage._fingerprint(items[0])
        state = tmp_path / "state.json"
        triage._save_state(state, {fp})
        calls: list = []
        monkeypatch.setattr(triage, "_run_bd", lambda *a, **kw: calls.append(a) or (0, "Created issue: x"))
        result = triage.triage(root=tmp_path, write=True, max_items=10, state_path=state)
        assert calls == []
        assert result["pending_count"] == 0

    def test_result_structure_keys(self, tmp_path, monkeypatch):
        monkeypatch.setattr(triage, "REPO", tmp_path)
        _make_evolve(tmp_path)
        state = tmp_path / "state.json"
        result = triage.triage(root=tmp_path, write=False, max_items=5, state_path=state)
        for key in ("audit", "write", "input_count", "pending_count", "planned_count", "created_count", "actions"):
            assert key in result


# ---------------------------------------------------------------------------
# extract_issue_id
# ---------------------------------------------------------------------------


class TestExtractIssueId:
    def test_extracts_id_from_output(self):
        assert triage._extract_issue_id("Created issue: CH-42") == "CH-42"

    def test_returns_empty_when_absent(self):
        assert triage._extract_issue_id("No match here") == ""

    def test_case_insensitive(self):
        assert triage._extract_issue_id("created issue: abc-1") == "abc-1"
