# SOP-001: Pre-Mission Planning Gate

**Document:** Procedure  
**Version:** 1.0  
**Effective Date:** 2026-06-19  
**Owner:** User + Audit Agent  
**Estimated Duration:** 15 minutes

---

## Purpose

Establish a clear plan before any significant development mission begins. The PDR (Project Definition Record) is the baseline for measuring success and managing scope.

---

## Scope

**Applies to:**
- ✅ Development missions >30 min planned duration
- ✅ Multiple-objective work
- ✅ All work involving agent-assisted tasks

**Does NOT apply to:**
- ❌ Quick lookups (<5 min)
- ❌ Single objective, <15 min work
- ❌ Pure documentation or reading

---

## Trigger

**Event:** SessionStart hook  
**Automatic?** Yes — pre-session hook fires automatically  
**Manual override?** Optional: User can run `bash ~/.claude/hooks/mission-planning-gate.sh` anytime

---

## Procedure Steps

### Step 1: Hook Fires (Automatic)
**Actor:** Governance Bot (via SessionStart hook)  
**Input:** Current date (YYYY-MM-DD)  
**Output:** PDR template created at `.artifacts/LOGHOUSE/missions/YYYY-MM-DD-pdr.md`

**Hook Script:**
```bash
#!/bin/bash
# Pre-session mission planning gate
LOGHOUSE_PATH="$HOME/chromatic-harness-v2/.artifacts/LOGHOUSE"
MISSIONS_PATH="$LOGHOUSE_PATH/missions"
TIMESTAMP=$(date +%Y-%m-%d)
PDR_FILE="$MISSIONS_PATH/$TIMESTAMP-pdr.md"

mkdir -p "$MISSIONS_PATH"

if [ ! -f "$PDR_FILE" ]; then
    echo "📋 No PDR found for today. Creating template..."
    cat > "$PDR_FILE" << 'EOF'
# Mission PDR - [YYYY-MM-DD]
**Start Time:** [HH:MM UTC]  
**Projected Duration:** ___ hours  
**Planned Scope:**  
- [ ] Objective 1  
- [ ] Objective 2  

**Success Metrics:**  
- Metric 1: ___  
- Metric 2: ___  
- Metric 3: ___  

**Risk Register:**  
1. Risk: ___ | Probability: High/Medium/Low | Impact: High/Medium/Low | Mitigation: ___  
2. Risk: ___ | ...  
3. Risk: ___ | ...  
4. Risk: ___ | ...  
5. Risk: ___ | ...  

**Team Composition:**  
- Lead: ___  
- Resources: ___  

**Notes:**  
EOF
    echo "✅ PDR template created: $PDR_FILE"
fi

# Validation: Check PDR content (NEW — added per audit recommendation)
echo "🔍 Validating PDR content..."

# Check 1: Projected Duration is filled and > 0
if ! grep -q "Projected Duration:.*[1-9]" "$PDR_FILE"; then
    echo "❌ ERROR: Projected Duration must be filled (>0 hours)"
    echo "   Please edit: $PDR_FILE"
    exit 1
fi

# Check 2: Planned Scope has ≥2 objectives
SCOPE_COUNT=$(grep -c "- \[ \]" "$PDR_FILE" || echo "0")
if [ "$SCOPE_COUNT" -lt 2 ]; then
    echo "❌ ERROR: Planned Scope requires ≥2 objectives"
    echo "   Current: $SCOPE_COUNT. Please edit: $PDR_FILE"
    exit 1
fi

# Check 3: Success Metrics has ≥3 entries
METRIC_COUNT=$(grep -c "Metric [0-9]:" "$PDR_FILE" || echo "0")
if [ "$METRIC_COUNT" -lt 3 ]; then
    echo "❌ ERROR: Success Metrics requires ≥3 entries"
    echo "   Current: $METRIC_COUNT. Please edit: $PDR_FILE"
    exit 1
fi

# Check 4: Risk Register has ≥3 risks
RISK_COUNT=$(grep -c "^[0-9]\." "$PDR_FILE" || echo "0")
if [ "$RISK_COUNT" -lt 3 ]; then
    echo "❌ ERROR: Risk Register requires ≥3 identified risks"
    echo "   Current: $RISK_COUNT. Please edit: $PDR_FILE"
    exit 1
fi

echo "✅ PDR validation PASSED"
echo ""
echo "📊 Pre-Mission Checklist:"
echo "   ✓ Timeline estimated (hours)"
echo "   ✓ Scope defined (≥2 objectives)"
echo "   ✓ Success metrics listed (≥3)"
echo "   ✓ Risks identified (≥3)"
echo ""
echo "🚀 Mission Context Loaded"
echo "   PDR: $PDR_FILE"
echo "   Archive: $LOGHOUSE_PATH"
echo ""
echo "ℹ️  Next step: Proceed with mission work. PDR is your baseline."
```

