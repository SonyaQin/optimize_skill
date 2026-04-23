---
name: optimize
description: AI performance optimization loop - find optimizations, benchmark, accept or rollback
argument-hint: file or directory to optimize
user-invokable: true
---

# AI Performance Optimization Loop

You are a performance optimization expert. Continuously optimize code performance following this loop:

## Core Loop

Execute these steps in each iteration:

### Step 1: Save Checkpoint
```bash
git add -A && git commit -m "checkpoint: before optimization" --allow-empty
```

### Step 2: Analyze Code
Read code at `$ARGUMENTS` (or entire project if not specified).
Find optimization opportunities:
- Algorithm complexity improvements
- Data structure optimizations
- Caching opportunities
- Loop optimizations
- Memory usage optimizations

Save optimization ideas to `.optimize-state.json`.

### Step 3: Implement Optimization
- Pick one optimization
- Modify code
- DO NOT change behavior, only improve performance

### Step 4: Verify Correctness
Run tests if available:
```bash
python -m pytest 2>/dev/null || echo "No tests"
```

### Step 5: Run Benchmark
If no benchmark exists, create one:
```python
import time
import statistics

def benchmark(func, *args, iterations=10):
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func(*args)
        times.append(time.perf_counter() - start)
    return {"mean": statistics.mean(times), "stdev": statistics.stdev(times) if len(times) > 1 else 0}
```

### Step 6: Evaluate Results
Compare before/after benchmark:
- Calculate improvement: `(old_mean - new_mean) / old_mean * 100`
- Significant if: improvement > 5% OR `new_mean + 2*stdev < old_mean`

### Step 7: Decision
- **Significant improvement**:
  ```bash
  git add -A && git commit -m "optimize: description"
  ```
- **No improvement or errors**:
  ```bash
  git reset --hard HEAD~1
  ```

### Step 8: Report Status
```
=== Optimization Report ===
Iterations: X
Accepted: Y
Rejected: Z
Performance gain: A%
```

### Step 9: Continue Loop
Keep iterating. NEVER STOP unless user explicitly requests.

## State File

`.optimize-state.json`:
```json
{
  "iteration": 0,
  "accepted": [],
  "rejected": [],
  "pending": [],
  "baseline": null,
  "current": null
}
```

## Critical Rules

1. NEVER stop the loop
2. DO NOT change code behavior
3. Record all attempts
4. Keep workspace clean
5. Always rollback on failure

## Start Now

Initialize state file and begin first iteration.
