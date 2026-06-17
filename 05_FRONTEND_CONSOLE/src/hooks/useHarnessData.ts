'use client';

import { useState, useEffect } from 'react';

export interface HarnessHealth {
  overall_status: 'green' | 'yellow' | 'red';
  readiness_score: number;
  counts: { pass: number; warn: number; fail: number };
  checks: Array<{ name: string; status: string; message: string; value?: any }>;
  budget_weekly: {
    current_usd: number;
    cap_usd: number;
    remaining_usd: number;
    target_utilization_pct: number;
  };
  budget_channels: Record<
    string,
    {
      weekly_spent_usd: number;
      cap_weekly_usd: number;
      risk_level: string;
      weekly_utilization_forecast: number;
    }
  >;
}

export interface TokenGovernance {
  status: string;
  counts: { pass: number; warn: number; fail: number };
}

export interface DriftAudit {
  audit: {
    current_entries: number;
    expected_entries: number;
    missing_required: string[];
    added_unexpected: string[];
  };
}

export interface HarnessCI {
  generated_at: string;
  default_branch: string;
  counts: {
    local_total: number;
    remote_total: number;
    local_stale: number;
    remote_stale: number;
  };
  caps: { local_max_total: number; remote_max_total: number };
  violations: string[];
  local_stale: Array<{ name: string; age_days: number }>;
}

export interface HarnessGit {
  branch: string;
  commit: string;
  commitMsg: string;
  modified: number;
  untracked: number;
}

export interface BeadEvent {
  id: string;
  kind: string;
  created_at: string;
  actor: string;
  issue_id: string;
  extra?: {
    field?: string;
    new_value?: string;
    old_value?: string;
    reason?: string;
    [key: string]: unknown;
  };
}

export interface HarnessGoModeFactors {
  objective_clarity: number;
  scope_clarity: number;
  evidence_quality: number;
  reversibility: number;
  tool_fit: number;
  risk_awareness: number;
  testability: number;
}

export interface HarnessGoMode {
  confidence: {
    score: number;
    band: string;
    action: string;
    may_mutate: boolean;
    factors: HarnessGoModeFactors;
  };
  dispatch_allowed: boolean;
  selected?: { id: string; title: string; priority: string };
  decision: string;
}

export interface HarnessSecurity {
  passed: boolean;
  high_severity_total: number;
  secrets?: { status: string; total: number; high_severity: number };
  timestamp: string;
}

export interface HarnessUnifiedGuard {
  ok: boolean;
  codegraph_status?: string;
  timestamp?: string;
}

export interface HarnessBundle {
  health: HarnessHealth | null;
  tokens: TokenGovernance | null;
  drift: DriftAudit | null;
  ci: HarnessCI | null;
  beads_interactions: string[];
  git: HarnessGit | null;
  timestamp: string;
  go_mode: HarnessGoMode | null;
  security: HarnessSecurity | null;
  unified_guard: HarnessUnifiedGuard | null;
  bead_events: BeadEvent[];
}

export default function useHarnessData(intervalMs = 30000) {
  const [data, setData] = useState<HarnessBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/harness');
        const json: HarnessBundle = await res.json();
        setData(json);
        setError(null);
        setLoading(false);
      } catch (e: any) {
        setError(e.message);
        setLoading(false);
      }
    };

    fetchData();
    const id = setInterval(fetchData, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return { data, loading, error };
}
