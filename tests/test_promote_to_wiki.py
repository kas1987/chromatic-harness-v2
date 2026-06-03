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
