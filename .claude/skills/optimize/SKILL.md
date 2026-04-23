---
name: optimize
description: AI performance optimization loop - find optimizations, benchmark, accept or rollback
argument-hint: file or directory to optimize
user-invokable: true
---

# AI Performance Optimization Loop

You are a performance optimization expert operating within a **Stateless Function** architecture. You receive complete context, propose single optimizations, and the external orchestrator handles all state management.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR (Python)                       │
│  - State persistence via .optimizer_state.json               │
│  - Git worktree isolation                                     │
│  - Graveyard of failed optimizations                          │
│  - Statistical benchmark comparison                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM (Stateless - YOU)                     │
│  Input: code + tests + graveyard warnings                    │
│  Output: single optimization diff                             │
└─────────────────────────────────────────────────────────────┘
```

## Core Principles

1. **You are stateless** - Every call receives complete context
2. **One optimization at a time** - Focus on a single, specific improvement
3. **Never change behavior** - Output must remain identical for identical inputs
4. **Avoid graveyard failures** - Do not repeat previously failed approaches

## Execution Loop

### Step 1: Initialize State

Read and update `.optimizer_state.json`:

```json
{
  "iteration": 0,
  "total_attempted": 0,
  "total_accepted": 0,
  "total_rejected": 0,
  "current_target": null,
  "current_phase": "idle",
  "total_improvement": 0.0,
  "baseline_benchmark": null,
  "current_benchmark": null
}
```

### Step 2: Prepare Environment

1. Create Git checkpoint:
   ```bash
   git add -A && git commit -m "checkpoint: before optimization" --allow-empty
   ```

2. Identify target files at `$ARGUMENTS`

3. Check for existing tests:
   - `.unit_tests/` - Unit tests for semantic verification
   - `.perf_tests/` - Performance benchmarks

4. If no tests exist, generate them by running:
   ```bash
   python .claude/skills/optimize/tools/generate_tests.py <target>
   ```

### Step 3: Read Graveyard Warnings

Read `optimization_graveyard.json` to see failed attempts:

```json
{
  "entries": [
    {
      "file_path": "example.py",
      "diff_hash": "abc123",
      "failure_type": "unit_test",
      "failure_reason": "Changed output for edge case",
      "optimization_type": "caching"
    }
  ]
}
```

**CRITICAL**: Do NOT propose similar optimizations to those in the graveyard.

### Step 4: Analyze and Propose Optimization

Read target code and analyze for optimization opportunities:

**Optimization Categories**:
- `algorithm` - Algorithmic complexity improvements (O(n²) → O(n log n))
- `memory` - Memory allocation, data structure optimizations
- `caching` - Add caching/memoization
- `io` - I/O operations, buffering
- `loop` - Loop optimizations, vectorization

**Analysis Checklist**:
1. Identify hot paths (frequently called functions)
2. Look for nested loops (O(n²) or worse)
3. Check for repeated computations
4. Find unnecessary allocations
5. Look for I/O that could be batched

### Step 5: Generate Diff

Output a **single, focused optimization** as a unified diff:

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,5 +10,6 @@
 def process_items(items):
+    # Cache for repeated lookups
     result = []
     for item in items:
-        value = expensive_lookup(item)
+        value = lookup_cache.get(item) or expensive_lookup(item)
         result.append(value)
```

**Rules**:
1. Minimal changes - only what's needed for the optimization
2. Preserve all error handling
3. Keep all edge case behavior
4. No hardcoding of values

### Step 6: Apply and Verify

Apply the diff in an isolated Git worktree:

```bash
# Create isolated worktree
git worktree add -b opt-run-<timestamp> .opt-worktrees/run-<timestamp> HEAD

# Apply diff
git apply <patch-file>

# Run unit tests
python -m pytest .unit_tests/ -v
```

If tests fail:
1. Record failure in `optimization_graveyard.json`
2. Discard worktree: `git worktree remove --force`
3. Return to Step 4 with a DIFFERENT approach

### Step 7: Statistical Benchmark

Run rigorous benchmark comparison:

```bash
python .claude/skills/optimize/tools/run_benchmark.py \
    "<benchmark-command>" \
    --iterations 10 \
    --warmup 3 \
    --alternating
```

**Acceptance Criteria** (BOTH required):
1. p-value < 0.05 (statistically significant)
2. Improvement > 2% (practically meaningful)

### Step 8: Decision

**If optimization succeeds**:
```bash
git add -A && git commit -m "optimize: <description> (+X%)"
# Clear graveyard entries for this file
```

**If optimization fails**:
```bash
# Record in graveyard
git worktree remove --force
git branch -D opt-run-<timestamp>
```

### Step 9: Report and Continue

Update state file and report:

```
=== Optimization Report ===
Iteration: X
Phase: <current_phase>
Attempted: Y
Accepted: Z
Rejected: W
Total Improvement: A%
===========================
```

**NEVER STOP** unless user explicitly requests. Continue to Step 4.

## Pitfall Prevention

### 1. Behavior Drift & Overfitting
- **NEVER** remove error handling
- **NEVER** hardcode values that should be computed
- **NEVER** skip edge cases
- Always run unit tests before accepting

### 2. Benchmark Noise
- Use alternating A/B/A/B pattern
- Require p-value < 0.05
- Require improvement > 2%
- Use multiple iterations (minimum 10)

### 3. Amnesia Loop
- Always check graveyard before proposing
- Do not repeat failed optimization types
- If similar code pattern failed, try different approach

### 4. Workspace Corruption
- Always use Git worktrees for isolation
- Never modify main branch directly
- Always rollback on any failure

## State File Schema

`.optimizer_state.json`:
```json
{
  "iteration": 0,
  "total_attempted": 0,
  "total_accepted": 0,
  "total_rejected": 0,
  "current_target": "path/to/file.py",
  "current_phase": "proposing_optimization",
  "last_error": null,
  "started_at": "2024-01-01T00:00:00",
  "last_update": "2024-01-01T00:01:00",
  "total_improvement": 0.0,
  "baseline_benchmark": {"mean": 1.5, "stdev": 0.1},
  "current_benchmark": {"mean": 1.2, "stdev": 0.1}
}
```

## Graveyard Schema

`optimization_graveyard.json`:
```json
{
  "version": 1,
  "entries": [
    {
      "timestamp": "2024-01-01T00:00:00",
      "file_path": "example.py",
      "diff_hash": "sha256hash",
      "diff_content": "...",
      "failure_type": "unit_test|benchmark|syntax|no_improvement",
      "failure_reason": "...",
      "error_details": "...",
      "optimization_type": "algorithm|memory|caching|io|loop"
    }
  ]
}
```

## Quick Reference Commands

```bash
# Check current status
python .claude/skills/optimize/orchestrator.py <target> --status

# Generate tests
python .claude/skills/optimize/tools/generate_tests.py <target>

# Run semantic verification
python .claude/skills/optimize/tools/verify_semantics.py <target>

# Run benchmark
python .claude/skills/optimize/tools/run_benchmark.py "<command>" -n 10

# Analyze for opportunities
python .claude/skills/optimize/tools/propose_patch.py <target> --analyze
```

## Start Now

1. Read `.optimizer_state.json` (or initialize)
2. Read `optimization_graveyard.json` (or initialize)
3. Analyze target code at `$ARGUMENTS`
4. Begin optimization loop
