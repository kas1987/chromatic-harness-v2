"""OBS-009: secret-scan gate detects tokens, supports allowlist + staged mode.

Also covers the CODE REVIEW hardenings: Authorization/Cookie header redaction
and the closing-quote fix in redact_secrets.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCANNER = REPO / "scripts" / "scan_for_secrets.py"

sys.path.insert(0, str(REPO / "scripts"))
from redact_secrets import redact  # noqa: E402

FAKE_OPENAI = "sk-" + "A1b2C3d4E5f6G7h8I9j0"  # 20 chars after sk-
FAKE_OPENAI_PROJ = "sk-proj-" + "A1b2C3d4E5f6G7"


def _scan(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCANNER), "--repo-root", str(root), *extra],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True, text=True)


# ---- detection ------------------------------------------------------------


def test_detects_fake_openai_token(tmp_path):
    (tmp_path / "leak.py").write_text(f'KEY = "{FAKE_OPENAI}"\n', encoding="utf-8")
    r = _scan(tmp_path)
    assert r.returncode == 1
    assert "leak.py" in r.stderr


def test_detects_fake_openai_project_token(tmp_path):
    (tmp_path / "leak.txt").write_text(f"token={FAKE_OPENAI_PROJ}\n", encoding="utf-8")
    assert _scan(tmp_path).returncode == 1


def test_clean_repo_passes(tmp_path):
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    assert _scan(tmp_path).returncode == 0


# ---- false-positive handling ---------------------------------------------


def test_allowlist_pragma_suppresses_match(tmp_path):
    (tmp_path / "ex.py").write_text(f'KEY = "{FAKE_OPENAI}"  # pragma: allowlist secret\n', encoding="utf-8")
    assert _scan(tmp_path).returncode == 0


# ---- staged mode ----------------------------------------------------------


def test_staged_mode_only_scans_staged_files(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@e.com")
    _git(tmp_path, "config", "user.name", "T")
    # Unstaged leak must be ignored in --staged mode.
    (tmp_path / "unstaged.py").write_text(f'K="{FAKE_OPENAI}"\n', encoding="utf-8")
    assert _scan(tmp_path, "--staged").returncode == 0
    # Now stage a leak -> detected.
    (tmp_path / "staged.py").write_text(f'K="{FAKE_OPENAI}"\n', encoding="utf-8")
    _git(tmp_path, "add", "staged.py")
    r = _scan(tmp_path, "--staged")
    assert r.returncode == 1
    assert "staged.py" in r.stderr


# ---- redact_secrets hardenings (CODE REVIEW) ------------------------------


def test_redacts_authorization_bearer_header():
    out, changed = redact("Authorization: Bearer abc123def456ghi789")
    assert changed is True
    assert "abc123def456ghi789" not in out
    assert "[REDACTED]" in out


def test_redacts_cookie_header():
    out, changed = redact("Cookie: session=supersecretvalue123")
    assert changed is True
    assert "supersecretvalue123" not in out


def test_redacts_quoted_value_including_closing_quote():
    # Assemble the probe so no literal credential-assignment appears in source
    # (otherwise the repo's own security_scan.py would flag this test file).
    secret_val = "verysecretvalue"
    probe = "api" + "_key" + ' = "' + secret_val + '"'
    out, _ = redact(probe)
    assert secret_val not in out
    assert "[REDACTED]" in out


def test_redacts_github_token_backcompat():
    out, changed = redact("ghp_" + "A" * 36)
    assert changed is True
    assert "ghp_" + "A" * 36 not in out


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
