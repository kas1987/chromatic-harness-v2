"""Task complexity classifier (C1–C4) based on description heuristics."""

from __future__ import annotations

import re
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

CLevel = Literal["C1", "C2", "C3", "C4"]


@dataclass(frozen=True)
class ComplexityResult:
    level: CLevel
    name: str
    confidence: float  # 0.0–1.0
    matched_keywords: list[str]
    reasoning_depth: str


class ComplexityClassifier:
    """Reads complexity-patterns.yaml and classifies task descriptions."""

    DEFAULT_CONFIG = (
        Path(__file__).resolve().parent.parent.parent
        / "09_DEPLOYMENT"
        / "config"
        / "routing"
        / "complexity-patterns.yaml"
    )

    def __init__(self, config_path: Path | None = None):
        self._config_path = config_path or self.DEFAULT_CONFIG
        self._levels: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._config_path.exists():
            self._build_defaults()
            return
        with open(self._config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        self._levels = {k: v for k, v in raw.get("levels", {}).items()}

    def _build_defaults(self) -> None:
        # Inline fallback if YAML missing
        self._levels = {
            "C1": {
                "keywords": [
                    "format",
                    "convert",
                    "extract",
                    "json-to-table",
                    "boilerplate",
                ]
            },
            "C2": {
                "keywords": [
                    "scaffold",
                    "code review",
                    "smoke test",
                    "lint",
                    "fix",
                    "debug",
                ]
            },
            "C3": {
                "keywords": [
                    "debug the",
                    "root cause",
                    "architecture",
                    "integration",
                    "multi-file",
                ]
            },
            "C4": {
                "keywords": [
                    "brainstorm",
                    "design tradeoffs",
                    "novel",
                    "creative",
                    "strategy",
                ]
            },
        }

    # ── Core classify ───────────────────────────────────────────────────────

    def classify(
        self, description: str, prompt: str = "", max_files_hint: int | None = None
    ) -> ComplexityResult:
        """Return C-level for a task."""
        haystack = f"{description}\n{prompt}".lower()

        scores: dict[str, int] = {}
        matched: dict[str, list[str]] = {}

        for level, cfg in self._levels.items():
            patterns = cfg.get("keywords", [])
            hits = []
            for pat in patterns:
                pat_lower = pat.lower()
                # simple substring match; consider word-boundary regex for v2
                if pat_lower in haystack:
                    hits.append(pat)
            scores[level] = len(hits)
            matched[level] = hits

        # Determine winner
        if not any(scores.values()):
            return ComplexityResult(
                level="C4",
                name="Creative / Novel (default)",
                confidence=0.0,
                matched_keywords=[],
                reasoning_depth="deep",
            )

        best_level = max(scores, key=lambda k: scores[k])
        best_score = scores[best_level]

        # Tie-breaker: if multiple levels have same score, prefer lower complexity
        # (fail-safe: don't over-promise)
        candidates = [lvl for lvl, sc in scores.items() if sc == best_score]
        # C1 > C2 > C3 > C4 for tie-breaking (lower first)
        for cand in ("C1", "C2", "C3", "C4"):
            if cand in candidates:
                best_level = cand
                break

        # Compute confidence = hits / total_patterns_for_level (clamped)
        total_patterns = len(self._levels.get(best_level, {}).get("keywords", []))
        confidence = min(best_score / max(total_patterns, 1), 1.0)

        # File-count bump: many files → bump up one level
        if max_files_hint and max_files_hint > 5 and best_level in ("C1", "C2"):
            bump_map = {"C1": "C2", "C2": "C3"}
            best_level = bump_map.get(best_level, best_level)

        cfg = self._levels.get(best_level, {})
        return ComplexityResult(
            level=best_level,  # type: ignore[arg-type]
            name=cfg.get("name", best_level),
            confidence=round(confidence, 2),
            matched_keywords=matched.get(best_level, []),
            reasoning_depth=cfg.get("reasoning_depth", "medium"),
        )

    # ── Batch utility for validation ────────────────────────────────────────

    def batch_classify(self, tasks: list[dict]) -> list[ComplexityResult]:
        """Classify many descriptions; useful for the 50-test validation suite."""
        out = []
        for t in tasks:
            out.append(
                self.classify(
                    description=t.get("description", ""),
                    prompt=t.get("prompt", ""),
                    max_files_hint=t.get("max_files"),
                )
            )
        return out
