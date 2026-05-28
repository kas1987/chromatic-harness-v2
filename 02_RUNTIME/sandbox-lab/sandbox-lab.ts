/**
 * Sandbox Lab
 *
 * Orchestrates the L0-L5 promotion ladder for agents.
 * Manages trust profiles, executions, promotions, and demotions.
 */

import {
  SandboxLevel,
  AgentBehavior,
  AgentTrustProfile,
  PromotionDecision,
  SandboxLabConfig,
  DEFAULT_SANDBOX_CONFIG,
  SANDBOX_LEVEL_NAMES,
} from './sandbox-types';
import { SandboxValidator } from './sandbox-validator';
import { PromotionScorer } from './promotion-scorer';

export class SandboxLab {
  private agents: Map<string, AgentTrustProfile> = new Map();
  private validator: SandboxValidator;
  private scorer: PromotionScorer;
  private config: SandboxLabConfig;

  constructor(config?: Partial<SandboxLabConfig>) {
    this.config = { ...DEFAULT_SANDBOX_CONFIG, ...config };
    this.validator = new SandboxValidator();
    this.scorer = new PromotionScorer(config);
  }

  /**
   * Register a new agent at L0
   */
  registerAgent(agent_id: string): AgentTrustProfile {
    const profile: AgentTrustProfile = {
      agent_id,
      current_level: 0,
      promotion_history: [
        {
          level: 0,
          date: Date.now(),
          reason: 'Initial registration at L0 (dry run)',
        },
      ],
      total_executions: 0,
      successful_executions: 0,
      success_rate: 1.0,
      avg_confidence: 0.5,
      risk_score: 0.5,
      approved_for_level: 0,
    };

    this.agents.set(agent_id, profile);
    return profile;
  }

  /**
   * Get agent trust profile
   */
  getProfile(agent_id: string): AgentTrustProfile | undefined {
    return this.agents.get(agent_id);
  }

  /**
   * Record agent execution
   */
  recordExecution(agent_id: string, behavior: AgentBehavior): {
    validation_passed: boolean;
    promotion_available: boolean;
    decision?: PromotionDecision;
  } {
    const profile = this.agents.get(agent_id);
    if (!profile) {
      throw new Error(`Agent ${agent_id} not registered`);
    }

    // Update profile
    profile.total_executions++;

    const validation = this.validator.validate(behavior);

    if (validation.passed) {
      profile.successful_executions++;
    }

    // Update metrics
    profile.success_rate =
      profile.successful_executions / Math.max(1, profile.total_executions);
    profile.avg_confidence =
      (profile.avg_confidence * (profile.total_executions - 1) + validation.confidence_score) /
      profile.total_executions;

    // Update risk score (inverse of confidence)
    profile.risk_score = 1 - validation.confidence_score;

    // Check for violations
    const violations = this.validator.detectViolations(behavior);
    if (violations.should_demote) {
      this.demoteAgent(agent_id, violations.violations[0]);
      return {
        validation_passed: false,
        promotion_available: false,
      };
    }

    // Check promotion eligibility
    let decision: PromotionDecision | undefined;
    let promotionAvailable = false;

    if (validation.passed && profile.current_level < 5) {
      decision = this.scorer.scorePromotion(
        agent_id,
        profile.current_level,
        profile,
        behavior
      );

      if (decision.ready_to_promote && this.config.auto_promote) {
        this.promoteAgent(
          agent_id,
          decision.recommended_level as SandboxLevel,
          'Automatic promotion after execution'
        );
        promotionAvailable = false; // Already promoted
      } else if (decision.ready_to_promote) {
        promotionAvailable = true; // Available but requires manual approval
      }
    }

    return {
      validation_passed: validation.passed,
      promotion_available: promotionAvailable,
      decision,
    };
  }

  /**
   * Manually promote agent
   */
  promoteAgent(
    agent_id: string,
    target_level: SandboxLevel,
    reason: string
  ): void {
    const profile = this.agents.get(agent_id);
    if (!profile) {
      throw new Error(`Agent ${agent_id} not registered`);
    }

    if (target_level <= profile.current_level) {
      throw new Error(
        `Cannot promote to L${target_level} when currently at L${profile.current_level}`
      );
    }

    if (target_level > 5) {
      throw new Error('Maximum level is L5');
    }

    profile.current_level = target_level;
    profile.approved_for_level = Math.max(target_level, profile.approved_for_level);
    profile.promotion_history.push({
      level: target_level,
      date: Date.now(),
      reason,
    });
  }

