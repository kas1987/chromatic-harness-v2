# Prism → Chromatic Harness v2 Migration
Date: 2026-06-16

## Decision
Migrate control-plane pieces from C:\.04_Prism into chromatic-harness-v2. Archive product repos individually. Delete .04_Prism.

## Scope: What Moves
| Source (C:\.04_Prism) | Destination (chromatic-harness-v2) |
|---|---|
| gen/ (Node routing service) | 02_RUNTIME/gen/ |
| docs/architecture/MODEL-DISPATCH-GATEWAY.md | docs/architecture/ |
| docs/governance/ | docs/governance/ (merge) |
| docs/superpowers/specs/ | docs/superpowers/specs/ (merge) |
| gen/src/routes/routing-matrix.json | docs/routing/ |

## Scope: What Stays Separate
ml-pipeline, rudalo, rudalo-ui, Whisper-Prism, codex-ccs, platform/, products/, prism_* — each tagged in .04_Prism git history before deletion.

## Migration Approach
- Clean copy (no git history preservation)
- Product repos individually tagged: archive/2026-06-16-<name>
- .04_Prism final snapshot tag: archive/2026-06-16-prism-full
- .04_Prism directory deleted after verification

## Reference Updates
- multi-router-matrix.yaml: gen_routing_matrix and gen_gateway_doc paths updated to harness-v2 locations
- estate.repos.json: .04_Prism marked status=ARCHIVED
