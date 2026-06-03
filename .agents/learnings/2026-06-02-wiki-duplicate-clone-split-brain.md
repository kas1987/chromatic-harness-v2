---
id: learning-2026-06-02-wiki-duplicate-clone-split-brain
type: learning
date: 2026-06-02
category: operations
confidence: high
maturity: confirmed
---

# Learning: Two Local Wiki Clones = Split-Brain for Path-Based Promotion

## What We Learned

`promote_to_wiki.py` writes to a filesystem PATH, not a remote URL. If two local clones of the same wiki repo exist on disk, promotions can silently land in the wrong checkout — the stale one. This was discovered when the original `Chromatic_Wiki/` folder (from before a repo rename) was still present beside the canonical `chromatic-wiki/` clone.

The config file (`config/wiki_harness_sync.yaml`) names a canonical path; any second clone at a different path is invisible to the config but reachable by accident (e.g. old env vars, manual cd, or autocomplete).

## Why It Matters

Split-brain wiki state means: promotions appear to succeed (no error), but the committed content goes to a clone that may be on a stale branch, behind `main`, or about to be deleted. The wiki library diverges from what was promoted.

## How to Apply

After any wiki repo rename:
1. Immediately rename the old local folder: `mv Chromatic_Wiki Chromatic_Wiki.RETIRED-<date>`
2. Verify the canonical clone path matches `config/wiki_harness_sync.yaml`
3. Delete the `.RETIRED` folder once you've confirmed 0 uncommitted / 0 unpushed content

Guard: `scripts/check_wiki_clone_hygiene.py` fails if ≠1 clone exists, fails if canonical path is wrong, and warns if the clone is parked off its default branch. Files with `.retired` in the name are skipped (sanctioned-retirement convention). Wired into pre-push via `run-all-e2e.py` OMH-6 wiki suite.
