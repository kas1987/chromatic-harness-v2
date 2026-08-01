# Execution Plan — Harness V2 Remediation 2026-06-21

> Phased, command-level plan. Each step has a concrete acceptance command. Do not advance to the next step until the prior acceptance passes.

---

## Phase 0 — Security & Syntax (No Dependencies — Do First)
**Wall-clock estimate:** 20 minutes  
**Blocker if skipped:** Active security exposure, broken CI import

---

### Step 0.1 — Revoke the Leaked GitHub Token

```
1. Open: https://github.com/settings/tokens
2. Find token with prefix ghp_REDACTED_ROTATED_2026-06-21 — click Revoke
3. Confirm revocation
```

---

### Step 0.2 — Check Git History for Token

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
git log --all -p | Select-String "ghp_REDACTED_ROTATED_2026-06-21"
```

**If output is empty:** proceed to 0.3 (token only in working tree).  
**If output is non-empty:** run git-filter-repo to purge history (see PDR §4.1).

---

### Step 0.3 — Redact Token in Working Tree

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
(Get-Content "12_HANDOFFS\SESSION_2026-05-28_FINAL.md") `
  -replace 'ghp_REDACTED_ROTATED_2026-06-21[A-Za-z0-9_]+', 'ghp_REDACTED_ROTATED_2026-06-21' `
  | Set-Content "12_HANDOFFS\SESSION_2026-05-28_FINAL.md"
```

**Acceptance:**
```powershell
git grep "ghp_REDACTED_ROTATED_2026-06-21"  # must return nothing
```

---

### Step 0.4 — Fix Syntax Error in `rudalo_migration_audit.py`

Open `scripts/rudalo_migration_audit.py` at line 339. Find the f-string containing a backslash escape. Fix using one of:

```python
# Option A — extract escape to variable (preferred):
_nl = "\n"
msg = f"...{_nl}..."

# Option B — use string concatenation instead:
msg = "...\n" + str(detail)
```

**Acceptance:**
```powershell
Set-Location "E:\.02_chromatic-harness-v2"
python -m py_compile scripts/rudalo_migration_audit.py; echo "Exit: $LASTEXITCODE"
# Must print: Exit: 0
```

---

### Step 0.5 — Commit Phase 0

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
git add 12_HANDOFFS/SESSION_2026-05-28_FINAL.md scripts/rudalo_migration_audit.py
git commit -m "fix: redact leaked token, fix f-string syntax error in rudalo_migration_audit"
```

---

## Phase 1 — Infrastructure Integrity
**Wall-clock estimate:** 45 minutes  
**Blocker if skipped:** GitHub out of sync, pytest can't run, stale manifest

---

### Step 1.1 — Push `main` to Origin

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
git checkout main
git push origin main
```

**Acceptance:**
```powershell
git log --oneline origin/main..main  # must be empty
```

---

### Step 1.2 — Diagnose Pytest Environment

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
python -m pytest tests/test_auto_clean.py -v 2>&1 | Select-Object -First 20
```

**If `hydra` / `antlr4` error appears in traceback:**

```powershell
# Check if hydra-core is actually imported by harness:
Select-String -Path "02_RUNTIME\**\*.py","scripts\*.py" -Pattern "hydra" -Recurse

# If NO matches: uninstall cleanly
pip uninstall hydra-core antlr4-python3-runtime -y

# If matches found: pin compatible antlr4 version
pip install "antlr4-python3-runtime==4.9.3"
```

**Acceptance:**
```powershell
python -m pytest tests/test_auto_clean.py -v 2>&1 | Select-String "passed|failed|error"
# Must show: "24 passed"
```

---

### Step 1.3 — Fix `ARTIFACT_MANIFEST.json` Stale Adapter Path

Open `ARTIFACT_MANIFEST.json`. Find `"adapters"` → `"claude"`. The value `.claude/CLAUDE.md` does not exist. Update to `CLAUDE.md` (root-level file that does exist).

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
$m = Get-Content "ARTIFACT_MANIFEST.json" -Raw | ConvertFrom-Json
$m.adapters.claude = "CLAUDE.md"
$m | ConvertTo-Json -Depth 10 | Set-Content "ARTIFACT_MANIFEST.json"
```

