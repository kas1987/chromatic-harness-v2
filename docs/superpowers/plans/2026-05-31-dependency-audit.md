# dependency-audit Chromatic Family — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `audit-family@local` Chromatic Family plugin with a `/dependency-audit` skill that scans Python/Node/shell deps and reports MCP tool usage frequency, coverage gaps, and cost.

**Architecture:** Six Python scripts (one entrypoint, four scanners, one renderer) under a standard Chromatic Family plugin scaffold. The skill invokes `run_audit.py` which orchestrates the scanners, collects JSON, and pipes through `render.py` for terminal output + written report. Two config files (`installed_plugins.json`, `skills-family.ps1`) updated to register and wire the family.

**Tech Stack:** Python 3.8+ stdlib only (`ast`, `json`, `re`, `pathlib`, `argparse`, `datetime`). No third-party deps.

---

## Task 1: Plugin scaffold + plugin.json

**Files:**
- Create: `~/.claude/plugins/local/audit-family/.claude-plugin/plugin.json`

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p ~/.claude/plugins/local/audit-family/.claude-plugin
mkdir -p ~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts
mkdir -p ~/.claude/plugins/local/audit-family/skills/dependency-audit/references
```

- [ ] **Step 2: Write plugin.json**

```json
{
  "license": "MIT",
  "name": "audit-family",
  "author": {
    "name": "kas41"
  },
  "description": "Dependency and MCP usage auditing — dependency-audit",
  "version": "1.0.0"
}
```

Save to `~/.claude/plugins/local/audit-family/.claude-plugin/plugin.json`.

- [ ] **Step 3: Verify structure**

```bash
find ~/.claude/plugins/local/audit-family -type d
```

Expected output:
```
~/.claude/plugins/local/audit-family
~/.claude/plugins/local/audit-family/.claude-plugin
~/.claude/plugins/local/audit-family/skills
~/.claude/plugins/local/audit-family/skills/dependency-audit
~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts
~/.claude/plugins/local/audit-family/skills/dependency-audit/references
```

- [ ] **Step 4: Commit**

```bash
git -C ~/.claude add plugins/local/audit-family
git -C ~/.claude commit -m "feat: scaffold audit-family plugin"
```

---

## Task 2: SKILL.md

**Files:**
- Create: `~/.claude/plugins/local/audit-family/skills/dependency-audit/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: dependency-audit
description: 'Audit declared vs actual dependencies (Python, Node, shell) and MCP tool usage (frequency, coverage gaps, cost). Triggers: "dependency-audit", "dep audit", "audit deps", "audit dependencies", "show me deps", "what deps are we using".'
skill_api_version: 1
model: haiku
permissions:
  allowed: [Read, Glob, Grep, Bash, Write]
  forbidden: [Edit, Agent, Skill, WebFetch, WebSearch, NotebookEdit, LSP]
  bash_scope: "python3 scripts — read-only scan + write one report file"
  model_tier: micro
context:
  window: inherit
  intent:
    mode: none
  intel_scope: none
metadata:
  tier: session
  dependencies: []
---

# /dependency-audit — Dependency & MCP Audit

> **Purpose:** Scan declared vs actual dependencies across Python/Node/shell and report MCP tool usage patterns from harness logs.

**YOU MUST EXECUTE THIS WORKFLOW. Do not just describe it.**

---

## Usage

```
/dependency-audit                    # scan $PWD
/dependency-audit --path /some/repo  # scan a specific path
/dependency-audit --python-only      # skip node/shell/mcp sections
/dependency-audit --mcp-only         # just MCP intelligence report
/dependency-audit --days 7           # MCP log window in days (default: 30)
```

---

## Execution Steps

### Step 1: Resolve target path

```bash
TARGET="${1:-.}"
# Strip --path flag if present
if echo "$*" | grep -q "\-\-path"; then
  TARGET=$(echo "$*" | sed 's/.*--path[= ]\([^ ]*\).*/\1/')
fi
```

