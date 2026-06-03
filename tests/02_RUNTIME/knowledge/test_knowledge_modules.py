"""Tests for 02_RUNTIME/knowledge/ — harvest_rigs.py and select_learnings.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from knowledge.harvest_rigs import (  # noqa: E402
    Artifact,
    HarvestReport,
    _content_hash,
    _normalize_body,
    _normalize_confidence,
    _parse_frontmatter,
    dedupe_artifacts,
    discover_rig_roots,
    promote_artifacts,
    run_harvest,
    scan_rig,
)
from knowledge.select_learnings import (  # noqa: E402
    _parse_frontmatter as sl_parse_frontmatter,
    _title,
    format_for_injection,
    load_learnings,
    score,
    select_top,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_md(base: Path, name: str, confidence: float, body: str, extra_meta: str = "") -> Path:
    path = base / ".agents" / "learnings" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\nconfidence: {confidence}\n{extra_meta}---\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def _write_pattern(base: Path, name: str, confidence: float, body: str) -> Path:
    path = base / ".agents" / "patterns" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\nconfidence: {confidence}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def _write_sl(d: Path, name: str, date: str, conf: str, tags: str, title: str) -> None:
    (d / name).write_text(
        f"---\ndate: {date}\nconfidence: {conf}\ntags: [{tags}]\n---\n\n# {title}\n\nbody\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# harvest_rigs — _parse_frontmatter
# ---------------------------------------------------------------------------


def test_parse_frontmatter_basic():
    text = "---\nname: test\nconfidence: 0.9\n---\n\nBody."
    meta = _parse_frontmatter(text)
    assert meta["name"] == "test"
    assert meta["confidence"] == "0.9"


def test_parse_frontmatter_no_frontmatter():
    meta = _parse_frontmatter("Just a body, no frontmatter.")
    assert meta == {}


def test_parse_frontmatter_strips_quotes():
    text = '---\nname: "quoted name"\n---\n\nBody.'
    meta = _parse_frontmatter(text)
    assert meta["name"] == "quoted name"


# ---------------------------------------------------------------------------
# harvest_rigs — _normalize_confidence
# ---------------------------------------------------------------------------


def test_normalize_confidence_fraction():
    assert _normalize_confidence(0.75) == pytest.approx(0.75)


def test_normalize_confidence_percentage():
    assert _normalize_confidence(85) == pytest.approx(0.85)


def test_normalize_confidence_none_default():
    assert _normalize_confidence(None) == pytest.approx(0.5)


def test_normalize_confidence_bad_string():
    assert _normalize_confidence("high") == pytest.approx(0.5)


def test_normalize_confidence_clamps_to_one():
    assert _normalize_confidence(150) == pytest.approx(1.0)


def test_normalize_confidence_clamps_to_zero():
    assert _normalize_confidence(-5) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# harvest_rigs — _normalize_body / _content_hash
# ---------------------------------------------------------------------------


def test_normalize_body_strips_frontmatter():
    text = "---\nname: foo\n---\n\n  Multi  word   body. "
    body = _normalize_body(text)
    assert "name" not in body
    assert "multi word body." in body


def test_content_hash_deterministic():
    text = "---\nname: foo\n---\n\nBody content."
    assert _content_hash(text) == _content_hash(text)


def test_content_hash_same_body_different_meta():
    t1 = "---\nname: a\nconfidence: 0.9\n---\n\nBody content."
    t2 = "---\nname: b\nconfidence: 0.1\n---\n\nBody content."
    # Same body → same hash.
    assert _content_hash(t1) == _content_hash(t2)


def test_content_hash_different_body():
    t1 = "---\nname: a\n---\n\nBody A."
    t2 = "---\nname: a\n---\n\nBody B."
    assert _content_hash(t1) != _content_hash(t2)


# ---------------------------------------------------------------------------
# harvest_rigs — discover_rig_roots
# ---------------------------------------------------------------------------


def test_discover_rig_roots_finds_agents_dir(tmp_path):
    _write_md(tmp_path, "test-art", 0.8, "Body.")
    roots = discover_rig_roots(tmp_path)
    assert len(roots) == 1
    assert roots[0] == tmp_path.resolve()


def test_discover_rig_roots_no_agents_dir(tmp_path):
    roots = discover_rig_roots(tmp_path)
    assert roots == []


def test_discover_rig_roots_extra_roots(tmp_path):
    _write_md(tmp_path, "main", 0.8, "Body.")
    extra = tmp_path / "extra-rig"
    _write_md(extra, "extra", 0.7, "Body.")
    roots = discover_rig_roots(tmp_path, [extra])
    assert len(roots) == 2


def test_discover_rig_roots_deduplicates(tmp_path):
    _write_md(tmp_path, "art", 0.8, "Body.")
    # Pass the same root twice via extra_roots.
    roots = discover_rig_roots(tmp_path, [tmp_path])
    assert len(roots) == 1


# ---------------------------------------------------------------------------
# harvest_rigs — scan_rig
# ---------------------------------------------------------------------------


def test_scan_rig_finds_learnings(tmp_path):
    _write_md(tmp_path, "alpha", 0.9, "Learning body.")
    artifacts = scan_rig(tmp_path)
    assert len(artifacts) == 1
    assert artifacts[0].name == "alpha"
    assert artifacts[0].confidence == pytest.approx(0.9)
    assert artifacts[0].artifact_type == "learnings"


def test_scan_rig_finds_patterns(tmp_path):
    _write_pattern(tmp_path, "pat-001", 0.7, "Pattern body.")
    artifacts = scan_rig(tmp_path)
    assert len(artifacts) == 1
    assert artifacts[0].artifact_type == "patterns"


def test_scan_rig_skips_dot_files(tmp_path):
    base = tmp_path / ".agents" / "learnings"
    base.mkdir(parents=True)
    (base / ".hidden.md").write_text("---\nname: hidden\n---\n\nHidden.", encoding="utf-8")
    (base / "visible.md").write_text("---\nname: visible\n---\n\nVisible.", encoding="utf-8")
    artifacts = scan_rig(tmp_path)
    assert all(a.name != "hidden" for a in artifacts)
    assert any(a.name == "visible" for a in artifacts)


def test_scan_rig_empty_agents_dir(tmp_path):
    (tmp_path / ".agents" / "learnings").mkdir(parents=True)
    artifacts = scan_rig(tmp_path)
    assert artifacts == []


# ---------------------------------------------------------------------------
# harvest_rigs — dedupe_artifacts
# ---------------------------------------------------------------------------


def test_dedupe_keeps_highest_confidence(tmp_path):
    _write_md(tmp_path, "art-a", 0.9, "Same body.")
    _write_md(tmp_path, "art-b", 0.5, "Same body.")
    arts = scan_rig(tmp_path)
    assert len(arts) == 2
    unique, dup_groups = dedupe_artifacts(arts)
    assert len(unique) == 1
    assert unique[0].confidence == pytest.approx(0.9)
    assert len(dup_groups) == 1


def test_dedupe_distinct_bodies_all_unique(tmp_path):
    _write_md(tmp_path, "art-x", 0.8, "Body X unique content.")
    _write_md(tmp_path, "art-y", 0.8, "Body Y unique content.")
    arts = scan_rig(tmp_path)
    unique, dup_groups = dedupe_artifacts(arts)
    assert len(unique) == 2
    assert dup_groups == []


# ---------------------------------------------------------------------------
# harvest_rigs — promote_artifacts
# ---------------------------------------------------------------------------


def test_promote_artifacts_dry_run_does_not_copy(tmp_path):
    src = tmp_path / "src"
    _write_md(src, "prom", 0.8, "Unique promote body.")
    arts = scan_rig(src)
    target = tmp_path / "target"
    target.mkdir()
    promoted, skipped = promote_artifacts(arts, target, dry_run=True, repo_root=tmp_path)
    assert len(promoted) == 1
    assert not (target / "prom.md").exists()


def test_promote_artifacts_actual_copy(tmp_path):
    src = tmp_path / "src"
    _write_md(src, "real-prom", 0.8, "Unique promote real body.")
    arts = scan_rig(src)
    target = tmp_path / "target"
    target.mkdir()
    promoted, skipped = promote_artifacts(arts, target, dry_run=False, repo_root=tmp_path)
    assert len(promoted) == 1
    assert (target / "real-prom.md").exists()


def test_promote_artifacts_skips_existing_hash(tmp_path):
    src = tmp_path / "src"
    _write_md(src, "dup-art", 0.8, "Same content duplicate.")
    arts = scan_rig(src)
    target = tmp_path / "target"
    target.mkdir()
    # Pre-place a file with the same content in the target.
    (target / "already-there.md").write_text(
        "---\nname: dup-art\nconfidence: 0.8\n---\n\nSame content duplicate.\n",
        encoding="utf-8",
    )
    promoted, skipped = promote_artifacts(arts, target, dry_run=False, repo_root=tmp_path)
    assert len(skipped) == 1
    assert "duplicate" in skipped[0]["reason"]


# ---------------------------------------------------------------------------
# harvest_rigs — run_harvest
# ---------------------------------------------------------------------------


def test_run_harvest_creates_catalog(tmp_path):
    _write_md(tmp_path, "good", 0.8, "Good learning.")
    report = run_harvest(tmp_path, min_confidence=0.5, dry_run=True)
    catalog_path = tmp_path / ".agents" / "harvest" / "latest.json"
    assert catalog_path.exists()
    import json

    data = json.loads(catalog_path.read_text())
    assert "rigs_scanned" in data
    assert data["dry_run"] is True


def test_run_harvest_filters_low_confidence(tmp_path):
    _write_md(tmp_path, "low-conf", 0.2, "Low confidence body.")
    report = run_harvest(tmp_path, min_confidence=0.5, dry_run=True)
    assert len(report.promoted) == 0


def test_run_harvest_promotes_qualifying(tmp_path):
    rig = tmp_path / "sub-rig"
    _write_md(rig, "qualify", 0.9, "High confidence unique learning body.")
    (tmp_path / ".agents" / "learnings").mkdir(parents=True, exist_ok=True)
    report = run_harvest(tmp_path, extra_roots=[rig], min_confidence=0.5, dry_run=False)
    assert len(report.promoted) == 1


def test_run_harvest_report_to_dict(tmp_path):
    _write_md(tmp_path, "art", 0.8, "Some body.")
    report = run_harvest(tmp_path, dry_run=True)
    d = report.to_dict()
    assert "generated_at" in d
    assert "artifacts_found" in d
    assert "unique_count" in d


# ---------------------------------------------------------------------------
# select_learnings — _parse_frontmatter
# ---------------------------------------------------------------------------


def test_sl_parse_frontmatter_basic():
    text = "---\ndate: 2026-01-01\nconfidence: high\ntags: [a, b]\n---\n\n# Title"
    meta = sl_parse_frontmatter(text)
    assert meta["date"] == "2026-01-01"
    assert meta["confidence"] == "high"
    assert meta["tags"] == ["a", "b"]


def test_sl_parse_frontmatter_no_start():
    meta = sl_parse_frontmatter("No frontmatter here.")
    assert meta == {}


def test_sl_parse_frontmatter_no_closing():
    meta = sl_parse_frontmatter("---\ndate: 2026-01-01\nno-close")
    assert meta == {}


# ---------------------------------------------------------------------------
# select_learnings — _title
# ---------------------------------------------------------------------------


def test_title_extracts_h1():
    text = "---\ndate: x\n---\n\n# My Title\n\nBody."
    assert _title(text, "fallback") == "My Title"


def test_title_uses_fallback_when_no_h1():
    text = "No heading here."
    assert _title(text, "stem") == "stem"


# ---------------------------------------------------------------------------
# select_learnings — load_learnings
# ---------------------------------------------------------------------------


def test_load_learnings_basic(tmp_path):
    _write_sl(tmp_path, "a.md", "2026-05-01", "high", "routing, cost", "Routing learning")
    items = load_learnings(tmp_path)
    assert len(items) == 1
    assert items[0]["confidence"] == "high"
    assert "routing" in items[0]["tags"]


def test_load_learnings_missing_dir(tmp_path):
    items = load_learnings(tmp_path / "nonexistent")
    assert items == []


def test_load_learnings_multiple_files(tmp_path):
    _write_sl(tmp_path, "a.md", "2026-05-01", "high", "loop", "Loop guard")
    _write_sl(tmp_path, "b.md", "2026-05-02", "low", "telemetry", "Telemetry note")
    items = load_learnings(tmp_path)
    assert len(items) == 2


def test_load_learnings_defaults_confidence_medium(tmp_path):
    (tmp_path / "no-conf.md").write_text(
        "---\ndate: 2026-01-01\n---\n\n# No Confidence\n\nBody.",
        encoding="utf-8",
    )
    items = load_learnings(tmp_path)
    assert items[0]["confidence"] == "medium"


# ---------------------------------------------------------------------------
# select_learnings — score
# ---------------------------------------------------------------------------


def test_score_high_confidence_beats_low():
    high = {"confidence": "high", "tags": [], "title": "T", "date": "2026-01-01"}
    low = {"confidence": "low", "tags": [], "title": "T", "date": "2026-01-01"}
    assert score(high, []) > score(low, [])


def test_score_term_overlap_adds_score():
    base = {"confidence": "low", "tags": ["loop"], "title": "Loop guard", "date": ""}
    no_match = {"confidence": "low", "tags": ["telemetry"], "title": "Telemetry", "date": ""}
    assert score(base, ["loop"]) > score(no_match, ["loop"])


def test_score_unknown_confidence_defaults_medium():
    item = {"confidence": "unknown", "tags": [], "title": "T", "date": ""}
    medium = {"confidence": "medium", "tags": [], "title": "T", "date": ""}
    assert score(item, []) == score(medium, [])


# ---------------------------------------------------------------------------
# select_learnings — select_top
# ---------------------------------------------------------------------------


def test_select_top_n_limit(tmp_path):
    for i in range(5):
        _write_sl(tmp_path, f"{i}.md", f"2026-0{i + 1}-01", "medium", "x", f"Title {i}")
    top = select_top(tmp_path, n=3)
    assert len(top) == 3


def test_select_top_term_relevance_wins(tmp_path):
    _write_sl(tmp_path, "a.md", "2026-05-01", "low", "telemetry", "Telemetry note")
    _write_sl(tmp_path, "b.md", "2026-05-01", "low", "routing, loop", "Loop guard note")
    top = select_top(tmp_path, n=1, terms=["loop"])
    assert top[0]["title"] == "Loop guard note"


def test_select_top_confidence_wins_no_terms(tmp_path):
    _write_sl(tmp_path, "a.md", "2026-05-01", "low", "x", "Low old")
    _write_sl(tmp_path, "b.md", "2026-05-09", "high", "y", "High new")
    top = select_top(tmp_path, n=1, terms=[])
    assert top[0]["title"] == "High new"


def test_select_top_empty_dir(tmp_path):
    results = select_top(tmp_path / "empty", n=3)
    assert results == []


# ---------------------------------------------------------------------------
# select_learnings — format_for_injection
# ---------------------------------------------------------------------------


def test_format_for_injection_empty():
    text = format_for_injection([])
    assert "no prior learnings" in text


def test_format_for_injection_includes_titles(tmp_path):
    items = [
        {
            "title": "Loop Guard Learning",
            "confidence": "high",
            "date": "2026-05-01",
            "tags": ["loop", "guard"],
        }
    ]
    text = format_for_injection(items)
    assert "Loop Guard Learning" in text
    assert "high" in text


def test_format_for_injection_limits_tags_to_four(tmp_path):
    items = [
        {
            "title": "Many Tags",
            "confidence": "medium",
            "date": "2026-05-01",
            "tags": ["a", "b", "c", "d", "e", "f"],
        }
    ]
    text = format_for_injection(items)
    # At most 4 tags shown (a, b, c, d) and e/f should not appear if truncated.
    tag_part = text.split("(")[-1].rstrip(")")
    shown_tags = [t.strip() for t in tag_part.split(",") if t.strip()]
    assert len(shown_tags) <= 4
