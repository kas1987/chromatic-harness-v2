#!/usr/bin/env python3
"""
Validate skill route references in SKILL.md files.

Catches dead-end SKILL.md references pre-push. When skills are deleted but
SKILL.md files still reference them, this validator detects the broken
references and prevents silent failures.

Usage:
    python validate_skill_routes.py [--skills-dir <path>] [--quiet]

Patterns detected:
  - `pipeline-family:name`  (backtick-quoted)
  - `trust-family:name`
  - `toolchain-family:name`
  - `name` (kebab-case skill-like patterns)
  - Skill({skill: "name" (JS-style invocations)

Exit codes:
  0: All references valid
  1: Dead-end references found
"""

import argparse
import json
import re
import sys
from pathlib import Path


def get_skills_dir(custom_path=None):
    """Get the skills directory path."""
    if custom_path:
        return Path(custom_path).expanduser().resolve()
    return Path.home() / ".claude" / "skills"


def get_installed_skills(skills_dir):
    """
    Scan skills_dir for installed skill directories.

    Returns a set of skill names (directories containing SKILL.md, excluding _archived).
    Also checks symlinks and resolves them to their targets.
    Also checks .agents/skills directory for pipeline/trust/toolchain families.
    """
    skills = set()

    if not skills_dir.exists():
        return skills

    # Scan primary skills directory
    for item in skills_dir.iterdir():
        if item.name.startswith(".") or item.name == "_archived":
            continue

        # Resolve symlinks
        try:
            resolved = item.resolve()
        except (OSError, RuntimeError):
            # If resolve fails, just use the item as-is
            resolved = item

        if not resolved.is_dir():
            continue

        # Check if SKILL.md exists
        skill_md = resolved / "SKILL.md"
        if skill_md.exists():
            skills.add(item.name)

    # Also scan .agents/skills for pipeline-family, trust-family, toolchain-family skills
    agents_skills = Path.home() / ".agents" / "skills"
    if agents_skills.exists():
        for family_dir in agents_skills.iterdir():
            if family_dir.is_dir() and not family_dir.name.startswith("."):
                # Add skills from .agents as bare names
                # (since they're referenced as family:skill, we validate the skill part)
                skill_md = family_dir / "SKILL.md"
                if skill_md.exists():
                    skills.add(family_dir.name)

    return skills


def extract_skill_references(content):
    """
    Extract skill references from SKILL.md content.

    Returns list of (skill_ref, line_number) tuples.

    Patterns matched:
    - `family:skill` — explicit family:skill references
    - `skill-name` skill — bare skill references in context
    """
    references = []

    for line_num, line in enumerate(content.split("\n"), 1):
        # Pattern 1: `family:skill` (backtick-quoted family:skill refs)
        # Matches: `pipeline-family:implement`, `trust-family:post-mortem`, etc.
        for match in re.finditer(r"`([a-z\-]+\-family:[a-z\-]+)`", line):
            skill_ref = match.group(1)
            references.append((skill_ref, line_num))

        # Pattern 2: `skill-name` skill — bare skill in context (backtick followed by " skill")
        # Matches: `recover` skill, `brainstorming` skill, etc.
        for match in re.finditer(r"`([a-z][a-z0-9\-]*)`\s+skill", line):
            skill_ref = match.group(1)
            references.append((skill_ref, line_num))

        # Pattern 3: invoke `skill-name` — backtick skill in "invoke" context
        for match in re.finditer(
            r"invoke\s+`([a-z][a-z0-9\-]*(?::[a-z][a-z0-9\-]*)?)`", line
        ):
            skill_ref = match.group(1)
            references.append((skill_ref, line_num))

        # Pattern 4: Skill({skill: "name" (JS-style invocations in docs)
        for match in re.finditer(r'Skill\s*\(\s*.*?skill\s*:\s*"([^"]+)"', line):
            skill_ref = match.group(1)
            references.append((skill_ref, line_num))

    return references


def resolve_skill_reference(ref, installed_skills):
    """
    Resolve a skill reference to a skill name.

    For family:skill references, check if skill exists in .agents/skills.
    For bare skill references, check if they're in installed_skills.
    Returns (is_valid, skill_name) tuple.
    """
    # Handle family:skill pattern (e.g., pipeline-family:implement)
    if ":" in ref:
        family, skill_name = ref.split(":", 1)
        # For family references, check if the skill exists as a directory in .agents/skills
        agents_skills = Path.home() / ".agents" / "skills" / skill_name
        is_valid = agents_skills.is_dir()
    else:
        skill_name = ref
        # For bare references, check installed_skills
        is_valid = skill_name in installed_skills

    return (is_valid, skill_name)


def validate_skill_routes(skills_dir=None, quiet=False):
    """
    Validate all skill references in SKILL.md files.

    Returns (pass: bool, broken_refs: list of (file, line, ref) tuples)
    """
    skills_dir = get_skills_dir(skills_dir)

    if not skills_dir.exists():
        if not quiet:
            print(f"Error: skills directory not found: {skills_dir}")
        return False, []

    # Get installed skills
    installed_skills = get_installed_skills(skills_dir)

    broken_refs = []

    # Scan all SKILL.md files
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        if skill_dir.name.startswith(".") or skill_dir.name == "_archived":
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception as e:
            if not quiet:
                print(f"Error reading {skill_md}: {e}")
            continue

        # Extract references from this file
        references = extract_skill_references(content)

        # Check each reference
        for ref, line_num in references:
            is_valid, skill_name = resolve_skill_reference(ref, installed_skills)

            if not is_valid:
                broken_refs.append(
                    (str(skill_md.relative_to(skills_dir.parent)), line_num, ref)
                )

    return len(broken_refs) == 0, broken_refs


def main():
    parser = argparse.ArgumentParser(
        description="Validate skill route references in SKILL.md files"
    )
    parser.add_argument(
        "--skills-dir",
        help="Path to skills directory (default: ~/.claude/skills)",
        default=None,
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress output, exit with code only"
    )

    args = parser.parse_args()

    passed, broken_refs = validate_skill_routes(args.skills_dir, args.quiet)

    if not args.quiet:
        skills_dir = get_skills_dir(args.skills_dir)
        installed_skills = get_installed_skills(skills_dir)

        # Count total references checked
        total_lines = 0
        for skill_name in installed_skills:
            skill_md = skills_dir / skill_name / "SKILL.md"
            if skill_md.exists():
                total_lines += len(skill_md.read_text(encoding="utf-8").split("\n"))

        print(f"Skill validation report")
        print(f"  Skills directory: {skills_dir}")
        print(f"  Installed skills: {len(installed_skills)}")
        print(f"  Lines scanned: {total_lines}")

        if passed:
            print(f"\nResult: PASS - All skill references resolve")
        else:
            print(f"\nResult: FAIL - {len(broken_refs)} dead-end reference(s) found\n")
            for file_path, line_num, ref in sorted(broken_refs):
                print(f"  {file_path}:{line_num}: {ref}")
            print()

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