### Step 2: Run audit

```bash
SKILL_DIR="$(dirname "$0")/.."
python3 "$SKILL_DIR/scripts/run_audit.py" --path "$TARGET" $@
```

### Step 3: Print output

The script handles all terminal output and file writing. Print the path to the report file at the end.
```

Save to `~/.claude/plugins/local/audit-family/skills/dependency-audit/SKILL.md`.

- [ ] **Step 2: Commit**

```bash
git -C ~/.claude add plugins/local/audit-family/skills/dependency-audit/SKILL.md
git -C ~/.claude commit -m "feat: add dependency-audit SKILL.md"
```

---

## Task 3: audit_python.py

**Files:**
- Create: `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_python.py`

- [ ] **Step 1: Write the script**

```python
"""Scan Python dependency manifests vs actual imports."""
import ast
import json
import re
import sys
from pathlib import Path

STDLIB = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else {
    'os', 'sys', 're', 'json', 'pathlib', 'math', 'collections', 'datetime',
    'shutil', 'subprocess', 'ast', 'argparse', 'time', 'logging', 'typing',
    'functools', 'hashlib', 'uuid', 'random', 'select', 'socket', 'threading'
}

SKIP_DIRS = {'.venv', 'venv', '__pycache__', 'node_modules', '.worktrees', '.git', 'dist', 'build'}


def parse_requirements(path: Path) -> set[str]:
    pkgs = set()
    for req_file in path.glob('requirements*.txt'):
        for line in req_file.read_text(errors='ignore').splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                name = re.split(r'[>=<!;@\[]', line)[0].strip().lower().replace('-', '_')
                if name:
                    pkgs.add(name)
    return pkgs


def parse_pyproject(path: Path) -> set[str]:
    pkgs = set()
    pyproject = path / 'pyproject.toml'
    if not pyproject.exists():
        return pkgs
    content = pyproject.read_text(errors='ignore')
    in_deps = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1].strip()
            in_deps = section in ('project.dependencies', 'tool.poetry.dependencies', 'tool.poetry.group.dev.dependencies')
            continue
        if in_deps:
            m = re.match(r'^"?([a-zA-Z0-9_\-]+)"?\s*[>=<!"\s=]', line)
            if m:
                pkgs.add(m.group(1).lower().replace('-', '_'))
    return pkgs


def collect_imports(path: Path) -> set[str]:
    imports = set()
    for py_file in path.rglob('*.py'):
        if any(part in SKIP_DIRS for part in py_file.parts):
            continue
        try:
            tree = ast.parse(py_file.read_text(errors='ignore'))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split('.')[0].lower().replace('-', '_')
                    if top not in STDLIB:
                        imports.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    top = node.module.split('.')[0].lower().replace('-', '_')
                    if top not in STDLIB:
                        imports.add(top)
    return imports


def run(target: Path) -> dict:
    declared = parse_requirements(target) | parse_pyproject(target)
    if not declared:
        return {'skipped': True, 'reason': 'no requirements.txt or pyproject.toml found'}
    actual = collect_imports(target)
    return {
        'declared_count': len(declared),
        'imported_count': len(actual),
        'unused_declared': sorted(declared - actual),
        'undeclared_imports': sorted(actual - declared),
    }


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    print(json.dumps(run(target), indent=2))
```

Save to `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_python.py`.

- [ ] **Step 2: Smoke test**

```bash
python3 ~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_python.py ~/chromatic-harness-v2
```

Expected: JSON with `declared_count`, `unused_declared`, `undeclared_imports` keys (no Python error).

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add plugins/local/audit-family/skills/dependency-audit/scripts/audit_python.py
git -C ~/.claude commit -m "feat: add audit_python.py scanner"
```

---

## Task 4: audit_node.py

**Files:**
- Create: `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_node.py`

- [ ] **Step 1: Write the script**

