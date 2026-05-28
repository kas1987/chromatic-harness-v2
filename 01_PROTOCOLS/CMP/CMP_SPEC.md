# CMP Spec: Chromatic Management Protocol

## Purpose

CMP is the control plane for Chromatic Harness. It defines what may happen, who may act, which tools are allowed, what confidence is required, what must be logged, and when execution must stop.

## Core Objects

- Mission Packet
- Confidence Gate
- Tool Budget
- Human Gate
- Run Log
- Agent Permission Profile

## Required Mission Fields

- mission_id
- objective
- source_intent
- agent_role
- model
- autonomy_level
- allowed_tools
- forbidden_tools
- allowed_paths
- forbidden_paths
- confidence_required
- risk_level
- stop_conditions
- required_outputs
- evidence_required

## Core Rule

No agent may act outside its mission packet.
