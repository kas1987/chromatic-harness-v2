"""Tests for scripts/docs_drift_gate.py -- network-free, no live repo required."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Allow importing from scripts/ without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from docs_drift_gate import (  # noqa: E402
    ARTIFACT_DIR,
    collect_and_assess,
    extract_interface_changes,
    summarize,
    write_artifact,
)

# ---------------------------------------------------------------------------
# Sample unified diff snippets
# ---------------------------------------------------------------------------

DIFF_PUBLIC_DEF = """\
diff --git a/scripts/foo.py b/scripts/foo.py
--- a/scripts/foo.py
+++ b/scripts/foo.py
@@ -1,3 +1,5 @@
 existing = 1
+def public_func(x):
+    pass
"""

DIFF_PRIVATE_DEF = """\
diff --git a/scripts/bar.py b/scripts/bar.py
--- a/scripts/bar.py
+++ b/scripts/bar.py
@@ -1,2 +1,4 @@
 x = 1
+def _private_helper():
+    pass
"""

DIFF_CLASS_ADDED = """\
diff --git a/src/models.py b/src/models.py
--- a/src/models.py
+++ b/src/models.py
@@ -0,0 +1,3 @@
+class MyModel:
+    pass
"""

DIFF_ASYNC_DEF = """\
diff --git a/scripts/server.py b/scripts/server.py
--- a/scripts/server.py
+++ b/scripts/server.py
@@ -1,2 +1,4 @@
 import asyncio
+async def handle_request(req):
+    pass
"""

DIFF_NO_INTERFACE = """\
diff --git a/scripts/utils.py b/scripts/utils.py
--- a/scripts/utils.py
+++ b/scripts/utils.py
@@ -1,2 +1,3 @@
 X = 1
+Y = 2
"""

DIFF_OUTSIDE_DIRS = """\
diff --git a/config/settings.py b/config/settings.py
--- a/config/settings.py
+++ b/config/settings.py
@@ -0,0 +1,2 @@
+def public_ignored(x):
+    pass
"""

# ---------------------------------------------------------------------------
# extract_interface_changes tests
# ---------------------------------------------------------------------------


def test_public_def_detected():
    changes = extract_interface_changes(DIFF_PUBLIC_DEF)
    assert len(changes) == 1
    assert changes[0]["name"] == "public_func"
    assert changes[0]["kind"] == "def"
    assert changes[0]["change"] == "added"
    assert changes[0]["file"] == "scripts/foo.py"


def test_private_def_ignored():
    changes = extract_interface_changes(DIFF_PRIVATE_DEF)
    assert changes == []


def test_class_added_detected():
    changes = extract_interface_changes(DIFF_CLASS_ADDED)
    assert len(changes) == 1
    assert changes[0]["name"] == "MyModel"
    assert changes[0]["kind"] == "class"


def test_async_def_detected():
    changes = extract_interface_changes(DIFF_ASYNC_DEF)
    assert len(changes) == 1
    assert changes[0]["name"] == "handle_request"
    assert changes[0]["kind"] == "async def"


def test_no_interface_change():
    changes = extract_interface_changes(DIFF_NO_INTERFACE)
    assert changes == []


def test_outside_dirs_ignored():
    """Files outside scripts/ and src/ should not be reported."""
    changes = extract_interface_changes(DIFF_OUTSIDE_DIRS)
    assert changes == []


# ---------------------------------------------------------------------------
# collect_and_assess tests (monkeypatched -- no live git)
# ---------------------------------------------------------------------------


def _patch_collect(monkeypatch, *, interface_changes, changed_paths, diff_text=""):
    """Monkeypatch the helpers used by collect_and_assess."""
    import docs_drift_gate as m

    monkeypatch.setattr(m, "_merge_base", lambda base: "FAKESHA")
    monkeypatch.setattr(m, "_get_numstat", lambda ref: changed_paths)
    monkeypatch.setattr(m, "_get_full_diff", lambda ref: diff_text)
    monkeypatch.setattr(m, "extract_interface_changes", lambda diff: interface_changes)


def test_drift_when_interface_changes_no_docs(monkeypatch):
    _patch_collect(monkeypatch, interface_changes=[{"name": "foo"}], changed_paths=["scripts/foo.py"])
    result = collect_and_assess("origin/base", strict=False)
    assert result["has_drift"] is True
    assert result["risk_level"] == "warn"
    assert result["passed"] is True  # warn => exit 0


def test_no_drift_when_docs_also_changed(monkeypatch):
    _patch_collect(
        monkeypatch,
        interface_changes=[{"name": "foo"}],
        changed_paths=["scripts/foo.py", "docs/api.md"],
    )
    result = collect_and_assess("origin/base", strict=False)
    assert result["has_drift"] is False
    assert result["risk_level"] == "ok"
    assert result["passed"] is True


def test_strict_fails_on_drift(monkeypatch):
    _patch_collect(monkeypatch, interface_changes=[{"name": "bar"}], changed_paths=["src/bar.py"])
    result = collect_and_assess("origin/base", strict=True)
    assert result["risk_level"] == "fail"
    assert result["passed"] is False


def test_no_interface_change_always_ok(monkeypatch):
    _patch_collect(monkeypatch, interface_changes=[], changed_paths=["scripts/utils.py"])
    result = collect_and_assess("origin/base", strict=True)
    assert result["risk_level"] == "ok"
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# write_artifact + summarize tests
# ---------------------------------------------------------------------------


def test_write_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("docs_drift_gate.ARTIFACT_DIR", tmp_path)
    result = {
        "interface_changes": [],
        "interface_change_count": 0,
        "docs_updated": False,
        "has_drift": False,
        "risk_level": "ok",
        "passed": True,
        "strict": False,
        "base": "SHA",
    }
    artifact = write_artifact(result, "20260101T000000Z")
    assert artifact.exists()
    data = json.loads(artifact.read_text())
    assert data["passed"] is True
    assert data["timestamp"] == "20260101T000000Z"


def test_summarize_fail_open(tmp_path, monkeypatch):
    monkeypatch.setattr("docs_drift_gate.ARTIFACT_DIR", tmp_path)
    # No latest.json exists yet.
    s = summarize()
    assert s["status"] == "no_scan"
    assert s["passed"] is None


def test_summarize_reads_latest(tmp_path, monkeypatch):
    monkeypatch.setattr("docs_drift_gate.ARTIFACT_DIR", tmp_path)
    payload = {
        "passed": False,
        "interface_change_count": 2,
        "docs_updated": False,
        "risk_level": "warn",
        "timestamp": "20260601T120000Z",
    }
    (tmp_path / "latest.json").write_text(json.dumps(payload))
    s = summarize()
    assert s["status"] == "ok"
    assert s["passed"] is False
    assert s["interface_changes"] == 2
    assert s["risk_level"] == "warn"