**Acceptance:**
```powershell
python -c "
import json, pathlib
m = json.load(open('ARTIFACT_MANIFEST.json'))
for k, v in m.get('adapters', {}).items():
    if not v.startswith('http') and not pathlib.Path(v).exists():
        print(f'MISSING: {k} -> {v}')
        exit(1)
print('All adapter paths resolve')
"
```

---

### Step 1.4 — Delete Stale Local Branches

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
git branch -d CC-Desk/bold-mayer-90b4d5 2>&1
git branch -d feat/harness-v2-30day-remediation-complete 2>&1
git branch -d feat/review-intake-loop-metrics 2>&1
```

**Acceptance:**
```powershell
git branch | Measure-Object -Line  # must show ≤5 lines
```

---

### Step 1.5 — Commit Phase 1

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
git add ARTIFACT_MANIFEST.json requirements.txt
git commit -m "fix: update manifest adapter path, pin antlr4 version"
```

---

## Phase 2 — Coverage Sprint
**Wall-clock estimate:** 2–3 sessions  
**Blocker if skipped:** Runtime bugs go undetected

### Step 2.0 — Verify pytest baseline

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Must show 56 passed (test_auto_clean=24, test_auto_heal=25, test_harness_swot=7)
```

---

### Step 2.1 — Runtime Coverage: Batch 1 (Critical Path)

Write test files for: `orchestrator.py`, `budget.py`, `db.py`, `queue.py`

**Pattern for each:**
```python
# tests/test_<module>.py
import importlib.util, pytest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent / "02_RUNTIME"

