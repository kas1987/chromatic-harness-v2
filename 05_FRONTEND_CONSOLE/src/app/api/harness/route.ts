import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

const REPO_ROOT = process.env.REPO_ROOT || path.join(process.cwd(), '..');

function readJson(filePath: string): unknown | null {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

function readLastLines(filePath: string, n: number): string[] {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n').filter((l) => l.trim() !== '');
    return lines.slice(-n);
  } catch {
    return [];
  }
}

function getGitStatus() {
  const opts = { encoding: 'utf8' as const, cwd: REPO_ROOT };
  try {
    const branch = execSync(`git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD`, opts).trim();
    const logLine = execSync(`git -C "${REPO_ROOT}" log -1 --format="%H %s" HEAD`, opts).trim();
    const spaceIdx = logLine.indexOf(' ');
    const fullSha = spaceIdx !== -1 ? logLine.slice(0, spaceIdx) : logLine;
    const commitSha = fullSha.slice(0, 8);
    const commitMsg = spaceIdx !== -1 ? logLine.slice(spaceIdx + 1) : '';
    const statusOutput = execSync(`git -C "${REPO_ROOT}" status --porcelain`, opts).trim();
    const statusLines = statusOutput ? statusOutput.split('\n') : [];
    const modified = statusLines.filter((l) => !l.startsWith('??')).length;
    const untracked = statusLines.filter((l) => l.startsWith('??')).length;
    return { branch, commit: commitSha, commitMsg, modified, untracked };
  } catch {
    return null;
  }
}

export async function GET() {
  const health = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'harness_health', 'latest.json'));
  const tokens = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'token_governance', 'latest.json'));
  const drift = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'drift', 'latest.json'));
  const ci = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'ci', 'branch_governance_latest.json'));
  const beads_interactions = readLastLines(path.join(REPO_ROOT, '.beads', 'interactions.jsonl'), 50);
  const git = getGitStatus();
  const go_mode = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'go_mode', 'latest.json'));
  const security = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'security', 'latest.json'));
  const unified_guard = readJson(path.join(REPO_ROOT, '07_LOGS_AND_AUDIT', 'unified_guard', 'latest.json'));
  const bead_events: unknown[] = readLastLines(path.join(REPO_ROOT, '.beads', 'interactions.jsonl'), 50).map((line: string) => {
    try { return JSON.parse(line); } catch { return null; }
  }).filter((x: unknown): x is object => x !== null);

  return NextResponse.json({
    health,
    tokens,
    drift,
    ci,
    beads_interactions,
    git,
    go_mode,
    security,
    unified_guard,
    bead_events,
    timestamp: new Date().toISOString(),
  });
}
