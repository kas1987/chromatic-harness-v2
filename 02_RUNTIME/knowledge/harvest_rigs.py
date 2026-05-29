"""Session-end cross-rig knowledge harvest and promotion."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ARTIFACT_DIRS = ("learnings", "patterns", "research")
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL | re.MULTILINE)


@dataclass
class Artifact:
    path: Path
    rig_id: str
    artifact_type: str
    name: str
    confidence: float
    content_hash: str
    body_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "rig_id": self.rig_id,
            "artifact_type": self.artifact_type,
            "name": self.name,
            "confidence": self.confidence,
            "content_hash": self.content_hash,
        }


@dataclass
class HarvestReport:
    generated_at: str
    rigs_scanned: list[str]
    artifacts_found: int = 0
    unique_count: int = 0
    duplicate_count: int = 0
    promoted: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    dry_run: bool = True
    min_confidence: float = 0.5
    global_hub: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _repo_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "00_SOURCE_OF_TRUTH").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip().lower()] = val.strip().strip('"').strip("'")
    return meta


def _normalize_confidence(raw: str | float | int | None, default: float = 0.5) -> float:
    if raw is None:
        return default
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return default
    if val > 1.0:
        val = val / 100.0
    return max(0.0, min(1.0, val))


def _normalize_body(text: str) -> str:
    body = _FRONTMATTER.sub("", text, count=1).strip()
    return re.sub(r"\s+", " ", body).lower()


def _content_hash(text: str) -> str:
    return hashlib.sha256(_normalize_body(text).encode("utf-8")).hexdigest()


def discover_rig_roots(
    repo_root: Path,
    extra_roots: list[Path] | None = None,
) -> list[Path]:
    """Rig roots that contain an `.agents` knowledge tree."""
    seen: set[str] = set()
    roots: list[Path] = []

    def add(root: Path) -> None:
        key = str(root.resolve())
        if key in seen:
            return
        agents = root / ".agents"
        if agents.is_dir() and any((agents / d).is_dir() for d in ARTIFACT_DIRS):
            seen.add(key)
            roots.append(root.resolve())

    add(repo_root)
    for extra in extra_roots or []:
        p = Path(extra).expanduser()
        if p.is_dir():
            add(p)
    return roots


def _rig_id(root: Path) -> str:
    return root.name or "rig"


def scan_rig(root: Path) -> list[Artifact]:
    artifacts: list[Artifact] = []
    rig = _rig_id(root)
    agents = root / ".agents"
    for artifact_type in ARTIFACT_DIRS:
        base = agents / artifact_type
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if path.name.startswith("."):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            meta = _parse_frontmatter(text)
            confidence = _normalize_confidence(meta.get("confidence"))
            name = meta.get("name") or path.stem
            artifacts.append(
                Artifact(
                    path=path,
                    rig_id=rig,
                    artifact_type=artifact_type,
                    name=name,
                    confidence=confidence,
                    content_hash=_content_hash(text),
                    body_preview=_normalize_body(text)[:120],
                )
            )
    return artifacts


def dedupe_artifacts(artifacts: list[Artifact]) -> tuple[list[Artifact], list[list[Artifact]]]:
    """Keep highest-confidence artifact per content hash."""
    by_hash: dict[str, list[Artifact]] = {}
    for art in artifacts:
        by_hash.setdefault(art.content_hash, []).append(art)

    unique: list[Artifact] = []
    duplicate_groups: list[list[Artifact]] = []
    for group in by_hash.values():
        group.sort(key=lambda a: (-a.confidence, a.path.as_posix()))
        unique.append(group[0])
        if len(group) > 1:
            duplicate_groups.append(group)
    return unique, duplicate_groups


def _promotion_target(repo_root: Path, *, global_hub: bool) -> Path:
    if global_hub:
        return Path.home() / ".agents" / "learnings"
    return repo_root / ".agents" / "learnings"


def _catalog_path(repo_root: Path) -> Path:
    return repo_root / ".agents" / "harvest" / "latest.json"


def promote_artifacts(
    candidates: list[Artifact],
    target_dir: Path,
    *,
    dry_run: bool,
    repo_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    target_dir.mkdir(parents=True, exist_ok=True)
    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    existing_hashes: dict[str, Path] = {}
    for path in target_dir.glob("*.md"):
        try:
            existing_hashes[_content_hash(path.read_text(encoding="utf-8"))] = path
        except OSError:
            continue

    for art in candidates:
        dest = target_dir / art.path.name
        if art.content_hash in existing_hashes:
            skipped.append(
                {
                    "path": str(art.path),
                    "reason": f"duplicate of {existing_hashes[art.content_hash].name}",
                }
            )
            continue
        try:
            rel_from = str(art.path.relative_to(repo_root))
        except ValueError:
            rel_from = str(art.path)
        record = {
            "from": rel_from,
            "to": str(dest),
            "rig_id": art.rig_id,
            "confidence": art.confidence,
            "content_hash": art.content_hash,
        }
        if not dry_run:
            shutil.copy2(art.path, dest)
            existing_hashes[art.content_hash] = dest
        promoted.append(record)
    return promoted, skipped


def run_harvest(
    repo_root: Path | None = None,
    *,
    extra_roots: list[Path] | None = None,
    min_confidence: float = 0.5,
    dry_run: bool = True,
    global_hub: bool = False,
    include_types: tuple[str, ...] = ARTIFACT_DIRS,
) -> HarvestReport:
    root = _repo_root(repo_root)
    rigs = discover_rig_roots(root, extra_roots)
    all_artifacts: list[Artifact] = []
    for rig_root in rigs:
        for art in scan_rig(rig_root):
            if art.artifact_type in include_types:
                all_artifacts.append(art)

    unique, dup_groups = dedupe_artifacts(all_artifacts)
    target = _promotion_target(root, global_hub=global_hub)
    target_resolved = target.resolve()
    candidates = [
        a
        for a in unique
        if a.confidence >= min_confidence and target_resolved not in a.path.resolve().parents
    ]
    promoted, skipped = promote_artifacts(candidates, target, dry_run=dry_run, repo_root=root)

    report = HarvestReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        rigs_scanned=[_rig_id(r) for r in rigs],
        artifacts_found=len(all_artifacts),
        unique_count=len(unique),
        duplicate_count=sum(len(g) - 1 for g in dup_groups),
        promoted=promoted,
        skipped=skipped,
        dry_run=dry_run,
        min_confidence=min_confidence,
        global_hub=global_hub,
    )

    catalog_dir = _catalog_path(root).parent
    catalog_dir.mkdir(parents=True, exist_ok=True)
    _catalog_path(root).write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return report


def run_session_harvest(
    repo_root: Path | None = None,
    *,
    dry_run: bool = False,
    min_confidence: float = 0.6,
) -> HarvestReport:
    """Lite session-end promotion: current repo only, no global hub by default."""
    return run_harvest(
        repo_root,
        min_confidence=min_confidence,
        dry_run=dry_run,
        global_hub=False,
    )
