import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

const REPO_ROOT = process.env.REPO_ROOT || path.join(process.cwd(), '..');
const PYTHON = process.env.PYTHON_BIN || 'python';

function checkFile(rel: string): { exists: boolean; size: number } {
  try {
    const stat = fs.statSync(path.join(REPO_ROOT, rel));
    return { exists: true, size: stat.size };
  } catch {
    return { exists: false, size: 0 };
  }
}

function exec(cmd: string): { ok: boolean; stdout: string; stderr: string } {
  try {
    const stdout = execSync(cmd, { cwd: REPO_ROOT, encoding: 'utf8', timeout: 20000 });
    return { ok: true, stdout: stdout.trim(), stderr: '' };
  } catch (e: unknown) {
    const err = e as { stdout?: string; stderr?: string; message?: string };
    return { ok: false, stdout: (err.stdout || '').trim(), stderr: (err.stderr || err.message || '').trim() };
  }
}

function readJsonField(rel: string, field: string): unknown {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(REPO_ROOT, rel), 'utf8'));
    return data[field];
  } catch { return null; }
}

export async function GET() {
  const checks: Array<{ name: string; status: 'pass' | 'warn' | 'fail'; detail: string }> = [];

  // 1. CHROMATIC_TREES.md
  const trees = checkFile('CHROMATIC_TREES.md') || checkFile('.claude/skills/CHROMATIC_TREES.md');
  checks.push({
    name: 'CHROMATIC_TREES.md',
    status: trees.exists ? 'pass' : 'fail',
    detail: trees.exists ? `present (${trees.size}b)` : 'missing — source of truth doc not found',
  });

  // 2. visual_node_registry.json
  const registry = checkFile('visual_node_registry.json');
  let registryNodeCount = 0;
  let registryEdgeCount = 0;
  if (registry.exists) {
    try {
      const data = JSON.parse(fs.readFileSync(path.join(REPO_ROOT, 'visual_node_registry.json'), 'utf8'));
      registryNodeCount = (data.nodes ?? []).length;
      registryEdgeCount = (data.edges ?? []).length;
    } catch { /* ignore */ }
  }
  checks.push({
    name: 'visual_node_registry.json',
    status: registry.exists ? 'pass' : 'warn',
    detail: registry.exists
      ? `nodes=${registryNodeCount} edges=${registryEdgeCount}`
      : 'not found — run generate-visuals to create',
  });

  // 3. validate_visual_registry.py
  const validateResult = registry.exists
    ? exec(`${PYTHON} scripts/validate_visual_registry.py`)
    : { ok: false, stdout: '', stderr: 'registry not found' };
  checks.push({
    name: 'Registry validation',
    status: validateResult.ok ? 'pass' : 'fail',
    detail: validateResult.ok ? validateResult.stdout : validateResult.stderr || validateResult.stdout,
  });

  // 4. Mermaid files
  let mermaidCount = 0;
  try {
    const docsDir = path.join(REPO_ROOT, 'docs');
    if (fs.existsSync(docsDir)) {
      const walk = (dir: string): string[] => {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        return entries.flatMap((e) =>
          e.isDirectory() ? walk(path.join(dir, e.name)) : e.name.endsWith('.mmd') || e.name.endsWith('.mermaid') ? [path.join(dir, e.name)] : []
        );
      };
      mermaidCount = walk(docsDir).length;
    }
  } catch { /* ignore */ }
  checks.push({
    name: 'Mermaid files',
    status: mermaidCount > 0 ? 'pass' : 'warn',
    detail: mermaidCount > 0 ? `${mermaidCount} .mmd/.mermaid files found` : 'none found — run generate-visuals',
  });

  // 5. Confidence gates in registry
  let hasConfidenceGates = false;
  if (registry.exists) {
    try {
      const raw = fs.readFileSync(path.join(REPO_ROOT, 'visual_node_registry.json'), 'utf8');
      hasConfidenceGates = raw.toLowerCase().includes('confidence') || raw.toLowerCase().includes('gate');
    } catch { /* ignore */ }
  }
  checks.push({
    name: 'Confidence gates represented',
    status: hasConfidenceGates ? 'pass' : 'warn',
    detail: hasConfidenceGates ? 'confidence/gate nodes found in registry' : 'no confidence gate nodes detected',
  });

  // 6. Observability events
  const observabilityFile = checkFile('00_META/observability/reports/OBSERVABILITY_REPORT_2026-06-16.md');
  checks.push({
    name: 'Observability events',
    status: observabilityFile.exists ? 'pass' : 'warn',
    detail: observabilityFile.exists ? 'observability report present' : 'no observability report found',
  });

  const passCount = checks.filter((c) => c.status === 'pass').length;
  const failCount = checks.filter((c) => c.status === 'fail').length;
  const warnCount = checks.filter((c) => c.status === 'warn').length;
  const overallStatus = failCount > 0 ? 'fail' : warnCount > 0 ? 'warn' : 'pass';

  return NextResponse.json({
    timestamp: new Date().toISOString(),
    overall: overallStatus,
    summary: { pass: passCount, warn: warnCount, fail: failCount },
    checks,
    registry: registry.exists ? { nodes: registryNodeCount, edges: registryEdgeCount } : null,
  });
}
