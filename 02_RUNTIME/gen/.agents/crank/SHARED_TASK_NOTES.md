# Shared Task Notes — Gen Integration Orchestration

## Epic Overview
Gen (Magic Genie) is live on port 43123 with hooks returning 200. This epic integrates Gen throughout the system:
- Wave 1: Foundation (rename references, config, docs)
- Wave 2: MetaChromatic integration (hook calls, TTS)
- Wave 3: Backend integration (Nate knowledge, ComfyUI, generation scripts)
- Wave 4: Deployment & CI (Docker, GitHub Actions, auth)

## Key System State
- Gen service: `http://localhost:43123` (must be running)
- Database: `.agents/nate/nate_knowledge.db` (expected to exist)
- TTS pipeline: wired into hooks, returning audioPath
- Budget config: maxExternalCallsPerTask=10000 (no call limit constraint)

## Cross-Wave Shared Files
- `.agents/` knowledge files (updated in Wave 1, read in subsequent waves)
- `Image-Prism/src/config.ts` (Wave 2.1 adds GEN_URL)
- `gen/src/routes/` (multiple files added across Wave 3)

## Critical Boundaries
- No breaking changes to MetaChromatic UI until Gen integration is transparent
- All hook responses must fail-open (continue: true)
- Auth defaults to "skip in dev", requires token in production
- No credentials in ecosystem.config.js (use ENV only)

---
