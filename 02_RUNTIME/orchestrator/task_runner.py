#!/usr/bin/env python3
"""task_runner.py — long-running next-task supervisor (bead chromatic-harness-v2-xab3).

A single supervisor that autonomously takes on the next ready bead, end to end,
with an explicit confidence score gating every action:

    Observe -> Select -> Score/Decide -> Claim+Lease -> Dispatch(worker)
            -> Await+CI -> Integrate(merge/close) -> Record -> Guard -> loop

This is thin orchestration glue over already-tested primitives:
  * selection + 7-factor confidence + dispatch gate :: scripts/go_mode.py (run_go)
  * worker governance + spawn                        :: scripts/claude_delegate_gate.py
  * claim safety / liveness                          :: scripts/lease_manager.py (+ heartbeat)
  * spend guard                                      :: scripts/loop_budget_guard.py
  * post-hoc agent scorecards (confidence feedback)  :: scripts/agent_scoring.py

Side-effecting operations live behind an ``Adapters`` object so the loop, state
machine, guards, and recording are fully unit-testable with injected fakes (no
network, no real ``claude``/``gh``). See docs/superpowers/specs/2026-06-02-
long-running-task-runner-design.md.

Safety invariants:
  * T4 is never autonomous (asserts t_level <= max_t_level; delegate gate blocks
    destructive patterns regardless).
  * Only the runner's own PR for the claimed bead is squash-merged.
  * Budget guard + iteration cap + consecutive-failure circuit-breaker + kill-switch.
  * Fail-open: a helper exception is recorded and degrades to on_breach, never crashes
    the loop or spins hot.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(REPO / "02_RUNTIME") not in sys.path:
    sys.path.insert(0, str(REPO / "02_RUNTIME"))

# go_mode is the selection + confidence + dispatch-decision engine. It is core;
# if it cannot be imported the runner cannot select work, so surface that clearly.
try:
    import go_mode  # type: ignore  # noqa: E402
except Exception as _exc:  # noqa: BLE001
    go_mode = None  # type: ignore
    _GO_MODE_IMPORT_ERROR = _exc
else:
    _GO_MODE_IMPORT_ERROR = None

_T_RANK = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}
_RESULT_MARKER = "RUNNER_RESULT:"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Models ────────────────────────────────────────────────────────────────────


class Outcome(str, Enum):
    IDLE = "idle"  # no new ready work -> stop loop
    SKIPPED = "skipped"  # below confidence gate -> not claimed
    COMPLETED = "completed"  # implemented, CI green, merged + closed
    FAILED = "failed"  # claimed + dispatched but CI red / merge failed
    ABANDONED = "abandoned"  # worker could not run
    BREACH = "breach"  # a guard tripped -> on_breach
    HALT = "halt"  # kill-switch or t_level > max_t_level


@dataclass
class WorkerResult:
    ok: bool
    pr_number: int | None = None
    branch: str = ""
    tests_passed: bool = False
    summary: str = ""
    raw: str = ""


@dataclass
class IterationResult:
    outcome: Outcome
    bead_id: str | None = None
    confidence: float | None = None
    band: str | None = None
    detail: str = ""
    pr_number: int | None = None
    generated_at_utc: str = field(default_factory=_ts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "bead_id": self.bead_id,
            "confidence": self.confidence,
            "band": self.band,
            "detail": self.detail,
            "pr_number": self.pr_number,
            "generated_at_utc": self.generated_at_utc,
        }


@dataclass
class RunnerConfig:
    scope: str = "epic"  # single-bead | epic | area
    epic: str = ""  # epic-id prefix filter when scope=epic
    t_level: str = "T3"  # T-level handed to the delegate gate per task
    max_t_level: str = "T3"  # ceiling; T4 is never autonomous
    max_iterations: int = 25
    max_usd: float = 10.0
    max_tokens: int = 0
    on_breach: str = "pause"  # pause | handoff | halt
    max_consecutive_failures: int = 3
    auto_merge: bool = True
    dry_run: bool = False
    worker_timeout: int = 1800
    ci_timeout: int = 1800
    artifact_dir: Path = field(default_factory=lambda: REPO / "07_LOGS_AND_AUDIT" / "task_runner")

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        d["artifact_dir"] = str(self.artifact_dir)
        return d


# ── Real adapters (subprocess / filesystem; not exercised by unit tests) ────────


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    """Best-effort subprocess via the harness-safe runner. Never raises."""
    try:
        from common_harness import run_safe  # noqa: E402

        proc = run_safe(cmd, cwd=REPO, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 1, f"run error: {exc}"


def _which(name: str) -> str | None:
    import shutil

    return shutil.which(name) or shutil.which(f"{name}.cmd") or shutil.which(f"{name}.exe")


def real_load_queue() -> list[dict]:
    if go_mode is None:
        return []
    try:
        return go_mode.load_queue_from_bd()
    except Exception:  # noqa: BLE001
        return []


def real_decide(queue: list[dict]) -> dict:
    if go_mode is None:
        return {"selected": None, "decision": "no_work", "dispatch_allowed": False}
    return go_mode.run_go(queue)


def real_claim(bead_id: str) -> bool:
    bd = _which("bd")
    if not bd:
        return False
    code, _ = _run([bd, "update", bead_id, "--claim"], timeout=30)
    return code == 0


def _build_worker_prompt(bead: dict, config: RunnerConfig) -> Path:
    """Run the delegate gate for governance, then compose a full-lifecycle worker prompt."""
    bead_id = str(bead.get("id", ""))
    title = str(bead.get("title") or bead.get("objective") or "").strip()
    gate_prompt = REPO / ".agents" / "handoffs" / "claude_delegate_prompt.md"
    # Governance pass (no spawn): writes the delegate prompt + enforces gates.
    _run(
        [
            sys.executable,
            str(_SCRIPTS / "claude_delegate_gate.py"),
            "--task",
            f"Implement {bead_id}: {title}",
            "--bead-id",
            bead_id,
            "--t-level",
            config.t_level,
        ],
        timeout=120,
    )
    base = ""
    try:
        if gate_prompt.is_file():
            base = gate_prompt.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        base = ""

    lifecycle = [
        base,
        "",
        "## Autonomous execution contract",
        f"You are a worker spawned by the long-running task runner for bead `{bead_id}`.",
        "Execute the FULL lifecycle yourself:",
        f"1. Create a branch `auto/{bead_id}` from the session base branch.",
        "2. Implement the bead per its acceptance criteria. Stay in scope.",
        "3. Run `ruff check` and the targeted pytest; fix until green.",
        "4. Register any new core-subsystem test suite in tests/run-all-e2e.py.",
        "5. Commit, push, and open a PR (base = session branch). Do NOT merge.",
        "6. NEVER force-push, hard-reset, touch secrets, or push to a protected branch.",
        "",
        "When done, print EXACTLY ONE final line, machine-readable:",
        f'{_RESULT_MARKER} {{"ok": true, "pr_number": <int>, "branch": "auto/{bead_id}", '
        '"tests_passed": true, "summary": "<one line>"}}',
        'If you could not complete it, print that line with "ok": false and a reason in summary.',
    ]
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    safe_id = bead_id.replace("/", "_").replace(".", "_") or "task"
    path = config.artifact_dir / f"worker_prompt_{safe_id}.md"
    path.write_text("\n".join(lifecycle) + "\n", encoding="utf-8")
    return path


def _parse_worker_result(out: str) -> WorkerResult:
    line = ""
    for ln in reversed(out.splitlines()):
        if ln.strip().startswith(_RESULT_MARKER):
            line = ln.strip()[len(_RESULT_MARKER) :].strip()
            break
    if not line:
        return WorkerResult(ok=False, summary="no RUNNER_RESULT line from worker", raw=out[-2000:])
    try:
        data = json.loads(line)
    except Exception as exc:  # noqa: BLE001
        return WorkerResult(ok=False, summary=f"unparseable worker result: {exc}", raw=out[-2000:])
    pr = data.get("pr_number")
    return WorkerResult(
        ok=bool(data.get("ok", False)),
        pr_number=int(pr) if isinstance(pr, (int, str)) and str(pr).isdigit() else None,
        branch=str(data.get("branch", "")),
        tests_passed=bool(data.get("tests_passed", False)),
        summary=str(data.get("summary", ""))[:300],
        raw=out[-2000:],
    )


def real_dispatch(bead: dict, confidence: dict, config: RunnerConfig) -> WorkerResult:
    """Spawn a worker (claude -p) to implement the bead -> tests -> PR."""
    if _which("claude") is None:
        return WorkerResult(ok=False, summary="claude CLI not found; cannot dispatch worker")
    prompt_path = _build_worker_prompt(bead, config)
    code, out = _run(["claude", "-p", f"@{prompt_path}"], timeout=config.worker_timeout)
    result = _parse_worker_result(out)
    if code != 0 and result.ok:
        result.ok = False
        result.summary = f"worker exited {code}: {result.summary}"
    return result


def real_await_ci(worker: WorkerResult, config: RunnerConfig) -> bool:
    """Watch CI for the worker's PR. Returns True only on a confirmed green run."""
    if worker.pr_number is None or _which("gh") is None:
        return False
    code, out = _run(
        ["gh", "pr", "checks", str(worker.pr_number), "--watch", "--fail-fast"],
        timeout=config.ci_timeout,
    )
    return code == 0


