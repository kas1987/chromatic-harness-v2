# Decision Log

| Date | Decision | Reason | Status |
|---|---|---|---|
| 2026-05-28 | Start fresh with Chromatic Harness v2 scaffold | Current architecture has grown enough that patching old scaffolds creates drag | Accepted |
| 2026-05-28 | Treat CMP as control plane above MCP | MCP should expose tools; CMP should govern whether tools may be used | Accepted |
| 2026-05-28 | Treat Magnets as observability probes, not agents | Prevents noisy, expensive, self-directed monitor agents | Accepted |
| 2026-05-28 | Add Sandbox Lab before integrating OpenHuman/Hermes/OpenHands | Prevents experimental agents from contaminating core scaffold | Accepted |
