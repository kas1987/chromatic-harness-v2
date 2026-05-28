/**
 * Intent Gate
 *
 * Validates that the user's stated goal is clear, specific, and achievable.
 * Blocks ambiguous or vague intents that could lead to unexpected behavior.
 */

import { MissionPacket } from '../../01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE';

export interface IntentGateResult {
  passed: boolean;
  clarity_score: number; // 0-1
  issues: string[];
  suggestions: string[];
}

export class IntentGate {
  /**
   * Evaluate intent clarity
   */
  evaluate(packet: MissionPacket): IntentGateResult {
    const issues: string[] = [];
    const suggestions: string[] = [];
    let score = 1.0;

    const intent = packet.intent.toLowerCase();

    // Check 1: Length (too short = unclear, too long = unfocused)
    if (packet.intent.length < 15) {
      issues.push('Intent too short to be clear');
      suggestions.push('Add more detail about what needs to be done');
      score -= 0.3;
    }

    if (packet.intent.length > 500) {
      issues.push('Intent too long; focus is unclear');
      suggestions.push('Summarize the goal in 2-3 sentences');
      score -= 0.2;
    }

    // Check 2: Vague keywords
    const vagueKeywords = [
      'fix',
      'improve',
      'better',
      'faster',
      'something',
      'stuff',
      'things',
      'whatever',
      'try',
      'maybe',
    ];
    const foundVague = vagueKeywords.filter((kw) => intent.includes(kw));
    if (foundVague.length > 2) {
      issues.push(`Vague language detected: ${foundVague.join(', ')}`);
      suggestions.push('Use specific verbs (add, remove, refactor, fix) and measurable criteria');
      score -= 0.15 * foundVague.length;
    }

    // Check 3: Lack of success criteria
    const hasCriteria = /(?:when|if|should|must|will|expected)/.test(intent);
    if (!hasCriteria) {
      issues.push('No clear success criteria mentioned');
      suggestions.push('State how you will know when the task is complete');
      score -= 0.1;
    }

    // Check 4: Multiple conflicting goals
    const hasAnd = (intent.match(/\band\b/g) || []).length;
    const hasOr = (intent.match(/\bor\b/g) || []).length;
    if (hasAnd > 3 || hasOr > 2) {
      issues.push('Intent combines too many separate goals');
      suggestions.push('Break into smaller, focused missions');
      score -= 0.2;
    }

    // Check 5: Presence of negations (what NOT to do is weaker than what to do)
    const negations = (intent.match(/\b(?:don't|don't|no|not|avoid|never|prevent)\b/g) || []).length;
    if (negations >= 2) {
      issues.push('Overuse of negations (avoid, prevent, not) instead of positive goals');
      suggestions.push('Rephrase as positive outcomes: "Add X" instead of "Avoid Y"');
      score -= 0.1 * negations;
    }

    score = Math.max(0, Math.min(1, score));

    return {
      passed: score >= 0.7,
      clarity_score: Math.round(score * 100) / 100,
      issues,
      suggestions,
    };
  }

  /**
   * Generate human-readable feedback
   */
  formatResult(result: IntentGateResult): string {
    const lines: string[] = [];
    lines.push(`Intent Clarity: ${(result.clarity_score * 100).toFixed(0)}%`);

    if (result.issues.length > 0) {
      lines.push('\nIssues:');
      for (const issue of result.issues) {
        lines.push(`  • ${issue}`);
      }
    }

    if (result.suggestions.length > 0) {
      lines.push('\nSuggestions:');
      for (const suggestion of result.suggestions) {
        lines.push(`  → ${suggestion}`);
      }
    }

    const verdict = result.passed ? '✓ PASS' : '✗ FAIL';
    lines.push(`\nVerdict: ${verdict}`);

    return lines.join('\n');
  }
}
