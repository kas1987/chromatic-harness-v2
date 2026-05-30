"""Confidence-gated git commit, push, PR, and merge automation."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from workflows.git_policy import GitPipelineDecision, evaluate_git_pipeline
from workflows.git_runner import active_git_backend, gh_argv, git_argv

SECRET_PATTERNS = (
    r"\.env$",
    r"\.env\.",
    r"credentials\.json",
    r"\.pem$",
    r"id_rsa",
    r"\.key$",
)
SECRET_RE = re.compile("|".join(SECRET_PATTERNS), re.IGNORECASE)


@dataclass
class GitRunResult:
    dry_run: bool
    decision: GitPipelineDecision
    steps: list[dict]
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "git_backend": active_git_backend(),
            "pipeline": self.decision.to_dict(),
            "steps": self.steps,
            "error": self.error,
        }


def _run(cmd: list[str], cwd: Path, *, dry_run: bool) -> dict:
    if dry_run:
        return {"cmd": cmd, "status": "dry_run", "stdout": "", "stderr": ""}
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)
    return {
        "cmd": cmd,
        "status": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
    }


def _git_status_porcelain(repo: Path) -> str:
    proc = subprocess.run(
        git_argv("status", "--porcelain"),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return proc.stdout or ""


def _has_staged_changes(repo: Path) -> bool:
    status = _git_status_porcelain(repo)
    return any(line and line[0] in "MADRC" for line in status.splitlines())


def _is_secret_path(path: str) -> bool:
    p = path.strip().replace("\\", "/")
    lower = p.lower()
    if lower.endswith(".env.example") or lower.endswith(".env.sample") or lower.endswith(".env.template"):
        return False
    return bool(SECRET_RE.search(p))


def _detect_secrets_in_changes(repo: Path) -> bool:
    proc = subprocess.run(
        git_argv("diff", "--name-only", "HEAD"),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    names = (proc.stdout or "") + _git_status_porcelain(repo)
    return any(_is_secret_path(n) for n in names.splitlines() if n.strip())


def _current_branch(repo: Path) -> str:
    proc = subprocess.run(
        git_argv("branch", "--show-current"),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return (proc.stdout or "").strip()


def _protected_branch(branch: str) -> bool:
    return branch in ("main", "master")


def _gh_available() -> bool:
    try:
        proc = subprocess.run(
            gh_argv("--version"),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return proc.returncode == 0
    except FileNotFoundError:
        return False


def _open_pr_exists(repo: Path, branch: str) -> bool:
    if not _gh_available():
        return False
    proc = subprocess.run(
        gh_argv("pr", "list", "--head", branch, "--json", "number", "--limit", "1"),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() not in ("", "[]")


def _ci_passed_for_branch(repo: Path, branch: str) -> bool:
    if not _gh_available():
        return False
    proc = subprocess.run(
        gh_argv("pr", "checks", "--branch", branch),
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        return False
    text = (proc.stdout or "").lower()
    return "fail" not in text and "pending" not in text


def run_git_pipeline(
    repo: Path,
    *,
    confidence: float,
    risk_level: str = "low",
    verifier_approved: bool = False,
    tests_passed: bool = False,
    bead_id: str = "",
    commit_message: str = "",
    dry_run: bool = True,
    for_plan: bool = False,
) -> GitRunResult:
    """Execute or simulate commit → push → PR → merge based on confidence."""
    branch = _current_branch(repo)
    secrets = _detect_secrets_in_changes(repo)
    staged = _has_staged_changes(repo) or for_plan
    on_protected = _protected_branch(branch)

    ci_ok = _ci_passed_for_branch(repo, branch) if _gh_available() else tests_passed

    decision = evaluate_git_pipeline(
        confidence=confidence,
        risk_level=risk_level,
        verifier_approved=verifier_approved,
        tests_passed=tests_passed,
        ci_passed=ci_ok,
        has_staged_changes=staged,
        on_protected_branch=on_protected,
        secrets_detected=secrets,
    )

    steps: list[dict] = []
    msg = commit_message or f"feat: close {bead_id}" if bead_id else "chore: workflow ship"

    if decision.commit:
        steps.append(_run(git_argv("add", "-A"), repo, dry_run=dry_run))
        steps.append(_run(git_argv("commit", "-m", msg), repo, dry_run=dry_run))
    else:
        steps.append({"step": "commit", "status": "skipped", "reason": decision.reasons.get("commit")})

    if decision.push:
        steps.append(_run(git_argv("pull", "--rebase"), repo, dry_run=dry_run))
        steps.append(_run(git_argv("push"), repo, dry_run=dry_run))
    else:
        steps.append({"step": "push", "status": "skipped", "reason": decision.reasons.get("push")})

    if decision.open_pr and _gh_available() and not _open_pr_exists(repo, branch):
        title = msg[:72]
        body = f"Automated PR from workflow_git.\n\nBead: {bead_id}\nConfidence: {confidence}"
        steps.append(
            _run(
                gh_argv("pr", "create", "--title", title, "--body", body),
                repo,
                dry_run=dry_run,
            )
        )
    elif decision.open_pr:
        steps.append(
            {
                "step": "open_pr",
                "status": "skipped",
                "reason": "PR exists or gh unavailable",
            }
        )
    else:
        steps.append({"step": "open_pr", "status": "skipped", "reason": decision.reasons.get("open_pr")})

    if decision.merge and _gh_available():
        steps.append(
            _run(
                gh_argv("pr", "merge", "--squash", "--auto"),
                repo,
                dry_run=dry_run,
            )
        )
    else:
        steps.append({"step": "merge", "status": "skipped", "reason": decision.reasons.get("merge")})

    return GitRunResult(dry_run=dry_run, decision=decision, steps=steps)
