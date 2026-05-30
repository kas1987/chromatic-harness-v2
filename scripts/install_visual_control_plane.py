#!/usr/bin/env python3
"""Copy this scaffold into a target repository."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

EXCLUDE = {".git", "__pycache__", ".DS_Store"}


def copy_tree(source: Path, target: Path) -> None:
    for item in source.iterdir():
        if item.name in EXCLUDE:
            continue
        destination = target / item.name
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            copy_tree(item, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                backup = destination.with_suffix(destination.suffix + ".bak")
                shutil.copy2(destination, backup)
            shutil.copy2(item, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Chromatic visual control plane scaffold into a repo.")
    parser.add_argument("--target", required=True, help="Target repository path")
    args = parser.parse_args()

    source = Path(__file__).resolve().parents[1]
    target = Path(args.target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    copy_tree(source, target)
    print(f"Installed scaffold into {target}")


if __name__ == "__main__":
    main()