```python
"""Scan Node/TypeScript package.json vs actual imports."""
import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {'.venv', 'venv', '__pycache__', 'node_modules', '.worktrees', '.git', 'dist', 'build'}
IMPORT_RE = re.compile(r"""(?:import\s+.*?\s+from\s+['"]|require\s*\(\s*['"])(@?[^@'"./][^'"]*?)['"]""")


def parse_package_json(path: Path) -> set[str]:
    pkgs = set()
    for pkg_file in list(path.glob('package.json')) + list(path.glob('*/package.json')) + list(path.glob('*/*/package.json')):
        if any(part in SKIP_DIRS for part in pkg_file.parts):
            continue
        try:
            data = json.loads(pkg_file.read_text(errors='ignore'))
        except json.JSONDecodeError:
            continue
        for section in ('dependencies', 'devDependencies'):
            pkgs.update(data.get(section, {}).keys())
    return {p.lower() for p in pkgs}


def collect_imports(path: Path) -> set[str]:
    imports = set()
    for ext in ('*.ts', '*.js', '*.tsx', '*.jsx'):
        for f in path.rglob(ext):
            if any(part in SKIP_DIRS for part in f.parts):
                continue
            content = f.read_text(errors='ignore')
            for m in IMPORT_RE.finditer(content):
                pkg = m.group(1)
                parts = pkg.split('/')
                if pkg.startswith('@') and len(parts) > 1:
                    imports.add(f"{parts[0]}/{parts[1]}".lower())
                else:
                    imports.add(parts[0].lower())
    return imports


def run(target: Path) -> dict:
    declared = parse_package_json(target)
    if not declared:
        return {'skipped': True, 'reason': 'no package.json found'}
    actual = collect_imports(target)
    return {
        'declared_count': len(declared),
        'imported_count': len(actual),
        'unused_declared': sorted(declared - actual),
        'undeclared_imports': sorted(actual - declared),
    }


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    print(json.dumps(run(target), indent=2))
```

Save to `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_node.py`.

- [ ] **Step 2: Smoke test**

```bash
python3 ~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_node.py ~/chromatic-harness-v2
```

Expected: JSON with `declared_count`, `unused_declared`, `undeclared_imports` (no Python error).

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add plugins/local/audit-family/skills/dependency-audit/scripts/audit_node.py
git -C ~/.claude commit -m "feat: add audit_node.py scanner"
```

---

## Task 5: audit_shell.py

**Files:**
- Create: `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_shell.py`

- [ ] **Step 1: Write the script**

```python
"""Scan .sh files for external tool calls."""
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {'.worktrees', '.git', 'node_modules', '.venv', 'venv'}
BASH_BUILTINS = {
    'if', 'then', 'else', 'elif', 'fi', 'for', 'while', 'do', 'done', 'case',
    'esac', 'function', 'return', 'exit', 'echo', 'printf', 'read', 'local',
    'export', 'source', '.', 'cd', 'pwd', 'set', 'unset', 'shift', 'eval',
    'exec', 'true', 'false', 'test', '[', '[[', ']]', ']', 'declare', 'typeset',
    'readonly', 'let', 'getopts', 'break', 'continue', 'trap', 'wait', 'kill',
    'jobs', 'bg', 'fg', 'hash', 'type', 'which', 'command', 'builtin',
}
COMMAND_RE = re.compile(r'(?:^|[|&;(]\s*|\$\()(\b[a-zA-Z][a-zA-Z0-9_\-]{1,30}\b)')


def collect_tools(path: Path) -> dict[str, list[str]]:
    tool_files: dict[str, list[str]] = defaultdict(list)
    for sh_file in path.rglob('*.sh'):
        if any(part in SKIP_DIRS for part in sh_file.parts):
            continue
        content = sh_file.read_text(errors='ignore')
        for m in COMMAND_RE.finditer(content):
            cmd = m.group(1)
            if cmd not in BASH_BUILTINS and not cmd.startswith('$'):
                tool_files[cmd].append(str(sh_file.relative_to(path)))
    return dict(tool_files)


