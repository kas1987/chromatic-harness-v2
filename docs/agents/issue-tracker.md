# Issue tracker

Chromatich Harness v2 uses **beads (`bd`)** as its canonical issue tracker.

## Conventions

- **Primary store**: `bd` / Dolt embedded database (`.beads/`).
- **Mirror**: GitHub repository `kas1987/chromatic-harness-v2` for public visibility and CI triggers.
- Every task, feature, bug, or investigation is represented by a bead issue.
- `bd ready` shows unblocked work; `bd update <id> --claim` claims it.
- Beads are closed with `bd close <id>` and a reason.

## When a skill says "publish to the issue tracker"

Use `bd create` (or `bd create --parent=<id>` for child tasks). Do not hand-author markdown TODOs.

## When a skill says "fetch the relevant ticket"

Use `bd show <id>`. For references found in commit messages or specs, read the bead ID directly.

## Wayfinding operations

Used by `mattpocock-wayfinder`.

- **Map**: a parent bead with children created via `bd create --parent=<map-id>`.
- **Child ticket**: a bead under the map parent, numbered by `bd` (not by file).
- **Blocking**: `bd dep add <child> <depends-on>` declares blocking edges.
- **Frontier**: `bd ready` under the map parent returns unblocked, unclaimed children.
- **Claim**: `bd update <id> --claim` before work.
- **Resolve**: `bd close <id> --reason="..."` and update the parent bead notes with the decision.
