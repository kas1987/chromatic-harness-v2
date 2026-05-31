#!/usr/bin/env python3
"""Capture external knowledge sources (URLs, PDFs, repos) into raw_capture sink.

Usage:
  python scripts/capture_external.py --url https://example.com
  python scripts/capture_external.py --pdf /path/to/file.pdf
  python scripts/capture_external.py --repo https://github.com/org/repo
  python scripts/capture_external.py --url https://example.com --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError


REPO = Path(__file__).resolve().parents[1]
RAW_CAPTURE_DIR = REPO / ".agents" / "raw_capture"


def slugify(text: str) -> str:
    """Create a slug from text."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:50]


def get_timestamp() -> str:
    """ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def strip_html(html: str) -> str:
    """Strip HTML tags with simple regex (no parser needed for MVP)."""
    # Remove script and style tags
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def capture_url(url: str, dry_run: bool = False) -> str:
    """Fetch URL and capture as markdown."""
    try:
        response = urlopen(url, timeout=10)
        html = response.read().decode("utf-8", errors="ignore")
        text = strip_html(html)
        text = text[:8000]

        # Infer title from URL or content
        title = url.split("://")[-1].split("/")[0]

        # Create frontmatter
        timestamp = get_timestamp()
        slug = slugify(title)
        filename = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}.md"

        content = (
            f"---\n"
            f"source_type: url\n"
            f"source: {url}\n"
            f"captured_at: {timestamp}\n"
            f"status: raw\n"
            f"title: {title}\n"
            f"---\n\n"
            f"{text}\n"
        )

        output_path = RAW_CAPTURE_DIR / filename

        if not dry_run:
            output_path.write_text(content, encoding="utf-8")
            print(f"saved to .agents/raw_capture/{filename}")
        else:
            print(f"[DRY-RUN] would save to .agents/raw_capture/{filename}")

        return filename
    except URLError as e:
        print(f"error fetching {url}: {e}", file=sys.stderr)
        sys.exit(1)


def capture_pdf(path: str, dry_run: bool = False) -> str:
    """Stub capture of PDF file."""
    pdf_path = Path(path)
    if not pdf_path.exists():
        print(f"error: PDF not found: {path}", file=sys.stderr)
        sys.exit(1)

    # Infer title from filename
    title = pdf_path.stem
    timestamp = get_timestamp()
    slug = slugify(title)
    filename = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}.md"

    content = (
        f"---\n"
        f"source_type: pdf\n"
        f"source: {pdf_path.resolve()}\n"
        f"captured_at: {timestamp}\n"
        f"status: raw\n"
        f"title: {title}\n"
        f"---\n\n"
        f"PDF file stub: {pdf_path.resolve()}\n\n"
        f"Note: PDF parsing is out of scope for MVP. This is a metadata record only.\n"
    )

    output_path = RAW_CAPTURE_DIR / filename

    if not dry_run:
        output_path.write_text(content, encoding="utf-8")
        print(f"saved to .agents/raw_capture/{filename}")
    else:
        print(f"[DRY-RUN] would save to .agents/raw_capture/{filename}")

    return filename


def capture_repo(repo_url: str, dry_run: bool = False) -> str:
    """Stub capture of GitHub repo."""
    # Extract org/repo from URL
    match = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if not match:
        print(f"error: invalid GitHub URL: {repo_url}", file=sys.stderr)
        sys.exit(1)

    org, repo = match.groups()
    title = f"{org}/{repo}"
    timestamp = get_timestamp()
    slug = slugify(title)
    filename = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}.md"

    content = (
        f"---\n"
        f"source_type: repo\n"
        f"source: {repo_url}\n"
        f"captured_at: {timestamp}\n"
        f"status: raw\n"
        f"title: {title}\n"
        f"---\n\n"
        f"Repository stub: {org}/{repo}\n\n"
        f"Note: Cloning and indexing is out of scope for MVP. This is a metadata record only.\n"
    )

    output_path = RAW_CAPTURE_DIR / filename

    if not dry_run:
        output_path.write_text(content, encoding="utf-8")
        print(f"saved to .agents/raw_capture/{filename}")
    else:
        print(f"[DRY-RUN] would save to .agents/raw_capture/{filename}")

    return filename


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture external knowledge sources")
    parser.add_argument("--url", help="URL to capture")
    parser.add_argument("--pdf", help="Path to PDF file")
    parser.add_argument("--repo", help="GitHub repo URL")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be saved without writing",
    )

    args = parser.parse_args()

    if not (args.url or args.pdf or args.repo):
        parser.print_help()
        return 1

    RAW_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

    if args.url:
        capture_url(args.url, dry_run=args.dry_run)
    elif args.pdf:
        capture_pdf(args.pdf, dry_run=args.dry_run)
    elif args.repo:
        capture_repo(args.repo, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
