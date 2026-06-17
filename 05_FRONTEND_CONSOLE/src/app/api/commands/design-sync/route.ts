import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

const REPO_ROOT = process.env.REPO_ROOT || path.join(process.cwd(), '..');
const PYTHON = process.env.PYTHON_BIN || 'python';

function readJson(p: string): Record<string, unknown> | null {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return null; }
}

function exec(cmd: string): { ok: boolean; stdout: string; stderr: string } {
  try {
    const stdout = execSync(cmd, { cwd: REPO_ROOT, encoding: 'utf8', timeout: 15000 });
    return { ok: true, stdout: stdout.trim(), stderr: '' };
  } catch (e: unknown) {
    const err = e as { stdout?: string; stderr?: string; message?: string };
    return { ok: false, stdout: (err.stdout || '').trim(), stderr: (err.stderr || err.message || '').trim() };
  }
}

export async function GET() {
  const health = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'harness_health', 'latest.json'));
  const ci     = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'ci', 'branch_governance_latest.json'));
  const security = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'security', 'latest.json'));
  const drift  = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'drift', 'latest.json'));

  // Hooks audit (--json mode)
  const hookResult = exec(`${PYTHON} scripts/audit_hooks.py --json`);
  let hooksData: Record<string, unknown> | null = null;
  try { hooksData = JSON.parse(hookResult.stdout); } catch { /* text fallback */ }
  const hookHighCount: number =
    typeof (hooksData as Record<string, unknown> | null)?.high_count === 'number'
      ? ((hooksData as Record<string, unknown>).high_count as number)
      : hookResult.stdout.toLowerCase().includes('high') ? 1 : 0;
  const hookCount: number =
    typeof (hooksData as Record<string, unknown> | null)?.total_count === 'number'
      ? ((hooksData as Record<string, unknown>).total_count as number)
      : 0;

  // Beads ready
  const beadsResult = exec('bd ready --json 2>/dev/null || bd ready');
  let beadsReady: unknown[] = [];
  try {
    beadsReady = JSON.parse(beadsResult.stdout);
  } catch {
    // parse plain-text bd ready output: lines like "○ id ● P1 title"
    beadsReady = beadsResult.stdout
      .split('\n')
      .filter((l) => l.trim().startsWith('○') || l.trim().startsWith('●'))
      .slice(0, 10)
      .map((l) => ({ raw: l.trim() }));
  }

  // Triage
  const checks = (health?.checks as Array<Record<string, unknown>> | null) ?? [];
  const fails = checks.filter((c) => c.status === 'fail').map((c) => c.name as string);
  const warns = checks.filter((c) => c.status === 'warn').map((c) => c.name as string);
  const readinessScore = typeof health?.readiness_score === 'number' ? health.readiness_score : 0;
  const overallStatus = (health?.overall_status as string) || 'unknown';

  const bw = (health?.budget_weekly as Record<string, unknown>) ?? {};
  const budgetCurrent = typeof bw.current_usd === 'number' ? bw.current_usd : 0;
  const budgetCap = typeof bw.cap_usd === 'number' ? bw.cap_usd : 100;
  const budgetGate = budgetCurrent > budgetCap ? 'RED' : budgetCurrent > budgetCap * 0.8 ? 'AMBER' : 'GREEN';

  const ciConclusion = (ci as Record<string, unknown> | null)?.conclusion as string | undefined;
  // branch_governance_latest.json uses `violations` not `conclusion`; treat any violation as CI failure
  const ciViolations = Array.isArray((ci as Record<string, unknown> | null)?.violations)
    ? ((ci as Record<string, unknown>).violations as unknown[]).length
    : 0;
  const ciOk = ciViolations === 0 && (!ciConclusion || ciConclusion === 'success');
  const securityFindings = typeof (security as Record<string, unknown> | null)?.high_severity_total === 'number'
    ? ((security as Record<string, unknown>).high_severity_total as number)
    : 0;

  const p0: string[] = [];
  if (hookHighCount >= 1) p0.push(`hook_high=${hookHighCount}`);
  if (!ciOk) p0.push(ciViolations > 0 ? `ci=violations(${ciViolations})` : `ci=${ciConclusion}`);
  if (overallStatus === 'red' && readinessScore < 20) p0.push(`health_red score=${readinessScore}`);
  if (budgetGate === 'RED') p0.push(`budget_over $${budgetCurrent.toFixed(2)}/$${budgetCap}`);
  if (securityFindings > 0) p0.push(`security_findings=${securityFindings}`);

  const p1: string[] = [...fails.slice(0, 5), ...warns.slice(0, 3)];

  // Route decision
  let routeAction = 'all_clear';
  let routeNext = 'Run /audit-visual-control-plane or /generate-visuals';
  if (p0.length > 0) {
    routeAction = `surface_blocker: ${p0[0]}`;
    routeNext = p0[0].startsWith('hook') ? 'python scripts/audit_hooks.py' :
                p0[0].startsWith('ci') ? 'Investigate CI failure' :
                p0[0].startsWith('budget') ? 'Halt non-essential work — budget over cap' :
                'Fix highest-impact blocker';
  } else if (beadsReady.length > 0) {
    routeAction = `surface_bead`;
    const first = beadsReady[0] as Record<string, unknown>;
    routeNext = `bd show ${first.id ?? ''} — then claim when ready`;
  } else if (p1.length > 0) {
    routeAction = `surface_warn: ${p1[0]}`;
    routeNext = `Fix: ${p1[0]}`;
  }

  return NextResponse.json({
    timestamp: new Date().toISOString(),
    health: { status: overallStatus, score: readinessScore, fails, warns },
    budget: { current: budgetCurrent, cap: budgetCap, gate: budgetGate },
    ci: { conclusion: ciConclusion ?? 'unknown', violations: ciViolations, ok: ciOk },
    hooks: { high_count: hookHighCount, total_count: hookCount },
    security: { findings: securityFindings },
    beads_ready: beadsReady,
    triage: { p0, p1, p2_count: beadsReady.length },
    route: { action: routeAction, next: routeNext },
    raw: { hooks: hooksData, drift },
  });
}
