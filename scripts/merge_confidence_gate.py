#!/usr/bin/env python3
"""Merge confidence gate — composite verdict for PR auto-merge (Option B, Phase 1).

Does NOT re-implement the existing gates. It runs them, folds their signals into a
single confidence score → band → verdict, and writes an audit artifact + (optionally)
a PR comment. The band thresholds mirror DecisionMagnet.decide_band so the merge gate
speaks the same language as the router's CMP gates:

    score >= 90  proceed     → verdict "auto"       (auto-merge may proceed)
    70..89       reversible  → verdict "human_ack"  (merge only with maintainer label)
    50..69       self_heal   → verdict "block"      (needs work)
    < 50         escalate    → verdict "block"
  + hard signals (P3/secret in diff, pr-governance fail) force "block" regardless.
  + soft signals (P4/compliance content) force at most "human_ack".

Composed signals (each fail-open — a collector that errors contributes nothing):
  • scripts/ai_review_gate.py   → risk_score 0-100 + level   (artifact: ai_review/latest.json)
  • scripts/pr_size_gate.py     → risk_level + protected paths (artifact: pr_risk/latest.json)
  • redact_secrets.PATTERNS     → secret-SHAPED strings in the diff (P3, hard block)
  • router.privacy.PrivacyGate  → P4/compliance keywords in the diff (human ack)
  • gh (optional, --pr)         → unresolved P2+ review threads, conflicting sibling PRs

PHASE 1 IS ADVISORY: the process exits 0 regardless of verdict unless --enforce is
passed. This lets thresholds be tuned against live PRs before the check ever blocks a
merge. To enforce later: pass --enforce in the workflow and append "merge-gate" to the
branch-protection required contexts.

Usage:
    python scripts/merge_confidence_gate.py --base main
    python scripts/merge_confidence_gate.py --base main --pr 240 --comment
    python scripts/merge_confidence_gate.py --base main --json
    python scripts/merge_confidence_gate.py --base main --enforce        # Phase 2
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "merge_gate"
ALLOWLIST_PRAGMA = "pragma: allowlist secret"

# Band thresholds — mirror 02_RUNTIME/magnets DecisionMagnet.decide_band.
BAND_PROCEED = 90
BAND_REVERSIBLE = 70
BAND_SELF_HEAL = 50


# ---------------------------------------------------------------------------
# Pure core (unit-tested) — no subprocess, no network.
# ---------------------------------------------------------------------------
def decide_band(score: int) -> str:
    """Map a 0-100 confidence score to a CMP band name."""
    if score >= BAND_PROCEED:
        return "proceed"
    if score >= BAND_REVERSIBLE:
        return "reversible"
    if score >= BAND_SELF_HEAL:
        return "self_heal"
    return "escalate"


def compute_verdict(signals: dict[str, Any]) -> dict[str, Any]:
    """Fold collected signals into {score, band, verdict, reasons, hard_block}.

    Pure: `signals` is a plain dict so this is fully testable without IO. Any signal
    key may be absent/None (collector failed) and is simply skipped (fail-open).
    """
    score = 100
    reasons: list[str] = []
    hard_block = False
    human_ack = False

    ai = signals.get("ai_review")
    if ai and ai.get("risk_score") is not None:
        pen = round(ai["risk_score"] * 0.5)  # risk 0-100 → up to -50
        if pen:
            score -= pen
            reasons.append(f"ai-review risk {ai['risk_score']}/100 (-{pen})")
        if ai.get("level") == "fail":
            score -= 10
            reasons.append("ai-review level=fail (-10)")

    ps = signals.get("pr_size")
    if ps:
        lvl = ps.get("risk_level")
        if lvl == "fail":
            score -= 40
            reasons.append("pr-size risk=fail (-40)")
        elif lvl == "warn":
            score -= 15
            reasons.append("pr-size risk=warn (-15)")
        protected = ps.get("protected_paths") or []
        if protected:
            score -= 20
            reasons.append(f"protected paths touched: {', '.join(protected[:5])} (-20)")

    priv = signals.get("privacy") or {}
    if priv.get("p3_hits"):
        hard_block = True
        reasons.append(f"P3/secret-shaped content in diff: {', '.join(priv['p3_hits'][:3])} (HARD BLOCK)")
    if priv.get("p4_hits"):
        human_ack = True
        reasons.append(f"P4/compliance content in diff: {', '.join(priv['p4_hits'][:3])} (needs human ack)")

    gov = signals.get("pr_governance")
    if gov is not None and gov.get("passed") is False:
        hard_block = True
        reasons.append("pr-governance validation failed (HARD BLOCK)")

    unresolved = signals.get("unresolved_reviews") or 0
    if unresolved:
        pen = min(unresolved * 10, 30)
        score -= pen
        reasons.append(f"{unresolved} unresolved review thread(s) (-{pen})")

    peers = signals.get("conflicting_peers") or 0
    if peers:
        score -= 15
        reasons.append(f"{peers} conflicting sibling PR(s) on base (-15)")

    score = max(0, min(100, score))
    band = decide_band(score)

    if hard_block:
        verdict = "block"
    elif band in ("self_heal", "escalate"):
        verdict = "block"
    elif band == "reversible" or human_ack:
        verdict = "human_ack"
    else:  # proceed, no human-ack signal
        verdict = "auto"

    if not reasons:
        reasons.append("no risk signals — clean change")

    return {
        "score": score,
        "band": band,
        "verdict": verdict,
        "hard_block": hard_block,
        "human_ack": human_ack,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Signal collectors (impure, each fail-open).
# ---------------------------------------------------------------------------
def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, check=False)
        return r.stdout
    except Exception:
        return ""


def _resolve_base(base: str) -> str:
    for ref in (f"origin/{base}", base, f"refs/remotes/origin/{base}"):
        if _run(["git", "rev-parse", "--verify", "--quiet", ref]).strip():
            return ref
    return base


def added_lines(base: str) -> list[str]:
    """Added (+) lines in the PR diff vs the merge-base with `base`."""
    ref = _resolve_base(base)
    mb = _run(["git", "merge-base", ref, "HEAD"]).strip() or ref
    diff = _run(["git", "diff", "--unified=0", f"{mb}..HEAD"])
    return [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def scan_diff_privacy(lines: list[str]) -> dict[str, Any]:
    """P3 (secret-shaped, reusing redact_secrets regexes) + P4 (compliance keywords)."""
    p3_hits: list[str] = []
    p4_hits: list[str] = []

    try:
        sys.path.insert(0, str(REPO / "scripts"))
        from redact_secrets import PATTERNS  # type: ignore
    except Exception:
        PATTERNS = []  # fail-open: no secret scan available

    for ln in lines:
        if ALLOWLIST_PRAGMA in ln:
            continue
        for pat, _ in PATTERNS:
            try:
                if pat.search(ln):
                    p3_hits.append(ln.strip()[:80])
                    break
            except Exception:
                continue

    try:
        sys.path.insert(0, str(REPO / "02_RUNTIME"))
        from router.contracts import PrivacyClass  # type: ignore
        from router.privacy import PrivacyGate  # type: ignore

        gate = PrivacyGate()
        for ln in lines:
            try:
                if gate.classify_text(ln) == PrivacyClass.P4:
                    p4_hits.append(ln.strip()[:80])
            except Exception:
                continue
    except Exception:
        pass  # fail-open: no privacy classifier available

    return {"p3_hits": p3_hits[:10], "p4_hits": p4_hits[:10]}


def _run_subgate(script: str, artifact_rel: str, base: str, ts: str) -> dict[str, Any] | None:
    """Run an existing gate, then read its freshly written latest.json artifact.

    Both ai_review_gate and pr_size_gate write their artifact before returning on
    exit 0 OR 1, so an expected return code means the artifact is fresh. Any other
    return code (crash) → None (signal unknown, fail-open).
    """
    cmd = [sys.executable, str(REPO / "scripts" / script), "--base", base, "--json", "--timestamp", ts]
    try:
        rc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, check=False).returncode
    except Exception:
        return None
    if rc not in (0, 1):
        return None
    try:
        return json.loads((REPO / artifact_rel).read_text(encoding="utf-8"))
    except Exception:
        return None


def _gh_signals(pr: int, base: str) -> dict[str, Any]:
    """Unresolved review threads on this PR + conflicting sibling PRs on the same base."""
    out: dict[str, Any] = {}
    # Unresolved review threads.
    try:
        q = (
            "query($o:String!,$n:String!,$p:Int!){repository(owner:$o,name:$n)"
            "{pullRequest(number:$p){reviewThreads(first:100){nodes{isResolved}}}}}"
        )
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        owner, name = (repo.split("/", 1) + [""])[:2] if "/" in repo else ("", "")
        raw = _run(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={q}",
                "-F",
                f"o={owner}",
                "-F",
                f"n={name}",
                "-F",
                f"p={pr}",
            ]
        )
        data = json.loads(raw) if raw.strip() else {}
        nodes = (
            data.get("data", {}).get("repository", {}).get("pullRequest", {}).get("reviewThreads", {}).get("nodes", [])
        )
        out["unresolved_reviews"] = sum(1 for t in nodes if not t.get("isResolved"))
    except Exception:
        pass
    # Conflicting sibling PRs on the same base.
    try:
        raw = _run(
            ["gh", "pr", "list", "--base", base, "--state", "open", "--json", "number,mergeable", "--limit", "100"]
        )
        peers = json.loads(raw) if raw.strip() else []
        out["conflicting_peers"] = sum(
            1 for p in peers if p.get("number") != pr and p.get("mergeable") == "CONFLICTING"
        )
    except Exception:
        pass
    return out


def collect_signals(base: str, ts: str, pr: int | None) -> dict[str, Any]:
    signals: dict[str, Any] = {}

    ai = _run_subgate("ai_review_gate.py", "07_LOGS_AND_AUDIT/ai_review/latest.json", base, ts)
    if ai is not None:
        signals["ai_review"] = {"risk_score": ai.get("risk_score"), "level": ai.get("level")}

    ps = _run_subgate("pr_size_gate.py", "07_LOGS_AND_AUDIT/pr_risk/latest.json", base, ts)
    if ps is not None:
        risk = ps.get("risk", {}) if isinstance(ps.get("risk"), dict) else {}
        signals["pr_size"] = {
            "risk_level": ps.get("risk_level"),
            "protected_paths": risk.get("protected_paths", []),
        }

    signals["privacy"] = scan_diff_privacy(added_lines(base))

    if pr is not None:
        signals.update(_gh_signals(pr, base))

    return signals


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
_EMOJI = {"auto": "✅", "human_ack": "🟡", "block": "🛑"}
_HEADLINE = {
    "auto": "auto-merge eligible",
    "human_ack": "needs maintainer ack (`merge-ok` label)",
    "block": "blocked — resolve before merge",
}


def render_comment(report: dict[str, Any]) -> str:
    v = report["verdict"]
    lines = [
        "## 🔀 Merge confidence gate — **advisory (Phase 1)**",
        "",
        f"{_EMOJI.get(v['verdict'], '•')} **{v['verdict'].replace('_', '-')}** — {_HEADLINE.get(v['verdict'], '')}",
        "",
        f"**Confidence:** {v['score']}/100  ·  **band:** `{v['band']}`",
        "",
        "**Signals:**",
    ]
    lines += [f"- {r}" for r in v["reasons"]]
    lines += [
        "",
        "_Advisory only — this check does not block merges yet. "
        "It will once thresholds are validated and `merge-gate` is added to branch protection._",
    ]
    return "\n".join(lines)


def write_artifact(report: dict[str, Any], ts: str) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({**report, "timestamp": ts}, indent=2)
    (ARTIFACT_DIR / f"{ts}.json").write_text(payload, encoding="utf-8")
    latest = ARTIFACT_DIR / "latest.json"
    latest.write_text(payload, encoding="utf-8")
    return latest


def _post_comment(pr: int, body: str) -> None:
    try:
        subprocess.run(
            ["gh", "pr", "comment", str(pr), "--body-file", "-"], cwd=str(REPO), input=body, text=True, check=False
        )
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge confidence gate (Option B, Phase 1 advisory)")
    ap.add_argument("--base", default=os.environ.get("GITHUB_BASE_REF") or "main")
    # str (not int): workflow_dispatch passes an empty PR number; tolerate it.
    ap.add_argument("--pr", default=os.environ.get("MERGE_GATE_PR") or "")
    ap.add_argument("--comment", action="store_true", help="Post the verdict as a PR comment (needs --pr + gh)")
    ap.add_argument("--enforce", action="store_true", help="Phase 2: exit 1 on block (default advisory exit 0)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--timestamp", default="")
    args = ap.parse_args()

    pr = int(args.pr) if str(args.pr).strip().isdigit() else None

    ts = args.timestamp
    if not ts:
        import datetime

        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    signals = collect_signals(args.base, ts, pr)
    verdict = compute_verdict(signals)
    report = {"verdict": verdict, "signals": signals, "base": args.base, "pr": pr}
    artifact = write_artifact(report, ts)

    sep = "=" * 60
    print("Merge confidence gate:")
    print(f"  confidence : {verdict['score']}/100  (band: {verdict['band']})")
    print(f"  verdict    : {verdict['verdict'].upper()}")
    for r in verdict["reasons"]:
        print(f"  - {r}")
    print(f"  artifact   : {artifact}")
    print(f"\n{sep}\nmerge-gate: {verdict['verdict'].upper()} (advisory)\n{sep}")

    if args.comment and pr:
        _post_comment(pr, render_comment(report))

    if args.json:
        print(json.dumps(report, indent=2))

    # Phase 1: advisory — never block. Phase 2 (--enforce): block on "block".
    if args.enforce and verdict["verdict"] == "block":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
