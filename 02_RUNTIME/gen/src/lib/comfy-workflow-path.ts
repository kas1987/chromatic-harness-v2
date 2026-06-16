import fs from 'fs';
import path from 'path';

/** MetaChromatic comfy workflows — same resolution as WAN / image Gen routes */
export function resolveWorkflowDir(): string {
  if (process.env.GEN_WORKFLOW_ROOT) {
    return path.resolve(process.env.GEN_WORKFLOW_ROOT);
  }
  const root = process.env.PRISM_MONOREPO_ROOT;
  if (root) {
    const p = path.join(path.resolve(root), 'Image-Prism', 'apps', 'metachromatic', 'comfy', 'workflows');
    if (fs.existsSync(p)) {
      return p;
    }
  }
  const fromSource = path.resolve(__dirname, '..', '..', '..', 'Image-Prism', 'apps', 'metachromatic', 'comfy', 'workflows');
  if (fs.existsSync(fromSource)) {
    return fromSource;
  }
  const fromCwdParent = path.resolve(process.cwd(), '..', 'Image-Prism', 'apps', 'metachromatic', 'comfy', 'workflows');
  if (fs.existsSync(fromCwdParent)) {
    return fromCwdParent;
  }
  return fromSource;
}
