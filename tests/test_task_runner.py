"""Tests for the long-running next-task supervisor (bead chromatic-harness-v2-xab3).

Network-free: bd/claude/gh are never invoked. All side-effecting operations are
injected as fakes via Adapters, so the loop, state machine, confidence gate,
guards, kill-switch, circuit breaker, fail-open behavior, and telemetry
normalization are verified deterministically.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    # The module inserts scripts/ on sys.path itself for its internal `import go_mode`.
    sys.path.insert(0, str(REPO / "scripts"))
    sys.path.insert(0, str(REPO / "02_RUNTIME"))
    spec = importlib.util.spec_from_file_location(
        "task_runner_mod", REPO / "02_RUNTIME" / "orchestrator" / "task_runner.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["task_runner_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


TR = _load()


# ── fakes ─────────────────────────────────────────────────────────────────────


def _record(bead_id: str, score: float, band: str, allowed: bool, reason: str = "") -> dict:
    return {
        "selected": {"id": bead_id, "title": f"title {bead_id}", "priority": "P1"},
        "confidence": {"score": score, "band": band},
        "decision": band,
        "dispatch_allowed": allowed,
        "dispatch_reason": reason,
        "mission_packet": {},
    }


def build_runner(
    tmp_path,
    *,
    queue=None,
    score=85.0,
    band="execute",
    allowed=True,
    claim=True,
    worker=None,
    ci_green=True,
    integrate_ok=True,
    budget=(False, "ok"),
    auto_merge=True,
    dry_run=False,
    on_breach="pause",
    max_iterations=5,
    max_consecutive_failures=3,
    t_level="T3",
    max_t_level="T3",
    raising=None,
):
    calls: dict[str, list] = {}
    queue = [{"id": "b1"}] if queue is None else queue
    worker = (
        worker
        if worker is not None
        else TR.WorkerResult(ok=True, pr_number=7, branch="auto/b1", tests_passed=True, summary="done")
    )
    raising = raising or set()

    def _load_queue():
        if "load_queue" in raising:
            raise RuntimeError("boom")
        return list(queue)

    def _decide(q):
        if "decide" in raising:
            raise RuntimeError("boom")
        if not q:
            return {"selected": None}
        return _record(str(q[0]["id"]), score, band, allowed)

    def _claim(bid):
        calls.setdefault("claim", []).append(bid)
        return claim

    def _dispatch(b, c, cfg):
        calls.setdefault("dispatch", []).append(str(b["id"]))
        if "dispatch" in raising:
            raise RuntimeError("boom")
        return worker

    def _ci(w, cfg):
        calls.setdefault("ci", []).append(w.pr_number)
        return ci_green

    def _integrate(b, w, cfg):
        calls.setdefault("integrate", []).append(str(b["id"]))
        return integrate_ok

    def _budget(cfg):
        return budget

    def _rec(artifact_dir, event):
        calls.setdefault("record", []).append(event)

    def _lease(action, bid, res):
        calls.setdefault("lease", []).append((action, bid))

    adapters = TR.Adapters(
        load_queue=_load_queue,
        decide=_decide,
        claim=_claim,
        dispatch=_dispatch,
        await_ci=_ci,
        integrate=_integrate,
        budget_breached=_budget,
        record_event=_rec,
        lease=_lease,
    )
    cfg = TR.RunnerConfig(
        scope="area",
        artifact_dir=tmp_path,
        auto_merge=auto_merge,
        dry_run=dry_run,
        on_breach=on_breach,
        max_iterations=max_iterations,
        max_consecutive_failures=max_consecutive_failures,
        t_level=t_level,
        max_t_level=max_t_level,
        max_usd=0,  # disable real budget path; fake budget controls breach
    )
    return TR.TaskRunner(cfg, adapters), calls


# ── selection & gate ────────────────────────────────────────────────────────


def test_empty_queue_is_idle(tmp_path):
    runner, calls = build_runner(tmp_path, queue=[])
    r = runner.run_once()
    assert r.outcome == TR.Outcome.IDLE
    assert "claim" not in calls


def test_below_gate_skips_without_claiming(tmp_path):
    runner, calls = build_runner(tmp_path, allowed=False, band="plan_only", score=42.0)
    r = runner.run_once()
    assert r.outcome == TR.Outcome.SKIPPED
    assert "claim" not in calls
    # the skip is recorded with its (normalized) confidence
    assert calls["record"][-1]["outcome"] == "abandoned"
    assert calls["record"][-1]["confidence"] == 0.42


def test_dry_run_stops_before_claim(tmp_path):
    runner, calls = build_runner(tmp_path, dry_run=True)
    r = runner.run_once()
    assert r.outcome == TR.Outcome.SKIPPED
    assert "dry-run" in r.detail
    assert "claim" not in calls
    assert "record" not in calls  # dry-run never pollutes telemetry


# ── happy path & lifecycle branches ───────────────────────────────────────────


def test_happy_path_completes_and_merges(tmp_path):
    runner, calls = build_runner(tmp_path)
    r = runner.run_once()
    assert r.outcome == TR.Outcome.COMPLETED
    assert r.pr_number == 7
    assert calls["claim"] == ["b1"]
    assert calls["dispatch"] == ["b1"]
    assert calls["integrate"] == ["b1"]
    assert calls["record"][-1]["outcome"] == "completed"
    # lease acquired then released
    assert ("acquire", "b1") in calls["lease"]
    assert ("release", "b1") in calls["lease"]


def test_confidence_is_normalized_to_unit_interval(tmp_path):
    runner, calls = build_runner(tmp_path, score=85.0)
    runner.run_once()
    assert calls["record"][-1]["confidence"] == 0.85  # 85/100


def test_ci_red_fails_without_merge(tmp_path):
    runner, calls = build_runner(tmp_path, ci_green=False)
    r = runner.run_once()
    assert r.outcome == TR.Outcome.FAILED
    assert "integrate" not in calls
    assert calls["record"][-1]["outcome"] == "failed"
    assert calls["record"][-1]["false_positive"] is True


def test_worker_failure_is_abandoned(tmp_path):
    runner, calls = build_runner(tmp_path, worker=TR.WorkerResult(ok=False, summary="claude missing"))
    r = runner.run_once()
    assert r.outcome == TR.Outcome.ABANDONED
    assert "ci" not in calls
    assert "integrate" not in calls


def test_no_auto_merge_completes_without_integrating(tmp_path):
    runner, calls = build_runner(tmp_path, auto_merge=False)
    r = runner.run_once()
    assert r.outcome == TR.Outcome.COMPLETED
    assert "integrate" not in calls


def test_merge_failure_is_failed(tmp_path):
    runner, calls = build_runner(tmp_path, integrate_ok=False)
    r = runner.run_once()
    assert r.outcome == TR.Outcome.FAILED
    assert calls["record"][-1]["outcome"] == "failed"


def test_claim_failure_skips(tmp_path):
    runner, calls = build_runner(tmp_path, claim=False)
    r = runner.run_once()
    assert r.outcome == TR.Outcome.SKIPPED
    assert "dispatch" not in calls


# ── guards & safety ────────────────────────────────────────────────────────


def test_budget_breach_halts_with_on_breach(tmp_path):
    runner, calls = build_runner(tmp_path, budget=(True, "over $10"))
    r = runner.run_once()
    assert r.outcome == TR.Outcome.BREACH
    assert (tmp_path / "breach_latest.json").exists()
    assert "claim" not in calls


def test_kill_switch_stop_file_halts(tmp_path):
    runner, _ = build_runner(tmp_path)
    (tmp_path / "STOP").write_text("stop", encoding="utf-8")
    r = runner.run_once()
    assert r.outcome == TR.Outcome.HALT


def test_kill_switch_env_halts(tmp_path, monkeypatch):
    runner, _ = build_runner(tmp_path)
    monkeypatch.setenv("TASK_RUNNER_STOP", "1")
    r = runner.run_once()
    assert r.outcome == TR.Outcome.HALT


def test_t4_is_never_autonomous(tmp_path):
    runner, _ = build_runner(tmp_path, t_level="T4", max_t_level="T3")
    r = runner.run_once()
    assert r.outcome == TR.Outcome.HALT
    assert "T4" in r.detail or "exceeds" in r.detail


def test_t_level_above_ceiling_halts(tmp_path):
    runner, _ = build_runner(tmp_path, t_level="T3", max_t_level="T2")
    r = runner.run_once()
    assert r.outcome == TR.Outcome.HALT


def test_handoff_writes_packet_to_artifact_dir(tmp_path):
    runner, _ = build_runner(tmp_path, budget=(True, "over"), on_breach="handoff")
    runner.run_once()
    assert (tmp_path / "task_runner_handoff.json").exists()


# ── loop control: no hot-loop, circuit breaker ─────────────────────────────────


def test_loop_does_not_re_select_attempted_bead(tmp_path):
    # A single bead that always skips must not be re-selected forever.
    runner, _ = build_runner(tmp_path, allowed=False, band="plan_only", max_iterations=10)
    results = runner.run_loop()
    outcomes = [r.outcome for r in results]
    assert outcomes[0] == TR.Outcome.SKIPPED
    assert outcomes[-1] == TR.Outcome.IDLE
    assert len(results) == 2  # skip b1, then queue is empty -> idle


def test_consecutive_failure_circuit_breaker(tmp_path):
    queue = [{"id": f"b{i}"} for i in range(1, 6)]
    runner, calls = build_runner(
        tmp_path,
        queue=queue,
        worker=TR.WorkerResult(ok=False, summary="fail"),
        on_breach="pause",
        max_consecutive_failures=3,
        max_iterations=10,
    )
    results = runner.run_loop()
    outcomes = [r.outcome for r in results]
    assert outcomes.count(TR.Outcome.ABANDONED) == 3
    assert outcomes[-1] == TR.Outcome.BREACH
    assert (tmp_path / "breach_latest.json").exists()


def test_loop_writes_summary(tmp_path):
    runner, _ = build_runner(tmp_path, queue=[{"id": "b1"}])
    runner.run_loop()
    assert (tmp_path / "summary_latest.json").exists()
    assert (tmp_path / "latest.json").exists()


# ── fail-open ────────────────────────────────────────────────────────────────


def test_load_queue_raising_is_fail_open(tmp_path):
    runner, _ = build_runner(tmp_path, raising={"load_queue"})
    r = runner.run_once()  # must not raise
    assert r.outcome == TR.Outcome.IDLE  # empty queue default -> idle


def test_dispatch_raising_is_fail_open(tmp_path):
    runner, _ = build_runner(tmp_path, raising={"dispatch"})
    r = runner.run_once()  # must not raise
    assert r.outcome == TR.Outcome.ABANDONED


# ── worker dispatch hardening (prompt from bead fields, no shared-file leak) ──


def test_worker_prompt_built_only_from_bead_fields(tmp_path):
    cfg = TR.RunnerConfig(artifact_dir=tmp_path)
    detail = {
        "title": "Define RoutingContext",
        "description": "Add RoutingContext dataclass in router/contracts.py.",
        "acceptance_criteria": "dataclass defined; functions pure; tests green",
    }
    prompt = TR._compose_worker_prompt("u8uj.1", detail, cfg)
    # Sourced from this bead only.
    assert "RoutingContext dataclass" in prompt
    assert "router/contracts.py" in prompt
    assert "tests green" in prompt
    assert "RUNNER_RESULT:" in prompt
    assert "auto/u8uj.1" in prompt
    # Must NOT depend on / leak the shared delegate handoff file.
    assert "Claude Delegation Packet" not in prompt
    # Audit copy written.
    assert (tmp_path / "worker_prompt_u8uj_1.md").exists()


def test_destructive_bead_content_is_detected():
    assert TR._DESTRUCTIVE_RE.search(TR._bead_content({"description": "Please run rm -rf /tmp/build and continue"}))
    assert TR._DESTRUCTIVE_RE.search(TR._bead_content({"acceptance_criteria": ["do git push --force"]}))
    assert not TR._DESTRUCTIVE_RE.search(TR._bead_content({"description": "Refactor the router into pure functions"}))


# ── worktree isolation (worker never moves the shared checkout's HEAD) ────────


def test_isolate_worktree_defaults_on():
    assert TR.RunnerConfig().isolate_worktree is True


def test_worktree_path_sanitizes_bead_id():
    p = TR._worktree_path("epic/u8uj.1")
    assert p.name == "auto-epic_u8uj_1"
    assert p.parent.name == ".worktrees"


def test_prompt_isolated_tells_worker_not_to_switch_branches(tmp_path):
    cfg = TR.RunnerConfig(artifact_dir=tmp_path, isolate_worktree=True)
    detail = {"title": "t", "description": "d", "acceptance_criteria": "c"}
    prompt = TR._compose_worker_prompt("u8uj.1", detail, cfg)
    assert "isolated git worktree" in prompt
    assert "Do NOT create or switch branches" in prompt
    assert "auto/u8uj.1" in prompt


def test_prompt_non_isolated_keeps_create_branch(tmp_path):
    cfg = TR.RunnerConfig(artifact_dir=tmp_path, isolate_worktree=False)
    detail = {"title": "t", "description": "d", "acceptance_criteria": "c"}
    prompt = TR._compose_worker_prompt("u8uj.1", detail, cfg)
    assert "Create branch `auto/u8uj.1`" in prompt
    assert "isolated git worktree" not in prompt


def test_dispatch_refuses_when_worktree_creation_fails(tmp_path, monkeypatch):
    cfg = TR.RunnerConfig(artifact_dir=tmp_path, isolate_worktree=True)
    monkeypatch.setattr(TR, "_which", lambda n: "claude")
    monkeypatch.setattr(TR, "_bead_detail", lambda bid: {"title": "t", "description": "d"})
    monkeypatch.setattr(TR, "_create_worktree", lambda bid: None)
    called = {"run": False}
    monkeypatch.setattr(TR, "_run", lambda *a, **k: (called.__setitem__("run", True), (0, ""))[1])
    r = TR.real_dispatch({"id": "u8uj.1"}, {}, cfg)
    assert r.ok is False
    assert "refusing to dispatch into the shared checkout" in r.summary
    assert called["run"] is False  # never touched the shared checkout


def test_dispatch_runs_worker_in_worktree_and_cleans_up(tmp_path, monkeypatch):
    cfg = TR.RunnerConfig(artifact_dir=tmp_path, isolate_worktree=True)
    wt = tmp_path / ".worktrees" / "auto-u8uj_1"
    monkeypatch.setattr(TR, "_which", lambda n: "claude")
    monkeypatch.setattr(TR, "_bead_detail", lambda bid: {"title": "t", "description": "d", "acceptance_criteria": "c"})
    monkeypatch.setattr(TR, "_create_worktree", lambda bid: wt)
    seen: dict = {}

    def fake_run(cmd, timeout=60, cwd=None):
        seen["cwd"] = cwd
        seen["cmd"] = cmd
        return (
            0,
            'RUNNER_RESULT: {"ok": true, "pr_number": 7, "branch": "auto/u8uj.1", "tests_passed": true, "summary": "done"}',
        )

    monkeypatch.setattr(TR, "_run", fake_run)
    removed: dict = {}
    monkeypatch.setattr(TR, "_remove_worktree", lambda p: removed.__setitem__("path", p))

    r = TR.real_dispatch({"id": "u8uj.1"}, {}, cfg)
    assert r.ok is True and r.pr_number == 7
    assert seen["cwd"] == wt  # worker ran INSIDE the worktree, not the shared checkout
    assert seen["cmd"][0] == "claude"
    assert removed["path"] == wt  # worktree torn down afterwards


def test_dispatch_cleans_up_worktree_even_on_worker_failure(tmp_path, monkeypatch):
    cfg = TR.RunnerConfig(artifact_dir=tmp_path, isolate_worktree=True)
    wt = tmp_path / ".worktrees" / "auto-u8uj_1"
    monkeypatch.setattr(TR, "_which", lambda n: "claude")
    monkeypatch.setattr(TR, "_bead_detail", lambda bid: {"title": "t", "description": "d"})
    monkeypatch.setattr(TR, "_create_worktree", lambda bid: wt)
    monkeypatch.setattr(TR, "_run", lambda *a, **k: (1, "boom"))
    removed: dict = {}
    monkeypatch.setattr(TR, "_remove_worktree", lambda p: removed.__setitem__("path", p))

    r = TR.real_dispatch({"id": "u8uj.1"}, {}, cfg)
    assert r.ok is False
    assert removed["path"] == wt  # cleaned up despite worker failure
