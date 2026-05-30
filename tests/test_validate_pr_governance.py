from __future__ import annotations

from scripts import validate_pr_governance as validator


def _stacked_body(
    *,
    base_branch: str = "pr/base",
    artifact_override: str = "none",
    size_override: str = "none",
) -> str:
    return f"""## Stack
- Stack position: 2 of 3
- Base branch: {base_branch}
- Merge after: #123
- Tracking: chromatic-harness-v2-1234

## Summary
- one focused behavior change

## Validation
- python -m pytest tests/test_session_closeout.py -q

## Files Intentionally Excluded
- .agents/
- 07_LOGS_AND_AUDIT/

## Risk
- Risk level: low

## Governance Overrides
- Artifact override: {artifact_override}
- Size override: {size_override}
"""


def test_validate_pr_skips_non_stacked_branches() -> None:
    errors = validator.validate_pr(
        title="Loose branch PR",
        body="## Summary\n- ok",
        head_ref="cursor/close-all-harness-gaps",
        base_ref="main",
        changed_files=[".agents/chronicle/events.jsonl"],
    )

    assert errors == []


def test_validate_pr_requires_stack_metadata_for_stacked_branches() -> None:
    errors = validator.validate_pr(
        title="Stacked PR",
        body="## Summary\n- missing required sections",
        head_ref="pr/closeout-policy-tests",
        base_ref="pr/closeout-telemetry-policy",
        changed_files=[],
    )

    assert "Missing required PR section: Stack" in errors
    assert "Missing required PR section: Validation" in errors


def test_validate_pr_rejects_base_branch_mismatch() -> None:
    errors = validator.validate_pr(
        title="Stacked PR",
        body=_stacked_body(base_branch="wrong/base"),
        head_ref="pr/closeout-policy-tests",
        base_ref="pr/closeout-telemetry-policy",
        changed_files=[],
    )

    assert (
        "Stack base branch 'wrong/base' does not match actual base ref "
        "'pr/closeout-telemetry-policy'"
    ) in errors


def test_validate_pr_blocks_generated_artifacts_without_override() -> None:
    errors = validator.validate_pr(
        title="Artifact drift",
        body=_stacked_body(),
        head_ref="pr/closeout-policy-tests",
        base_ref="pr/closeout-telemetry-policy",
        changed_files=["07_LOGS_AND_AUDIT/token_governance/latest.json"],
    )

    assert any("Generated/runtime artifact paths changed" in error for error in errors)


def test_validate_pr_allows_generated_artifacts_with_override() -> None:
    errors = validator.validate_pr(
        title="Artifact refresh",
        body=_stacked_body(
            base_branch="pr/closeout-telemetry-policy", artifact_override="approved"
        ),
        head_ref="pr/closeout-policy-tests",
        base_ref="pr/closeout-telemetry-policy",
        changed_files=["07_LOGS_AND_AUDIT/token_governance/latest.json"],
    )

    assert errors == []


def test_validate_pr_blocks_large_pr_without_size_override() -> None:
    errors = validator.validate_pr(
        title="Large PR",
        body=_stacked_body(base_branch="pr/closeout-telemetry-policy"),
        head_ref="pr/closeout-policy-tests",
        base_ref="pr/closeout-telemetry-policy",
        changed_files=["src/foo.py"],
        changed_files_count=30,
        insertions=1200,
        deletions=50,
        max_changed_files=25,
        max_insertions=800,
        max_deletions=400,
    )

    assert any("PR size thresholds exceeded" in error for error in errors)


def test_validate_pr_allows_large_pr_with_size_override() -> None:
    errors = validator.validate_pr(
        title="Large PR",
        body=_stacked_body(
            base_branch="pr/closeout-telemetry-policy", size_override="approved"
        ),
        head_ref="pr/closeout-policy-tests",
        base_ref="pr/closeout-telemetry-policy",
        changed_files=["src/foo.py"],
        changed_files_count=30,
        insertions=1200,
        deletions=50,
        max_changed_files=25,
        max_insertions=800,
        max_deletions=400,
    )

    assert errors == []