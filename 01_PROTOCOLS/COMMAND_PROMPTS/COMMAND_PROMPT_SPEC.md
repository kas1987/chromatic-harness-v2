# Command Prompt Protocol Spec

## Purpose

The Command Prompt Protocol defines how Chromatic Harness V2 switches between reusable operating postures while preserving CMP governance.

Modes are not personalities. They are execution contracts.

## Supported Modes

1. `operator`
2. `auditor`
3. `designer`

## Command Prompt Pack Contract

Each pack must define:

- mode id
- display name
- purpose
- default autonomy level
- confidence threshold
- allowed tools
- forbidden tools
- allowed paths
- forbidden paths
- required outputs
- default visible frontend panels
- asset pack
- stop conditions

## Mode Resolution Flow

```text
User intent
→ selected mode
→ command prompt pack
→ CMP Mission Packet defaults
→ Orchestrator dispatch
→ Magnets observe
→ Agent Lead synthesis
```

## Non-Negotiable Rule

Command modes may influence defaults, but **CMP remains the authority for execution permissions**.
