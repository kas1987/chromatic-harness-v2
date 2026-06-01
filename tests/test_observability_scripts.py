"""Unit tests for the 5 observability CLI scripts (Phase 2b).

Covers:
  - redact_secrets.redact_text
  - log_harness_event: build_event, append_event, now_iso, make_event_id, split_csv
  - summarize_error_patterns.load_events (+ main via subprocess)
  - detect_file_collisions.main (via subprocess)
  - validate_event_log.validate_line (+ main via subprocess)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"

# scripts/ must be importable so the modules (and the cross-import
# `from redact_secrets import redact_text` inside log_harness_event) resolve.
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import detect_file_collisions  # noqa: E402,F401  (imported for path coverage / subprocess uses file)
import log_harness_event  # noqa: E402
import redact_secrets  # noqa: E402
import summarize_error_patterns  # noqa: E402
import validate_event_log  # noqa: E402

PY = sys.executable


def _run(script_name: str, *cli_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, str(_SCRIPTS / script_name), *cli_args],
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------
# redact_secrets.redact_text
# --------------------------------------------------------------------------


class TestRedactText:
    def test_returns_tuple(self):
        out, flag = redact_secrets.redact_text("hello world")
        assert out == "hello world"
        assert flag is False

    def test_none_input_safe(self):
        out, flag = redact_secrets.redact_text(None)  # type: ignore[arg-type]
        assert out == ""
        assert flag is False

    def test_empty_string(self):
        assert redact_secrets.redact_text("") == ("", False)

    def test_openai_key(self):
        out, flag = redact_secrets.redact_text("key is sk-abcdefghij1234567890ABCD")
        assert flag is True
        assert "[REDACTED_SECRET]" in out
        assert "sk-abcdefghij" not in out

    def test_github_classic_pat(self):
        out, flag = redact_secrets.redact_text("ghp_abcdefghij1234567890ABCDEF")
        assert flag is True
        assert "ghp_" not in out

    def test_github_fine_grained_pat(self):
        out, flag = redact_secrets.redact_text("github_pat_abcdefghij1234567890ABCDEF")
        assert flag is True
        assert "[REDACTED_SECRET]" in out

    def test_keyvalue_assignment(self):
        out, flag = redact_secrets.redact_text('api_key="supersecretvalue"')  # pragma: allowlist secret
        assert flag is True
        assert "supersecretvalue" not in out

    def test_password_assignment_case_insensitive(self):
        out, flag = redact_secrets.redact_text("PASSWORD: hunter2longenough")
        assert flag is True

    def test_private_key_block(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"  # pragma: allowlist secret
        out, flag = redact_secrets.redact_text(text)
        assert flag is True
        assert "[REDACTED_SECRET]" in out
        assert "MIIEpAIBAAKCAQEA" not in out

    def test_multiple_secrets_one_flag(self):
        out, flag = redact_secrets.redact_text("sk-abcdefghij1234567890ABCD and ghp_abcdefghij1234567890ABCDEF")
        assert flag is True
        assert out.count("[REDACTED_SECRET]") >= 2

    def test_cli_passthrough(self):
        proc = subprocess.run(
            [PY, str(_SCRIPTS / "redact_secrets.py")],
            input="token=abcdefghijklmnop12345",
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert "abcdefghijklmnop12345" not in proc.stdout
        assert "[REDACTED_SECRET]" in proc.stdout


# --------------------------------------------------------------------------
# log_harness_event helpers
# --------------------------------------------------------------------------


class TestNowIso:
    def test_format(self):
        value = log_harness_event.now_iso()
        # round-trips as ISO 8601 with offset, second precision
        parsed = __import__("datetime").datetime.fromisoformat(value)
        assert parsed.tzinfo is not None


class TestMakeEventId:
    def test_prefix_and_uniqueness(self):
        a = log_harness_event.make_event_id()
        b = log_harness_event.make_event_id()
        assert a.startswith("evt_")
        assert a != b
        assert len(a.split("_")[-1]) == 8


class TestSplitCsv:
    def test_none(self):
        assert log_harness_event.split_csv(None) == []

    def test_empty(self):
        assert log_harness_event.split_csv("") == []

    def test_basic(self):
        assert log_harness_event.split_csv("a,b,c") == ["a", "b", "c"]

    def test_strips_and_drops_blank(self):
        assert log_harness_event.split_csv(" a , , b ,") == ["a", "b"]


def _ns(**overrides) -> argparse.Namespace:
    base = dict(
        event_id=None,
        timestamp=None,
        repo="myrepo",
        workspace=None,
        source="terminal",
        ide=None,
        agent=None,
        model=None,
        session_id="sess-1",
        event_type="error",
        severity="high",
        category="tool_failure",
        message="something broke",
        command=None,
        files_touched=None,
        error_signature=None,
        raw_excerpt=None,
        redacted=False,
        suspected_cause=None,
        action_taken=None,
        status="open",
        linked_fix=None,
        linked_learning=None,
        next_action=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class TestBuildEvent:
    def test_minimal_event_shape(self):
        event = log_harness_event.build_event(_ns())
        assert event["repo"] == "myrepo"
        assert event["event_type"] == "error"
        assert event["source"]["surface"] == "terminal"
        assert event["source"]["session_id"] == "sess-1"
        assert event["files_touched"] == []
        assert event["redacted"] is False
        assert event["metadata"] == {}

    def test_files_touched_split(self):
        event = log_harness_event.build_event(_ns(files_touched="a.py, b.py"))
        assert event["files_touched"] == ["a.py", "b.py"]

    def test_generates_id_and_timestamp(self):
        event = log_harness_event.build_event(_ns())
        assert event["event_id"].startswith("evt_")
        assert event["timestamp"]

    def test_honors_explicit_id_and_timestamp(self):
        event = log_harness_event.build_event(_ns(event_id="evt_fixed", timestamp="2026-01-01T00:00:00+00:00"))
        assert event["event_id"] == "evt_fixed"
        assert event["timestamp"] == "2026-01-01T00:00:00+00:00"

    def test_redaction_sets_flag(self):
        event = log_harness_event.build_event(_ns(message="leaked ghp_abcdefghij1234567890ABCDEF"))
        assert event["redacted"] is True
        assert "ghp_" not in event["message"]

    def test_explicit_redacted_flag_preserved(self):
        event = log_harness_event.build_event(_ns(redacted=True))
        assert event["redacted"] is True

    @pytest.mark.parametrize(
        "field,bad",
        [
            ("event_type", "bogus"),
            ("severity", "bogus"),
            ("category", "bogus"),
            ("status", "bogus"),
        ],
    )
    def test_invalid_enum_raises(self, field, bad):
        with pytest.raises(SystemExit):
            log_harness_event.build_event(_ns(**{field: bad}))


class TestAppendEvent:
    def test_writes_jsonl_and_creates_parent(self, tmp_path):
        log_path = tmp_path / "nested" / "ERROR_LOG.jsonl"
        event = log_harness_event.build_event(_ns(event_id="evt_x"))
        log_harness_event.append_event(event, log_path)
        log_harness_event.append_event(event, log_path)
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        loaded = json.loads(lines[0])
        assert loaded["event_id"] == "evt_x"
        # sort_keys=True is used on write
        assert list(loaded.keys()) == sorted(loaded.keys())


class TestLogHarnessEventCli:
    def test_end_to_end_append(self, tmp_path):
        log_path = tmp_path / "ERROR_LOG.jsonl"
        proc = _run(
            "log_harness_event.py",
            "--log",
            str(log_path),
            "--source",
            "terminal",
            "--event-type",
            "error",
            "--severity",
            "high",
            "--category",
            "tool_failure",
            "--message",
            "boom",
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout)
        assert out["logged"] is True
        record = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert record["message"] == "boom"

    def test_invalid_choice_rejected(self, tmp_path):
        proc = _run(
            "log_harness_event.py",
            "--log",
            str(tmp_path / "x.jsonl"),
            "--source",
            "terminal",
            "--event-type",
            "nope",
            "--severity",
            "high",
            "--category",
            "tool_failure",
            "--message",
            "boom",
        )
        assert proc.returncode != 0


# --------------------------------------------------------------------------
# summarize_error_patterns.load_events
# --------------------------------------------------------------------------


class TestLoadEvents:
    def test_missing_file_returns_empty(self, tmp_path):
        assert summarize_error_patterns.load_events(tmp_path / "nope.jsonl") == []

    def test_skips_blank_lines(self, tmp_path):
        path = tmp_path / "log.jsonl"
        path.write_text('{"a": 1}\n\n  \n{"b": 2}\n', encoding="utf-8")
        events = summarize_error_patterns.load_events(path)
        assert events == [{"a": 1}, {"b": 2}]

    def test_summary_main_runs(self, tmp_path):
        path = tmp_path / "log.jsonl"
        records = [
            {"category": "tool_failure", "severity": "high", "error_signature": "E1", "files_touched": ["a.py"]},
            {"category": "tool_failure", "severity": "low", "message": "another", "files_touched": ["a.py", "b.py"]},
        ]
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        proc = _run("summarize_error_patterns.py", "--log", str(path))
        assert proc.returncode == 0, proc.stderr
        assert "# Error Pattern Summary" in proc.stdout
        assert "tool_failure: 2" in proc.stdout
        assert "2x: a.py" in proc.stdout


# --------------------------------------------------------------------------
# detect_file_collisions (CLI / subprocess)
# --------------------------------------------------------------------------


class TestDetectFileCollisions:
    def test_missing_file_errors(self, tmp_path):
        proc = _run("detect_file_collisions.py", "--active-writers", str(tmp_path / "nope.json"))
        assert proc.returncode != 0
        assert "not found" in proc.stderr or "not found" in proc.stdout

    def test_no_collision(self, tmp_path):
        path = tmp_path / "active_writers.json"
        path.write_text(
            json.dumps(
                {
                    "writers": [
                        {"writer": "a", "files_claimed": ["x.py"]},
                        {"writer": "b", "files_claimed": ["y.py"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        proc = _run("detect_file_collisions.py", "--active-writers", str(path))
        assert proc.returncode == 0
        assert "No collisions detected." in proc.stdout

    def test_collision_detected_exit_2(self, tmp_path):
        path = tmp_path / "active_writers.json"
        path.write_text(
            json.dumps(
                {
                    "writers": [
                        {
                            "writer": "a",
                            "surface": "claude",
                            "session_id": "s1",
                            "task": "t1",
                            "files_claimed": ["shared.py"],
                        },
                        {
                            "writer": "b",
                            "surface": "codex",
                            "session_id": "s2",
                            "task": "t2",
                            "files_claimed": ["shared.py"],
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        proc = _run("detect_file_collisions.py", "--active-writers", str(path))
        assert proc.returncode == 2
        assert "Collisions detected:" in proc.stdout
        assert "shared.py" in proc.stdout
        assert "writer=a" in proc.stdout


# --------------------------------------------------------------------------
# validate_event_log.validate_line
# --------------------------------------------------------------------------


def _valid_record() -> dict:
    return {
        "event_id": "evt_1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "event_type": "error",
        "severity": "high",
        "category": "tool_failure",
        "message": "boom",
        "source": {"surface": "terminal"},
        "status": "open",
    }


class TestValidateLine:
    def test_valid(self):
        assert validate_event_log.validate_line(json.dumps(_valid_record()), 1) == []

    def test_invalid_json(self):
        errs = validate_event_log.validate_line("{not json", 3)
        assert len(errs) == 1
        assert "invalid JSON" in errs[0]
        assert "Line 3" in errs[0]

    def test_missing_required_fields(self):
        rec = _valid_record()
        del rec["event_id"]
        del rec["status"]
        errs = validate_event_log.validate_line(json.dumps(rec), 5)
        assert any("missing required fields" in e for e in errs)
        assert any("event_id" in e and "status" in e for e in errs)

    def test_source_not_object(self):
        rec = _valid_record()
        rec["source"] = "terminal"
        errs = validate_event_log.validate_line(json.dumps(rec), 1)
        assert any("source must be object" in e for e in errs)

    def test_source_missing_surface(self):
        rec = _valid_record()
        rec["source"] = {"ide": "vscode"}
        errs = validate_event_log.validate_line(json.dumps(rec), 1)
        assert any("source.surface missing" in e for e in errs)


class TestValidateEventLogCli:
    def test_missing_log_errors(self, tmp_path):
        proc = _run("validate_event_log.py", "--log", str(tmp_path / "nope.jsonl"))
        assert proc.returncode != 0
        assert "not found" in proc.stderr or "not found" in proc.stdout

    def test_valid_log_passes(self, tmp_path):
        path = tmp_path / "log.jsonl"
        path.write_text(json.dumps(_valid_record()) + "\n", encoding="utf-8")
        proc = _run("validate_event_log.py", "--log", str(path))
        assert proc.returncode == 0
        assert "Validation passed" in proc.stdout

    def test_invalid_log_fails(self, tmp_path):
        path = tmp_path / "log.jsonl"
        bad = _valid_record()
        del bad["message"]
        path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
        proc = _run("validate_event_log.py", "--log", str(path))
        assert proc.returncode == 1
        assert "Validation failed" in proc.stdout
