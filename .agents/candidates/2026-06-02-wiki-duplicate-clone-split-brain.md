---
name: 2026-06-02-wiki-duplicate-clone-split-brain
source_ids: [2026-06-02-wiki-duplicate-clone-split-brain]
source_type: learning
confidence: 0.90
suggested_use: Two local wiki clones cause silent split-brain for path-based promotion tools
canon_map: operations
status: approved
tags: [wiki, operations, git, split-brain]
---

## Summary

`promote_to_wiki.py` writes to a filesystem PATH; two local clones of the same wiki repo means promotions can silently land in the wrong checkout. After any repo rename, retire the old local folder (`mv <name> <name>.RETIRED-<date>`). Guard: `scripts/check_wiki_clone_hygiene.py` fails if ≠1 clone exists or canonical path is wrong; skips `.RETIRED`-tagged dirs.