### Step 2: User Completes PDR (Manual)
**Actor:** User  
**Duration:** 10-15 minutes  
**Input:** Mission requirements, timeline estimate, identified risks  
**Output:** Completed PDR file with all fields filled

**Checklist:**
- [ ] **Projected Duration** — Realistic estimate (hours); not a guess
- [ ] **Planned Scope** — ≥2 specific objectives; can include sub-bullets
- [ ] **Success Metrics** — ≥3 quantifiable or qualifiable measures
  - Example: "✓ All audit reports generated and stored in LOGHOUSE"
  - Example: "✓ Code review finds <3 CONFIRMED bugs"
  - Example: "✓ Timeline variance <30%"
- [ ] **Risk Register** — ≥3 specific risks with probability/impact/mitigation
  - Example: "Risk: Apt dependency conflicts | Prob: Medium | Impact: High | Mit: Pre-test install in sandbox"
  - Example: "Risk: Scope creep | Prob: High | Impact: Medium | Mit: User approval gate for >20% expansion"
  - Example: "Risk: Agent hallucination on code review | Prob: Low | Impact: High | Mit: 1-vote verification + manual spot-check"
- [ ] **Team Composition** — Who is involved? What is each person's role?
- [ ] **Notes** — Any special constraints, dependencies, or context?

### Step 3: User Approves PDR (or Revises)
**Actor:** User  
**Decision:** Go/No-Go  
**Output:** PDR approved (git commit) or returned for revision

**If APPROVED:**
- Commit PDR to git: `git add .artifacts/LOGHOUSE/missions/YYYY-MM-DD-pdr.md && git commit -m "feat: mission PDR approved — YYYY-MM-DD"`
- Proceed with mission work

**If REVISION NEEDED:**
- Edit PDR file
- Re-run validation: `bash ~/.claude/hooks/mission-planning-gate.sh`
- Resubmit for approval

**If REJECTED:**
- Don't start the mission
- Document the decision (why rejected?)
- Use learnings for next mission

---

## Quality Gates (Acceptance Criteria)

| Gate | Criterion | Measurement | Pass/Fail |
|------|-----------|-------------|-----------|
| **G1: Timeline** | Projected Duration > 0 | File contains numeric value | FAIL if missing or 0 |
| **G2: Scope** | ≥2 objectives listed | Count "- [ ]" bullets | FAIL if <2 |
| **G3: Metrics** | ≥3 success metrics | Count "Metric N:" lines | FAIL if <3 |
| **G4: Risks** | ≥3 risks identified | Count "N. Risk:" lines | FAIL if <3 |
| **G5: Mitigation** | Each risk has mitigation | Check "Mitigation:" field for each risk | FAIL if any risk missing mitigation |
| **G6: Sign-Off** | User approval recorded | PDR commit to git with message | FAIL if not committed |

---

## Escalation (If Gates Fail)

| Failure | Action | Decision Authority |
|---------|--------|-------------------|
| Projected Duration empty | Return PDR for revision | User |
| Scope <2 objectives | Return PDR; too narrow, discuss expansion | User + Audit Agent |
| Metrics <3 | Return PDR; success criteria must be measurable | User |
| Risks <3 | Return PDR; re-identify risks (use risk checklist if needed) | User |
| All gates pass, but User concerned | Optional: escalate to Audit Agent for pre-mission risk review | User |

---

## Success Criteria (SOP Completion)

**This SOP is successful if:**
1. ✅ PDR template created automatically at SessionStart
2. ✅ All validation gates (G1-G6) pass
3. ✅ PDR is committed to git before mission work begins
4. ✅ Timeline, scope, metrics, risks are explicit (not blank templates)
5. ✅ No mission work starts without approved PDR

---

## Exception Handling

**Case: User starts working before completing PDR**
- Audit Agent monitors for git commits without PDR in place
- If detected: Escalate to User for retroactive PDR completion
- Future missions: Pre-commit hook prevents commits without valid PDR (not yet implemented)

**Case: Mission scope changes mid-mission**
- Create a Change Request (CR) artifact: `.artifacts/LOGHOUSE/missions/YYYY-MM-DD-cr-N.md`
- For expansions >20%: Escalate to Audit Agent for mid-mission checkpoint
- At post-mission audit: Compare original PDR vs actual; document reason for each CR

---

## Related Documents

- **Charter:** audit-committee-charter.md §1 Pre-Mission Planning Review
- **Template:** templates/mission-pdr-template.md
- **Example:** templates/mission-pdr-example-filled.md
- **Related SOP:** SOP-002-execution-monitoring.md (mid-mission checkpoints)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-19 | Initial version; added content validation gates |

---

**Approved By:** Audit Committee  
**Last Updated:** 2026-06-19  
**Next Review:** 2026-09-19
