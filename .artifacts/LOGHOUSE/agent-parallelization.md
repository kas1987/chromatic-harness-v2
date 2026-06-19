# Agent Parallelization Guide
**+25% throughput via forked agent parallelization for independent operations**

**Status:** Implemented | Template Ready | Examples: git fetch, grep, npm install  
**Location:** `~/.claude/templates/parallel-ops-template.md` | `~/.claude/bin/`

---

## Quick Start

### Scenario: Parallel Git Fetch (3 repos)
```bash
# Sequential: 15+ seconds
git fetch /repo1          # 5s
git fetch /repo2          # 5s
git fetch /repo3          # 5s
# Total: 15s

# Parallel (Agent Forks): 6 seconds
fork agent 1: git fetch /repo1
fork agent 2: git fetch /repo2
fork agent 3: git fetch /repo3
# All concurrent: ~5s
# With overhead: ~6s total
# Speedup: 2.5x ✅
```

---

## When to Parallelize

### ✅ Good Candidates (2-3x speedup)

**1. Git Operations** (Highest ROI)
- Examples: git fetch, git clone, git pull across repos
- Sequential time: 3-10s per repo
- Overhead breakeven: 3 repos
- Speedup: 2-3x
```
Candidates:
├─ Multi-repo sync (fetch all projects)
├─ Mass cloning (bootstrap new env)
├─ Parallel branch creation (CI/CD prep)
└─ Distributed rebasing (long-running)
```

**2. Package Installation** (High ROI)
- Examples: npm install, pip install multiple projects
- Sequential time: 10-60s per project
- Overhead breakeven: 2-3 projects
- Speedup: 2-3x
```
Candidates:
├─ Install monorepo dependencies
├─ Install build tools/SDKs
├─ Setup CI environment
└─ Docker build parallel stages
```

**3. File Scanning** (Medium ROI)
- Examples: grep across large repos, glob patterns, find operations
- Sequential time: 2-5s per scan
- Overhead breakeven: 5+ scans
- Speedup: 1.5-2x
```
Candidates:
├─ Multi-pattern grep (search, codemod)
├─ Parallel linting (multiple dirs)
├─ Distributed test discovery
└─ Large file processing
```

### ⚠️ Borderline Cases (1-2x speedup)

**4. Test Execution** (Depends on suite size)
- Examples: Run test suites in parallel shards
- Sequential time: 30-120s per shard
- Overhead breakeven: 3+ shards
- Speedup: 1.5-2.5x
- ⚠️ Watch for: flaky tests, race conditions, shared state

**5. Docker/Build Operations** (High overhead)
- Examples: Build multiple images, multi-stage builds
- Sequential time: 30-300s per image
- Overhead breakeven: 2+ images
- Speedup: 2-3x
- ⚠️ Watch for: resource limits, disk I/O

### ❌ Poor Candidates (Not worth it)

**DON'T parallelize if:**
- Sequential time < 5 seconds (overhead kills savings)
- Tasks have dependencies (sequential required)
- CPU-intensive work (ML, compression)
- Shared state (race conditions, conflicts)
- <3 operations (setup cost too high)

---

## Architecture & Overhead

### Per-Agent Costs
```
Fork agent lifecycle:
├─ Startup: 200-300ms (context init, prompt transmission)
├─ Execution: Variable (depends on operation)
├─ Aggregation: 100-200ms (result collection)
└─ Total overhead: ~500ms per agent
```

### Concurrency Limits
```
Per-session concurrency: ~16 agents (CPU cores - 2)
Global agent cap: 1000 agents per workflow (prevent runaway)
Queueing: Agents queue if >16 concurrent (no blocking)
```

### Decision Matrix

| Operation Count | Avg Time/Op | Sequential | Parallel | Overhead | Speedup | Recommendation |
|-----------------|-------------|-----------|----------|----------|---------|-----------------|
| 2               | 5s          | 10s       | 5.5s     | 1s       | 1.8x    | Maybe (cost/benefit borderline) |
| 3               | 5s          | 15s       | 5.5s     | 1.5s     | 2.7x    | ✅ Yes (good ROI) |
| 5               | 5s          | 25s       | 5.5s     | 2.5s     | 4.5x    | ✅ Yes (excellent ROI) |
| 10              | 5s          | 50s       | 5.5s     | 5s       | 9x      | ✅ Yes (huge ROI) |
| 10              | 0.5s        | 5s        | 2.5s     | 5s       | 2x      | ✅ Yes (still worth it) |
| 10              | 0.2s        | 2s        | 5.5s     | 5s       | 0.36x   | ❌ No (overhead too high) |

**Rule:** If sequential > 10 seconds OR operations >= 5, parallelize.

---

## Implementation Examples

### Example 1: Parallel Git Fetch

**Sequential Approach:**
```bash
for repo in /repo1 /repo2 /repo3 /repo4 /repo5; do
  git -C $repo fetch
done
# ~25 seconds
```

**Parallel Approach (Agent Forks):**
```javascript
const repos = ['/repo1', '/repo2', '/repo3', '/repo4', '/repo5'];

const results = await Promise.all(
  repos.map(repo => 
    agent(`Execute: git -C ${repo} fetch`, {
      subagent_type: 'fork',
      label: `git-fetch-${basename(repo)}`
    })
  )
);

// Results aggregated automatically
// ~6 seconds (5s operation + 1s overhead)
// Speedup: 4.2x
```

### Example 2: Parallel Grep Across Repos

