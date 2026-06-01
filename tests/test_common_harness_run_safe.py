"""Regression tests for common_harness.run_safe (chromatic-harness-v2-j2r0).

run_safe replaces bare subprocess.run(timeout=) and must reap the WHOLE
process tree on timeout — on Windows a plain kill leaves grandchildren alive
holding locks/pipes (root cause of the bpc5 gate hang).
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, REPO / "scripts" / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


ch = _load("common_harness")


def test_run_safe_success_shape():
    r = ch.run_safe([sys.executable, "-c", "print('ok')"], timeout=10)
    assert r.returncode == 0
    assert "ok" in r.stdout
    assert hasattr(r, "stderr")


def test_run_safe_nonzero_exit():
    r = ch.run_safe([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=10)
    assert r.returncode == 3


def test_run_safe_reaps_process_tree_on_timeout(tmp_path):
    marker = tmp_path / "alive.log"
    grandchild = tmp_path / "grandchild.py"
    grandchild.write_text(
        textwrap.dedent(
            f"""
            import time
            for _ in range(400):
                with open(r"{marker}", "a") as fh:
                    fh.write("x")
                time.sleep(0.05)
            """
        )
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        textwrap.dedent(
            f"""
            import subprocess, sys, time
            subprocess.Popen([sys.executable, r"{grandchild}"])
            time.sleep(60)
            """
        )
    )

    r = ch.run_safe([sys.executable, str(parent)], timeout=2)
    assert r.returncode != 0, f"expected timeout failure, got {r.returncode}"

    size_at_kill = marker.stat().st_size if marker.exists() else 0
    time.sleep(2.0)
    size_later = marker.stat().st_size if marker.exists() else 0
    assert size_later == size_at_kill, (
        f"grandchild kept writing after run_safe timed out -> tree not reaped ({size_at_kill} -> {size_later} bytes)"
    )


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