def load(name):
    spec = importlib.util.spec_from_file_location(name, RUNTIME / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class TestOrchestrator:
    def test_import_clean(self): load("orchestrator")
    def test_happy_path(self, tmp_path): ...
    def test_error_path(self, tmp_path): ...
    def test_boundary(self): ...
    def test_fail_open(self): ...
```

**Acceptance after batch 1:**
```powershell
python -m pytest tests/test_orchestrator.py tests/test_budget.py tests/test_db.py tests/test_queue.py -v
# All must pass
```

---

### Step 2.2 — Runtime Coverage: Batch 2 (Server & Task Graph)

Write: `tests/test_server.py`, `tests/test_main.py`, `tests/test_task_graph.py`, `tests/test_enforcer.py`

---

### Step 2.3 — Runtime Coverage: Batch 3 (Guards & Security)

Write: `tests/test_guard.py`, `tests/test_permission.py`, `tests/test_verifier.py`, `tests/test_handlers.py`

---

### Step 2.4 — Runtime Coverage: Batch 4 (State & Healing)

Write: `tests/test_self_heal.py`, `tests/test_store.py`, `tests/test_ollama_adapter.py`

---

### Step 2.5 — Coverage Gate

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
python -m pytest tests/ --cov=02_RUNTIME --cov-report=term-missing 2>&1 | tail -20
# Target: ≥80% line coverage across all 127 runtime modules
```

---

### Step 2.6 — Doc Sprawl Sprint

Write `scripts/doc_consolidator.py` (see PDR §4.5 for spec), then run:

```powershell
# Dry-run first:
python scripts/doc_consolidator.py --dry-run

# If output looks correct, apply:
python scripts/doc_consolidator.py --apply --archive-to 12_HANDOFFS/archive/doc-consolidation-2026-06-21
```

**Acceptance:**
```powershell
(Get-ChildItem "E:\.02_chromatic-harness-v2" -Recurse -Filter "*.md" | Measure-Object).Count
# Must be ≤300
```

---

### Step 2.7 — Commit Phase 2

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
git add tests/ scripts/doc_consolidator.py
git commit -m "feat: runtime test coverage batch 1-4, doc consolidation"
```

---

## Phase 3 — Automation & Merge
**Wall-clock estimate:** 30 minutes

---

### Step 3.1 — Prune Stale Remote Branches

```powershell
Set-Location "E:\.02_chromatic-harness-v2"

# Verify each is merged before deleting:
git log origin/main..origin/fix/junction-path-correction-2026-06-20 --oneline
git log origin/main..origin/session/chromatic-harness-v2-initial --oneline
# If empty = merged and safe to delete:

git push origin --delete fix/junction-path-correction-2026-06-20
git push origin --delete session/chromatic-harness-v2-initial
# For feat/command-center-p1-p2 and docs/harness-v2-assessment-synthesis:
# verify merged, then delete
```

---

### Step 3.2 — Wire `auto_clean` + `auto_heal` to CI

Edit `.github/workflows/harness-daily-audit.yml` to add:

```yaml
      - name: Auto Clean (dry-run on PR, apply on schedule)
        run: python scripts/auto_clean.py --dry-run

      - name: Auto Heal (check-only)
        run: python scripts/auto_heal.py --check-only
```

For nightly schedule trigger, add a conditional `--force` job.

---

### Step 3.3 — Final SWOT Re-run

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
python scripts/harness_swot.py
cat 05_REPORTS/HARNESS_SWOT_REPORT.md
```

**Target state:**
- Threats: 0 (token revoked, syntax fixed)
- Weaknesses: pytest environment clean, stale branches 0
- Script coverage: ≥75%
- Runtime coverage: ≥80%

---

### Step 3.4 — Open PR and Merge

```powershell
Set-Location "E:\.02_chromatic-harness-v2"
git checkout feature/harness-finalization-2026-06-20
git push origin feature/harness-finalization-2026-06-20

gh pr create \
  --title "feat: harness V2 hardening — remediation sprint 2026-06-21" \
  --base main \
  --body "Resolves all 12 SWOT findings: token revocation, syntax fix, pytest env, test coverage (30 runtime modules), doc consolidation (≤300 .md), CI wiring for auto_clean/auto_heal. See 08_PDRS/MISSION_PACK_HARNESS_REMEDIATION_2026-06-21.md"
```

**Acceptance:**
```powershell
# After merge:
git checkout main
git pull
git log --oneline -3
# Must show the merged commit at top
python -m pytest tests/ --cov=02_RUNTIME -q 2>&1 | tail -3
# Must show all passed, ≥80% coverage
```

---

## Phase Gate Summary

| Phase | Gate Command | Pass Criteria |
|-------|-------------|---------------|
| 0 | `git grep "ghp_REDACTED_ROTATED_2026-06-21"` | Empty |
| 0 | `python -m py_compile scripts/rudalo_migration_audit.py` | Exit 0 |
| 1 | `git log origin/main..main` | Empty |
| 1 | `pytest tests/test_auto_clean.py` | 24 passed |
| 2 | `pytest tests/ --cov=02_RUNTIME` | ≥80% coverage |
| 2 | `.md file count` | ≤300 |
| 3 | `harness_swot.py` | 0 threats |
| 3 | PR merged | `git log --oneline -1` shows merge commit |

---

## Quick-Reference: All Acceptance Commands

```powershell
# Run all gates at once (Phase 0-1 verification):
Set-Location "E:\.02_chromatic-harness-v2"

git grep "ghp_REDACTED_ROTATED_2026-06-21" && echo "FAIL: token" || echo "PASS: token"
python -m py_compile scripts/rudalo_migration_audit.py && echo "PASS: syntax" || echo "FAIL: syntax"
$ahead = git log --oneline origin/main..main | Measure-Object -Line; if ($ahead.Lines -eq 0) {"PASS: main synced"} else {"FAIL: main $($ahead.Lines) ahead"}
python -m pytest tests/test_auto_clean.py tests/test_auto_heal.py -q 2>&1 | tail -1
(Get-ChildItem -Recurse -Filter "*.md" | Measure-Object).Count
git branch | Measure-Object -Line
```

---

## Schedule

| Date | Target |
|------|--------|
| 2026-06-21 (today) | Phase 0 complete (token + syntax) |
| 2026-06-22 | Phase 1 complete (push main, pytest env, manifest, branches) |
| 2026-06-23–24 | Phase 2 runtime coverage batch 1–2 |
| 2026-06-25–26 | Phase 2 runtime coverage batch 3–4 + doc consolidation |
| 2026-06-27 | Phase 3 (CI wiring, SWOT re-run, PR merge) |
| 2026-06-28 | All gates green, mission pack closed |
