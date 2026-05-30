/**
 * CLI bridge for PromotionScorer — reads flat JSON from stdin, outputs PromotionDecision JSON.
 *
 * Input schema:
 *   { agent_id, current_level, successful_executions, success_rate,
 *     avg_confidence, last_execution_errors, scope_violations, risk_score? }
 *
 * Output: PromotionDecision JSON (see sandbox-types.ts)
 *
 * Used by Python tests via subprocess so they exercise real TS logic instead of a shadow copy.
 */
import { PromotionScorer } from './promotion-scorer';
import type { AgentTrustProfile, AgentBehavior, SandboxLevel } from './sandbox-types';

function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    process.stdin.on('data', (chunk: Buffer) => chunks.push(chunk));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString()));
    process.stdin.on('error', reject);
  });
}

(async () => {
  const raw = await readStdin();
  const input = JSON.parse(raw);

  const profile: AgentTrustProfile = {
    agent_id: input.agent_id,
    current_level: input.current_level as SandboxLevel,
    promotion_history: [],
    total_executions: input.successful_executions,
    successful_executions: input.successful_executions,
    success_rate: input.success_rate,
    avg_confidence: input.avg_confidence,
    risk_score: input.risk_score ?? 0.1,
    approved_for_level: input.current_level as SandboxLevel,
  };

  const lastBehavior: AgentBehavior = {
    agent_id: input.agent_id,
    level: input.current_level as SandboxLevel,
    execution_time_ms: 1000,
    tool_calls: 10,
    errors: input.last_execution_errors ?? 0,
    scope_violations: input.scope_violations ?? 0,
    test_pass_rate: input.success_rate,
    confidence_delta: 0,
    observations: {},
    passed: (input.last_execution_errors ?? 0) === 0 && (input.scope_violations ?? 0) === 0,
  };

  const scorer = new PromotionScorer();
  const decision = scorer.scorePromotion(
    input.agent_id,
    input.current_level as SandboxLevel,
    profile,
    lastBehavior,
  );

  process.stdout.write(JSON.stringify(decision) + '\n');
})();
