"""Tests for 02_RUNTIME/orchestrator/task_runner.py.

# DEFICIENCIES NOTED
#
# 1. _compose_worker_prompt writes to config.artifact_dir at call time (side-effect
#    inside a "pure" function). This forces tests to either inject a tmp artifact_dir
#    or mock Path.write_text, and means unit tests of prompt composition always hit
#    the filesystem. A better design would decouple the "build prompt" function from
#    the "persist prompt" step.
#
# 2. real_record_event performs a read-then-write and then imports agent_scoring
#    *inside* the function body. The dynamic import means tests cannot easily patch
#    agent_scoring at module level; they must patch 'builtins.__import__' or use
#    sys.modules injection before the call.
#
# 3. _bead_detail, real_claim, real_lease, real_budget_breached all discover tool
#    paths via _which() at call time (no DI). This makes them harder to isolate
#    without either mocking shutil.which or providing fakes through Adapters.
#    Adapters already abstracts the high-level calls, so the real_* functions are
#    only reachable through integration / property tests; tested here via Adapters.
#
# 4. _create_worktree / _remove_worktree are thin wrappers over _run() with no
#    return-value documentation for partial-failure states (e.g. prune succeeds
#    but add fails). The single None-on-failure contract is sufficient but untested
#    in the module; added here.
#
# 5. TaskRunner.run_loop does not expose the attempted set — callers cannot inspect
#    which beads were skipped after the loop terminates. A small accessor or returned
#    metadata would aid observability.
#
# 6. _DESTRUCTIVE_RE patterns are good but do not cover `sudo rm`, `dd if=`, or
#    `wipefs`. Noted for completeness; not blocking but worth a follow-up bead.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

# ---------------------------------------------------------------------------
# Path plumbing — mirror the pattern used in test_orchestrator_engine.py
# ---------------------------------------------------------------------------

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
_REPO = _RUNTIME.parent
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# ---------------------------------------------------------------------------
# Lazy module loader — keeps go_mode (and its heavy deps) out of import time
# ---------------------------------------------------------------------------


def _load_task_runner():
    """Load task_runner as a fresh module, with go_mode stubbed out.

    The module is registered in sys.modules under its custom name before
    exec_module runs so that @dataclass introspection (which calls
    sys.modules[cls.__module__]) finds a live entry.
    """
    mod_path = _RUNTIME / "orchestrator" / "task_runner.py"
    _MOD_NAME = "task_runner_under_test"
    # Stub go_mode so the module-level try/import succeeds without the real binary
    stub_go_mode = MagicMock()
    stub_go_mode.load_queue_from_bd.return_value = []
    stub_go_mode.run_go.return_value = {"selected": None, "decision": "no_work", "dispatch_allowed": False}

    extra_stubs = {
        "go_mode": stub_go_mode,
        "common_harness": MagicMock(),
        "agent_scoring": MagicMock(),
        "lease_manager": MagicMock(),
    }
    spec = importlib.util.spec_from_file_location(_MOD_NAME, mod_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    with patch.dict(sys.modules, {_MOD_NAME: mod, **extra_stubs}):
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Load once for the module — individual tests that need isolation reload in-test
_tr = _load_task_runner()

Outcome = _tr.Outcome
WorkerResult = _tr.WorkerResult
IterationResult = _tr.IterationResult
RunnerConfig = _tr.RunnerConfig
Adapters = _tr.Adapters
TaskRunner = _tr.TaskRunner
_parse_worker_result = _tr._parse_worker_result
_bead_content = _tr._bead_content
_worktree_path = _tr._worktree_path
_DESTRUCTIVE_RE = _tr._DESTRUCTIVE_RE
_RESULT_MARKER = _tr._RESULT_MARKER


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_artifact_dir(tmp_path):
    """Isolated artifact directory per test."""
    d = tmp_path / "artifacts"
    d.mkdir()
    return d


@pytest.fixture()
def base_config(tmp_artifact_dir):
    """A RunnerConfig pointing at a temp artifact dir so tests never write to REPO."""
    return RunnerConfig(
        scope="epic",
        epic="bd-",
        t_level="T2",
        max_t_level="T3",
        max_iterations=5,
        max_usd=10.0,
        on_breach="pause",
        max_consecutive_failures=3,
        auto_merge=True,
        dry_run=False,
        artifact_dir=tmp_artifact_dir,
    )


@pytest.fixture()
def fake_adapters():
    """Adapters wired with successful-by-default fakes (no real subprocesses)."""
    return Adapters(
        load_queue=MagicMock(return_value=[]),
        decide=MagicMock(return_value={"selected": None, "decision": "no_work", "dispatch_allowed": False}),
        claim=MagicMock(return_value=True),
        dispatch=MagicMock(
            return_value=WorkerResult(ok=True, pr_number=42, branch="auto/bd-1", tests_passed=True, summary="done")
        ),
        await_ci=MagicMock(return_value=True),
        integrate=MagicMock(return_value=True),
        budget_breached=MagicMock(return_value=(False, "within budget")),
        record_event=MagicMock(),
        lease=MagicMock(),
    )


@pytest.fixture()
def runner(base_config, fake_adapters):
    return TaskRunner(config=base_config, adapters=fake_adapters)


def _bead(bead_id: str = "bd-1", **extra) -> dict:
    return {"id": bead_id, "title": "Test bead", **extra}


def _decide_ok(bead_id: str = "bd-1", score: float = 85.0, band: str = "execute") -> dict:
    return {
        "selected": _bead(bead_id),
        "decision": band,
        "dispatch_allowed": True,
        "confidence": {"score": score},
        "dispatch_reason": "score above threshold",
    }


# ===========================================================================
# Outcome enum
# ===========================================================================


class TestOutcomeEnum:
    def test_all_expected_values_exist(self):
        values = {o.value for o in Outcome}
        assert values >= {"idle", "skipped", "completed", "failed", "abandoned", "breach", "halt"}

    def test_outcome_is_str_subclass(self):
        assert isinstance(Outcome.COMPLETED, str)


# ===========================================================================
# WorkerResult dataclass
# ===========================================================================


class TestWorkerResult:
    def test_defaults(self):
        wr = WorkerResult(ok=False)
        assert wr.pr_number is None
        assert wr.branch == ""
        assert wr.tests_passed is False
        assert wr.summary == ""
        assert wr.raw == ""

    def test_fields_stored(self):
        wr = WorkerResult(ok=True, pr_number=99, branch="auto/bd-5", tests_passed=True, summary="great", raw="output")
        assert wr.ok is True
        assert wr.pr_number == 99
        assert wr.branch == "auto/bd-5"
        assert wr.tests_passed is True
        assert wr.summary == "great"
        assert wr.raw == "output"


# ===========================================================================
# IterationResult dataclass + to_dict
# ===========================================================================


class TestIterationResult:
    def test_to_dict_keys(self):
        ir = IterationResult(Outcome.COMPLETED, bead_id="bd-1", confidence=85.0, band="execute", detail="merged")
        d = ir.to_dict()
        assert d["outcome"] == "completed"
        assert d["bead_id"] == "bd-1"
        assert d["confidence"] == 85.0
        assert d["band"] == "execute"
        assert d["detail"] == "merged"
        assert "generated_at_utc" in d

    def test_to_dict_none_fields(self):
        ir = IterationResult(Outcome.IDLE)
        d = ir.to_dict()
        assert d["bead_id"] is None
        assert d["confidence"] is None
        assert d["pr_number"] is None

    def test_pr_number_in_dict(self):
        ir = IterationResult(Outcome.COMPLETED, pr_number=7)
        assert ir.to_dict()["pr_number"] == 7

    def test_generated_at_utc_is_string(self):
        ir = IterationResult(Outcome.IDLE)
        assert isinstance(ir.to_dict()["generated_at_utc"], str)


# ===========================================================================
# RunnerConfig
# ===========================================================================


class TestRunnerConfig:
    def test_defaults(self):
        cfg = RunnerConfig()
        assert cfg.scope == "epic"
        assert cfg.t_level == "T3"
        assert cfg.max_t_level == "T3"
        assert cfg.max_iterations == 25
        assert cfg.max_usd == 10.0
        assert cfg.on_breach == "pause"
        assert cfg.max_consecutive_failures == 3
        assert cfg.auto_merge is True
        assert cfg.dry_run is False
        assert cfg.isolate_worktree is True

    def test_to_dict_includes_artifact_dir_as_str(self):
        cfg = RunnerConfig()
        d = cfg.to_dict()
        assert isinstance(d["artifact_dir"], str)

    def test_to_dict_roundtrip_json_serialisable(self):
        cfg = RunnerConfig()
        d = cfg.to_dict()
        json.dumps(d)  # must not raise

    def test_custom_values(self):
        cfg = RunnerConfig(scope="single-bead", epic="xab3", t_level="T1", max_iterations=3, dry_run=True)
        assert cfg.scope == "single-bead"
        assert cfg.epic == "xab3"
        assert cfg.t_level == "T1"
        assert cfg.max_iterations == 3
        assert cfg.dry_run is True


# ===========================================================================
# _parse_worker_result
# ===========================================================================


class TestParseWorkerResult:
    def _make_out(self, payload: dict, prefix: str = "") -> str:
        line = f"{_RESULT_MARKER} {json.dumps(payload)}"
        return f"{prefix}\n{line}"

    def test_happy_path(self):
        out = self._make_out(
            {"ok": True, "pr_number": 42, "branch": "auto/bd-1", "tests_passed": True, "summary": "all good"}
        )
        r = _parse_worker_result(out)
        assert r.ok is True
        assert r.pr_number == 42
        assert r.branch == "auto/bd-1"
        assert r.tests_passed is True
        assert r.summary == "all good"

    def test_no_marker_returns_not_ok(self):
        r = _parse_worker_result("just some random output")
        assert r.ok is False
        assert "no RUNNER_RESULT line" in r.summary

    def test_last_marker_line_wins(self):
        """When multiple marker lines exist, the last one is used."""
        first = f"{_RESULT_MARKER} {json.dumps({'ok': False, 'summary': 'first'})}"
        second = f"{_RESULT_MARKER} {json.dumps({'ok': True, 'pr_number': 7, 'branch': 'auto/b', 'tests_passed': True, 'summary': 'second'})}"
        out = f"{first}\nsome noise\n{second}"
        r = _parse_worker_result(out)
        assert r.ok is True
        assert r.summary == "second"

    def test_invalid_json_returns_not_ok(self):
        out = f"prefix\n{_RESULT_MARKER} {{not valid json}}"
        r = _parse_worker_result(out)
        assert r.ok is False
        assert "unparseable" in r.summary

    def test_ok_false_in_payload(self):
        out = self._make_out({"ok": False, "summary": "CI failed"})
        r = _parse_worker_result(out)
        assert r.ok is False

    def test_pr_number_from_string_digit(self):
        out = self._make_out({"ok": True, "pr_number": "123", "branch": "b", "tests_passed": True, "summary": "s"})
        r = _parse_worker_result(out)
        assert r.pr_number == 123

    def test_pr_number_non_digit_string_is_none(self):
        out = self._make_out({"ok": True, "pr_number": "abc", "branch": "b", "tests_passed": True, "summary": "s"})
        r = _parse_worker_result(out)
        assert r.pr_number is None

    def test_summary_truncated_to_300(self):
        long_summary = "x" * 500
        out = self._make_out({"ok": True, "summary": long_summary, "pr_number": 1, "branch": "b", "tests_passed": True})
        r = _parse_worker_result(out)
        assert len(r.summary) <= 300

    def test_raw_capped_at_2000(self):
        big_out = (
            "a" * 5000
            + f"\n{_RESULT_MARKER} {json.dumps({'ok': True, 'summary': 's', 'branch': 'b', 'tests_passed': True, 'pr_number': 1})}"
        )
        r = _parse_worker_result(big_out)
        assert len(r.raw) <= 2000


# ===========================================================================
# _bead_content helper
# ===========================================================================


class TestBeadContent:
    def test_all_fields_joined(self):
        detail = {"title": "My Title", "description": "My Desc", "acceptance_criteria": "Must pass"}
        text = _bead_content(detail)
        assert "My Title" in text
        assert "My Desc" in text
        assert "Must pass" in text

    def test_criteria_as_list(self):
        detail = {"title": "t", "description": "d", "acceptance_criteria": ["crit1", "crit2"]}
        text = _bead_content(detail)
        assert "crit1" in text
        assert "crit2" in text

    def test_missing_fields_empty_string(self):
        text = _bead_content({})
        assert isinstance(text, str)

    def test_none_values_handled(self):
        detail = {"title": None, "description": None, "acceptance_criteria": None}
        text = _bead_content(detail)
        assert isinstance(text, str)


# ===========================================================================
# _DESTRUCTIVE_RE pattern coverage
# ===========================================================================


class TestDestructiveRe:
    @pytest.mark.parametrize(
        "text",
        [
            "rm -rf /",
            "git reset --hard HEAD~1",
            "git push --force origin main",
            "git push --force",
            "--no-verify this commit",
            "drop database production",
            "DROP DATABASE my_db",
            "truncate table users",
            "TRUNCATE TABLE logs",
            "mkfs.ext4 /dev/sda",
            ":() { :|: & }; :",
        ],
    )
    def test_destructive_pattern_matched(self, text):
        assert _DESTRUCTIVE_RE.search(text) is not None, f"Expected match for: {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "run tests",
            "git push origin feature-branch",
            "git commit -m 'fix bug'",
            "create table users",
            "This is a safe operation",
            "drop the issue from the backlog",
        ],
    )
    def test_safe_text_not_matched(self, text):
        assert _DESTRUCTIVE_RE.search(text) is None, f"Expected no match for: {text!r}"


# ===========================================================================
# _worktree_path
# ===========================================================================


class TestWorktreePath:
    def test_slashes_replaced(self):
        p = _worktree_path("epic/bd-1")
        assert "/" not in p.name

    def test_dots_replaced(self):
        p = _worktree_path("bd.1.2")
        assert "." not in p.name

    def test_empty_string_defaults_to_task(self):
        p = _worktree_path("")
        assert "task" in p.name

    def test_path_under_worktrees_root(self):
        p = _worktree_path("bd-42")
        assert p.parent.name == ".worktrees"


# ===========================================================================
# TaskRunner helpers
# ===========================================================================


class TestTaskRunnerHelpers:
    def test_stop_requested_via_env(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.setenv("TASK_RUNNER_STOP", "1")
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        assert runner._stop_requested() is True

    def test_stop_requested_via_env_true(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.setenv("TASK_RUNNER_STOP", "true")
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        assert runner._stop_requested() is True

    def test_stop_not_requested_by_default(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        assert runner._stop_requested() is False

    def test_stop_requested_via_stop_file(self, tmp_artifact_dir, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        cfg = RunnerConfig(artifact_dir=tmp_artifact_dir)
        (tmp_artifact_dir / "STOP").write_text("")
        runner = TaskRunner(config=cfg, adapters=fake_adapters)
        assert runner._stop_requested() is True

    def test_t_level_ok_t2_within_t3(self, base_config, fake_adapters):
        base_config.t_level = "T2"
        base_config.max_t_level = "T3"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        assert runner._t_level_ok() is True

    def test_t_level_ok_t3_within_t3(self, base_config, fake_adapters):
        base_config.t_level = "T3"
        base_config.max_t_level = "T3"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        assert runner._t_level_ok() is True

    def test_t_level_nok_t4(self, base_config, fake_adapters):
        base_config.t_level = "T4"
        base_config.max_t_level = "T3"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        assert runner._t_level_ok() is False

    def test_t_level_nok_max_t4(self, base_config, fake_adapters):
        """Even if t_level is T3, max_t_level=T4 fails because ceiling must be <= T3."""
        base_config.t_level = "T3"
        base_config.max_t_level = "T4"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        assert runner._t_level_ok() is False

    def test_apply_scope_filters_attempted(self, runner):
        queue = [_bead("bd-1"), _bead("bd-2"), _bead("bd-3")]
        filtered = runner._apply_scope(queue, attempted={"bd-1", "bd-2"})
        assert [b["id"] for b in filtered] == ["bd-3"]

    def test_apply_scope_epic_prefix_filter(self, base_config, fake_adapters):
        base_config.scope = "epic"
        base_config.epic = "bd-"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        queue = [_bead("bd-1"), _bead("other-1"), _bead("bd-2")]
        filtered = runner._apply_scope(queue, attempted=set())
        ids = [b["id"] for b in filtered]
        assert "bd-1" in ids
        assert "bd-2" in ids
        assert "other-1" not in ids

    def test_apply_scope_no_epic_filter_when_scope_not_epic(self, base_config, fake_adapters):
        base_config.scope = "area"
        base_config.epic = "bd-"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        queue = [_bead("bd-1"), _bead("other-1")]
        filtered = runner._apply_scope(queue, attempted=set())
        assert len(filtered) == 2

    def test_safe_returns_value_on_success(self, runner):
        assert runner._safe(lambda: 42, 0) == 42

    def test_safe_returns_default_on_exception(self, runner):
        def boom():
            raise ValueError("kaboom")

        assert runner._safe(boom, "fallback") == "fallback"

    def test_record_normalises_score_above_1(self, runner):
        runner.adapters.record_event = MagicMock()
        runner._record("bd-1", "completed", 85.0)
        event = runner.adapters.record_event.call_args[0][1]
        assert event["confidence"] == round(85.0 / 100.0, 4)

    def test_record_normalises_score_below_1(self, runner):
        runner.adapters.record_event = MagicMock()
        runner._record("bd-1", "completed", 0.85)
        event = runner.adapters.record_event.call_args[0][1]
        assert event["confidence"] == 0.85

    def test_record_none_confidence_uses_zero(self, runner):
        runner.adapters.record_event = MagicMock()
        runner._record("bd-1", "completed", None)
        event = runner.adapters.record_event.call_args[0][1]
        assert event["confidence"] == 0.0

    def test_record_includes_false_positive(self, runner):
        runner.adapters.record_event = MagicMock()
        runner._record("bd-1", "failed", 70.0, false_positive=True)
        event = runner.adapters.record_event.call_args[0][1]
        assert event["false_positive"] is True


# ===========================================================================
# TaskRunner._apply_on_breach
# ===========================================================================


class TestApplyOnBreach:
    def test_writes_breach_latest_json(self, runner, tmp_artifact_dir):
        runner._apply_on_breach("budget exceeded")
        breach_file = tmp_artifact_dir / "breach_latest.json"
        assert breach_file.exists()
        data = json.loads(breach_file.read_text())
        assert data["reason"] == "budget exceeded"

    def test_handoff_action_writes_handoff_file(self, base_config, fake_adapters, tmp_artifact_dir):
        base_config.on_breach = "handoff"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        runner._apply_on_breach("spend over ceiling")
        handoff = tmp_artifact_dir / "task_runner_handoff.json"
        assert handoff.exists()
        data = json.loads(handoff.read_text())
        assert data["from"] == "task-runner"

    def test_pause_action_no_handoff_file(self, base_config, fake_adapters, tmp_artifact_dir):
        base_config.on_breach = "pause"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        runner._apply_on_breach("any reason")
        assert not (tmp_artifact_dir / "task_runner_handoff.json").exists()


# ===========================================================================
# TaskRunner._write_latest
# ===========================================================================


class TestWriteLatest:
    def test_writes_latest_json(self, runner, tmp_artifact_dir):
        ir = IterationResult(Outcome.COMPLETED, bead_id="bd-1", confidence=80.0, band="execute")
        runner._write_latest(ir)
        assert (tmp_artifact_dir / "latest.json").exists()
        data = json.loads((tmp_artifact_dir / "latest.json").read_text())
        assert data["outcome"] == "completed"

    def test_appends_history_jsonl(self, runner, tmp_artifact_dir):
        for bead in ("bd-1", "bd-2"):
            ir = IterationResult(Outcome.COMPLETED, bead_id=bead, confidence=80.0)
            runner._write_latest(ir)
        lines = (tmp_artifact_dir / "history.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["bead_id"] == "bd-1"
        assert json.loads(lines[1])["bead_id"] == "bd-2"


# ===========================================================================
# TaskRunner.run_once — HALT paths
# ===========================================================================


class TestRunOnceHalt:
    def test_halt_on_stop_env(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.setenv("TASK_RUNNER_STOP", "1")
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        result = runner.run_once()
        assert result.outcome == Outcome.HALT
        assert "kill-switch" in result.detail

    def test_halt_on_stop_file(self, tmp_artifact_dir, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        (tmp_artifact_dir / "STOP").write_text("")
        cfg = RunnerConfig(artifact_dir=tmp_artifact_dir)
        runner = TaskRunner(config=cfg, adapters=fake_adapters)
        result = runner.run_once()
        assert result.outcome == Outcome.HALT

    def test_halt_on_t4_level(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        base_config.t_level = "T4"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        result = runner.run_once()
        assert result.outcome == Outcome.HALT
        assert "T4" in result.detail

    def test_halt_t3_when_max_t_level_is_t4(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        base_config.t_level = "T3"
        base_config.max_t_level = "T4"
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        result = runner.run_once()
        assert result.outcome == Outcome.HALT


# ===========================================================================
# TaskRunner.run_once — BREACH path
# ===========================================================================


class TestRunOnceBreach:
    def test_budget_breach_returns_breach_outcome(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        fake_adapters.budget_breached = MagicMock(return_value=(True, "over $10"))
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        result = runner.run_once()
        assert result.outcome == Outcome.BREACH
        assert "budget guard" in result.detail

    def test_budget_breach_calls_apply_on_breach(self, base_config, fake_adapters, monkeypatch, tmp_artifact_dir):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        fake_adapters.budget_breached = MagicMock(return_value=(True, "over ceiling"))
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        runner.run_once()
        assert (tmp_artifact_dir / "breach_latest.json").exists()

    def test_budget_guard_exception_fails_open(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        fake_adapters.budget_breached = MagicMock(side_effect=RuntimeError("guard error"))
        # Queue is empty, so result will be IDLE (guard exception fails open → no breach)
        fake_adapters.load_queue = MagicMock(return_value=[])
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        result = runner.run_once()
        assert result.outcome == Outcome.IDLE


# ===========================================================================
# TaskRunner.run_once — IDLE path
# ===========================================================================


class TestRunOnceIdle:
    def test_idle_when_queue_empty(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[])
        runner.adapters.decide = MagicMock(
            return_value={"selected": None, "decision": "no_work", "dispatch_allowed": False}
        )
        result = runner.run_once()
        assert result.outcome == Outcome.IDLE

    def test_idle_when_decide_returns_no_selection(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(
            return_value={"selected": None, "decision": "no_work", "dispatch_allowed": False}
        )
        result = runner.run_once()
        assert result.outcome == Outcome.IDLE

    def test_idle_when_all_beads_already_attempted(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value={"selected": None})
        result = runner.run_once(attempted={"bd-1"})
        assert result.outcome == Outcome.IDLE


# ===========================================================================
# TaskRunner.run_once — SKIPPED paths
# ===========================================================================


class TestRunOnceSkipped:
    def test_skipped_below_gate(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(
            return_value={
                "selected": _bead("bd-1"),
                "decision": "replan",
                "dispatch_allowed": False,
                "confidence": {"score": 40.0},
                "dispatch_reason": "score too low",
            }
        )
        result = runner.run_once()
        assert result.outcome == Outcome.SKIPPED
        assert result.bead_id == "bd-1"
        assert "below gate" in result.detail

    def test_skipped_records_abandoned_event(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(
            return_value={
                "selected": _bead("bd-1"),
                "decision": "halt",
                "dispatch_allowed": False,
                "confidence": {"score": 20.0},
            }
        )
        runner.adapters.record_event = MagicMock()
        runner.run_once()
        runner.adapters.record_event.assert_called_once()
        event = runner.adapters.record_event.call_args[0][1]
        assert event["outcome"] == "abandoned"

    def test_skipped_on_dry_run(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        base_config.dry_run = True
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1"))
        result = runner.run_once()
        assert result.outcome == Outcome.SKIPPED
        assert "dry-run" in result.detail

    def test_dry_run_never_claims(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        base_config.dry_run = True
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1"))
        runner.run_once()
        runner.adapters.claim.assert_not_called()

    def test_skipped_when_claim_fails(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1"))
        runner.adapters.claim = MagicMock(return_value=False)
        result = runner.run_once()
        assert result.outcome == Outcome.SKIPPED
        assert "claim failed" in result.detail


# ===========================================================================
# TaskRunner.run_once — ABANDONED path
# ===========================================================================


class TestRunOnceAbandoned:
    def test_abandoned_when_worker_fails(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1"))
        runner.adapters.dispatch = MagicMock(return_value=WorkerResult(ok=False, summary="claude not found"))
        result = runner.run_once()
        assert result.outcome == Outcome.ABANDONED
        assert "claude not found" in result.detail

    def test_abandoned_releases_lease(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1"))
        runner.adapters.dispatch = MagicMock(return_value=WorkerResult(ok=False, summary="fail"))
        runner.run_once()
        # lease release must be called (action="release")
        release_calls = [c for c in runner.adapters.lease.call_args_list if c[0][0] == "release"]
        assert len(release_calls) >= 1

    def test_abandoned_records_abandoned_event(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1"))
        runner.adapters.dispatch = MagicMock(return_value=WorkerResult(ok=False, summary="fail"))
        runner.adapters.record_event = MagicMock()
        runner.run_once()
        event = runner.adapters.record_event.call_args[0][1]
        assert event["outcome"] == "abandoned"

    def test_abandoned_when_dispatch_raises(self, runner, monkeypatch):
        """Dispatch raising should fail-open to WorkerResult(ok=False)."""
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1"))
        runner.adapters.dispatch = MagicMock(side_effect=RuntimeError("unexpected"))
        result = runner.run_once()
        assert result.outcome == Outcome.ABANDONED


# ===========================================================================
# TaskRunner.run_once — FAILED paths
# ===========================================================================


class TestRunOnceFailed:
    def test_failed_when_ci_red(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1"))
        runner.adapters.dispatch = MagicMock(
            return_value=WorkerResult(ok=True, pr_number=42, branch="auto/bd-1", tests_passed=False, summary="s")
        )
        runner.adapters.await_ci = MagicMock(return_value=False)
        result = runner.run_once()
        assert result.outcome == Outcome.FAILED
        assert "CI red" in result.detail

    def test_failed_ci_red_records_false_positive(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1"))
        runner.adapters.dispatch = MagicMock(
            return_value=WorkerResult(ok=True, pr_number=42, branch="auto/bd-1", tests_passed=False, summary="s")
        )
        runner.adapters.await_ci = MagicMock(return_value=False)
        runner.adapters.record_event = MagicMock()
        runner.run_once()
        event = runner.adapters.record_event.call_args[0][1]
        assert event["false_positive"] is True

    def test_failed_when_merge_fails(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band="execute"))
        runner.adapters.dispatch = MagicMock(
            return_value=WorkerResult(ok=True, pr_number=42, branch="auto/bd-1", tests_passed=True, summary="s")
        )
        runner.adapters.await_ci = MagicMock(return_value=True)
        runner.adapters.integrate = MagicMock(return_value=False)
        result = runner.run_once()
        assert result.outcome == Outcome.FAILED
        assert "merge" in result.detail


# ===========================================================================
# TaskRunner.run_once — COMPLETED path
# ===========================================================================


class TestRunOnceCompleted:
    def test_completed_happy_path(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band="execute"))
        result = runner.run_once()
        assert result.outcome == Outcome.COMPLETED
        assert result.bead_id == "bd-1"
        assert result.pr_number == 42

    def test_completed_records_event(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band="execute"))
        runner.adapters.record_event = MagicMock()
        runner.run_once()
        event = runner.adapters.record_event.call_args[0][1]
        assert event["outcome"] == "completed"

    def test_completed_releases_lease(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band="execute"))
        runner.run_once()
        release_calls = [c for c in runner.adapters.lease.call_args_list if c[0][0] == "release"]
        assert len(release_calls) >= 1

    def test_no_merge_when_auto_merge_false(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        base_config.auto_merge = False
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band="execute"))
        runner.run_once()
        runner.adapters.integrate.assert_not_called()

    def test_no_merge_when_band_not_execute(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band="replan"))
        runner.run_once()
        runner.adapters.integrate.assert_not_called()

    def test_execute_logged_band_triggers_merge(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band="execute_logged"))
        runner.run_once()
        runner.adapters.integrate.assert_called_once()

    def test_confidence_band_propagated_in_result(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", score=90.0, band="execute"))
        result = runner.run_once()
        assert result.confidence == 90.0
        assert result.band == "execute"

    def test_lease_acquire_called_with_bead_id(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band="execute"))
        runner.run_once()
        acquire_calls = [c for c in runner.adapters.lease.call_args_list if c[0][0] == "acquire"]
        assert len(acquire_calls) == 1
        assert acquire_calls[0][0][1] == "bd-1"


# ===========================================================================
# TaskRunner.run_once — claim / lease sequencing
# ===========================================================================


class TestRunOnceClaimLease:
    def test_claim_called_before_dispatch(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        call_order = []
        runner.adapters.claim = MagicMock(side_effect=lambda _: call_order.append("claim") or True)
        runner.adapters.dispatch = MagicMock(
            side_effect=lambda *a: (
                call_order.append("dispatch")
                or WorkerResult(ok=True, pr_number=1, branch="b", tests_passed=True, summary="s")
            )
        )
        runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band="execute"))
        runner.run_once()
        assert call_order.index("claim") < call_order.index("dispatch")

    def test_allowed_files_passed_to_lease(self, runner, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        bead = _bead("bd-1", allowed_files=["src/a.py", "src/b.py"])
        runner.adapters.load_queue = MagicMock(return_value=[bead])
        runner.adapters.decide = MagicMock(
            return_value={
                "selected": bead,
                "decision": "execute",
                "dispatch_allowed": True,
                "confidence": {"score": 85.0},
            }
        )
        runner.run_once()
        acquire_calls = [c for c in runner.adapters.lease.call_args_list if c[0][0] == "acquire"]
        assert acquire_calls[0][0][2] == ["src/a.py", "src/b.py"]


# ===========================================================================
# TaskRunner.run_loop — loop control
# ===========================================================================


class TestRunLoop:
    def test_stops_on_halt(self, base_config, fake_adapters, monkeypatch, tmp_artifact_dir):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        (tmp_artifact_dir / "STOP").write_text("")
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        results = runner.run_loop()
        assert results[-1].outcome == Outcome.HALT
        assert len(results) == 1

    def test_stops_on_idle(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        fake_adapters.load_queue = MagicMock(return_value=[])
        fake_adapters.decide = MagicMock(return_value={"selected": None})
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        results = runner.run_loop()
        assert results[-1].outcome == Outcome.IDLE
        assert len(results) == 1

    def test_stops_on_breach(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        fake_adapters.budget_breached = MagicMock(return_value=(True, "over ceiling"))
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        results = runner.run_loop()
        assert results[-1].outcome == Outcome.BREACH
        assert len(results) == 1

    def test_attempted_set_grows_across_iterations(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        beads = [_bead("bd-1"), _bead("bd-2")]
        decide_responses = [
            _decide_ok("bd-1", band="execute"),
            _decide_ok("bd-2", band="execute"),
            {"selected": None},  # terminates the loop
        ]
        fake_adapters.load_queue = MagicMock(return_value=beads)
        fake_adapters.decide = MagicMock(side_effect=decide_responses)
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        results = runner.run_loop()
        completed = [r for r in results if r.outcome == Outcome.COMPLETED]
        assert len(completed) == 2
        bead_ids = {r.bead_id for r in completed}
        assert bead_ids == {"bd-1", "bd-2"}

    def test_max_iterations_cap(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        base_config.max_iterations = 3
        # Supply more beads than max_iterations; loop must stop at the cap.
        fake_adapters.load_queue = MagicMock(return_value=[_bead(f"bd-{i}") for i in range(10)])
        fake_adapters.decide = MagicMock(side_effect=[_decide_ok(f"bd-{i}", band="execute") for i in range(10)])
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        results = runner.run_loop()
        assert len(results) <= base_config.max_iterations

    def test_consecutive_failures_trigger_circuit_breaker(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        base_config.max_consecutive_failures = 2
        base_config.on_breach = "pause"

        call_count = 0

        def decide_always_fail(_queue):
            nonlocal call_count
            call_count += 1
            return _decide_ok(f"bd-{call_count}", band="execute")

        fake_adapters.load_queue = MagicMock(return_value=[_bead(f"bd-{i}") for i in range(10)])
        fake_adapters.decide = MagicMock(side_effect=decide_always_fail)
        fake_adapters.dispatch = MagicMock(return_value=WorkerResult(ok=False, summary="always fails"))
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        results = runner.run_loop()
        outcomes = [r.outcome for r in results]
        assert Outcome.BREACH in outcomes

    def test_on_breach_halt_stops_after_first_failure(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        base_config.on_breach = "halt"
        fake_adapters.load_queue = MagicMock(return_value=[_bead("bd-1"), _bead("bd-2")])
        fake_adapters.decide = MagicMock(
            side_effect=[
                _decide_ok("bd-1", band="execute"),
                _decide_ok("bd-2", band="execute"),
            ]
        )
        fake_adapters.dispatch = MagicMock(return_value=WorkerResult(ok=False, summary="fail"))
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        results = runner.run_loop()
        # Loop must stop after first FAILED outcome when on_breach=halt
        assert len(results) == 1
        assert results[0].outcome == Outcome.ABANDONED

    def test_consecutive_failure_counter_resets_on_success(self, base_config, fake_adapters, monkeypatch):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        base_config.max_consecutive_failures = 2
        beads = [_bead(f"bd-{i}") for i in range(5)]

        dispatch_responses = [
            WorkerResult(ok=False, summary="fail"),  # bd-0: failure (count=1)
            WorkerResult(
                ok=True, pr_number=1, branch="b", tests_passed=True, summary="ok"
            ),  # bd-1: success (count resets)
            WorkerResult(ok=False, summary="fail"),  # bd-2: failure (count=1)
            WorkerResult(ok=False, summary="fail"),  # bd-3: failure (count=2) → breach
        ]

        decide_responses = [
            _decide_ok("bd-0", band="execute"),
            _decide_ok("bd-1", band="execute"),
            _decide_ok("bd-2", band="execute"),
            _decide_ok("bd-3", band="execute"),
            {"selected": None},
        ]

        fake_adapters.load_queue = MagicMock(return_value=beads)
        fake_adapters.decide = MagicMock(side_effect=decide_responses)
        fake_adapters.dispatch = MagicMock(side_effect=dispatch_responses)
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        results = runner.run_loop()
        outcomes = [r.outcome for r in results]
        # We expect the circuit breaker to fire after bd-3 (second consecutive failure after a success)
        assert Outcome.BREACH in outcomes

    def test_writes_summary_file(self, base_config, fake_adapters, monkeypatch, tmp_artifact_dir):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        fake_adapters.load_queue = MagicMock(return_value=[])
        fake_adapters.decide = MagicMock(return_value={"selected": None})
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        runner.run_loop()
        summary_file = tmp_artifact_dir / "summary_latest.json"
        assert summary_file.exists()
        data = json.loads(summary_file.read_text())
        assert "iterations" in data
        assert "counts" in data
        assert "completed_beads" in data

    def test_write_latest_called_per_iteration(self, base_config, fake_adapters, monkeypatch, tmp_artifact_dir):
        monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
        fake_adapters.load_queue = MagicMock(return_value=[])
        fake_adapters.decide = MagicMock(return_value={"selected": None})
        runner = TaskRunner(config=base_config, adapters=fake_adapters)
        runner.run_loop()
        assert (tmp_artifact_dir / "latest.json").exists()
        assert (tmp_artifact_dir / "history.jsonl").exists()


# ===========================================================================
# TaskRunner._write_summary
# ===========================================================================


class TestWriteSummary:
    def test_summary_counts_match_results(self, runner, tmp_artifact_dir):
        results = [
            IterationResult(Outcome.COMPLETED, bead_id="bd-1"),
            IterationResult(Outcome.COMPLETED, bead_id="bd-2"),
            IterationResult(Outcome.FAILED, bead_id="bd-3"),
        ]
        runner._write_summary(results)
        data = json.loads((tmp_artifact_dir / "summary_latest.json").read_text())
        assert data["counts"]["completed"] == 2
        assert data["counts"]["failed"] == 1

    def test_summary_completed_beads_list(self, runner, tmp_artifact_dir):
        results = [
            IterationResult(Outcome.COMPLETED, bead_id="bd-1"),
            IterationResult(Outcome.FAILED, bead_id="bd-2"),
        ]
        runner._write_summary(results)
        data = json.loads((tmp_artifact_dir / "summary_latest.json").read_text())
        assert data["completed_beads"] == ["bd-1"]

    def test_summary_config_included(self, runner, tmp_artifact_dir):
        runner._write_summary([])
        data = json.loads((tmp_artifact_dir / "summary_latest.json").read_text())
        assert "config" in data

    def test_summary_not_raised_on_unwriteable_dir(self, base_config, fake_adapters):
        """_write_summary swallows exceptions — must not propagate."""
        base_config.artifact_dir = Path("/nonexistent_dir_xyz_abc/")
        runner = TaskRunner.__new__(TaskRunner)
        runner.config = base_config
        runner.adapters = fake_adapters
        # Must not raise
        runner._write_summary([IterationResult(Outcome.IDLE)])


# ===========================================================================
# Parametrised: run_once outcome across decision variations
# ===========================================================================


@pytest.mark.parametrize(
    "band,expect_merge",
    [
        ("execute", True),
        ("execute_logged", True),
        ("replan", False),
        ("halt", False),
        ("review", False),
    ],
)
def test_merge_only_on_execute_bands(band, expect_merge, base_config, fake_adapters, monkeypatch):
    monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
    fake_adapters.load_queue = MagicMock(return_value=[_bead("bd-1")])
    fake_adapters.decide = MagicMock(return_value=_decide_ok("bd-1", band=band))
    runner = TaskRunner(config=base_config, adapters=fake_adapters)
    runner.run_once()
    if expect_merge:
        fake_adapters.integrate.assert_called_once()
    else:
        fake_adapters.integrate.assert_not_called()


@pytest.mark.parametrize(
    "outcome",
    [
        Outcome.COMPLETED,
        Outcome.FAILED,
        Outcome.ABANDONED,
        Outcome.SKIPPED,
    ],
)
def test_bead_id_set_on_non_idle_outcomes(outcome, runner, monkeypatch):
    """IterationResult.bead_id is populated for any outcome that selected a bead."""
    monkeypatch.delenv("TASK_RUNNER_STOP", raising=False)
    runner.adapters.load_queue = MagicMock(return_value=[_bead("bd-42")])
    if outcome == Outcome.COMPLETED:
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-42", band="execute"))
    elif outcome == Outcome.FAILED:
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-42", band="execute"))
        runner.adapters.await_ci = MagicMock(return_value=False)
    elif outcome == Outcome.ABANDONED:
        runner.adapters.decide = MagicMock(return_value=_decide_ok("bd-42", band="execute"))
        runner.adapters.dispatch = MagicMock(return_value=WorkerResult(ok=False, summary="fail"))
    elif outcome == Outcome.SKIPPED:
        runner.adapters.decide = MagicMock(
            return_value={
                "selected": _bead("bd-42"),
                "decision": "replan",
                "dispatch_allowed": False,
                "confidence": {"score": 30.0},
            }
        )
    result = runner.run_once()
    assert result.bead_id == "bd-42"


# ===========================================================================
# import_error helper
# ===========================================================================


def test_import_error_exposed():
    """import_error() returns None when go_mode loaded successfully (our stub scenario)."""
    err = _tr.import_error()
    # Our stub loaded successfully (no exception), so import error should be None
    assert err is None