def real_integrate(bead: dict, worker: WorkerResult, config: RunnerConfig) -> bool:
    """Squash-merge the worker's own PR, then close the bead + linked issue."""
    if worker.pr_number is None or _which("gh") is None:
        return False
    code, _ = _run(
        ["gh", "pr", "merge", str(worker.pr_number), "--squash", "--delete-branch"],
        timeout=300,
    )
    if code != 0:
        return False
    bead_id = str(bead.get("id", ""))
    bd = _which("bd")
    if bd and bead_id:
        _run([bd, "close", bead_id], timeout=30)
    return True


def real_budget_breached(config: RunnerConfig) -> tuple[bool, str]:
    """loop_budget_guard --check exits 3 when over ceiling. Fail-open on error."""
    guard = _SCRIPTS / "loop_budget_guard.py"
    if not guard.is_file() or (config.max_usd <= 0 and config.max_tokens <= 0):
        return False, "no ceiling set"
    cmd = [sys.executable, str(guard), "--check"]
    if config.max_usd > 0:
        cmd += ["--max-usd", str(config.max_usd)]
    if config.max_tokens > 0:
        cmd += ["--max-tokens", str(config.max_tokens)]
    code, out = _run(cmd, timeout=30)
    if code == 3:
        return True, out.strip()[-300:] or "spend over ceiling"
    return False, "within budget"


