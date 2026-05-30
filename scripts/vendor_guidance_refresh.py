#!/usr/bin/env python3
"""Generate a dated vendor-guidance refresh worksheet for governance updates.

This script operationalizes external best-practice review cadence without requiring
network access at runtime. It reads the official watchlist doc and emits a
review worksheet under 07_LOGS_AND_AUDIT/governance_intelligence/vendor_refresh.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WATCHLIST = REPO / "docs" / "governance" / "OFFICIAL_LLM_RESOURCE_WATCHLIST.md"
OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "vendor_refresh"


def _extract_sections(text: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_urls: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("### "):
            if current_name:
                sections.append((current_name, current_urls))
            current_name = line.replace("### ", "", 1).strip()
            current_urls = []
            continue

        if not current_name:
            continue

        match = re.match(r"^-\s+[^:]+:\s+(https?://\S+)$", line)
        if match:
            current_urls.append(match.group(1))

    if current_name:
        sections.append((current_name, current_urls))
    return sections


def _render(sections: list[tuple[str, list[str]]]) -> str:
    now = datetime.now(timezone.utc)
    lines: list[str] = []
    lines.append("# Vendor Guidance Refresh Worksheet")
    lines.append("")
    lines.append(f"Generated (UTC): {now.isoformat()}")
    lines.append("")
    lines.append("Use this worksheet to record deltas from official sources and drive routing/policy updates.")
    lines.append("")
    lines.append("## Review Checklist")
    lines.append("")

    for name, urls in sections:
        lines.append(f"### {name}")
        lines.append("")
        if urls:
            for url in urls:
                lines.append(f"- Source: {url}")
        else:
            lines.append("- Source: (none parsed from watchlist)")
        lines.append("- Date reviewed (UTC):")
        lines.append("- What changed:")
        lines.append("- Routing impact (none/low/medium/high):")
        lines.append("- Governance impact (none/low/medium/high):")
        lines.append("- Action required (yes/no):")
        lines.append("- Bead ID (if action required):")
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("- High-impact changes detected:")
    lines.append("- Policies updated:")
    lines.append("- Routing matrix updates:")
    lines.append("- Follow-up beads created:")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate vendor guidance refresh worksheet")
    parser.add_argument("--write-latest", action="store_true", help="Also update latest.md pointer")
    args = parser.parse_args()

    if not WATCHLIST.is_file():
        raise SystemExit(f"missing watchlist: {WATCHLIST}")

    text = WATCHLIST.read_text(encoding="utf-8")
    sections = _extract_sections(text)
    rendered = _render(sections)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"vendor_refresh_{stamp}.md"
    out_path.write_text(rendered, encoding="utf-8")

    if args.write_latest:
        (OUT_DIR / "latest.md").write_text(rendered, encoding="utf-8")

    print(str(out_path.relative_to(REPO)).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
