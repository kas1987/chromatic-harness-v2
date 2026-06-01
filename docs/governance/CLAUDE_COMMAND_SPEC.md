# Claude Command Specification

## Required Fields

Every Claude command must declare:

```yaml
name: /example
purpose: Human-readable purpose
authority_source: harness | queue | ci | verifier | human | read_only
script: path/to/script.py
mutation: none | conditional | yes
required_gates:
  - confidence
  - lease
  - verifier
  - tests
  - ci
logs_to: path/or/artifact
stop_conditions:
  - condition
```

## Command Contract

1. The command loads its registry entry.
2. The command checks authority source.
3. The command invokes the mapped harness script or reads mapped artifacts.
4. The command does not implement independent orchestration logic.
5. The command logs or references an artifact.
6. The command stops on missing gates.

## Minimum Allowed Commands

- `/go`
- `/audit`
- `/status`
- `/ship`
- `/recover`
- `/queue`
- `/explain`

## Versioning

Any command behavior change must update:

- command registry;
- policy docs;
- tests;
- issue or PDR reference.
