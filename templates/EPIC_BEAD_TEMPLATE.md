# Epic + Bead Authoring Template

> Fill in the angle-bracket fields. Run the `bd` commands **one at a time, in order**
> (Dolt is single-writer — parallel `bd` writes fail). Protocol: `docs/playbooks/BEAD_EPIC_AUTHORING_PROTOCOL.md`.

## Pre-flight

- [ ] PDR exists at `08_PDRS/PDR_<NAME>.md`
- [ ] Plan produced via `/plan` at `.agents/plans/<date>-<slug>.md` (baseline audit + waves)
- [ ] Each planned task has a mechanically-verifiable acceptance check
- [ ] Confidence scores mapped to bd `P0–P4` (NOT raw 0–100)
- [ ] No stray `bd`/`dolt` processes running (`Get-Process bd,dolt`)

## 1. Create the epic (capture the id)

```bash
bd create "<Epic title> (<PDR-ID>)" --type epic --priority <P0-P4> \
  --labels planned,<area> \
  -d "<1-2 sentence scope. Cross-cutting: Always <...>; Never <...>.>" \
  --acceptance "<how the whole epic is proven done>"
# → note the returned id, e.g. chromatic-harness-v2-XXXX
```

## 2. Create each child — SERIALLY, one command at a time

Repeat per task. Map priority from confidence (90+→P0/P1, 75-89→P1/P2, 60-74→P2/P3).

```bash
bd create "<TASK-ID> <short imperative title>" \
  --parent <epic-id> --priority <P0-P4> --assignee <Owner> \
  --labels planned,<area> \
  --description "<what to do — reference plan for symbol-level detail>

\`\`\`validation
{\"files_exist\": [\"<path>\"], \"command\": \"<runnable check>\"}
\`\`\`
"
```

> ❗ One `bd create` finishes before the next starts. Do **not** background or parallelize.

## 3. Add dependencies to form waves — SERIALLY

`bd dep add <issue> <depends-on>` → `<issue>` becomes blocked by `<depends-on>`.

```bash
bd dep add <epic-id>.3 <epic-id>.1   # task 3 waits for task 1
bd dep add <epic-id>.4 <epic-id>.1
bd dep add <epic-id>.4 <epic-id>.2
```

## 4. Verify

```bash
bd ready                 # should list ONLY Wave-1 (unblocked) beads
bd show <epic-id>        # confirm children + priorities + parent linkage
```

## 5. Commit + hand off

```bash
git add .agents/plans/<plan>.md
git commit -m "docs(plan): <epic> decomposition (<PDR-ID>)"
# then: /pre-mortem  →  /crank   (or /implement <first-bead>)
```

## Do / Don't

| Do | Don't |
|----|-------|
| Run `bd` writes one at a time | Fan out `bd create` in parallel / background |
| Use `P0`–`P4` for priority | Pass confidence scores (`95`, `92`) |
| Give every child a `--parent` and ```validation``` block | Create orphan beads or skip validation |
| Add deps only for real file/output coupling | Add logical-ordering deps (kills parallelism) |
| Leave Dolt + governance locks ON | "Remove the locks to go faster" (corrupts the store) |
| Let `[agent]` beads stay ephemeral & auto-closed | Hand-author or parent `[agent]` beads |
