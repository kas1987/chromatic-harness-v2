#!/usr/bin/env python3
"""
harness_swot.py — Chromatic Harness V2 SWOT Analysis Generator

Measures real harness health across Strengths, Weaknesses, Opportunities,
and Threats. Outputs Markdown report to 05_REPORTS/HARNESS_SWOT_REPORT.md
and also prints to stdout.

No external deps beyond stdlib.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
HARNESS_ROOT = SCRIPT_DIR.parent
REPORT_DIR = HARNESS_ROOT / "05_REPORTS"
REPORT_FILE = REPORT_DIR / "HARNESS_SWOT_REPORT.md"

NOW = datetime.now(tz=timezone.utc)
NOW_TS = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path = HARNESS_ROOT) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return -1, "", str(exc)


def _iter_tracked_files() -> list[Path]:
    """Return list of files tracked by git."""
    rc, out, _ = _run(["git", "ls-files"])
    if rc != 0:
        return []
    return [HARNESS_ROOT / p for p in out.splitlines() if p]


def _all_files_under(directory: Path, suffix: str | None = None) -> list[Path]:
    """Walk a directory tree and return matching files."""
    result: list[Path] = []
    if not directory.exists():
        return result
    for p in directory.rglob("*"):
        if p.is_file():
            if suffix is None or p.suffix == suffix:
                result.append(p)
    return result


def _file_age_days(p: Path) -> float:
    """Return file age in days (mtime vs now)."""
    try:
        mtime = p.stat().st_mtime
        age = NOW.timestamp() - mtime
        return age / 86400.0
    except OSError:
        return 0.0


def _file_size_mb(p: Path) -> float:
    try:
        return p.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def _has_syntax_error(p: Path) -> str | None:
    """Return error string if file has a Python syntax error, else None."""
    try:
        source = p.read_text(encoding="utf-8", errors="replace")
        ast.parse(source, filename=str(p))
        return None
    except SyntaxError as exc:
        return f"line {exc.lineno}: {exc.msg}"
    except Exception as exc:
        return str(exc)


SECRET_PATTERNS = re.compile(
    r"""(?ix)
    (
        api[_-]?key\s*[=:]\s*['"]?[A-Za-z0-9+/]{10,}
      | password\s*[=:]\s*['"]?[A-Za-z0-9+/!@#$%^&*]{6,}
      | token\s*[=:]\s*['"]?[A-Za-z0-9+/._-]{10,}
      | secret\s*[=:]\s*['"]?[A-Za-z0-9+/]{8,}
      | private[_-]?key\s*[=:]
    )
    """,
)

PLACEHOLDER_PATTERN = re.compile(
    r"(YOUR_|REPLACE_ME|<YOUR|EXAMPLE_KEY|DUMMY_)",
    re.IGNORECASE,
)


def _scan_secrets(p: Path) -> list[str]:
    """Return list of (line_no: snippet) strings with potential secret patterns."""
    hits: list[str] = []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines, 1):
            if SECRET_PATTERNS.search(line):
                # Skip obvious placeholders / docs
                if PLACEHOLDER_PATTERN.search(line):
                    continue
                snippet = line.strip()[:80]
                hits.append(f"line {i}: {snippet}")
    except OSError:
        pass
    return hits


# ---------------------------------------------------------------------------
# STRENGTHS
# ---------------------------------------------------------------------------

def measure_strengths() -> dict:
    """Return dict of strength metrics."""
    results: dict = {}

    # 1. CI/CD workflows
    workflow_dir = HARNESS_ROOT / ".github" / "workflows"
    workflows = list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")) if workflow_dir.exists() else []
    results["ci_workflow_count"] = len(workflows)
    results["ci_workflows"] = sorted(w.name for w in workflows)

    # 2. Governance docs presence
    gov_files = [
        "CLAUDE.md", "AGENTS.md", "README.md", "pyproject.toml",
        "pytest.ini", "DEPLOYMENT_GUIDE.md", "GOVERNANCE_AND_ROUTING_ARCHITECTURE.md",
    ]
    found_gov = [f for f in gov_files if (HARNESS_ROOT / f).exists()]
    results["governance_docs_found"] = found_gov
    results["governance_docs_missing"] = [f for f in gov_files if f not in found_gov]

    # 3. Scripts with test counterparts
    scripts_dir = HARNESS_ROOT / "scripts"
    tests_dir = HARNESS_ROOT / "tests"
    py_scripts = [p for p in _all_files_under(scripts_dir, ".py") if not p.name.startswith("test_")]
    test_files_flat = set()
    for td in [tests_dir, scripts_dir]:
        for tp in _all_files_under(td, ".py"):
            if tp.name.startswith("test_"):
                test_files_flat.add(tp.stem.replace("test_", "", 1))

    validated = [s for s in py_scripts if s.stem in test_files_flat]
    unvalidated = [s for s in py_scripts if s.stem not in test_files_flat]
    results["validated_scripts"] = len(validated)
    results["unvalidated_scripts"] = len(unvalidated)
    results["unvalidated_list"] = sorted(s.name for s in unvalidated)

    # 4. Test file count
    all_test_files = _all_files_under(tests_dir, ".py") if tests_dir.exists() else []
    results["test_file_count"] = len([t for t in all_test_files if t.name.startswith("test_")])

    # 5. Git health
    rc_status, out_status, _ = _run(["git", "status", "--porcelain"])
    results["git_clean_worktree"] = rc_status == 0 and out_status == ""

    rc_branch, out_branch, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    results["git_current_branch"] = out_branch if rc_branch == 0 else "unknown"

    rc_fetch, _, _ = _run(["git", "fetch", "--dry-run"])
    rc_up, out_up, _ = _run(["git", "status", "-sb"])
    results["git_up_to_date"] = "behind" not in out_up and "ahead" not in out_up

    return results


# ---------------------------------------------------------------------------
# WEAKNESSES
# ---------------------------------------------------------------------------

def measure_weaknesses() -> dict:
    results: dict = {}

    # 1. Scripts without test coverage (already computed above — recompute here for independence)
    scripts_dir = HARNESS_ROOT / "scripts"
    tests_dir = HARNESS_ROOT / "tests"
    py_scripts = [p for p in _all_files_under(scripts_dir, ".py") if not p.name.startswith("test_")]
    test_stems = set()
    for td in [tests_dir, scripts_dir]:
        for tp in _all_files_under(td, ".py"):
            if tp.name.startswith("test_"):
                test_stems.add(tp.stem.replace("test_", "", 1))
    uncovered = [s for s in py_scripts if s.stem not in test_stems]
    results["scripts_without_tests"] = len(uncovered)
    results["scripts_without_tests_list"] = sorted(s.name for s in uncovered)[:30]  # cap for readability

    # 2. .pyc files not in .gitignore
    gitignore_path = HARNESS_ROOT / ".gitignore"
    gitignore_content = gitignore_path.read_text(errors="replace") if gitignore_path.exists() else ""
    pyc_ignored = "*.pyc" in gitignore_content or "__pycache__" in gitignore_content
    results["pyc_in_gitignore"] = pyc_ignored
    # Count tracked .pyc files (they slipped through)
    tracked = _iter_tracked_files()
    tracked_pyc = [f for f in tracked if f.suffix == ".pyc"]
    results["tracked_pyc_count"] = len(tracked_pyc)
    results["tracked_pyc_files"] = [str(f.relative_to(HARNESS_ROOT)) for f in tracked_pyc[:10]]

    # 3. Empty directories
    empty_dirs: list[str] = []
    for dirpath in HARNESS_ROOT.rglob("*"):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            try:
                empty_dirs.append(str(dirpath.relative_to(HARNESS_ROOT)))
            except ValueError:
                pass
    results["empty_dir_count"] = len(empty_dirs)
    results["empty_dirs"] = sorted(empty_dirs)[:20]

    # 4. Stale branches (merged into main but not deleted)
    rc, out, _ = _run(["git", "branch", "--merged", "main"])
    if rc == 0:
        merged = [b.strip().lstrip("* ") for b in out.splitlines() if b.strip() not in ("main", "* main", "")]
        results["stale_branches"] = merged
        results["stale_branch_count"] = len(merged)
    else:
        results["stale_branches"] = []
        results["stale_branch_count"] = 0

    # 5. Docs older than 90 days
    docs_dir = HARNESS_ROOT / "02_DOCS"
    old_docs: list[str] = []
    if docs_dir.exists():
        for p in _all_files_under(docs_dir, ".md"):
            if _file_age_days(p) > 90:
                old_docs.append(str(p.relative_to(HARNESS_ROOT)))
    results["old_docs_count"] = len(old_docs)
    results["old_docs"] = sorted(old_docs)[:20]

    return results


# ---------------------------------------------------------------------------
# OPPORTUNITIES
# ---------------------------------------------------------------------------

def assess_opportunities() -> dict:
    results: dict = {}

    # 1. Modules that could be auto-healed (have TODO/FIXME/HACK comments)
    todo_pattern = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
    healable: dict[str, int] = {}
    for p in _all_files_under(HARNESS_ROOT / "scripts", ".py"):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            count = sum(1 for l in lines if todo_pattern.search(l))
            if count > 0:
                healable[p.name] = count
        except OSError:
            pass
    results["scripts_with_todos"] = len(healable)
    results["top_todo_scripts"] = sorted(healable.items(), key=lambda x: -x[1])[:10]

    # 2. Test gaps — scripts/ files with no tests (top candidates)
    scripts_dir = HARNESS_ROOT / "scripts"
    tests_dir = HARNESS_ROOT / "tests"
    py_scripts = [p for p in _all_files_under(scripts_dir, ".py") if not p.name.startswith("test_")]
    test_stems = set()
    for td in [tests_dir, scripts_dir]:
        for tp in _all_files_under(td, ".py"):
            if tp.name.startswith("test_"):
                test_stems.add(tp.stem.replace("test_", "", 1))
    uncovered = [s for s in py_scripts if s.stem not in test_stems]
    # Sort by file size desc — larger uncovered files are highest-value targets
    uncovered_sized = sorted(uncovered, key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    results["top_test_gap_targets"] = [p.name for p in uncovered_sized[:10]]
    coverage_pct = (
        round(100 * (len(py_scripts) - len(uncovered)) / len(py_scripts), 1) if py_scripts else 100.0
    )
    results["current_script_coverage_pct"] = coverage_pct
    results["potential_coverage_pct"] = 100.0

    # 3. Remote branches that could be merged/pruned
    rc, out, _ = _run(["git", "branch", "-r"])
    if rc == 0:
        remote_branches = [b.strip() for b in out.splitlines() if "->" not in b and b.strip()]
        results["remote_branch_count"] = len(remote_branches)
        # Branches not main/HEAD
        non_main = [b for b in remote_branches if "main" not in b and "HEAD" not in b]
        results["mergeable_remote_branches"] = non_main
        results["mergeable_count"] = len(non_main)
    else:
        results["remote_branch_count"] = 0
        results["mergeable_remote_branches"] = []
        results["mergeable_count"] = 0

    return results


# ---------------------------------------------------------------------------
# THREATS
# ---------------------------------------------------------------------------

def detect_threats() -> dict:
    results: dict = {}

    tracked = _iter_tracked_files()

    # 1. Large files > 5MB
    large_files: list[dict] = []
    for f in tracked:
        if f.exists():
            size = _file_size_mb(f)
            if size > 5.0:
                large_files.append({"file": str(f.relative_to(HARNESS_ROOT)), "size_mb": round(size, 2)})
    large_files.sort(key=lambda x: -x["size_mb"])
    results["large_files"] = large_files
    results["large_file_count"] = len(large_files)

    # 2. Secrets scan
    secret_hits: list[dict] = []
    scan_extensions = {".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml", ".env", ".sh", ".md"}
    for f in tracked:
        if f.exists() and f.suffix.lower() in scan_extensions:
            hits = _scan_secrets(f)
            if hits:
                secret_hits.append({
                    "file": str(f.relative_to(HARNESS_ROOT)),
                    "hits": hits[:3],
                })
    results["secret_hit_count"] = len(secret_hits)
    results["secret_files"] = secret_hits[:15]

    # 3. Broken imports / syntax errors in Python files
    broken: list[dict] = []
    for f in tracked:
        if f.exists() and f.suffix == ".py":
            err = _has_syntax_error(f)
            if err:
                broken.append({"file": str(f.relative_to(HARNESS_ROOT)), "error": err})
    results["syntax_error_count"] = len(broken)
    results["syntax_errors"] = broken[:20]

    # 4. Missing required files
    required = ["README.md", "pyproject.toml", "pytest.ini", ".gitignore", "requirements.txt"]
    missing = [f for f in required if not (HARNESS_ROOT / f).exists()]
    results["missing_required_files"] = missing

    return results


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _badge(condition: bool, true_label: str = "PASS", false_label: str = "FAIL") -> str:
    return f"**[{true_label}]**" if condition else f"**[{false_label}]**"


def render_report(strengths: dict, weaknesses: dict, opportunities: dict, threats: dict) -> str:
    lines: list[str] = []

    lines += [
        f"# Harness SWOT Analysis Report",
        f"",
        f"Generated: {NOW_TS}  ",
        f"Harness root: `{HARNESS_ROOT}`",
        f"",
        "---",
        "",
    ]

    # ---- STRENGTHS ----
    lines += [
        "## S — Strengths",
        "",
        "### CI/CD Coverage",
        f"- Workflow files present: **{strengths['ci_workflow_count']}**",
    ]
    for w in strengths["ci_workflows"]:
        lines.append(f"  - `{w}`")

    lines += [
        "",
        "### Governance Documentation",
    ]
    for f in strengths["governance_docs_found"]:
        lines.append(f"  - {_badge(True)} `{f}`")
    for f in strengths["governance_docs_missing"]:
        lines.append(f"  - {_badge(False, 'PRESENT', 'ABSENT')} `{f}`")

    lines += [
        "",
        "### Script Validation Coverage",
        f"- Scripts with test counterparts: **{strengths['validated_scripts']}**",
        f"- Scripts without tests: **{strengths['unvalidated_scripts']}**",
        f"- Test files total: **{strengths['test_file_count']}**",
        "",
        "### Git Health",
        f"- Current branch: `{strengths['git_current_branch']}`",
        f"- Worktree clean: {_badge(strengths['git_clean_worktree'])}",
        f"- Up to date with remote: {_badge(strengths['git_up_to_date'])}",
        "",
        "---",
        "",
    ]

    # ---- WEAKNESSES ----
    lines += [
        "## W — Weaknesses",
        "",
        "### Scripts Without Test Coverage",
        f"- Count: **{weaknesses['scripts_without_tests']}**",
    ]
    if weaknesses["scripts_without_tests_list"]:
        lines.append("")
        lines.append("<details><summary>View uncovered scripts (up to 30)</summary>")
        lines.append("")
        for s in weaknesses["scripts_without_tests_list"]:
            lines.append(f"  - `{s}`")
        lines.append("")
        lines.append("</details>")

    lines += [
        "",
        "### .pyc / Cache Hygiene",
        f"- `*.pyc` in .gitignore: {_badge(weaknesses['pyc_in_gitignore'])}",
        f"- Tracked `.pyc` files: **{weaknesses['tracked_pyc_count']}**",
    ]
    for f in weaknesses["tracked_pyc_files"]:
        lines.append(f"  - `{f}`")

    lines += [
        "",
        "### Empty Directories",
        f"- Count: **{weaknesses['empty_dir_count']}**",
    ]
    for d in weaknesses["empty_dirs"][:10]:
        lines.append(f"  - `{d}/`")
    if weaknesses["empty_dir_count"] > 10:
        lines.append(f"  - _(and {weaknesses['empty_dir_count'] - 10} more)_")

    lines += [
        "",
        "### Stale Branches (merged into main, not deleted)",
        f"- Count: **{weaknesses['stale_branch_count']}**",
    ]
    for b in weaknesses["stale_branches"]:
        lines.append(f"  - `{b}`")

    lines += [
        "",
        "### Documentation Staleness (>90 days)",
        f"- Old docs count: **{weaknesses['old_docs_count']}**",
    ]
    for d in weaknesses["old_docs"][:10]:
        lines.append(f"  - `{d}`")

    lines += ["", "---", ""]

    # ---- OPPORTUNITIES ----
    lines += [
        "## O — Opportunities",
        "",
        "### Auto-Healing Candidates (TODO/FIXME/HACK markers)",
        f"- Scripts with actionable markers: **{opportunities['scripts_with_todos']}**",
    ]
    if opportunities["top_todo_scripts"]:
        lines.append("")
        lines.append("| Script | Marker Count |")
        lines.append("|--------|-------------|")
        for name, count in opportunities["top_todo_scripts"]:
            lines.append(f"| `{name}` | {count} |")

    lines += [
        "",
        "### Test Coverage Improvement",
        f"- Current script coverage: **{opportunities['current_script_coverage_pct']}%**",
        f"- Potential coverage (if all gaps filled): **{opportunities['potential_coverage_pct']}%**",
        "",
        "Top 10 highest-value test gap targets (by file size):",
    ]
    for t in opportunities["top_test_gap_targets"]:
        lines.append(f"  - `{t}`")

    lines += [
        "",
        "### Branch Simplification",
        f"- Remote branches total: **{opportunities['remote_branch_count']}**",
        f"- Non-main remote branches (merge/prune candidates): **{opportunities['mergeable_count']}**",
    ]
    for b in opportunities["mergeable_remote_branches"][:10]:
        lines.append(f"  - `{b}`")
    if opportunities["mergeable_count"] > 10:
        lines.append(f"  - _(and {opportunities['mergeable_count'] - 10} more)_")

    lines += ["", "---", ""]

    # ---- THREATS ----
    lines += [
        "## T — Threats",
        "",
        "### Large Tracked Files (>5 MB)",
        f"- Count: **{threats['large_file_count']}**",
    ]
    if threats["large_files"]:
        lines.append("")
        lines.append("| File | Size (MB) |")
        lines.append("|------|-----------|")
        for lf in threats["large_files"][:10]:
            lines.append(f"| `{lf['file']}` | {lf['size_mb']} |")

    lines += [
        "",
        "### Potential Secret Exposure",
        f"- Files with secret-pattern hits: **{threats['secret_hit_count']}**",
    ]
    if threats["secret_files"]:
        lines.append("")
        for item in threats["secret_files"]:
            lines.append(f"  - `{item['file']}`")
            for h in item["hits"]:
                lines.append(f"    - {h}")
    else:
        lines.append("  - _No secret patterns detected._")

    lines += [
        "",
        "### Syntax Errors in Python Files",
        f"- Files with syntax errors: **{threats['syntax_error_count']}**",
    ]
    if threats["syntax_errors"]:
        lines.append("")
        lines.append("| File | Error |")
        lines.append("|------|-------|")
        for e in threats["syntax_errors"]:
            lines.append(f"| `{e['file']}` | {e['error']} |")
    else:
        lines.append("  - _No syntax errors detected._")

    lines += [
        "",
        "### Missing Required Files",
    ]
    if threats["missing_required_files"]:
        for f in threats["missing_required_files"]:
            lines.append(f"  - {_badge(False, 'PRESENT', 'MISSING')} `{f}`")
    else:
        lines.append("  - _All required files present._")

    lines += [
        "",
        "---",
        "",
        "## Summary Score",
        "",
        "| Quadrant | Key Metric |",
        "|----------|-----------|",
        f"| Strengths | {strengths['ci_workflow_count']} CI workflows · {strengths['validated_scripts']} validated scripts · {strengths['test_file_count']} test files |",
        f"| Weaknesses | {weaknesses['scripts_without_tests']} untested scripts · {weaknesses['stale_branch_count']} stale branches · {weaknesses['empty_dir_count']} empty dirs |",
        f"| Opportunities | {opportunities['scripts_with_todos']} auto-heal targets · {opportunities['current_script_coverage_pct']}% → 100% coverage potential |",
        f"| Threats | {threats['large_file_count']} large files · {threats['secret_hit_count']} secret-pattern files · {threats['syntax_error_count']} syntax errors |",
        "",
        f"_Report generated by `scripts/harness_swot.py` at {NOW_TS}_",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"[harness_swot] Root: {HARNESS_ROOT}")
    print("[harness_swot] Measuring STRENGTHS...")
    s = measure_strengths()

    print("[harness_swot] Measuring WEAKNESSES...")
    w = measure_weaknesses()

    print("[harness_swot] Assessing OPPORTUNITIES...")
    o = assess_opportunities()

    print("[harness_swot] Detecting THREATS...")
    t = detect_threats()

    report = render_report(s, w, o, t)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")

    print("\n" + "=" * 72)
    print(report)
    print("=" * 72)
    print(f"\n[harness_swot] Report written to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
