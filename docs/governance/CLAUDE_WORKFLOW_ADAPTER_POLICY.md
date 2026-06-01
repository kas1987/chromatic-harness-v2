# Claude Workflow Adapter Policy

## Core Policy

Claude workflow and slash commands are **adapters only**.

They may invoke, summarize, or explain harness-controlled scripts and artifacts, but they may not become an independent source of orchestration, queue authority, confidence scoring, lease ownership, verifier approval, shipping, or release promotion.

## Authority Statement

```text
Claude commands are convenience wrappers.
Harness scripts are authority.
GitHub issues and bd queue are the source of work.
CI and verifier gates are the source of promotion.
```

## Allowed Uses

Claude commands may:

- run read-only health checks;
- summarize current queue state;
- invoke approved harness scripts;
- generate a human-readable explanation of artifacts;
- request lease inspection;
- ask for human approval when required;
- call `workflow_git.py plan` or `workflow_git.py ship` only through existing gates.

## Forbidden Uses

Claude commands must not:

- pick arbitrary work outside the queue;
- bypass GitHub issues or bd queue;
- invent confidence scores without harness scoring;
- ignore lease conflicts;
- skip verifier gates;
- skip tests or CI gates;
- directly merge code;
- dispatch hidden agents;
- mutate state below confidence thresholds;
- duplicate existing harness decision logic;
- convert warnings into approval;
- treat a conversational instruction as release authority.

## Approved Command Pattern

Each command must define:

- command name;
- purpose;
- authority source;
- called script/artifact;
- read/write behavior;
- required gates;
- logging output;
- stop conditions.

## Default Stop Conditions

A Claude command must stop when:

- required harness script is missing;
- command registry entry is missing;
- confidence is below required threshold;
- lease conflict exists;
- verifier approval is missing for mutation/promotion;
- tests are missing or failed;
- CI is red;
- human gate is required;
- command would need to invent logic.

## Emergency Override

Only the human may approve emergency override.

Overrides must be logged with:

- reason;
- affected command;
- affected files/state;
- risk tier;
- rollback plan;
- timestamp;
- human confirmation.

## Maintainer Rule

Any new Claude workflow command requires:

1. registry entry;
2. authority mapping;
3. stop conditions;
4. validator update if needed;
5. test coverage;
6. governance review.
