from __future__ import annotations

import json
from datetime import datetime, timezone


def _write_learning(path, name: str, category: str, confidence: float, date: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"category: {category}",
                f"confidence: {confidence}",
                f"date: {date}",
                "tags: harness,governance",
                "type: learning",
                "---",
                "",
                f"# {name}",
                "",
                "body",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_usage(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=True) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_compute_learning_tiers_ranks_historical_usage_higher(tmp_path, monkeypatch):
    import scripts.compute_learning_tiers as clt

    repo = tmp_path
    learnings = repo / ".agents" / "learnings"
    usage = repo / ".agents" / "metrics" / "learning_usage.jsonl"
    policy = repo / "config" / "learning_tier_policy.json"

    _write_learning(
        learnings / "historical.md",
        "Historical Standard",
        "governance",
        0.9,
        "2026-01-01",
    )
    _write_learning(
        learnings / "new.md",
        "New Candidate",
        "workflow",
        0.9,
        "2026-05-28",
    )

    rows = []
    for i in range(30):
        rows.append(
            {
                "timestamp_utc": "2026-05-01T00:00:00Z",
                "event_type": "wiki_promoted",
                "learning_name": "Historical Standard",
                "rig_id": f"rig-{(i % 2) + 1}",
            }
        )
    _write_usage(usage, rows)

    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        (clt.REPO / "config" / "learning_tier_policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    monkeypatch.setattr(clt, "REPO", repo)
    monkeypatch.setattr(clt, "LEARNINGS", learnings)
    monkeypatch.setattr(clt, "USAGE_LOG", usage)
    monkeypatch.setattr(clt, "POLICY_PATH", policy)

    report = clt.compute_learning_tiers(now=datetime(2026, 5, 30, tzinfo=timezone.utc))
    ranked = report["top_ranked"]
    assert ranked[0]["name"] == "Historical Standard"
    assert ranked[0]["evidence_tier"] in {"E1", "E2", "E3", "E4"}


def test_compute_learning_tiers_need_mapping(tmp_path, monkeypatch):
    import scripts.compute_learning_tiers as clt

    repo = tmp_path
    learnings = repo / ".agents" / "learnings"
    usage = repo / ".agents" / "metrics" / "learning_usage.jsonl"
    policy = repo / "config" / "learning_tier_policy.json"

    _write_learning(
        learnings / "survival.md",
        "Rollback Guard",
        "security",
        0.8,
        "2026-03-01",
    )

    _write_usage(usage, [])

    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        (clt.REPO / "config" / "learning_tier_policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    monkeypatch.setattr(clt, "REPO", repo)
    monkeypatch.setattr(clt, "LEARNINGS", learnings)
    monkeypatch.setattr(clt, "USAGE_LOG", usage)
    monkeypatch.setattr(clt, "POLICY_PATH", policy)

    report = clt.compute_learning_tiers(now=datetime(2026, 5, 30, tzinfo=timezone.utc))
    item = report["top_ranked"][0]
    assert item["need_level"] == "N1"


def test_compute_learning_tiers_delta_promoted_from_previous_report(tmp_path, monkeypatch):
    import scripts.compute_learning_tiers as clt

    repo = tmp_path
    learnings = repo / ".agents" / "learnings"
    usage = repo / ".agents" / "metrics" / "learning_usage.jsonl"
    policy = repo / "config" / "learning_tier_policy.json"

    _write_learning(
        learnings / "historical.md",
        "Historical Standard",
        "governance",
        0.9,
        "2026-01-01",
    )

    rows = []
    for i in range(12):
        rows.append(
            {
                "timestamp_utc": "2026-05-01T00:00:00Z",
                "event_type": "applied_success",
                "learning_name": "Historical Standard",
                "rig_id": f"rig-{(i % 2) + 1}",
            }
        )
    _write_usage(usage, rows)

    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        (clt.REPO / "config" / "learning_tier_policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    previous = {
        "top_ranked": [
            {
                "slug": "historical-standard",
                "name": "Historical Standard",
                "evidence_tier": "E0",
                "score": 0.2,
            }
        ]
    }

    monkeypatch.setattr(clt, "REPO", repo)
    monkeypatch.setattr(clt, "LEARNINGS", learnings)
    monkeypatch.setattr(clt, "USAGE_LOG", usage)
    monkeypatch.setattr(clt, "POLICY_PATH", policy)

    report = clt.compute_learning_tiers(
        now=datetime(2026, 5, 30, tzinfo=timezone.utc),
        previous_report=previous,
    )
    assert int(report["delta"]["promoted"]) >= 1


def test_compute_learning_tiers_uses_previous_items_not_only_top_ranked(tmp_path, monkeypatch):
    import scripts.compute_learning_tiers as clt

    repo = tmp_path
    learnings = repo / ".agents" / "learnings"
    usage = repo / ".agents" / "metrics" / "learning_usage.jsonl"
    policy = repo / "config" / "learning_tier_policy.json"

    _write_learning(
        learnings / "x.md",
        "X Learning",
        "workflow",
        0.9,
        "2026-01-01",
    )
    _write_usage(usage, [])

    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        (clt.REPO / "config" / "learning_tier_policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    previous = {
        "items": [
            {
                "slug": "x-learning",
                "name": "X Learning",
                "evidence_tier": "E1",
                "score": 0.4,
            }
        ],
        "top_ranked": [],
    }

    monkeypatch.setattr(clt, "REPO", repo)
    monkeypatch.setattr(clt, "LEARNINGS", learnings)
    monkeypatch.setattr(clt, "USAGE_LOG", usage)
    monkeypatch.setattr(clt, "POLICY_PATH", policy)

    report = clt.compute_learning_tiers(
        now=datetime(2026, 5, 30, tzinfo=timezone.utc),
        previous_report=previous,
    )
    assert report["top_ranked"][0]["previous_tier"] == "E1"
