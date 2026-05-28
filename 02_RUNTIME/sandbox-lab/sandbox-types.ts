/**
 * Sandbox Lab Types
 *
 * Definitions for the L0-L5 agent promotion ladder.
 */

/**
 * Sandbox levels - trust progression for new agents
 *
 * L0: Dry run (reasoning only, no tools)
 * L1: Read-only (fake files, scope validation)
 * L2: Simulated (patch copy only, no merge)
 * L3: Sandboxed (container execution)
 * L4: Draft PR (real branch, no merge)
 * L5: Trusted (narrow autonomous work, real merge if approved)
 */
export type SandboxLevel = 0 | 1 | 2 | 3 | 4 | 5;

export const SANDBOX_LEVEL_NAMES: Record<SandboxLevel, string> = {
  0: 'Dry Run (Reasoning Only)',
  1: 'Read-Only (Fake Files)',
  2: 'Simulated (Patch Copy)',
  3: 'Sandboxed (Container Tests)',
  4: 'Draft PR (Real Branch)',
  5: 'Trusted (Autonomous)',
};

export const SANDBOX_LEVEL_DESCRIPTIONS: Record<SandboxLevel, string> = {
  0: 'Agent can reason and plan but cannot execute any tools. Observe reasoning quality.',
  1: 'Agent can read files and explore scope with fake filesystem. Validate scope discipline.',
  2: 'Agent can create patches but only as copies. No commit/merge. Validate patch quality.',
  3: 'Agent runs in isolated container. Can test changes but not merge. Validate reliability.',
  4: 'Agent creates real branches and PRs. Cannot merge. Human must approve. Final validation.',
  5: 'Agent is fully trusted. Can merge after passing gates. Use for proven agents.',
};

/**
 * Agent behavior at a sandbox level
 */
export interface AgentBehavior {
  agent_id: string;
  level: SandboxLevel;
  execution_time_ms: number;
  tool_calls: number;
  errors: number;
  scope_violations: number;
  test_pass_rate: number; // 0-1
  confidence_delta: number; // How much magnet confidence changed
  observations: Record<string, any>;
  passed: boolean;
}

/**
 * Promotion decision
 */
export interface PromotionDecision {
  agent_id: string;
  current_level: SandboxLevel;
  recommended_level: SandboxLevel | 'stay' | 'demote';
  confidence_score: number; // 0-1
  issues: string[];
  recommendations: string[];
  ready_to_promote: boolean;
  reason: string;
}

/**
 * Agent trust profile
 */
export interface AgentTrustProfile {
  agent_id: string;
  current_level: SandboxLevel;
  promotion_history: {
    level: SandboxLevel;
    date: number;
    reason: string;
  }[];
  total_executions: number;
  successful_executions: number;
  success_rate: number; // 0-1
  avg_confidence: number; // 0-1
  risk_score: number; // 0-1 (higher = more risky)
  approved_for_level: SandboxLevel; // Highest level approved
  last_violation?: {
    date: number;
    level: SandboxLevel;
    violation_type: string;
  };
}

/**
 * Sandbox Lab configuration
 */
export interface SandboxLabConfig {
  min_executions_per_level: number; // How many successful runs before promotion
  confidence_threshold_per_level: Record<SandboxLevel, number>; // Min confidence to promote
  error_threshold: number; // Max errors allowed before demotion
  scope_violation_threshold: number; // Max scope violations before demotion
  auto_promote: boolean; // Auto-promote if thresholds met
  audit_trail: boolean; // Log all promotions
}

/**
 * Default sandbox config
 */
export const DEFAULT_SANDBOX_CONFIG: SandboxLabConfig = {
  min_executions_per_level: 3,
  confidence_threshold_per_level: {
    0: 0.5,
    1: 0.6,
    2: 0.7,
    3: 0.75,
    4: 0.85,
    5: 0.9,
  },
  error_threshold: 2,
  scope_violation_threshold: 1,
  auto_promote: true,
  audit_trail: true,
};