**Sequential:**
```bash
grep -r "pattern1" /repo1
grep -r "pattern1" /repo2
grep -r "pattern1" /repo3
# 15 seconds
```

**Parallel (Agent Forks):**
```javascript
const repos = ['/repo1', '/repo2', '/repo3'];
const patterns = ['pattern1', 'pattern2'];

const results = await Promise.all(
  repos.flatMap(repo =>
    patterns.map(pattern =>
      agent(`Grep: grep -r "${pattern}" ${repo}`, {
        subagent_type: 'fork'
      })
    )
  )
);

// 6 operations in parallel
// ~5 seconds (longest grep + overhead)
// Speedup: 3x
```

### Example 3: Parallel npm Install

**Sequential:**
```bash
cd /project1 && npm install   # 30s
cd /project2 && npm install   # 40s
cd /project3 && npm install   # 35s
# 105 seconds
```

**Parallel (Agent Forks):**
```javascript
const projects = ['/project1', '/project2', '/project3'];

const results = await Promise.all(
  projects.map(project =>
    agent(`cd ${project} && npm install`, {
      subagent_type: 'fork',
      timeout: 120000
    })
  )
);

// Max time: 40s (longest install)
// Total with overhead: 42s
// Speedup: 2.5x
```

---

## Cost-Benefit Analysis

### Speedup Formula
```
T_seq = sum of individual operation times
T_par = max(individual times) + overhead
Speedup = T_seq / T_par
Efficiency = Speedup / num_agents (100% = perfect scaling)
```

### Example: 5 git fetches (5s each)
```
T_seq = 5 × 5s = 25s
T_par = 5s + 2.5s (overhead) = 7.5s
Speedup = 25 / 7.5 = 3.3x ✅
Efficiency = 3.3 / 5 = 66% (good)
```

### Example: 10 small operations (0.5s each)
```
T_seq = 10 × 0.5s = 5s
T_par = 0.5s + 5s (overhead) = 5.5s
Speedup = 5 / 5.5 = 0.9x ❌
Efficiency = 0.9 / 10 = 9% (poor)
→ Don't parallelize
```

---

## Tools & Templates

### Template Files
- **`~/.claude/templates/parallel-ops-template.md`**
  - When/how to parallelize
  - Architecture overview
  - Error handling patterns
  - Decision matrix

### Generator Tools
- **`~/.claude/bin/parallel-template-generator.js`**
  - Generates fork prompts for any command
  - Calculates speedup/efficiency
  - Creates aggregator code
  - Usage: `node parallel-template-generator.js "command" target1 target2 ...`

### Example Scripts
- **`~/.claude/bin/parallel-git-fetch.sh`**
  - Ready-to-use git fetch parallelization
  - Color output, timing, efficiency report
  - Usage: `./parallel-git-fetch.sh /repo1 /repo2 /repo3`

---

## Best Practices

### 1. Isolation
- Each fork must be independent
- No shared state between operations
- No assumptions about other forks' progress

### 2. Error Handling
```javascript
// Soft failure: continue despite some errors
const results = await Promise.allSettled(forks);
const successful = results.filter(r => r.status === 'fulfilled');
const failed = results.filter(r => r.status === 'rejected');

console.log(`${successful.length} succeeded, ${failed.length} failed`);

// Hard failure: abort on first error
const results = await Promise.all(forks);  // throws if any fails
```

### 3. Monitoring
- Track per-agent elapsed time
- Measure actual vs. predicted speedup
- Monitor for straggler agents (slow outliers)
- Log all fork execution details

### 4. Scaling Safely
- Start with 3 agents, measure overhead
- Don't exceed 16 concurrent agents (CPU cores - 2)
- Use queue if >16 agents needed
- Monitor memory usage during large fan-outs

---

## Troubleshooting

### Agent takes too long?
- Check if operation is CPU-bound (not parallelizable)
- Verify network conditions (for git/downloads)
- Look for straggler agents with high latency

### Not getting expected speedup?
- Measure actual sequential time (not estimate)
- Account for overhead: 500ms per agent
- Check if operations have hidden dependencies
- Verify all agents can run concurrently

### Results inconsistent/missing?
- Ensure aggregator collects ALL results
- Use Promise.allSettled (not Promise.all) for robustness
- Check error handling and timeouts
- Log fork completion status

---

## Roadmap & Future Enhancements

### Phase 1 (Now)
- ✅ Template creation
- ✅ Example: git fetch
- ✅ Parallel template generator

### Phase 2 (Next)
- [ ] Automatic speedup prediction
- [ ] Agent pool pre-warming (reduce startup overhead)
- [ ] Monitoring dashboard integration
- [ ] Multi-pattern grep optimization

### Phase 3 (Future)
- [ ] ML model for speedup prediction
- [ ] Automatic parallelization suggestions
- [ ] Distributed execution (spawn agents across machines)
- [ ] Cloud-native support (AWS Lambda, GCP Functions)

---

## Appendix: Formula Reference

```
Speedup (S) = T_sequential / T_parallel
Efficiency (E) = S / N_agents × 100%

Breakeven point: where S = 1
  T_seq = T_op + (N × overhead)
  
Optimal N_agents = min(N_ops, CPU_cores - 2)

Max theoretical speedup: N_agents (linear scaling)
Practical speedup: 2-4x (sublinear, due to overhead + Amdahl)
```

---

**Agent Parallelization Ready** | Use templates in `~/.claude/templates/` | Examples in `~/.claude/bin/`
