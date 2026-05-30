#!/usr/bin/env python3
"""Compute need hierarchy and evidence tiers for harness learnings."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
LEARNINGS = REPO / ".agents" / "learnings"
USAGE_LOG = REPO / ".agents" / "metrics" / "learning_usage.jsonl"
POLICY_PATH = REPO / "config" / "learning_tier_policy.json"
OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "learning_tiers"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip()
    return meta, text[m.end() :]


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _parse_dt(raw: str | None) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def _confidence(meta: dict[str, str]) -> float:
    raw = str(meta.get("confidence", "0")).strip().lower()
    categorical = {"low": 0.3, "medium": 0.6, "high": 0.9}
    if raw in categorical:
        return categorical[raw]
    try:
        val = float(raw)
    except ValueError:
        return 0.0
    if val > 1.0:
        val = val / 100.0
    return max(0.0, min(1.0, val))


def _slug(raw: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", str(raw or "").lower()).strip("-")
    return base[:90] or "learning"


def _wilson_lower_bound(successes: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    p = successes / float(total)
    denom = 1.0 + (z * z) / total
    center = p + (z * z) / (2.0 * total)
    margin = z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * total)) / total)
    return max(0.0, (center - margin) / denom)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _load_usage_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not USAGE_LOG.is_file():
        return rows
    for line in USAGE_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _need_level(meta: dict[str, str], body: str, policy: dict[str, Any]) -> str:
    corpus = " ".join(
        [
            str(meta.get("category", "")),
            str(meta.get("type", "")),
            str(meta.get("tags", "")),
            body[:300].lower(),
        ]
    ).lower()
    mapping = policy.get("need_mapping") or {}
    for level in ("N1", "N2", "N3", "N4"):
        block = mapping.get(level) or {}
        terms = [str(x).lower() for x in (block.get("match_any") or [])]
        if any(term and term in corpus for term in terms):
            return level
    return "N4"


def _tier_for(metrics: dict[str, float], policy: dict[str, Any]) -> str:
    tiers = policy.get("tiers") or {}
    order = ["E4", "E3", "E2", "E1", "E0"]
    for tier in order:
        rule = tiers.get(tier) or {}
        if metrics["score"] < float(rule.get("min_score") or 0.0):
            continue
        if metrics["uses"] < float(rule.get("min_uses") or 0.0):
            continue
        if metrics["weeks"] < float(rule.get("min_weeks") or 0.0):
            continue
        if metrics["breadth"] < float(rule.get("min_breadth") or 0.0):
            continue
        if metrics["failure_rate"] > float(rule.get("max_failure_rate") or 1.0):
            continue
        return tier
    return "E0"


def _tier_rank(tier: str) -> int:
    order = {"E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4}
    return order.get(str(tier or "E0"), 0)


def _index_previous_report(previous: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    previous_items = previous.get("items") or previous.get("top_ranked") or []
    for item in previous_items:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        index[slug] = item
    return index


def compute_learning_tiers(
    now: datetime | None = None,
    previous_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now_utc = now or datetime.now(timezone.utc)
    policy = _load_json(POLICY_PATH, {})
    previous = previous_report if previous_report is not None else _load_json(OUT_DIR / "latest.json", {})
    prev_by_slug = _index_previous_report(previous)
    weights = policy.get("weights") or {}
    penalties = policy.get("penalties") or {}
    stale_after_days = int(penalties.get("stale_after_days") or 90)
    stale_penalty = float(penalties.get("stale_penalty") or 0.2)
    failure_weight = float(penalties.get("failure_weight") or 0.15)

    events = _load_usage_events()
    by_slug: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        name = str(event.get("learning_name") or event.get("learning_path") or "")
        slug = _slug(name)
        by_slug.setdefault(slug, []).append(event)

    items: list[dict[str, Any]] = []
    if LEARNINGS.is_dir():
        for path in sorted(LEARNINGS.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            meta, body = _parse_frontmatter(text)
            name = str(meta.get("name") or path.stem)
            slug = _slug(name)
            item_events = by_slug.get(slug, [])

            usage_events = [
                e
                for e in item_events
                if str(e.get("event_type", "")).strip().lower()
                in {"harvest_promoted", "wiki_promoted", "applied_success", "applied_failure"}
            ]
            uses = len(usage_events)
            successes = len(
                [
                    e
                    for e in usage_events
                    if str(e.get("event_type", "")).strip().lower()
                    in {"harvest_promoted", "wiki_promoted", "applied_success"}
                ]
            )
            failures = len(
                [
                    e
                    for e in usage_events
                    if str(e.get("event_type", "")).strip().lower() == "applied_failure"
                ]
            )
            rigs = {
                str(e.get("rig_id"))
                for e in usage_events
                if str(e.get("rig_id") or "").strip()
            }
            breadth = len(rigs) if rigs else 1

            event_times = [
                _parse_dt(str(e.get("timestamp_utc") or ""))
                for e in usage_events
            ]
            event_times = [t for t in event_times if t is not None]
            meta_dt = _parse_dt(meta.get("date"))
            file_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            first_seen = min([*event_times, meta_dt, file_dt] if meta_dt else [*event_times, file_dt])
            last_seen = max(event_times) if event_times else (meta_dt or file_dt)
            age_days = max(0.0, (now_utc - first_seen).total_seconds() / 86400.0)
            weeks = age_days / 7.0
            days_since_last = max(0.0, (now_utc - last_seen).total_seconds() / 86400.0)

            confidence = _confidence(meta)
            total_trials = max(uses, successes + failures)
            if total_trials == 0:
                total_trials = 1
            if successes == 0 and failures == 0:
                successes = 1 if confidence >= 0.75 else 0

            wlb = _wilson_lower_bound(successes, total_trials)
            usage_score = _clamp(math.log1p(uses) / math.log1p(120.0))
            breadth_score = _clamp((breadth - 1.0) / 3.0)
            stability_score = _clamp(weeks / 12.0)
            recency_score = _clamp(1.0 - (days_since_last / 90.0))
            evidence_fields = sum(
                1
                for key in ("confidence", "date", "tags", "category", "maturity", "type")
                if key in meta and str(meta[key]).strip()
            )
            evidence_score = _clamp(evidence_fields / 6.0)
            failure_rate = failures / float(max(1, successes + failures))

            score = (
                float(weights.get("wilson") or 0.35) * wlb
                + float(weights.get("usage") or 0.2) * usage_score
                + float(weights.get("breadth") or 0.15) * breadth_score
                + float(weights.get("stability") or 0.15) * stability_score
                + float(weights.get("recency") or 0.1) * recency_score
                + float(weights.get("evidence") or 0.05) * evidence_score
                - failure_weight * failure_rate
            )
            if days_since_last > stale_after_days:
                score -= stale_penalty
            score = _clamp(score)

            tier = _tier_for(
                {
                    "score": score,
                    "uses": float(uses),
                    "weeks": weeks,
                    "breadth": float(breadth),
                    "failure_rate": failure_rate,
                },
                policy,
            )
            need = _need_level(meta, body, policy)

            items.append(
                {
                    "name": name,
                    "slug": slug,
                    "path": str(path.relative_to(REPO)).replace("\\", "/"),
                    "need_level": need,
                    "evidence_tier": tier,
                    "score": round(score, 4),
                    "metrics": {
                        "confidence": round(confidence, 4),
                        "uses": uses,
                        "successes": successes,
                        "failures": failures,
                        "wilson": round(wlb, 4),
                        "breadth": breadth,
                        "weeks": round(weeks, 2),
                        "days_since_last_use": round(days_since_last, 2),
                        "failure_rate": round(failure_rate, 4),
                    },
                }
            )

    items.sort(key=lambda x: (-float(x.get("score") or 0.0), str(x.get("name") or "")))

    promoted_count = 0
    demoted_count = 0
    unchanged_count = 0
    new_count = 0
    movement_rows: list[dict[str, Any]] = []
    for item in items:
        slug = str(item.get("slug") or "")
        prev = prev_by_slug.get(slug) or {}
        prev_tier = str(prev.get("evidence_tier") or "")
        prev_score = float(prev.get("score") or 0.0)
        curr_tier = str(item.get("evidence_tier") or "E0")
        curr_score = float(item.get("score") or 0.0)
        score_delta = round(curr_score - prev_score, 4)
        tier_delta = _tier_rank(curr_tier) - _tier_rank(prev_tier)
        movement = "unchanged"
        if not prev_tier:
            movement = "new"
            new_count += 1
        elif tier_delta > 0:
            movement = "promoted"
            promoted_count += 1
        elif tier_delta < 0:
            movement = "demoted"
            demoted_count += 1
        else:
            unchanged_count += 1

        item["previous_tier"] = prev_tier or None
        item["previous_score"] = round(prev_score, 4) if prev_tier else None
        item["tier_delta"] = tier_delta if prev_tier else None
        item["score_delta"] = score_delta if prev_tier else None
        item["movement"] = movement
        movement_rows.append(
            {
                "name": item.get("name"),
                "slug": slug,
                "movement": movement,
                "previous_tier": prev_tier or None,
                "current_tier": curr_tier,
                "tier_delta": tier_delta if prev_tier else None,
                "score_delta": score_delta if prev_tier else None,
            }
        )

    movement_rows.sort(
        key=lambda row: (
            {"promoted": 0, "demoted": 1, "new": 2, "unchanged": 3}.get(str(row.get("movement")), 4),
            -abs(float(row.get("score_delta") or 0.0)),
            str(row.get("name") or ""),
        )
    )

    pyramid: dict[str, dict[str, int]] = {}
    for tier in ("E0", "E1", "E2", "E3", "E4"):
        pyramid[tier] = {"N1": 0, "N2": 0, "N3": 0, "N4": 0}
    for item in items:
        t = str(item.get("evidence_tier") or "E0")
        n = str(item.get("need_level") or "N4")
        pyramid.setdefault(t, {"N1": 0, "N2": 0, "N3": 0, "N4": 0})
        if n not in pyramid[t]:
            pyramid[t][n] = 0
        pyramid[t][n] += 1

    report = {
        "generated_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy_path": str(POLICY_PATH),
        "total_learnings": len(items),
        "usage_events_total": len(events),
        "pyramid": pyramid,
        "delta": {
            "promoted": promoted_count,
            "demoted": demoted_count,
            "new": new_count,
            "unchanged": unchanged_count,
            "changed_items": [
                row for row in movement_rows if row.get("movement") in {"promoted", "demoted"}
            ][:50],
        },
        "items": items,
        "top_ranked": items[:25],
    }
    return report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Learning Reliability Pyramid",
        "",
        f"- generated_at_utc: {report.get('generated_at_utc', '')}",
        f"- total_learnings: {int(report.get('total_learnings') or 0)}",
        f"- usage_events_total: {int(report.get('usage_events_total') or 0)}",
        "",
        "## Tier Delta",
        "",
        f"- promoted: {int((report.get('delta') or {}).get('promoted') or 0)}",
        f"- demoted: {int((report.get('delta') or {}).get('demoted') or 0)}",
        f"- new: {int((report.get('delta') or {}).get('new') or 0)}",
        f"- unchanged: {int((report.get('delta') or {}).get('unchanged') or 0)}",
        "",
        "## Pyramid Counts",
        "",
        "| Evidence Tier | N1 | N2 | N3 | N4 |",
        "|---|---:|---:|---:|---:|",
    ]
    pyramid = report.get("pyramid") or {}
    for tier in ("E4", "E3", "E2", "E1", "E0"):
        row = pyramid.get(tier) or {}
        lines.append(
            f"| {tier} | {int(row.get('N1') or 0)} | {int(row.get('N2') or 0)} | {int(row.get('N3') or 0)} | {int(row.get('N4') or 0)} |"
        )

    lines.extend(["", "## Top Ranked (Top 10)", ""])
    for item in (report.get("top_ranked") or [])[:10]:
        name = str(item.get("name") or "")
        tier = str(item.get("evidence_tier") or "E0")
        need = str(item.get("need_level") or "N4")
        score = float(item.get("score") or 0.0)
        metrics = item.get("metrics") or {}
        uses = int(metrics.get("uses") or 0)
        breadth = int(metrics.get("breadth") or 1)
        lines.append(f"- {name}: {tier} / {need} (score={score:.3f}, uses={uses}, breadth={breadth})")

    changed = (report.get("delta") or {}).get("changed_items") or []
    if changed:
        lines.extend(["", "## Changed Items", ""])
        for row in changed[:10]:
            lines.append(
                f"- {row.get('name')}: {row.get('previous_tier')} -> {row.get('current_tier')} (movement={row.get('movement')})"
            )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute learning reliability tiers")
    parser.add_argument("--write", action="store_true", help="Write latest.json and latest.md")
    args = parser.parse_args()

    report = compute_learning_tiers()
    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (OUT_DIR / "latest.md").write_text(_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
