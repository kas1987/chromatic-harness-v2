"""Unit tests for the 5 observability CLI scripts (Phase 2b).

Covers:
  - redact_secrets.redact
  - log_harness_event: via subprocess (CLI only; helpers live in common_harness)
  - summarize_error_patterns.load_events (+ main via subprocess)
  - detect_file_collisions.main (via subprocess)
  - validate_event_log.validate_line (+ main via subprocess)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"

# scripts/ must be importable so the modules resolve.
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import detect_file_collisions  # noqa: E402,F401  (imported for path coverage)
import redact_secrets  # noqa: E402
import summarize_error_patterns  # noqa: E402
import validate_event_log  # noqa: E402

PY = sys.executable


def _run(script_name: str, *cli_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, str(_SCRIPTS / script_name), *cli_args],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
    )


# --------------------------------------------------------------------------
# redact_secrets.redact
# --------------------------------------------------------------------------


class TestRedactText:
    def test_returns_tuple(self):
        out, flag = redact_secrets.redact("hello world")
        assert out == "hello world"
        assert flag is False

    def test_none_input_raises(self):
        with pytest.raises(TypeError):
            redact_secrets.redact(None)  # type: ignore[arg-type]

    def test_empty_string(self):
        assert redact_secrets.redact("") == ("", False)

    def test_openai_key(self):
        out, flag = redact_secrets.redact("key is sk-abcdefghij1234567890ABCD")  # pragma: allowlist secret
        assert flag is True
        assert "sk-[REDACTED]" in out
        assert "sk-abcdefghij" not in out

    def test_github_classic_pat(self):
        out, flag = redact_secrets.redact("ghp_abcdefghij1234567890ABCDEF")  # pragma: allowlist secret
        assert flag is True
        assert "ghp_[REDACTED]" in out
        assert "ghp_abcdefghij" not in out

    def test_github_fine_grained_pat(self):
        out, flag = redact_secrets.redact("github_pat_abcdefghij1234567890ABCDEF")  # pragma: allowlist secret
        assert flag is True
        assert "github_pat_[REDACTED]" in out

    def test_keyvalue_assignment(self):
        out, flag = redact_secrets.redact('api_key="supersecretvalue"')  # pragma: allowlist secret
        assert flag is True
        assert "supersecretvalue" not in out

    def test_password_assignment_case_insensitive(self):
        out, flag = redact_secrets.redact("PASSWORD: hunter2longenough")  # pragma: allowlist secret
        assert flag is True

    def test_private_key_block(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"  # pragma: allowlist secret
        out, flag = redact_secrets.redact(text)
        assert flag is True
        assert "[REDACTED_PRIVATE_KEY]" in out
        assert "MIIEpAIBAAKCAQEA" not in out

    def test_multiple_secrets_one_flag(self):
        multi = "sk-abcdefghij1234567890ABCD and ghp_abcdefghij1234567890ABCDEF"  # pragma: allowlist secret
        out, flag = redact_secrets.redact(multi)
        assert flag is True
        assert "sk-[REDACTED]" in out
        assert "ghp_[REDACTED]" in out

    def test_cli_passthrough(self):
        proc = subprocess.run(
            [PY, str(_SCRIPTS / "redact_secrets.py")],
            input="token=abcdefghijklmnop12345",  # pragma: allowlist secret
            capture_output=True,
            text=True,
            cwd=str(_REPO),
        )
        assert proc.returncode == 0
        assert "abcdefghijklmnop12345" not in proc.stdout
        assert "[REDACTED]" in proc.stdout


# --------------------------------------------------------------------------
# log_harness_event — CLI only (helpers are in common_harness)
# --------------------------------------------------------------------------


class TestLogHarnessEventCli:
    def test_end_to_end_append(self, tmp_path):
        log_path = tmp_path / "ERROR_LOG.jsonl"
        proc = _run(
            "log_harness_event.py",
            "--log-path",
            str(log_path),
            "--surface",
            "terminal",
            "--event-type",
            "error",
            "--severity",
            "high",
            "--category",
            "tool_failure",
            "--repo",
            "testrepo",
        )
        assert proc.returncode == 0, proc.stderr
        # stdout is the event_id
        assert proc.stdout.strip().startswith("evt_")
        record = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert record["repo"] == "testrepo"

    def test_invalid_event_type_rejected(self, tmp_path):
        proc = _run(
            "log_harness_event.py",
            "--log-path",
            str(tmp_path / "x.jsonl"),
            "--surface",
            "terminal",
            "--event-type",
            "nope",
            "--severity",
            "high",
            "--category",
            "tool_failure",
            "--repo",
            "testrepo",
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
    def test_missing_file_returns_success(self, tmp_path):
        # Missing file → read_json returns default {} → no collisions → exit 0
        proc = _run("detect_file_collisions.py", "--active-writers", str(tmp_path / "nope.json"))
        assert proc.returncode == 0
        assert "No active writer collisions detected." in proc.stdout

    def test_no_collision(self, tmp_path):
        path = tmp_path / "active_writers.json"
        path.write_text(
            json.dumps(
                {
                    "writers": [
                        {"session": "s1", "files": ["x.py"]},
                        {"session": "s1", "files": ["y.py"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        proc = _run("detect_file_collisions.py", "--active-writers", str(path))
        assert proc.returncode == 0
        assert "No active writer collisions detected." in proc.stdout

    def test_collision_detected_exit_1(self, tmp_path):
        path = tmp_path / "active_writers.json"
        path.write_text(
            json.dumps(
                {
                    "writers": [
                        {
                            "session": "s1",
                            "files": ["shared.py"],
                        },
                        {
                            "session": "s2",
                            "files": ["shared.py"],
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        proc = _run("detect_file_collisions.py", "--active-writers", str(path))
        assert proc.returncode == 1
        assert "COLLISIONS DETECTED" in proc.stderr
        assert "shared.py" in proc.stderr


# --------------------------------------------------------------------------
# validate_event_log.validate_line (+ CLI)
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
        assert proc.returncode == 2
        assert "not found" in proc.stderr.lower()

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