def check_path(tool: str) -> bool:
    import shutil
    return shutil.which(tool) is not None


def run(target: Path) -> dict:
    sh_files = list(target.rglob('*.sh'))
    sh_files = [f for f in sh_files if not any(part in SKIP_DIRS for part in f.parts)]
    if not sh_files:
        return {'skipped': True, 'reason': 'no .sh files found'}
    tool_files = collect_tools(target)
    not_in_path = [t for t in tool_files if not check_path(t)]
    return {
        'sh_files_scanned': len(sh_files),
        'external_tools': sorted(tool_files.keys()),
        'not_in_path': sorted(not_in_path),
        'tool_file_map': {k: sorted(set(v)) for k, v in tool_files.items()},
    }


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    print(json.dumps(run(target), indent=2))
```

Save to `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_shell.py`.

- [ ] **Step 2: Smoke test**

```bash
python3 ~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_shell.py ~/chromatic-harness-v2
```

Expected: JSON with `sh_files_scanned`, `external_tools`, `not_in_path`.

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add plugins/local/audit-family/skills/dependency-audit/scripts/audit_shell.py
git -C ~/.claude commit -m "feat: add audit_shell.py scanner"
```

---

## Task 6: audit_mcp.py

**Files:**
- Create: `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_mcp.py`

- [ ] **Step 1: Write the script**

```python
"""Scan MCP tool registrations vs actual usage from harness logs."""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

LOG_FILES = [
    '07_LOGS_AND_AUDIT/budget/ledger.jsonl',
    '07_LOGS_AND_AUDIT/token_governance/history.jsonl',
    '07_LOGS_AND_AUDIT/AGENT_RUN_LOG.jsonl',
]
CLAUDE_JSON_PATHS = [
    Path.home() / '.claude.json',
    Path.home() / '.claude' / '.claude.json',
]


def load_registered_tools(target: Path) -> list[str]:
    candidates = CLAUDE_JSON_PATHS + [target / '.claude.json']
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(errors='ignore'))
                servers = data.get('mcpServers', {})
                tools = []
                for server_name in servers:
                    tools.append(server_name)
                return tools
            except (json.JSONDecodeError, KeyError):
                continue
    return []


def load_log_events(target: Path, days: int) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days)
    events = []
    for rel_path in LOG_FILES:
        log_file = target / rel_path
        if not log_file.exists():
            continue
        for line in log_file.read_text(errors='ignore').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                ts_str = event.get('timestamp') or event.get('ts') or event.get('time', '')
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        if ts.tzinfo is not None:
                            ts = ts.replace(tzinfo=None)
                        if ts < cutoff:
                            continue
                    except ValueError:
                        pass
                events.append(event)
            except json.JSONDecodeError:
                continue
    return events


def extract_tool_stats(events: list[dict]) -> tuple[dict, dict]:
    call_counts: dict[str, int] = defaultdict(int)
    token_costs: dict[str, float] = defaultdict(float)
    tool_keys = ('tool', 'tool_name', 'toolName', 'name')
    cost_keys = ('cost', 'token_cost', 'tokens', 'total_tokens')
    for event in events:
        tool = None
        for k in tool_keys:
            if k in event:
                tool = str(event[k])
                break
        if not tool:
            continue
        call_counts[tool] += 1
        for k in cost_keys:
            if k in event:
                try:
                    token_costs[tool] += float(event[k])
                except (ValueError, TypeError):
                    pass
    return dict(call_counts), dict(token_costs)


def run(target: Path, days: int = 30) -> dict:
    registered = load_registered_tools(target)
    logs_path = target / '07_LOGS_AND_AUDIT'
    if not logs_path.exists():
        return {
            'warning': '07_LOGS_AND_AUDIT not found — MCP usage data unavailable',
            'registered_tools': registered,
            'called_tools': [],
            'dead_registrations': registered,
            'top_by_calls': [],
            'top_by_cost': [],
        }
    events = load_log_events(target, days)
    call_counts, token_costs = extract_tool_stats(events)
    called = set(call_counts.keys())
    dead = []
    for server in registered:
        if not any(server in tool or tool in server for tool in called):
            dead.append(server)
    dead = sorted(dead)
    top_calls = sorted(call_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_cost = sorted(token_costs.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        'days_window': days,
        'registered_count': len(registered),
        'called_count': len(called),
        'dead_count': len(dead),
        'dead_registrations': dead,
        'top_by_calls': [{'tool': t, 'calls': c} for t, c in top_calls],
        'top_by_cost': [{'tool': t, 'tokens': round(c)} for t, c in top_cost],
    }


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    print(json.dumps(run(target, days), indent=2))
```