def real_record_event(artifact_dir: Path, event: dict) -> None:
    """Append the task event and refresh agent_scoring scorecards. Never raises."""
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        events_path = artifact_dir / "agent_events.jsonl"
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
        # Refresh scorecards from the cumulative event log.
        events: list[dict] = []
        for ln in events_path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                events.append(json.loads(ln))
            except Exception:  # noqa: BLE001
                continue
        import agent_scoring  # noqa: E402

        agent_scoring.run_scoring(events, _utc_now().strftime("%Y%m%dT%H%M%SZ"))
    except Exception:  # noqa: BLE001
        pass


def real_lease(action: str, bead_id: str, resources: list[str]) -> None:
    """Best-effort lease op (single supervisor has no contention; this is liveness)."""
    lm = _SCRIPTS / "lease_manager.py"
    if not lm.is_file() or not bead_id:
        return
    if action == "acquire":
        cmd = [
            sys.executable,
            str(lm),
            "acquire",
            "--owner",
            f"task-runner:{bead_id}",
            "--resources",
            *(resources or [bead_id]),
        ]
    elif action == "release":
        cmd = [sys.executable, str(lm), "release", "--owner", f"task-runner:{bead_id}"]
    else:
        return
    _run(cmd, timeout=20)


@dataclass
class Adapters:
    """Injection seam. Real defaults touch CLIs/network; tests pass fakes."""

    load_queue: Callable[[], list[dict]] = real_load_queue
    decide: Callable[[list[dict]], dict] = real_decide
    claim: Callable[[str], bool] = real_claim
    dispatch: Callable[[dict, dict, RunnerConfig], WorkerResult] = real_dispatch
    await_ci: Callable[[WorkerResult, RunnerConfig], bool] = real_await_ci
    integrate: Callable[[dict, WorkerResult, RunnerConfig], bool] = real_integrate
    budget_breached: Callable[[RunnerConfig], tuple[bool, str]] = real_budget_breached
    record_event: Callable[[Path, dict], None] = real_record_event
    lease: Callable[[str, str, list[str]], None] = real_lease


