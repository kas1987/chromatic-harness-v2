"""Unit tests for router.loop_guard — per-session loop-iteration guard.

# DEFICIENCIES NOTED
#
# 1. FAIL-OPEN SWALLOWS ALL EXCEPTIONS: The except clause in bump_and_check()
#    catches all Exception subclasses with no logging. A filesystem permission
#    error, a JSON decode error in an existing state file, or even a programmer
#    bug in the guard itself all look identical from the caller's perspective:
#    ok=False, level="ok". There is no way to distinguish a guard malfunction
#    from an intentional bypass.
#
# 2. STATE FILE IS SCOPED ONLY BY session_id, NOT BY REPO ROOT: Two different
#    repos that share the same .agents/ parent directory and the same session_id
#    would overwrite each other's state. The design assumes one repo per process.
#
# 3. NO ATOMIC WRITE: The state JSON is written non-atomically via Path.write_text.
#    Concurrent invocations from multiple agent processes in the same session can
#    produce a corrupt or partially-overwritten JSON file. The next read would
#    fail and fail-open, silently resetting counts to zero.
#
# 4. TRUNCATION OF TASK DESCRIPTION: task_signature() silences the input at 200
#    characters after normalization. Two tasks whose descriptions differ only
#    beyond the 200-character mark collide on the same signature and share a
#    count. The truncation is not documented in the caller-facing docstring.
#
# 5. THRESHOLDS READ AT MODULE IMPORT TIME: WARN_THRESHOLD and BLOCK_THRESHOLD
#    are evaluated once when the module is first imported from os.environ. Changing
#    the environment variables at runtime (e.g., in tests) requires monkeypatching
#    the module attributes directly rather than setting env vars; the module-level
#    docstring does not mention this subtlety.
#
# 6. _session_id() FALLBACK IS "default": When neither CLAUDE_SESSION_ID nor
#    CHROMATIC_SESSION_ID is set, all sessions share the key "default", meaning
#    loop counts accumulate across what should be independent sessions in
#    environments that do not inject session IDs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import router.loop_guard as lg
from router.loop_guard import (
    BLOCK_THRESHOLD,
    WARN_THRESHOLD,
    advisory_note,
    bump_and_check,
    task_signature,
)


# ---------------------------------------------------------------------------
# task_signature — normalization and stability
# ---------------------------------------------------------------------------


class TestTaskSignature:
    def test_returns_16_hex_chars(self):
        sig = task_signature("some task", "agent-type")
        assert len(sig) == 16
        assert all(c in "0123456789abcdef" for c in sig)

    def test_stable_across_calls(self):
        a = task_signature("Refactor the gate", "code-reviewer")
        b = task_signature("Refactor the gate", "code-reviewer")
        assert a == b

    def test_normalizes_extra_whitespace(self):
        a = task_signature("Refactor   the  gate", "general-purpose")
        b = task_signature("refactor the gate", "general-purpose")
        assert a == b

    def test_normalizes_leading_trailing_whitespace(self):
        a = task_signature("  refactor the gate  ", "t")
        b = task_signature("refactor the gate", "t")
        assert a == b

    def test_case_insensitive(self):
        a = task_signature("REFACTOR THE GATE", "t")
        b = task_signature("refactor the gate", "t")
        assert a == b

    def test_different_descriptions_produce_different_signatures(self):
        a = task_signature("task A", "t")
        b = task_signature("task B", "t")
        assert a != b

    def test_different_agent_types_produce_different_signatures(self):
        a = task_signature("same task", "agent-1")
        b = task_signature("same task", "agent-2")
        assert a != b

    def test_empty_description_does_not_raise(self):
        sig = task_signature("", "t")
        assert len(sig) == 16

    def test_empty_subagent_type_allowed(self):
        sig = task_signature("a task")
        assert len(sig) == 16

    def test_truncates_at_200_chars_after_normalization(self):
        # Two descriptions that differ only past the 200-char mark must collide.
        base = "x " * 100  # 200 normalized chars
        a = task_signature(base + "AAA", "t")
        b = task_signature(base + "BBB", "t")
        assert a == b

    def test_descriptions_within_200_chars_differ(self):
        a = task_signature("short A", "t")
        b = task_signature("short B", "t")
        assert a != b


# ---------------------------------------------------------------------------
# bump_and_check — counting and verdict escalation
# ---------------------------------------------------------------------------


class TestBumpAndCheckCounting:
    def test_first_call_returns_count_one(self, tmp_path):
        v = bump_and_check("my task", "t1", repo_root=tmp_path, session_id="s1")
        assert v["count"] == 1

    def test_second_call_returns_count_two(self, tmp_path):
        bump_and_check("my task", "t1", repo_root=tmp_path, session_id="s1")
        v = bump_and_check("my task", "t1", repo_root=tmp_path, session_id="s1")
        assert v["count"] == 2

    def test_count_increments_monotonically(self, tmp_path):
        counts = []
        for _ in range(5):
            v = bump_and_check("repeat", "t", repo_root=tmp_path, session_id="s")
            counts.append(v["count"])
        assert counts == [1, 2, 3, 4, 5]

    def test_distinct_tasks_counted_independently(self, tmp_path):
        v1 = bump_and_check("task A", repo_root=tmp_path, session_id="s2")
        v2 = bump_and_check("task B", repo_root=tmp_path, session_id="s2")
        assert v1["count"] == 1
        assert v2["count"] == 1

    def test_distinct_agent_types_counted_independently(self, tmp_path):
        v1 = bump_and_check("same task", "agent-alpha", repo_root=tmp_path, session_id="s")
        v2 = bump_and_check("same task", "agent-beta", repo_root=tmp_path, session_id="s")
        assert v1["count"] == 1
        assert v2["count"] == 1


class TestBumpAndCheckVerdictEscalation:
    @pytest.fixture(autouse=True)
    def _set_thresholds(self, monkeypatch):
        monkeypatch.setattr(lg, "WARN_THRESHOLD", 3)
        monkeypatch.setattr(lg, "BLOCK_THRESHOLD", 5)

    def _bump_n(self, n: int, tmp_path: Path) -> list[str]:
        return [bump_and_check("task", "t", repo_root=tmp_path, session_id="s")["level"] for _ in range(n)]

    def test_ok_level_below_warn_threshold(self, tmp_path):
        levels = self._bump_n(3, tmp_path)
        assert all(lv == "ok" for lv in levels)

    def test_warn_level_above_warn_below_block(self, tmp_path):
        levels = self._bump_n(5, tmp_path)
        # counts 1,2,3 -> ok; 4,5 -> warn
        assert levels[3] == "warn"
        assert levels[4] == "warn"

    def test_block_level_above_block_threshold(self, tmp_path):
        levels = self._bump_n(7, tmp_path)
        # counts 6,7 -> block
        assert levels[5] == "block"
        assert levels[6] == "block"

    def test_full_escalation_sequence(self, tmp_path):
        levels = self._bump_n(7, tmp_path)
        assert levels == ["ok", "ok", "ok", "warn", "warn", "block", "block"]

    def test_ok_level_never_reached_after_block(self, tmp_path):
        # Once blocked, subsequent calls remain blocked (counts keep rising)
        self._bump_n(6, tmp_path)
        v = bump_and_check("task", "t", repo_root=tmp_path, session_id="s")
        assert v["level"] == "block"

    def test_verdict_contains_ok_true_on_success(self, tmp_path):
        v = bump_and_check("task", "t", repo_root=tmp_path, session_id="s")
        assert v["ok"] is True

    def test_verdict_contains_signature(self, tmp_path):
        v = bump_and_check("a unique task", "t", repo_root=tmp_path, session_id="s")
        expected_sig = task_signature("a unique task", "t")
        assert v["signature"] == expected_sig

    def test_verdict_count_matches_signature_count(self, tmp_path):
        for i in range(1, 4):
            v = bump_and_check("consistent task", "t", repo_root=tmp_path, session_id="s")
            assert v["count"] == i


# ---------------------------------------------------------------------------
# bump_and_check — session isolation
# ---------------------------------------------------------------------------


class TestBumpAndCheckSessionIsolation:
    def test_new_session_id_resets_counts(self, tmp_path):
        for _ in range(4):
            bump_and_check("loopy", repo_root=tmp_path, session_id="old")
        fresh = bump_and_check("loopy", repo_root=tmp_path, session_id="new")
        assert fresh["count"] == 1

    def test_new_session_level_is_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lg, "WARN_THRESHOLD", 2)
        monkeypatch.setattr(lg, "BLOCK_THRESHOLD", 3)
        for _ in range(10):
            bump_and_check("heavy task", repo_root=tmp_path, session_id="old")
        fresh = bump_and_check("heavy task", repo_root=tmp_path, session_id="new_clean")
        assert fresh["level"] == "ok"
        assert fresh["count"] == 1

    def test_same_session_accumulates_across_calls(self, tmp_path):
        for _ in range(3):
            bump_and_check("same", repo_root=tmp_path, session_id="persistent")
        v = bump_and_check("same", repo_root=tmp_path, session_id="persistent")
        assert v["count"] == 4

    def test_session_id_from_environment_when_not_provided(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session-42")
        v1 = bump_and_check("env task", repo_root=tmp_path)
        v2 = bump_and_check("env task", repo_root=tmp_path)
        # Both calls used the same env session; count must be 2
        assert v2["count"] == 2

    def test_chromatic_session_id_env_var_used_as_fallback(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        monkeypatch.setenv("CHROMATIC_SESSION_ID", "chromatic-42")
        v1 = bump_and_check("chromatic task", repo_root=tmp_path)
        v2 = bump_and_check("chromatic task", repo_root=tmp_path)
        assert v2["count"] == 2


# ---------------------------------------------------------------------------
# bump_and_check — state persistence
# ---------------------------------------------------------------------------


class TestBumpAndCheckPersistence:
    def test_state_file_created(self, tmp_path):
        bump_and_check("task", repo_root=tmp_path, session_id="s")
        state_file = tmp_path / ".agents" / "context" / "session_loop_counts.json"
        assert state_file.exists()

    def test_state_file_contains_valid_json(self, tmp_path):
        bump_and_check("task", repo_root=tmp_path, session_id="s")
        state_file = tmp_path / ".agents" / "context" / "session_loop_counts.json"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert "session_id" in data
        assert "counts" in data

    def test_state_file_session_id_matches_provided(self, tmp_path):
        bump_and_check("task", repo_root=tmp_path, session_id="my-session")
        state_file = tmp_path / ".agents" / "context" / "session_loop_counts.json"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["session_id"] == "my-session"

    def test_count_persisted_between_calls(self, tmp_path):
        bump_and_check("task", repo_root=tmp_path, session_id="s")
        bump_and_check("task", repo_root=tmp_path, session_id="s")
        state_file = tmp_path / ".agents" / "context" / "session_loop_counts.json"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        sig = task_signature("task", "")
        assert data["counts"][sig] == 2

    def test_stale_session_file_overwritten(self, tmp_path):
        state_dir = tmp_path / ".agents" / "context"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session_loop_counts.json"
        old_state = {"session_id": "old-session", "counts": {"abc123": 99}}
        state_file.write_text(json.dumps(old_state), encoding="utf-8")

        v = bump_and_check("fresh task", repo_root=tmp_path, session_id="new-session")
        assert v["count"] == 1

    def test_corrupted_state_file_handled_gracefully(self, tmp_path):
        state_dir = tmp_path / ".agents" / "context"
        state_dir.mkdir(parents=True)
        (state_dir / "session_loop_counts.json").write_text("{not valid json!!!", encoding="utf-8")

        # Should not raise; should fail-open with a fresh count
        v = bump_and_check("task", repo_root=tmp_path, session_id="s")
        assert v["count"] == 1
        assert v["ok"] is True


# ---------------------------------------------------------------------------
# bump_and_check — fail-open behaviour
# ---------------------------------------------------------------------------


class TestBumpAndCheckFailOpen:
    def test_fail_open_on_illegal_path(self):
        """Guard never blocks on a malfunction — always returns level='ok'."""
        v = bump_and_check("x", repo_root=Path("\x00illegal"), session_id="s")
        assert v["ok"] is False
        assert v["level"] == "ok"
        assert v["count"] == 0

    def test_fail_open_includes_error_key(self):
        v = bump_and_check("x", repo_root=Path("\x00illegal"), session_id="s")
        assert "error" in v

    def test_fail_open_returns_dict_not_exception(self):
        # Must return a dict even when everything is broken
        result = bump_and_check("x", repo_root=Path("\x00bad"), session_id="s")
        assert isinstance(result, dict)

    def test_fail_open_does_not_raise(self):
        try:
            bump_and_check("x", repo_root=Path("/no/such/path/zzzzzz"), session_id="s")
        except Exception as exc:
            pytest.fail(f"bump_and_check raised instead of failing open: {exc}")


# ---------------------------------------------------------------------------
# advisory_note — human-readable messages
# ---------------------------------------------------------------------------


class TestAdvisoryNote:
    @pytest.fixture(autouse=True)
    def _set_thresholds(self, monkeypatch):
        monkeypatch.setattr(lg, "WARN_THRESHOLD", 3)
        monkeypatch.setattr(lg, "BLOCK_THRESHOLD", 5)

    def test_ok_level_returns_empty_string(self):
        assert advisory_note({"level": "ok", "count": 1}) == ""

    def test_warn_level_returns_nonempty_string(self):
        note = advisory_note({"level": "warn", "count": 4})
        assert note != ""

    def test_warn_note_contains_loop_warn_marker(self):
        note = advisory_note({"level": "warn", "count": 4})
        assert "LOOP WARN" in note

    def test_warn_note_contains_dispatch_count(self):
        note = advisory_note({"level": "warn", "count": 4})
        assert "4" in note

    def test_warn_note_contains_warn_threshold(self):
        note = advisory_note({"level": "warn", "count": 4})
        # monkeypatched threshold is 3
        assert "3" in note

    def test_block_level_returns_nonempty_string(self):
        note = advisory_note({"level": "block", "count": 6})
        assert note != ""

    def test_block_note_contains_loop_block_marker(self):
        note = advisory_note({"level": "block", "count": 6})
        assert "LOOP BLOCK" in note

    def test_block_note_contains_dispatch_count(self):
        note = advisory_note({"level": "block", "count": 6})
        assert "6" in note

    def test_block_note_contains_block_threshold(self):
        note = advisory_note({"level": "block", "count": 6})
        # monkeypatched threshold is 5
        assert "5" in note

    def test_missing_level_key_returns_empty_string(self):
        assert advisory_note({"count": 3}) == ""

    def test_empty_verdict_dict_returns_empty_string(self):
        assert advisory_note({}) == ""

    def test_ok_level_zero_count_returns_empty_string(self):
        assert advisory_note({"level": "ok", "count": 0}) == ""


# ---------------------------------------------------------------------------
# Integration: bump_and_check + advisory_note pipeline
# ---------------------------------------------------------------------------


class TestLoopGuardIntegration:
    @pytest.fixture(autouse=True)
    def _set_thresholds(self, monkeypatch):
        monkeypatch.setattr(lg, "WARN_THRESHOLD", 2)
        monkeypatch.setattr(lg, "BLOCK_THRESHOLD", 4)

    def test_advisory_note_empty_when_count_below_warn(self, tmp_path):
        v = bump_and_check("task", "t", repo_root=tmp_path, session_id="s")
        assert advisory_note(v) == ""

    def test_advisory_note_warns_after_threshold_crossed(self, tmp_path):
        for _ in range(2):
            bump_and_check("task", "t", repo_root=tmp_path, session_id="s")
        v = bump_and_check("task", "t", repo_root=tmp_path, session_id="s")
        assert v["level"] == "warn"
        assert "LOOP WARN" in advisory_note(v)

    def test_advisory_note_blocks_after_block_threshold(self, tmp_path):
        for _ in range(4):
            bump_and_check("task", "t", repo_root=tmp_path, session_id="s")
        v = bump_and_check("task", "t", repo_root=tmp_path, session_id="s")
        assert v["level"] == "block"
        assert "LOOP BLOCK" in advisory_note(v)

    def test_different_tasks_each_get_own_advisory(self, tmp_path):
        for _ in range(3):
            bump_and_check("heavy task", "t", repo_root=tmp_path, session_id="s")
        v_heavy = bump_and_check("heavy task", "t", repo_root=tmp_path, session_id="s")
        v_light = bump_and_check("light task", "t", repo_root=tmp_path, session_id="s")

        assert v_heavy["level"] in ("warn", "block")
        assert v_light["level"] == "ok"
        assert advisory_note(v_light) == ""

    def test_counts_reset_after_new_session(self, tmp_path):
        for _ in range(5):
            bump_and_check("task", "t", repo_root=tmp_path, session_id="old")
        v = bump_and_check("task", "t", repo_root=tmp_path, session_id="brand_new")
        assert v["level"] == "ok"
        assert advisory_note(v) == ""