Save to `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_mcp.py`.

- [ ] **Step 2: Smoke test**

```bash
python3 ~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/audit_mcp.py ~/chromatic-harness-v2
```

Expected: JSON with `registered_count`, `called_count`, `dead_registrations`, `top_by_calls`, `top_by_cost`.

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add plugins/local/audit-family/skills/dependency-audit/scripts/audit_mcp.py
git -C ~/.claude commit -m "feat: add audit_mcp.py scanner"
```

---

## Task 7: render.py

**Files:**
- Create: `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/render.py`

- [ ] **Step 1: Write the script**

```python
"""Render audit results to terminal + written report file."""
import json
import sys
from datetime import datetime
from pathlib import Path


def _col(items: list, max_per_line: int = 6) -> str:
    if not items:
        return '(none)'
    chunks = [', '.join(items[i:i+max_per_line]) for i in range(0, len(items), max_per_line)]
    return ('\n' + ' ' * 22).join(chunks)


def render_terminal(results: dict, target: Path, report_path: Path) -> None:
    repo_name = target.resolve().name
    width = 68
    bar = '═' * width

    lines = [
        f'╔{bar}╗',
        f'║  DEPENDENCY AUDIT — {repo_name:<{width-22}}║',
        f'║  {datetime.now().strftime("%Y-%m-%d %H:%M"):<{width-2}}║',
        f'╚{bar}╝',
        '',
    ]

    # Python
    py = results.get('python', {})
    if py.get('skipped'):
        lines += [f'── PYTHON {"─"*58}', f'  (skipped: {py.get("reason")})', '']
    else:
        lines += [
            f'── PYTHON {"─"*58}',
            f'  Declared: {py.get("declared_count", 0)} packages  |  Imported: {py.get("imported_count", 0)} packages',
        ]
        unused = py.get('unused_declared', [])
        undecl = py.get('undeclared_imports', [])
        lines.append(f'  {"✗" if unused else "✓"} Unused declared:    {_col(unused)}')
        lines.append(f'  {"✗" if undecl else "✓"} Undeclared imports: {_col(undecl)}')
        lines.append('')

    # Node
    node = results.get('node', {})
    if node.get('skipped'):
        lines += [f'── NODE / TYPESCRIPT {"─"*47}', f'  (skipped: {node.get("reason")})', '']
    else:
        lines += [
            f'── NODE / TYPESCRIPT {"─"*47}',
            f'  Declared: {node.get("declared_count", 0)} packages  |  Imported: {node.get("imported_count", 0)} packages',
        ]
        unused = node.get('unused_declared', [])
        undecl = node.get('undeclared_imports', [])
        lines.append(f'  {"✗" if unused else "✓"} Unused declared:    {_col(unused)}')
        lines.append(f'  {"✗" if undecl else "✓"} Undeclared imports: {_col(undecl)}')
        lines.append('')

    # Shell
    sh = results.get('shell', {})
    if sh.get('skipped'):
        lines += [f'── SHELL SCRIPTS {"─"*51}', f'  (skipped: {sh.get("reason")})', '']
    else:
        tools = sh.get('external_tools', [])
        bad = sh.get('not_in_path', [])
        lines += [
            f'── SHELL SCRIPTS {"─"*51}',
            f'  .sh files scanned: {sh.get("sh_files_scanned", 0)}',
            f'  External tools: {_col(tools)}',
            f'  {"⚠" if bad else "✓"} Not in PATH: {_col(bad)}',
            '',
        ]

    # MCP
    mcp = results.get('mcp', {})
    if mcp.get('warning'):
        lines += [f'── MCP TOOLS {"─"*55}', f'  ⚠ {mcp["warning"]}', '']
    else:
        top_calls = ', '.join(f'{x["tool"]}({x["calls"]})' for x in mcp.get('top_by_calls', [])[:5])
        top_cost  = ', '.join(f'{x["tool"]}({x["tokens"]}tok)' for x in mcp.get('top_by_cost', [])[:5])
        dead = mcp.get('dead_registrations', [])
        lines += [
            f'── MCP TOOLS {"─"*55}',
            f'  Registered: {mcp.get("registered_count", 0)}  |  Called ({mcp.get("days_window", 30)}d): {mcp.get("called_count", 0)}  |  Dead: {mcp.get("dead_count", 0)}',
            f'  Top by calls:  {top_calls or "(no data)"}',
            f'  Top by cost:   {top_cost or "(no data)"}',
            f'  {"⚠" if dead else "✓"} Dead registrations: {_col(dead)}',
            '',
        ]

    lines.append(f'Full report → {report_path}')
    print('\n'.join(lines))


