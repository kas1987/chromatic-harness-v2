# Budget Operations Runbook

## Scenario 1: Task blocked — "Daily token budget exceeded"

**Symptom:** Task receives 403 from Gen with `stopReason: "budget_exceeded"` and wall-time has not expired.

**Immediate action (5 min):**
1. Check current daily token spend: `GET http://localhost:43123/budget/daily-summary`
2. Identify which tasks consumed budget: query `budget_states` table
3. If legitimate overage: switch to Ollama mode (`POST /admin/budget-policy { "policy": "normalized" }`)
4. If bug: kill hung task (`DELETE /tasks/:id`) and investigate

**Root cause investigation:**
- Check for runaway loops: `grep "incrementTokens" gen/logs/*.log | tail -50`
- Check if daily reset fired: `SELECT * FROM daily_budget_reset ORDER BY last_reset_at DESC LIMIT 5;`

**Recovery:**
- Manual reset: `UPDATE daily_budget_reset SET last_reset_date = '1970-01-01';` (forces reset on next request)
- Switch to aggressive mode with Ollama fallback: `BUDGET_POLICY=aggressive`

---

## Scenario 2: Cost spike — Model spend approaching monthly limit

**Symptom:** Alert fires: "Monthly model budget 80% consumed for GPT"

**Immediate action:**
1. Check current spend: query `budget_allocations` table for `spent_usd / (pct/100 * totalMonthly)`
2. Switch to cheaper model: `POST /admin/budget-policy { "policy": "aggressive" }` — auto-routes to Gemini/Ollama
3. Check cost prediction accuracy: are estimates within 20% of actuals?

**Prevention:**
- Set `BUDGET_POLICY=aggressive` for batch jobs
- Review tasks classified as "complex" routing to Claude — consider reclassifying

---

## Scenario 3: Token counting gap — Budget shows 0 tokens despite activity

**Symptom:** `budget_states.tokens_used` stays at 0 despite active generation.

**Diagnosis:**
1. Check if Claude API returns `tokens` in response: `grep "token_count\|tokens" gen/logs/*.log | head -20`
2. Check for token counting errors: `grep "Failed to record token count" gen/logs/*.log`
3. Verify `budget_states` is being updated: `SELECT task_id, tokens_used FROM budget_states WHERE stopped = 0;`

**Fix:**
- If Claude API response format changed, update extraction in PostToolUse hook
- If DB write failing, check SQLite file permissions

---

## Scenario 4: Daily reset not firing

**Symptom:** Tokens accumulate across days; `getTokensUsedToday()` returns stale data.

**Diagnosis:**
```sql
SELECT * FROM daily_budget_reset;
-- Should show today's date in last_reset_date
```

**Fix:**
- Force reset: `UPDATE daily_budget_reset SET last_reset_date = '1970-01-01';`
- Restart Gen service (BudgetStore constructor calls dailyReset())

---

## Scenario 5: BUDGET_POLICY env var ignored

**Symptom:** Switched to `aggressive` but tasks still use lenient thresholds.

**Diagnosis:**
1. Check current policy: `GET /admin/budget-policy`
2. Verify env var is set: in the Gen process environment, `echo $BUDGET_POLICY`
3. Check if runtime switch was applied: `grep "Policy changed" gen/logs/*.log`

**Fix:**
- Use runtime switch (not just env var): `POST /admin/budget-policy { "policy": "aggressive" }`
- Restart Gen if env var was changed after process start

---

## Monitoring Queries

```sql
-- Daily token spend by role
SELECT agent_role, SUM(tokens_used) as total_tokens
FROM budget_states
WHERE DATE(started_at) = DATE('now')
GROUP BY agent_role;

-- Cost by model this month
SELECT model, spent_usd, pct,
  ROUND(spent_usd / (pct/100.0 * 50), 2) as pct_of_allocation
FROM budget_allocations
WHERE month = strftime('%Y-%m', 'now')
ORDER BY spent_usd DESC;

-- Tasks near budget ceiling
SELECT task_id, agent_role, tokens_used,
  ROUND(tokens_used * 100.0 / 50000, 1) as pct_of_limit
FROM budget_states
WHERE stopped = 0 AND tokens_used > 40000
ORDER BY tokens_used DESC;
```
