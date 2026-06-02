from __future__ import annotations


def test_discover_candidates_includes_auto_turn_threshold_report(tmp_path, monkeypatch):
    from scripts import promote_to_wiki as p2w

    learnings_dir = tmp_path / ".agents" / "learnings"
    auto_turn_dir = tmp_path / "07_LOGS_AND_AUDIT" / "auto_turn_thresholds"
    learnings_dir.mkdir(parents=True, exist_ok=True)
    auto_turn_dir.mkdir(parents=True, exist_ok=True)

    md = "\n".join(
        [
            "---",
            "name: auto-turn-threshold-calibration",
            "confidence: 0.82",
            "status: candidate",
            "---",
            "",
            "# Auto-Turn Threshold Calibration",
            "",
            "body",
            "",
        ]
    )
    source = auto_turn_dir / "latest.md"
    source.write_text(md, encoding="utf-8")

    monkeypatch.setattr(p2w, "REPO", tmp_path)
    monkeypatch.setattr(p2w, "LEARNINGS", learnings_dir)
    monkeypatch.setattr(p2w, "AUTO_TURN_REPORTS", auto_turn_dir)

    items = p2w._discover_candidates(0.75)
    paths = {str(item.get("path")).replace("\\", "/") for item in items}
    assert "07_LOGS_AND_AUDIT/auto_turn_thresholds/latest.md" in paths


def test_promote_auto_turn_report_to_canonical_slug(tmp_path, monkeypatch):
    from scripts import promote_to_wiki as p2w

    source = tmp_path / "07_LOGS_AND_AUDIT" / "auto_turn_thresholds" / "latest.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "\n".join(
            [
                "---",
                "name: auto-turn-threshold-calibration",
                "confidence: 0.82",
                "status: candidate",
                "---",
                "",
                "# Auto-Turn Threshold Calibration",
                "",
                "body",
                "",
            ]
        ),
        encoding="utf-8",
    )

    wiki_root = tmp_path / "wiki"
    (wiki_root / p2w.WIKI_LEARNINGS).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(p2w, "REPO", tmp_path)
    rel = p2w._promote_one(source, wiki_root, execute=True)
    rel_norm = str(rel or "").replace("\\", "/")
    assert rel_norm == "02_LEARNINGS/auto-turn-threshold-calibration.md"

    dest = wiki_root / p2w.WIKI_LEARNINGS / "auto-turn-threshold-calibration.md"
    assert dest.is_file()
    written = dest.read_text(encoding="utf-8")
    assert "promoted_from: 07_LOGS_AND_AUDIT/auto_turn_thresholds/latest.md" in written


def _learning(name: str, body: str = "shared body text") -> str:
    return "\n".join(["---", f"name: {name}", "confidence: 0.9", "status: candidate", "---", "", body, ""])


def test_cross_repo_dedup_skips_same_body_under_different_slug(tmp_path, monkeypatch):
    """OMH-6: a learning promoted by one repo is not re-promoted by another."""
    from scripts import promote_to_wiki as p2w

    monkeypatch.setattr(p2w, "REPO", tmp_path)
    wiki = tmp_path / "wiki"
    (wiki / p2w.WIKI_LEARNINGS).mkdir(parents=True, exist_ok=True)

    src_a = tmp_path / "a.md"
    src_a.write_text(_learning("repo-a-name", "identical lesson"), encoding="utf-8")
    src_b = tmp_path / "b.md"
    src_b.write_text(_learning("repo-b-name", "identical lesson"), encoding="utf-8")  # same body, different name

    index: dict = {}
    rel_a = p2w._promote_one(src_a, wiki, execute=True, index=index, repo_id="kas1987/harness", cadence="epic-close")
    rel_b = p2w._promote_one(src_b, wiki, execute=True, index=index, repo_id="kas1987/systems", cadence="weekly")

    assert str(rel_a or "").replace("\\", "/") == "02_LEARNINGS/repo-a-name.md"
    assert rel_b is None  # deduped: same body already promoted by repo-a
    assert len(index) == 1
    entry = next(iter(index.values()))
    assert entry["repo_id"] == "kas1987/harness" and entry["cadence"] == "epic-close"
    # The second repo's slug file was never written.
    assert not (wiki / p2w.WIKI_LEARNINGS / "repo-b-name.md").is_file()


def test_promotion_index_round_trips(tmp_path):
    from scripts import promote_to_wiki as p2w

    wiki = tmp_path / "wiki"
    (wiki / p2w.WIKI_LEARNINGS).mkdir(parents=True, exist_ok=True)
    assert p2w._load_promotion_index(wiki) == {}
    idx = {"abc": {"slug": "x", "repo_id": "r", "cadence": "weekly", "promoted_at": "2026-06-02T00:00:00Z"}}
    p2w._save_promotion_index(wiki, idx)
    assert p2w._load_promotion_index(wiki) == idx


def test_index_none_preserves_legacy_behavior(tmp_path, monkeypatch):
    from scripts import promote_to_wiki as p2w

    monkeypatch.setattr(p2w, "REPO", tmp_path)
    wiki = tmp_path / "wiki"
    (wiki / p2w.WIKI_LEARNINGS).mkdir(parents=True, exist_ok=True)
    src = tmp_path / "a.md"
    src.write_text(_learning("legacy", "body"), encoding="utf-8")
    rel = p2w._promote_one(src, wiki, execute=True)  # no index -> legacy path
    assert str(rel or "").replace("\\", "/") == "02_LEARNINGS/legacy.md"
    assert not (wiki / p2w.WIKI_LEARNINGS / p2w.PROMOTION_INDEX).is_file()
