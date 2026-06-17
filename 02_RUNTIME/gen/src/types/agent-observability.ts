/**
 * Master Specification: Agent Observability, Analysis, and Accumulation Layer
 * Canonical Objects & Event Typings
 */

export type RiskTier = 'low' | 'medium' | 'high' | 'critical';
export type TaskStatus = 'pending' | 'running' | 'blocked' | 'waiting' | 'completed' | 'failed' | 'cancelled';
export type TraceStatus = 'success' | 'failure' | 'error' | 'timeout';

/**
 * 6.1 Agent Contract
 */
export interface AgentContract {
  agent_id: string;
  name: string;
  role: string;
  owner: string;
  version: string;
  system_prompt_ref: string;
  input_schema: string;
  output_schema: string;
  allowed_tools: string[];
  handoff_targets: string[];
  guardrails: string[];
  success_metrics: string[];
  risk_tier: RiskTier;
  policy_pack_ref: string;
}

/**
 * 6.2 Task Object
 */
export interface TaskObject {
  task_id: string;
  parent_task_id: string | null;
  workflow_id: string;
  assigned_agent: string;
  priority: string;
  status: TaskStatus;
  created_by: string;
  created_at: string; // ISO 8601
  inputs: Record<string, any>;
  context_refs: string[];
  depends_on: string[];
  risk_tier: RiskTier;
  approval_required: boolean;
}

/**
 * 6.3 Trace Object
 */
export interface TraceStep {
  step_type: 'prompt_render' | 'retrieval' | 'tool_call' | 'handoff' | 'result_emit' | string;
  [key: string]: any;
}

export interface TraceObject {
  trace_id: string;
  workflow_id: string;
  task_id: string;
  agent_id: string;
  prompt_version: string;
  policy_version: string;
  tool_registry_version: string;
  start_time: string; // ISO 8601
  end_time: string; // ISO 8601
  steps: TraceStep[];
  cost: {
    model_tokens_in: number;
    model_tokens_out: number;
    usd: number;
  };
  outcome: {
    status: TraceStatus;
    confidence: number;
  };
}

/**
 * 6.4 Scorecard Object
 */
export interface ScorecardObject {
  scorecard_id: string;
  trace_id: string;
  workflow_id: string;
  task_id: string;
  agent_id: string;
  metrics: {
    accuracy: number;
    completeness: number;
    latency_ms: number;
    cost_usd: number;
    policy_violations: number;
    human_acceptance: 'pending' | 'accepted' | 'rejected' | string;
    downstream_success: 'success' | 'failure' | 'unknown' | string;
  };
}

/**
 * 6.5 Artifact Object
 */
export interface ArtifactObject {
  artifact_id: string;
  trace_id: string;
  task_id: string;
  artifact_type: string;
  storage_uri: string;
  content_hash: string;
  version: number;
  published: boolean;
}

/**
 * 6.6 Approval Object
 */
export interface ApprovalObject {
  approval_id: string;
  task_id: string;
  trace_id: string;
  required_by_policy: boolean;
  reviewer_type: 'human' | 'system' | string;
  reviewer_id: string;
  status: 'pending' | 'granted' | 'denied' | string;
  review_started_at?: string; // ISO 8601
  review_completed_at?: string; // ISO 8601
  notes?: string;
}

/**
 * 9.2 Event Envelope
 */
export interface EventEnvelopePayload {
  tool_name?: string;
  arguments_hash?: string;
  status?: string;
  [key: string]: any;
}

export interface EventEnvelope {
  event_id: string;
  event_type: string;
  timestamp: string; // ISO 8601
  workflow_id: string;
  task_id: string;
  trace_id: string;
  agent_id: string;
  version_refs: {
    prompt: string;
    policy: string;
    tools: string;
  };
  payload: EventEnvelopePayload;
}
