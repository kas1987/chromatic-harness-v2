"""Tests for sync_wiki_mirror.py."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]


def test_mirror_dry_run_finds_governance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "manifest.yaml").write_text(
        yaml.dump(
            {
                "harness_docs_mirror": [
                    {
                        "source": "docs/governance/ACTIVITY_LOG_AND_DUAL_BACKLOG.md",
                        "target": "03_GOVERNANCE/ACTIVITY_LOG_AND_DUAL_BACKLOG.md",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    src = REPO / "docs" / "governance" / "ACTIVITY_LOG_AND_DUAL_BACKLOG.md"
    if not src.is_file():
        pytest.skip("governance doc missing in harness")

    monkeypatch.setenv("CHROMATIC_WIKI_ROOT", str(wiki))
    import scripts.sync_wiki_mirror as mod

    results = mod._mirror_tree(
        REPO,
        wiki,
        "docs/governance/ACTIVITY_LOG_AND_DUAL_BACKLOG.md",
        "03_GOVERNANCE/ACTIVITY_LOG_AND_DUAL_BACKLOG.md",
        execute=False,
    )
    assert len(results) == 1
    assert results[0]["changed"] is True