def render_report(results: dict, target: Path) -> str:
    repo_name = target.resolve().name
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [f'# Dependency Audit — {repo_name}', f'**Generated:** {ts}', '']

    for section, title in [('python', 'Python'), ('node', 'Node / TypeScript'), ('shell', 'Shell Scripts'), ('mcp', 'MCP Tools')]:
        data = results.get(section, {})
        lines.append(f'## {title}')
        if data.get('skipped'):
            lines.append(f'_Skipped: {data.get("reason")}_')
        else:
            lines.append(f'```json\n{json.dumps(data, indent=2)}\n```')
        lines.append('')
    return '\n'.join(lines)


def write_report(content: str, target: Path) -> Path:
    log_dir = target / '07_LOGS_AND_AUDIT' / 'dep-audit'
    if not log_dir.parent.exists():
        log_dir = target
    log_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime('%Y-%m-%d-%H') + '.md'
    report_path = log_dir / filename
    report_path.write_text(content)
    return report_path


def run(results: dict, target: Path) -> None:
    report_content = render_report(results, target)
    report_path = write_report(report_content, target)
    render_terminal(results, target, report_path)


if __name__ == '__main__':
    results = json.loads(sys.stdin.read())
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    run(results, target)
```

Save to `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/render.py`.

- [ ] **Step 2: Commit**

```bash
git -C ~/.claude add plugins/local/audit-family/skills/dependency-audit/scripts/render.py
git -C ~/.claude commit -m "feat: add render.py — terminal + file output"
```

---

## Task 8: run_audit.py (entrypoint)

**Files:**
- Create: `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/run_audit.py`

- [ ] **Step 1: Write the script**

```python
"""Entrypoint: parse args, run scanners, pipe to renderer."""
import argparse
import sys
from pathlib import Path

# Add scripts dir to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

import audit_python
import audit_node
import audit_shell
import audit_mcp
import render


