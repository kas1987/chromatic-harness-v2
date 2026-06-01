"""Tests for harvest_rigs knowledge promotion."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from knowledge.harvest_rigs import (  # noqa: E402
    dedupe_artifacts,
    discover_rig_roots,
    run_harvest,
    scan_rig,
)


def _write_learning(base: Path, name: str, confidence: float, body: str) -> None:
    path = base / ".agents" / "learnings" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\nconfidence: {confidence}\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_discover_and_dedupe(tmp_path: Path):
    _write_learning(tmp_path, "alpha", 0.9, "Same pattern insight.")
    rig2 = tmp_path / "rig-b"
    _write_learning(rig2, "alpha-dup", 0.5, "Same pattern insight.")

    roots = discover_rig_roots(tmp_path, [rig2])
    assert len(roots) == 2

    arts = []
    for r in roots:
        arts.extend(scan_rig(r))
    assert len(arts) == 2
    unique, dups = dedupe_artifacts(arts)
    assert len(unique) == 1
    assert len(dups) == 1


def test_run_harvest_promotes_high_confidence(tmp_path: Path):
    rig = tmp_path / "satellite-rig"
    _write_learning(rig, "promote-me", 0.85, "High value learning for harness.")
    _write_learning(rig, "skip-me", 0.2, "Low confidence noise.")
    (tmp_path / ".agents" / "learnings").mkdir(parents=True, exist_ok=True)

    report = run_harvest(tmp_path, extra_roots=[rig], min_confidence=0.5, dry_run=False)
    assert report.artifacts_found == 2
    assert len(report.promoted) == 1
    dest = tmp_path / ".agents" / "learnings" / "promote-me.md"
    assert dest.is_file()
    catalog = json.loads((tmp_path / ".agents" / "harvest" / "latest.json").read_text(encoding="utf-8"))
    assert catalog["unique_count"] == 2


def test_harvest_cli_dry_run():
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "harvest_rigs.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout.strip())
    assert "rigs_scanned" in data
    assert data["dry_run"] is True
