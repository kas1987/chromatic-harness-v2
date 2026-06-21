# Image-Prism (MetaChromatic) — Pipeline Adoption Doc

> **Status:** Candidate for harness-v2 management. Documented 2026-06-02 after the `D:\.04_Prism` runtime was retired (see `D:\_QUARANTINE_2026-06-02\04_Prism__from_D-root\MANIFEST.md`).
> **Owner action required:** clone from GitHub into a harness-managed location and re-own the automation (see §6).

---

## 1. What it is

| | |
|---|---|
| **Repo** | `github.com/kas1987/Image-Prism` (PRIVATE) |
| **Default branch** | `main` (pushed 2026-06-02 — current) |
| **Package name** | `metachromatic-monorepo` |
| **Product name** | **MetaChromatic** |
| **Stack** | pnpm@10.28.2 monorepo · TypeScript (strict) · Electron + Vite web apps · Python ML pipeline |
| **Quality** | husky pre-commit, Playwright E2E, security scans (checkov, gitleaks, grype, hadolint, semgrep) |

**Mission:** a unified workspace for **image-metadata tooling**, **ML pipeline management**, and **AI-driven content workflows** — browse, tag, train, and generate from one Electron desktop app and aligned toolchain. Local-first (Ollama / ComfyUI / TTS / `models.db` on-machine).

## 2. Architecture — apps & packages

**Apps (pnpm workspace, 10 on disk):**

| App | Purpose | Dev script |
|-----|---------|-----------|
| `metachromatic` | Main Electron app — all modes, IPC, stores, integrations | `pnpm dev:metachromatic` |
| `pipeline-dashboard` | ML pipeline inspector | `pnpm dev:pipeline-dashboard` |
| `prism-studio` | AI image tools (web) | `pnpm dev:prism-studio` |
| `storyboard-studio` | Narrative/storyboard | `pnpm dev:storyboard-studio` |
| `voice-studio` | TTS / voice | `pnpm dev:voice-studio` |
| `comfy-studio` | ComfyUI integration | `pnpm dev:comfy-studio` |
| `ai-training-studio` | Checkpoint/LoRA training UI | `pnpm dev:ai-training-studio` |
| `bust-atlas` | Measurement/visual tooling | `pnpm dev:bust-atlas` |
| `fx-demo` | Effects showcase (`@prism/fx`) | `pnpm dev:fx-demo` |
| `metachromatic-mobile` + `miga` | Mobile shell + companion | `pnpm dev:mobile` / `pnpm dev:miga` |

Shell bridges: `/#/voice-studio`, `/#/comfyui`, `/#/ai-training`, `/#/dashboard`, `/#/telemetry`, `/#/scraper`.
Design system: **Controlled Radiance** (glass UI, tokens, WCAG 2.1 AA) — `@prism/chromatic`, `@prism/fx`.

## 3. ML pipeline (Python)

Located under `ml-pipeline/` — driven via root `package.json` `pipeline:*` scripts:

| Script | Command | Purpose |
|--------|---------|---------|
| `pipeline:scorecard` | `ml-pipeline/production-scrapers/reliability_scorecard.py` | Scraper reliability scorecard |
| `pipeline:metadata:audit` | `ml-pipeline/checkpoint-training/scripts/metadata_reasonableness_audit.py` | Metadata sanity audit |
| `pipeline:metadata:web-needed` | `ml-pipeline/production-scrapers/web_metadata_as_needed.py` | Backfill web metadata (has `--dry-run`) |
| `pipeline:dedupe-models` | `ml-pipeline/production-scrapers/cleanup_duplicate_models.py --apply` | De-dupe model library (has `--dry-run`) |
| `pipeline:comfyui:export` | `ml-pipeline/production-scrapers/export_comfyui_payloads.py` | Export ComfyUI payloads |
| `pipeline:path-lockdown:check` | `scripts/check_app_path_lockdown.py` | Enforce path lockdown (has `--strict`) |

## 4. Services & ports

| Service | Port | Entry |
|---------|------|-------|
| Companion API | **5191** | `apps/metachromatic/electron/web-server.mjs` (`/api/health`) |
| MetaChromatic Mobile | **5190** | `pnpm dev:mobile` |
| Dev lanes | various | `docs/architecture/dev-port-map.md`, `packages/app-contracts` (`devLanes`, `backendLanes`, `sisterAppTargets`); check via `pnpm dev:lanes:check` |

Local launcher: `start-services.ps1` (clears 5190/5191, starts Companion API then Mobile).

**External dependencies (local-first):** ComfyUI · Ollama · Flask storyboard API · TTS-Qwen · `models.db`. Model library was at `D:\.000_AI\scraped_models` (re-point for harness — see §6).

## 5. Automation that drove it (now disabled)

These ran under the retired `D:\.04_Prism` runtime and are **currently `Disabled`** (backed up in `~/.claude/state/prism-retire-2026-06-02/`):

| Scheduled task | Target script | npm equiv |
|----------------|---------------|-----------|
| `ImagePrism-PipelineScorecardWeekly` | `tooling/pipeline/run-weekly-pipeline-scorecard.ps1` | `pipeline:weekly:run` |
| `ImagePrism-SkillsGovernanceWeekly` | `tooling/skills/run-weekly-skills-governance.ps1` | `skills:weekly:run` |

(Self-register via `pipeline:weekly:register` / `skills:weekly:register`.)

**MCP servers** (part of the rig):
- **Director** — `tooling/director/` (`bridge_daemon.py`; `mcp:director:*` scripts; has docker-compose).
- **Dispatch** — `tooling/dispatch-server/` (pm2 `ecosystem.config.cjs`; `mcp:dispatch:*`; Windows service via `setup-windows-service.ps1`).

**CI (GitHub Actions):** *MetaChromatic CI* runs `ci:design-platform` on push/PR to `main`/`develop`; *Cross-App Preflight* runs `ci:trunk` on relevant path changes.

## 6. Current physical state & adoption plan

**Where the code is (2026-06-02):**
- ✅ **Canonical:** `github.com/kas1987/Image-Prism` @ `main` — current, clean. **Use this.**
- ✅ **Complete local fallback:** `E:\_QUARANTINE_2026-06-02\Image-Prism__from_.89_Gits` (1.1 GB, 10 apps + ml-pipeline).
- ⚠️ Original `D:\.04_Prism\Image-Prism` retired (Prism teardown); `…\pipelines\Image-Prism` is a gutted docs/`.git` shell only. Nothing lost — GitHub is authoritative.

**To bring under harness-v2 management:**
1. **Clone** `git@github.com:kas1987/Image-Prism.git` (branch `main`) into a stable harness-governed path (NOT under a temp/retired tree). `pnpm install && pnpm prepare`.
2. **Fix hardcoded paths** that pointed at the old runtime:
   - `CLAUDE.md` → "Root directory: `D:\.04_Prism\Image-Prism`"
   - `start-services.ps1` → `cd D:\.04_Prism\Image-Prism\apps\metachromatic`
   - models dir → `D:\.000_AI\scraped_models`
3. **Re-own automation** under the harness: re-point + re-enable the two weekly tasks (or convert to harness-managed schedule), and register Director + Dispatch MCP servers / pm2 in the harness service stack.
4. **Add to** `docs/REPO_AND_RIG_INVENTORY.md` as a managed pipeline.
5. **Verify:** `pnpm run ci:metachromatic`, then `start-services.ps1` → check `http://localhost:5191/api/health`.

**Restore the old runtime (if ever needed):** `C:\Users\kas41\.claude\state\prism-retire-2026-06-02\RESTORE.ps1`.