def main():
    parser = argparse.ArgumentParser(description='Dependency and MCP usage audit')
    parser.add_argument('--path', default='.', help='Target repo path (default: cwd)')
    parser.add_argument('--python-only', action='store_true')
    parser.add_argument('--node-only', action='store_true')
    parser.add_argument('--shell-only', action='store_true')
    parser.add_argument('--mcp-only', action='store_true')
    parser.add_argument('--days', type=int, default=30, help='MCP log window in days')
    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.exists():
        print(f'Error: path does not exist: {target}', file=sys.stderr)
        sys.exit(1)

    only_flags = [args.python_only, args.node_only, args.shell_only, args.mcp_only]
    run_all = not any(only_flags)

    results = {}
    if run_all or args.python_only:
        results['python'] = audit_python.run(target)
    if run_all or args.node_only:
        results['node'] = audit_node.run(target)
    if run_all or args.shell_only:
        results['shell'] = audit_shell.run(target)
    if run_all or args.mcp_only:
        results['mcp'] = audit_mcp.run(target, args.days)

    render.run(results, target)


if __name__ == '__main__':
    main()
```

Save to `~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/run_audit.py`.

- [ ] **Step 2: Full end-to-end smoke test**

```bash
python3 ~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/run_audit.py \
  --path ~/chromatic-harness-v2
```

Expected: 4-section terminal output ending with `Full report →` path. No Python errors.

- [ ] **Step 3: Test --mcp-only flag**

```bash
python3 ~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/run_audit.py \
  --path ~/chromatic-harness-v2 --mcp-only
```

Expected: Only MCP section printed.

- [ ] **Step 4: Commit**

```bash
git -C ~/.claude add plugins/local/audit-family/skills/dependency-audit/scripts/run_audit.py
git -C ~/.claude commit -m "feat: add run_audit.py entrypoint"
```

---

## Task 9: references/log-schema.md

**Files:**
- Create: `~/.claude/plugins/local/audit-family/skills/dependency-audit/references/log-schema.md`

- [ ] **Step 1: Write log-schema.md**

```markdown
# MCP Log Schema Reference

`audit_mcp.py` reads these files from `07_LOGS_AND_AUDIT/`:

## budget/ledger.jsonl
Each line is a JSON object. Fields read:
- `tool` or `tool_name` or `toolName` — tool identifier
- `cost` or `token_cost` — numeric cost value
- `timestamp` or `ts` or `time` — ISO 8601 datetime for window filtering

## token_governance/history.jsonl
Each line is a JSON object. Fields read:
- `tool` or `name` — tool identifier
- `tokens` or `total_tokens` — token count
- `timestamp` — ISO 8601 datetime

## AGENT_RUN_LOG.jsonl
Each line is a JSON object. Fields read:
- `tool` — tool identifier
- `timestamp` — ISO 8601 datetime

## Registered tools source
`~/.claude.json` → `mcpServers` keys. Falls back to `<target>/.claude.json`.
```

Save to `~/.claude/plugins/local/audit-family/skills/dependency-audit/references/log-schema.md`.

- [ ] **Step 2: Commit**

```bash
git -C ~/.claude add plugins/local/audit-family/skills/dependency-audit/references/log-schema.md
git -C ~/.claude commit -m "docs: add log-schema reference for audit_mcp"
```

---

## Task 10: Register audit-family@local in installed_plugins.json

**Files:**
- Modify: `~/.claude/plugins/installed_plugins.json`

- [ ] **Step 1: Add entry to installed_plugins.json**

Open `~/.claude/plugins/installed_plugins.json`. Under the `"plugins"` key, add:

```json
"audit-family@local": [
  {
    "scope": "user",
    "installPath": "C:\\Users\\kas41\\.claude\\plugins\\local\\audit-family",
    "version": "1.0.0",
    "installedAt": "2026-05-31T00:00:00.000Z",
    "lastUpdated": "2026-05-31T00:00:00.000Z",
    "gitCommitSha": "local"
  }
]
```

- [ ] **Step 2: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open(r'C:/Users/kas41/.claude/plugins/installed_plugins.json')); print('valid')"
```

Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add plugins/installed_plugins.json
git -C ~/.claude commit -m "feat: register audit-family@local in installed_plugins.json"
```

---

## Task 11: Update skills-family.ps1

**Files:**
- Modify: `~/.claude/bin/skills-family.ps1`

- [ ] **Step 1: Update the script**

Replace the contents of `~/.claude/bin/skills-family.ps1` with:

```powershell
#!/usr/bin/env pwsh
# Toggle skill families in settings.json
# Usage: skills-family.ps1 [pipeline] [trust] [toolchain] [audit] [--off pipeline] ...
# Examples:
#   skills-family.ps1 core              # all families off (base token minimum)
#   skills-family.ps1 all               # all families on
#   skills-family.ps1 audit             # audit only (infra session)
#   skills-family.ps1 pipeline trust    # pipeline + trust on, rest off

