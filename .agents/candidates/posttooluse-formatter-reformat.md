---
name: posttooluse-formatter-reformat
source_ids: [2026-05-21-postToolUse-formatter-reformat]
source_type: principle
confidence: 0.90
suggested_use: PostToolUse formatter rewrites Python files after Edit
canon_map: knowledge
status: approved
tags: []
---

## Summary

PostToolUse formatter rewrites Python files after Edit

## Evidence

# Learning: PostToolUse formatter rewrites Python files after Edit

## What We Learned

In this Claude Code environment, edits to `.py` files trigger a PostToolUse hook that runs a formatter (Black/ruff). The formatter may rewrite the code — e.g., a backslash-continuation ternary becomes a parenthesized multi-line form. Always Read the file back immediately after any Edit to `.py` files to capture the final post-hook state before referencing line numbers or quoting code.

## Why It Matters

If you quote the pre-format code in a commit message or subsequent edit, you'll introduce a mismatch between what you said and what actually landed. The Read-back loop costs one tool call and eliminates that class of drift.

## Source

Observed during test_mcp_node_smoke.py edit in this session. The session-reminder also flagged it explicitly.
