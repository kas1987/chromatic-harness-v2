import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

const REPO_ROOT = process.env.REPO_ROOT || path.join(process.cwd(), '..');
const PYTHON = process.env.PYTHON_BIN || 'python';

function exec(cmd: string): { ok: boolean; stdout: string; stderr: string } {
  try {
    const stdout = execSync(cmd, { cwd: REPO_ROOT, encoding: 'utf8', timeout: 30000 });
    return { ok: true, stdout: stdout.trim(), stderr: '' };
  } catch (e: unknown) {
    const err = e as { stdout?: string; stderr?: string; message?: string };
    return { ok: false, stdout: (err.stdout || '').trim(), stderr: (err.stderr || err.message || '').trim() };
  }
}

export async function POST() {
  const stages: Array<{ name: string; ok: boolean; output: string; skipped?: boolean }> = [];

  // Stage 1 — validate registry
  const registryPath = path.join(REPO_ROOT, 'visual_node_registry.json');
  const registryExists = fs.existsSync(registryPath);
  if (!registryExists) {
    stages.push({ name: 'validate_registry', ok: false, output: 'visual_node_registry.json not found — cannot generate' });
    return NextResponse.json({ timestamp: new Date().toISOString(), ok: false, stages });
  }

  const validate = exec(`${PYTHON} scripts/validate_visual_registry.py`);
  stages.push({ name: 'validate_registry', ok: validate.ok, output: validate.ok ? validate.stdout : validate.stderr || validate.stdout });

  if (!validate.ok) {
    return NextResponse.json({ timestamp: new Date().toISOString(), ok: false, stages });
  }

  // Stage 2 — generate mermaid
  const mermaid = exec(`${PYTHON} scripts/generate_harness_mermaid.py`);
  stages.push({ name: 'generate_mermaid', ok: mermaid.ok, output: mermaid.ok ? mermaid.stdout : mermaid.stderr || mermaid.stdout });

  const allOk = stages.every((s) => s.ok);
  return NextResponse.json({ timestamp: new Date().toISOString(), ok: allOk, stages });
}

// GET returns last-generated state (just check if mermaid files exist)
export async function GET() {
  let mermaidFiles: string[] = [];
  try {
    const docsDir = path.join(REPO_ROOT, 'docs');
    if (fs.existsSync(docsDir)) {
      const walk = (dir: string): string[] => {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        return entries.flatMap((e) =>
          e.isDirectory() ? walk(path.join(dir, e.name)) : (e.name.endsWith('.mmd') || e.name.endsWith('.mermaid')) ? [path.relative(REPO_ROOT, path.join(dir, e.name))] : []
        );
      };
      mermaidFiles = walk(docsDir);
    }
  } catch { /* ignore */ }

  const registryExists = fs.existsSync(path.join(REPO_ROOT, 'visual_node_registry.json'));
  return NextResponse.json({
    timestamp: new Date().toISOString(),
    registry_present: registryExists,
    mermaid_file_count: mermaidFiles.length,
    mermaid_files: mermaidFiles.slice(0, 20),
  });
}