# ── Supervisor ──────────────────────────────────────────────────────────────


class TaskRunner:
    """The confidence-gated long-running supervisor."""

    def __init__(self, config: RunnerConfig | None = None, adapters: Adapters | None = None):
        self.config = config or RunnerConfig()
        self.adapters = adapters or Adapters()
        self.config.artifact_dir.mkdir(parents=True, exist_ok=True)

    # -- helpers ------------------------------------------------------------

    def _stop_requested(self) -> bool:
        if (self.config.artifact_dir / "STOP").exists():
            return True
        return os.environ.get("TASK_RUNNER_STOP", "").lower() in {"1", "true", "yes"}

    def _t_level_ok(self) -> bool:
        return _T_RANK.get(self.config.t_level, 4) <= _T_RANK.get(self.config.max_t_level, 3) <= _T_RANK["T3"]

    def _apply_scope(self, queue: list[dict], attempted: set[str]) -> list[dict]:
        out = [it for it in queue if str(it.get("id", "")) not in attempted]
        if self.config.scope == "epic" and self.config.epic:
            out = [it for it in out if str(it.get("id", "")).startswith(self.config.epic)]
        return out

    def _record(
        self, bead_id: str | None, outcome: str, confidence: float | None, false_positive: bool = False
    ) -> None:
        score = confidence if confidence is not None else 0.0
        # agent_scoring expects confidence in [0,1]; go_mode score is 0-100.
        norm = score / 100.0 if score > 1.0 else score
        self.adapters.record_event(
            self.config.artifact_dir,
            {
                "agent": "task-runner",
                "bead_id": bead_id or "",
                "outcome": outcome,
                "confidence": round(norm, 4),
                "false_positive": false_positive,
                "ts": _ts(),
            },
        )

    def _apply_on_breach(self, reason: str) -> None:
        rec = {"event": "on_breach", "action": self.config.on_breach, "reason": reason, "ts": _ts()}
        try:
            (self.config.artifact_dir / "breach_latest.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
            if self.config.on_breach == "handoff":
                # Keep the handoff in the runner's own artifact dir; never clobber the
                # shared .agents/handoffs/latest.json that session boot reads.
                (self.config.artifact_dir / "task_runner_handoff.json").write_text(
                    json.dumps({"from": "task-runner", **rec}, indent=2), encoding="utf-8"
                )
        except Exception:  # noqa: BLE001
            pass

    def _write_latest(self, result: IterationResult) -> None:
        try:
            (self.config.artifact_dir / "latest.json").write_text(
                json.dumps(result.to_dict(), indent=2), encoding="utf-8"
            )
            with (self.config.artifact_dir / "history.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(result.to_dict()) + "\n")
        except Exception:  # noqa: BLE001
            pass

    # -- one iteration ------------------------------------------------------

    def run_once(self, attempted: set[str] | None = None) -> IterationResult:
        """Run a single bead through the lifecycle and return the result."""
        attempted = attempted or set()

        if self._stop_requested():
            return IterationResult(Outcome.HALT, detail="kill-switch (STOP file or TASK_RUNNER_STOP)")
        if not self._t_level_ok():
            return IterationResult(
                Outcome.HALT,
                detail=f"t_level {self.config.t_level} exceeds ceiling {self.config.max_t_level} (T4 never autonomous)",
            )

        breached, why = self._safe(lambda: self.adapters.budget_breached(self.config), (False, "guard error"))
        if breached:
            self._apply_on_breach(f"budget: {why}")
            return IterationResult(Outcome.BREACH, detail=f"budget guard: {why}")

        # Observe -> Select -> Score -> Decide (fail-open).
        queue = self._safe(self.adapters.load_queue, [])
        queue = self._apply_scope(queue, attempted)
        record = self._safe(lambda: self.adapters.decide(queue), {"selected": None})

        selected = record.get("selected") if isinstance(record, dict) else None
        if not selected:
            return IterationResult(Outcome.IDLE, detail="no new ready work")

        bead_id = str(selected.get("id", ""))
        conf_obj = record.get("confidence") or {}
        confidence = conf_obj.get("score") if isinstance(conf_obj, dict) else None
        band = record.get("decision")

        if not record.get("dispatch_allowed"):
            self._record(bead_id, "abandoned", confidence)  # tracked as a low-confidence non-attempt
            return IterationResult(
                Outcome.SKIPPED, bead_id, confidence, band, f"below gate: {record.get('dispatch_reason', '')}"
            )

        if self.config.dry_run:
            return IterationResult(Outcome.SKIPPED, bead_id, confidence, band, "dry-run: would claim + dispatch")

        if not self._safe(lambda: self.adapters.claim(bead_id), False):
            return IterationResult(
                Outcome.SKIPPED, bead_id, confidence, band, "claim failed (already claimed / bd unavailable)"
            )
        self._safe(lambda: self.adapters.lease("acquire", bead_id, list(selected.get("allowed_files") or [])), None)

        worker = self._safe(
            lambda: self.adapters.dispatch(selected, conf_obj, self.config),
            WorkerResult(ok=False, summary="dispatch raised"),
        )
        if not worker.ok:
            self._record(bead_id, "abandoned", confidence)
            self._safe(lambda: self.adapters.lease("release", bead_id, []), None)
            return IterationResult(
                Outcome.ABANDONED, bead_id, confidence, band, f"worker failed: {worker.summary}", worker.pr_number
            )

        ci_green = self._safe(lambda: self.adapters.await_ci(worker, self.config), False)
        if not ci_green:
            self._record(bead_id, "failed", confidence, false_positive=True)
            self._safe(lambda: self.adapters.lease("release", bead_id, []), None)
            return IterationResult(Outcome.FAILED, bead_id, confidence, band, "CI red / unverified", worker.pr_number)

        if self.config.auto_merge and band in ("execute", "execute_logged"):
            merged = self._safe(lambda: self.adapters.integrate(selected, worker, self.config), False)
            if not merged:
                self._record(bead_id, "failed", confidence)
                self._safe(lambda: self.adapters.lease("release", bead_id, []), None)
                return IterationResult(
                    Outcome.FAILED, bead_id, confidence, band, "merge/close failed", worker.pr_number
                )

        self._record(bead_id, "completed", confidence)
        self._safe(lambda: self.adapters.lease("release", bead_id, []), None)
        return IterationResult(
            Outcome.COMPLETED, bead_id, confidence, band, worker.summary or "merged + closed", worker.pr_number
        )

    # -- the loop -----------------------------------------------------------

    def run_loop(self) -> list[IterationResult]:
        results: list[IterationResult] = []
        attempted: set[str] = set()
        consecutive_failures = 0

        for _ in range(max(1, self.config.max_iterations)):
            result = self.run_once(attempted)
            self._write_latest(result)
            results.append(result)

            if result.outcome in (Outcome.HALT, Outcome.IDLE):
                break
            if result.outcome == Outcome.BREACH:
                break  # on_breach already applied inside run_once

            if result.bead_id:
                attempted.add(result.bead_id)

            if result.outcome in (Outcome.FAILED, Outcome.ABANDONED):
                consecutive_failures += 1
                if self.config.on_breach == "halt":
                    self._apply_on_breach("task failure with on_breach=halt")
                    break
                if consecutive_failures >= self.config.max_consecutive_failures:
                    self._apply_on_breach(f"{consecutive_failures} consecutive failures (circuit breaker)")
                    results.append(IterationResult(Outcome.BREACH, detail="consecutive-failure circuit breaker"))
                    break
            else:
                consecutive_failures = 0

        self._write_summary(results)
        return results

    def _write_summary(self, results: list[IterationResult]) -> None:
        counts: dict[str, int] = {}
        for r in results:
            counts[r.outcome.value] = counts.get(r.outcome.value, 0) + 1
        summary = {
            "generated_at_utc": _ts(),
            "iterations": len(results),
            "counts": counts,
            "config": self.config.to_dict(),
            "completed_beads": [r.bead_id for r in results if r.outcome == Outcome.COMPLETED],
        }
        try:
            (self.config.artifact_dir / "summary_latest.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    # -- fail-open wrapper --------------------------------------------------

    @staticmethod
    def _safe(fn: Callable[[], Any], default: Any) -> Any:
        try:
            return fn()
        except Exception:  # noqa: BLE001
            return default


def import_error() -> Exception | None:
    """Expose the go_mode import error (if any) for the CLI to report."""
    return _GO_MODE_IMPORT_ERROR