param(
    [string[]]$On = @(),
    [string[]]$Off = @()
)

$settingsPath = "$HOME\.claude\settings.json"
$settings = Get-Content $settingsPath | ConvertFrom-Json

$families = @(
    "pipeline-family@local",
    "trust-family@local",
    "toolchain-family@local",
    "audit-family@local"
)
$familyMap = @{
    "pipeline"  = "pipeline-family@local"
    "trust"     = "trust-family@local"
    "toolchain" = "toolchain-family@local"
    "audit"     = "audit-family@local"
}

# Handle shorthand args
$args = $On
if ($args -contains "all") {
    $families | ForEach-Object { $settings.enabledPlugins.$_ = $true }
} elseif ($args -contains "core") {
    $families | ForEach-Object { $settings.enabledPlugins.$_ = $false }
} else {
    # Disable all first, then enable named ones
    $families | ForEach-Object { $settings.enabledPlugins.$_ = $false }
    foreach ($name in $args) {
        $key = $familyMap[$name]
        if ($key) { $settings.enabledPlugins.$key = $true }
        else { Write-Warning "Unknown family: $name (valid: pipeline, trust, toolchain, audit)" }
    }
}

$settings | ConvertTo-Json -Depth 20 | Set-Content $settingsPath -Encoding UTF8

# Show current state
Write-Host "`nSkill families:"
$families | ForEach-Object {
    $short = $_ -replace "-family@local",""
    $state = if ($settings.enabledPlugins.$_) { "[ON] " } else { "[OFF]" }
    Write-Host "  $state $short"
}
Write-Host "`nRestart Claude Code to apply changes."
```

- [ ] **Step 2: Smoke test**

```powershell
pwsh ~/.claude/bin/skills-family.ps1 audit
```

Expected output:
```
Skill families:
  [OFF] pipeline
  [OFF] trust
  [OFF] toolchain
  [ON]  audit

Restart Claude Code to apply changes.
```

- [ ] **Step 3: Reset to all**

```powershell
pwsh ~/.claude/bin/skills-family.ps1 all
```

- [ ] **Step 4: Commit**

```bash
git -C ~/.claude add bin/skills-family.ps1
git -C ~/.claude commit -m "feat: add audit family to skills-family.ps1 switcher"
```

---

## Task 12: Verify end-to-end

- [ ] **Step 1: Check plugin is discoverable**

```bash
cat ~/.claude/plugins/installed_plugins.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
key = 'audit-family@local'
if key in d['plugins']:
    print(f'FOUND: {key}')
    print(json.dumps(d[\"plugins\"][key][0], indent=2))
else:
    print('MISSING')
"
```

Expected: `FOUND: audit-family@local` with the install entry.

- [ ] **Step 2: Run full audit against harness**

```bash
python3 ~/.claude/plugins/local/audit-family/skills/dependency-audit/scripts/run_audit.py \
  --path ~/chromatic-harness-v2
```

Expected: All 4 sections print without errors. Report file written to `07_LOGS_AND_AUDIT/dep-audit/`.

- [ ] **Step 3: Verify report file written**

```bash
ls ~/chromatic-harness-v2/07_LOGS_AND_AUDIT/dep-audit/
```

Expected: A `.md` file with today's date.

- [ ] **Step 4: Final commit tag**

```bash
git -C ~/.claude log --oneline -8
```

Confirm all 8 feature commits are present.