  /**
   * Demote agent (automatic due to violations)
   */
  private demoteAgent(agent_id: string, reason: string): void {
    const profile = this.agents.get(agent_id);
    if (!profile) return;

    const newLevel = Math.max(0, profile.current_level - 1) as SandboxLevel;

    if (newLevel === profile.current_level) {
      return; // Already at L0
    }

    profile.current_level = newLevel;
    profile.last_violation = {
      date: Date.now(),
      level: newLevel,
      violation_type: reason,
    };

    profile.promotion_history.push({
      level: newLevel,
      date: Date.now(),
      reason: `Demotion due to: ${reason}`,
    });
  }

  /**
   * Reset agent to L0 (for testing or fresh start)
   */
  resetAgent(agent_id: string): void {
    const profile = this.agents.get(agent_id);
    if (!profile) {
      this.registerAgent(agent_id);
      return;
    }

    profile.current_level = 0;
    profile.total_executions = 0;
    profile.successful_executions = 0;
    profile.success_rate = 1.0;
    profile.avg_confidence = 0.5;
    profile.risk_score = 0.5;
    profile.last_violation = undefined;
    profile.promotion_history = [
      {
        level: 0,
        date: Date.now(),
        reason: 'Reset to L0',
      },
    ];
  }

  /**
   * Get all agents
   */
  listAgents(): AgentTrustProfile[] {
    return Array.from(this.agents.values());
  }

  /**
   * Get agents at a specific level
   */
  getAgentsAtLevel(level: SandboxLevel): AgentTrustProfile[] {
    return Array.from(this.agents.values()).filter((p) => p.current_level === level);
  }

  /**
   * Format agent summary for display
   */
  formatAgentSummary(profile: AgentTrustProfile): string {
    const lines: string[] = [];

    lines.push('═════════════════════════════════════════');
    lines.push(`AGENT: ${profile.agent_id}`);
    lines.push('═════════════════════════════════════════');
    lines.push('');
    lines.push(`Current Level: L${profile.current_level} (${SANDBOX_LEVEL_NAMES[profile.current_level]})`);
    lines.push(`Approved For: L${profile.approved_for_level}`);
    lines.push('');
    lines.push(`Executions: ${profile.total_executions} total, ${profile.successful_executions} successful`);
    lines.push(`Success Rate: ${(profile.success_rate * 100).toFixed(0)}%`);
    lines.push(`Avg Confidence: ${(profile.avg_confidence * 100).toFixed(0)}%`);
    lines.push(`Risk Score: ${(profile.risk_score * 100).toFixed(0)}%`);
    lines.push('');

    lines.push('Promotion History:');
    for (const entry of profile.promotion_history) {
      const date = new Date(entry.date).toLocaleDateString();
      lines.push(`  L${entry.level} (${date}): ${entry.reason}`);
    }

    if (profile.last_violation) {
      lines.push('');
      lines.push('Last Violation:');
      const date = new Date(profile.last_violation.date).toLocaleDateString();
      lines.push(
        `  ${profile.last_violation.violation_type} (${date}, L${profile.last_violation.level})`
      );
    }

    lines.push('');
    lines.push('═════════════════════════════════════════');

    return lines.join('\n');
  }

  /**
   * Get lab statistics
   */
  getStats(): {
    total_agents: number;
    agents_by_level: Record<SandboxLevel, number>;
    avg_success_rate: number;
    avg_confidence: number;
    critical_risk_agents: string[];
  } {
    const profiles = Array.from(this.agents.values());
    const agents_by_level: Record<SandboxLevel, number> = {
      0: 0,
      1: 0,
      2: 0,
      3: 0,
      4: 0,
      5: 0,
    };

    for (const profile of profiles) {
      agents_by_level[profile.current_level]++;
    }

    const avg_success_rate =
      profiles.length > 0
        ? profiles.reduce((sum, p) => sum + p.success_rate, 0) / profiles.length
        : 0;

    const avg_confidence =
      profiles.length > 0
        ? profiles.reduce((sum, p) => sum + p.avg_confidence, 0) / profiles.length
        : 0;

    const critical_risk_agents = profiles
      .filter((p) => p.risk_score > 0.7)
      .map((p) => p.agent_id);

    return {
      total_agents: profiles.length,
      agents_by_level,
      avg_success_rate,
      avg_confidence,
      critical_risk_agents,
    };
  }
}
