# Sandbox Lab Playbook

## Purpose

Safely test OpenHuman, Hermes, OpenHands, or any future agent framework before integrating it into the main harness.

## Promotion Ladder

| Level | Permission | Exit Criteria |
|---|---|---|
| L0 | No tools | Reasoning trace reviewed |
| L1 | Fake read-only tools | No scope drift |
| L2 | Simulated patch | Patch quality passes |
| L3 | Container execution | Tests pass in sandbox |
| L4 | Draft PR branch | Human-reviewable PR generated |
| L5 | Trusted narrow autonomy | Incident-free operating history |

## Hard Rules

- No real secrets in sandbox.
- No production endpoints.
- No direct main-branch writes.
- Every test emits Magnet events.
- Failed agents go to quarantine.
