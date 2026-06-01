"""Guards for the issue->bead pipeline description builder.

Regression coverage for two bugs found 2026-06-01:
1. Multi-line descriptions passed as a Windows `bd.cmd` argument were truncated
   to the first line — the seeder must pass them via stdin (--body-file -).
2. Non-ASCII glyphs (em-dash, middle-dot) in descriptions were rejected by the
   Dolt column charset — descriptions must be ASCII-encodable.

These tests are network-free: they exercise pure functions only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, REPO / "scripts" / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


REC = {
    "number": 57,
    "title": "Security gates",
    "ext_ref": "gh-57",
    "objective": "Prevent vulnerable code reaching CI.",
    "scope": "- Secret scanning.\n- Dep audit.",
    "acceptance": "- [ ] Detect secrets.\n- [ ] Audit runs.",
    "owner": "Sentinel + Auditor",
    "slug": "ciq.2",
    "c_level": "C2",
    "valid": True,
}


def test_description_is_ascii_encodable():
    seed = _load("seed_issues_to_beads")
    desc = seed.build_bead_description(REC, "CI & Quality Hardening")
    # Must encode as ASCII — Dolt column rejected em-dash/middle-dot bytes.
    desc.encode("ascii")  # raises UnicodeEncodeError on regression


def test_description_carries_eval_requirements():
    seed = _load("seed_issues_to_beads")
    desc = seed.build_bead_description(REC, "CI & Quality Hardening")
    assert "## Eval requirements (definition of done)" in desc
    assert desc.count("- [ ]") == 2  # both acceptance items preserved
    assert "gh-57" in desc  # traceability
    assert "C-level hint: C2" in desc


def test_ascii_safe_coerces_known_glyphs():
    seed = _load("seed_issues_to_beads")
    dirty = "epic — packs · items § ref → done “quote”"
    clean = seed.ascii_safe(dirty)
    clean.encode("ascii")  # raises on regression
    assert "—" not in clean and "·" not in clean and "§" not in clean
    assert seed.ascii_safe(clean) == clean  # idempotent


def test_seeder_passes_description_via_stdin_not_arg():
    """The create path must use --body-file - + stdin, never --description <arg>
    (which truncates multi-line content on Windows bd.cmd)."""
    src = (REPO / "scripts" / "seed_issues_to_beads.py").read_text(encoding="utf-8")
    assert "--body-file" in src
    assert "stdin=ascii_safe(desc)" in src  # piped via stdin, coerced to ASCII
    # No raw --description arg in the create/update path.
    assert '"--description"' not in src


def test_intake_normalizes_inline_acceptance():
    intake = _load("intake_issues")
    issue = {
        "number": 63,
        "title": "[queue] Agent scoring",
        "body": "bead:ciq.8\n\nMeasure agent effectiveness.\n\nAcceptance:\n- Scorecards.\n- Trend dashboard.\n\nSuggested owner: Financier + Auditor",
        "labels": [],
    }
    rec = intake.parse_issue(issue)
    assert rec["valid"] is True
    assert rec["acceptance"].count("- [ ]") == 2
    assert rec["objective"] == "Measure agent effectiveness."


def test_intake_rejects_missing_acceptance():
    intake = _load("intake_issues")
    issue = {"number": 51, "title": "[queue] No checks", "body": "Just prose, no acceptance.", "labels": []}
    rec = intake.parse_issue(issue)
    assert rec["valid"] is False
    assert "acceptance" in rec["reason"].lower()


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
