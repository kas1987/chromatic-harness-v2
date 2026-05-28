# GO Mode Playbook

## Purpose

Defines what happens when the user says GO or requests autonomous continuation.

## GO Rule

GO does not mean wander. GO means select the highest-priority unblocked Bead or mission, score confidence, attach Magnets, and execute only inside approved boundaries.

## GO Variants

| Command | Meaning |
|---|---|
| GO | Execute next unblocked task |
| GO AUDIT | Run audit/review path only |
| GO DEEP | Expand analysis, but do not mutate without confidence gate |
| GO BUILD | Execute scoped implementation task |
| GO SAFE | Dry run or sandbox only |

## Required Controls

- confidence score
- tool budget
- stop conditions
- run log
- Magnet events
- next Bead or report
