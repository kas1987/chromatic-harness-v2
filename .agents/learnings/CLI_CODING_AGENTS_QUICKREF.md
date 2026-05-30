# CLI Coding Agents Quick Reference
## Claude Code + OpenAI Codex

Both are already installed on this machine.

---

## Claude Code (Anthropic)

**Installed:** `claude` (npm global)
**Model:** Claude Sonnet 4.6 (native Anthropic API)
**Best for:** Complex refactoring, multi-file changes, deep codebase understanding

### Basic Usage
```bash
# Start in any repo
claude

# With a specific prompt (non-interactive)
claude "refactor the auth module to use JWT"

# Background mode (runs in tmux/screen)
claude --bg "implement the missing tests for utils.py"
```

### Key Commands Inside Claude Code
| Command | What it does |
|---------|-------------|
| `/help` | Show all commands |
| `/compact` | Summarize conversation history (save tokens) |
| `/clear` | Clear screen |
| `/exit` | Quit |
| `Enter` | Accept Claude's proposed edit |
| `Ctrl+C` | Cancel current operation |

### What Claude Code Can Do
- Read and edit multiple files
- Run bash commands
- Run tests and iterate on failures
- Search the codebase
- Git operations (diff, commit, branch)
- Install dependencies

### Cost
- Uses your Claude API key (`CLAUDE_API_KEY`)
- Sonnet 4.6: $3 in / $15 out per 1M tokens
- Typical coding session: $0.50-$3.00

---

## OpenAI Codex

**Installed:** `codex` (npm global)
**Model:** GPT-5.4 or your configured default
**Best for:** Quick implementations, single-file changes, prototyping

### Basic Usage
```bash
# Interactive mode
codex

# Full-auto mode (no confirmation prompts)
codex --full-auto "add error handling to the login function"

# With specific file context
codex -f src/auth.js "fix the JWT validation bug"

# Sandbox levels (required)
codex -s read-only --full-auto "review this code for bugs"      # Review only
codex -s workspace-write --full-auto "implement the feature"       # Can edit files
codex -s danger-full-access --full-auto "rm -rf && rebuild"        # ⚠️ Everything
```

### Key Flags
| Flag | Meaning |
|------|---------|
| `--full-auto` | No confirmation prompts |
| `-s read-only` | Cannot modify files (review/analysis) |
| `-s workspace-write` | Can edit files in current directory |
| `-f <file>` | Focus on specific file |
| `-m <model>` | Override model (e.g., `gpt-5.4`, `o3-mini`) |
| `-o <file>` | Save output to file |
| `--json` | JSONL output for monitoring |

### Cost
- Uses your OpenAI API key (`OPENAI_API_KEY`)
- GPT-5.4: $2.50 in / $15 out per 1M tokens
- o3-mini: $1.10 in / $4.40 out per 1M tokens (reasoning)
- Typical session: $0.30-$2.00

---

## When to Use Which

| Task | Use | Why |
|------|-----|-----|
| Deep refactor across 5+ files | **Claude Code** | Better at cross-file reasoning |
| Single function implementation | **Codex** (`--full-auto`) | Faster, less overhead |
| Code review (no edits) | **Codex** (`-s read-only`) | Cheaper, focused |
| Debug complex bug | **Claude Code** | Better at root-cause analysis |
| Add tests for existing code | **Either** | Toss-up |
| Scaffold new project | **Claude Code** | Better at architecture decisions |
| Quick regex fix | **Codex** | Overkill for Claude Code |
| Work offline / no API spend | **Local Ollama** (`qwen2.5-coder:14b`) | Free, GPU-fast |

---

## Pro Tips

### 1. Claude Code + Git Workflow
```bash
# Start on a feature branch
git checkout -b feature/new-thing

# Let Claude Code implement it
claude "implement the user profile page with React + Tailwind"

# Review the diff
git diff

# Claude can even commit for you (inside the session)
/git commit -m "feat: add user profile page"
```

### 2. Codex for Batch Tasks
```bash
# Process multiple files with one prompt
for f in src/*.js; do
  codex -s workspace-write --full-auto -f "$f" "add JSDoc comments"
done
```

### 3. Claude Code Context Management
Claude Code loads the **entire repo context** automatically. For huge repos:
```bash
# Exclude large directories
claude --ignore "node_modules/" --ignore "dist/"
```

### 4. Cost Control
```bash
# Set a spend limit on your API keys
# OpenAI: https://platform.openai.com/settings/organization/limits
# Anthropic: https://console.anthropic.com/settings/cost-management
```

---

## Integration with Our Router

The router's **speed mode** affects which cloud provider you get, but **Claude Code and Codex are separate CLI tools** that bypass the router. They use their own API keys directly.

If you want the router to influence CLI agent model selection:
- Set `provider_preference: openrouter` in `user-preferences.yaml`
- Use the OpenRouter API key in Claude Code / Codex (both support custom base URLs)
- Then model selection happens at the OpenRouter layer

### Using OpenRouter with Claude Code
```bash
# Not natively supported, but you can proxy
# Use openrouter's base_url with Claude Code's SDK calls
```

### Using OpenRouter with Codex
```bash
# Codex uses OpenAI SDK under the hood
codex -m openrouter/auto --full-auto "do the thing"
# (Requires OPENROUTER_API_KEY set)
```

---

## Quick Start Cheat Sheet

```bash
# --- Claude Code ---
claude                              # Interactive session
claude "refactor auth to JWT"       # One-shot prompt
claude --bg "write tests"           # Background

# --- Codex ---
codex                               # Interactive
codex --full-auto "fix the bug"     # Auto-execute
codex -s read-only "review this"    # Review only
codex -m o3-mini --full-auto "solve this math problem"  # Reasoning model

# --- Local (free) ---
ollama run qwen2.5-coder:14b        # Chat with local model
# Or use the LAN desktop:
curl http://desktop.local:11434/api/generate -d '{"model":"qwen2.5-coder:14b","prompt":"fix this"}'
```

---

*Reference version: 2026-05-28*
