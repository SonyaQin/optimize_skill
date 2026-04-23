# Auto-Optimizer Skill

A robust, infinite-loop performance optimization system for Claude Code that treats the LLM as a "stateless function" while a Python orchestrator manages all state, preventing the common pitfalls of LLM-based automation.

## Architecture

The key insight: **LLMs have limited context and will inevitably forget rules or repeat mistakes in long-running loops.** The solution is to use:

- **Stateful Orchestrator (Python)** - Manages state, coordinates phases, persists data
- **Stateless LLM** - Receives complete context, outputs single optimization proposals
- **Git as State Machine** - Single source of truth for code state

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR (Stateful)                      │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Phase 1  │─▶│ Phase 2  │─▶│ Phase 3  │─▶│ Phase 4  │─┐      │
│  │Env Prep  │  │Propose   │  │Verify    │  │Benchmark │ │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │      │
│       ▲                                          │       │      │
│       └──────────────────────────────────────────┘       │      │
│                                                          ▼      │
│                                                   ┌──────────┐  │
│                                                   │ Phase 5  │  │
│                                                   │Persist   │  │
│                                                   └──────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Dual-Track Verification
- **Unit Tests**: Verify semantic behavior is preserved
- **Benchmarks**: Measure performance with statistical rigor
- Both must pass for an optimization to be accepted

### 2. Statistical Benchmarking
- A/B/A/B alternating pattern to eliminate time-based noise
- Welch's t-test for comparing means with unequal variances
- Requires BOTH p-value < 0.05 AND improvement > threshold

### 3. Graveyard of Failed Optimizations
- Records every failed attempt with reason and diff
- Injects warnings into LLM prompts to prevent repetition
- Prevents the "Amnesia Loop" problem

### 4. Git Sandbox Isolation
- Every optimization runs in an isolated Git worktree
- Main branch is never directly modified
- Failed experiments are completely discarded

## Supported Languages

The optimizer supports multiple programming languages with varying levels of functionality:

| Language | Function Parsing | Unit Tests | Benchmark | Semantic Verification |
|----------|-----------------|------------|-----------|----------------------|
| **Python** | ✅ Full | ✅ pytest | ✅ | ✅ |
| **C/C++** | ✅ Full | ✅ Google Test | ✅ Google Benchmark | ⚠️ Custom command |
| **JavaScript** | ✅ Full | ⚠️ Jest/Mocha | ⚠️ Basic | ⚠️ npm test |
| **TypeScript** | ✅ Full | ⚠️ Jest | ⚠️ Basic | ⚠️ npm test |
| **Go** | ✅ Full | ⚠️ go test | ⚠️ Basic | ⚠️ go test |
| **Rust** | ✅ Full | ⚠️ cargo test | ⚠️ Basic | ⚠️ cargo test |
| **Java** | ✅ Full | ⚠️ JUnit | ⚠️ JMH | ⚠️ mvn test |

### Language-Agnostic Features

These core features work for **all languages**:

- ✅ Git sandbox isolation (worktrees)
- ✅ Graveyard of failed optimizations
- ✅ Statistical benchmarking (Welch's t-test)
- ✅ A/B alternating test pattern
- ✅ Diff generation and application

### C/C++ Setup

```bash
# Ubuntu/Debian
sudo apt install libgtest-dev libbenchmark-dev

# macOS
brew install googletest google-benchmark

# Generate tests
python .claude/skills/optimize/tools/generate_tests.py src/sort.cpp

# Build and run tests
g++ -std=c++17 .unit_tests/test_sort.cpp -lgtest -lgtest_main -pthread -o test_runner
./test_runner
```

### Custom Test Commands

For languages other than Python, configure custom test commands:

```bash
# C++ with CMake
python orchestrator.py src/ --test-command "ctest --output-on-failure"

# JavaScript/TypeScript
python orchestrator.py src/ --test-command "npm test"

# Go
python orchestrator.py src/ --test-command "go test ./..."

# Rust
python orchestrator.py src/ --test-command "cargo test"

# Java
python orchestrator.py src/ --test-command "mvn test"
```

## Installation

### From Claude Code Marketplace

Install directly from the Git repository URL:

```bash
# In Claude Code, run:
/install https://github.com/SonyaQin/optimize_skill
```

Or add to your project's `.claude/settings.local.json`:

```json
{
  "marketplace": [
    "https://github.com/SonyaQin/optimize_skill"
  ]
}
```

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/SonyaQin/optimize_skill.git
```

2. Copy the skill to your project:
```bash
cp -r auto-optimizer/.claude/skills/optimize your-project/.claude/skills/
```

3. Install Python dependencies:
```bash
pip install scipy
```

### Requirements

- Python 3.8+
- Git
- scipy (optional, for statistical tests)

## Usage

### Basic Usage

Invoke the skill from Claude Code:

```
/optimize <file-or-directory>
```

### Configuration Options

The orchestrator supports various configuration options:

```bash
# Run with custom settings
python .claude/skills/optimize/orchestrator.py <target> \
    --max-iterations 100 \
    --benchmark-iterations 10 \
    --significance 0.05 \
    --improvement-threshold 2.0 \
    --test-command "pytest" \
    --benchmark-command "python benchmark.py"
```

### Check Status

```bash
python .claude/skills/optimize/orchestrator.py <target> --status
```

## File Structure

```
auto-optimizer/
├── claude.json                   # Plugin manifest for marketplace
├── README.md                     # This documentation
├── LICENSE                       # MIT License
└── .claude/
    └── skills/
        └── optimize/
            ├── SKILL.md              # Skill definition for Claude Code
            ├── README.md             # Detailed skill documentation
            ├── __init__.py           # Python package init
            ├── orchestrator.py       # Core infinite loop scheduler
            ├── workspace_manager.py  # Git operations with sandbox isolation
            ├── graveyard_manager.py  # Failed optimization records
            └── tools/
                ├── __init__.py
                ├── generate_tests.py   # Generate unit tests and benchmarks
                ├── propose_patch.py    # Generate code diffs
                ├── verify_semantics.py # Semantic verification via unit tests
                └── run_benchmark.py    # Statistical benchmark execution
```

## State Files

### `.optimizer_state.json`

Tracks the current state of the optimization loop:

```json
{
  "iteration": 42,
  "total_attempted": 45,
  "total_accepted": 3,
  "total_rejected": 42,
  "current_target": "src/parser.py",
  "current_phase": "benchmarking",
  "total_improvement": 12.5,
  "baseline_benchmark": {"mean": 1.5, "stdev": 0.1},
  "current_benchmark": {"mean": 1.2, "stdev": 0.1}
}
```

### `optimization_graveyard.json`

Records failed optimization attempts:

```json
{
  "version": 1,
  "entries": [
    {
      "timestamp": "2024-01-01T12:00:00",
      "file_path": "src/parser.py",
      "diff_hash": "a1b2c3d4",
      "failure_type": "unit_test",
      "failure_reason": "Edge case output changed",
      "optimization_type": "caching"
    }
  ]
}
```

## Pitfalls Addressed

### 1. Behavior Drift & Overfitting
**Problem**: AI removes error handling or hardcodes values to improve benchmarks.

**Solution**: Dual-track verification with unit tests that must pass before any benchmark is run.

### 2. Benchmark Noise
**Problem**: CPU variance causes false positives in performance measurement.

**Solution**: Statistical hypothesis testing with Welch's t-test, alternating A/B/A/B pattern, and minimum improvement thresholds.

### 3. Amnesia Loop
**Problem**: LLM repeatedly proposes the same failed optimization.

**Solution**: Graveyard of failed attempts, injected into prompts as warnings.

### 4. Workspace Corruption
**Problem**: Failed optimizations leave the codebase in a broken state.

**Solution**: Git worktree isolation - every experiment runs in a sandbox.

## Parallel Optimization (Future)

The architecture supports parallel exploration:

1. Orchestrator spawns multiple LLM requests with different optimization focuses
2. Each proposal is tested in parallel Git worktrees
3. Unit tests run in parallel
4. Benchmarks are serialized (CPU contention would skew results)

## Customization

### Test Command

Set a custom test command:

```bash
export OPTIMIZER_TEST_COMMAND="npm test"
# or
python orchestrator.py --test-command "npm test"
```

### Benchmark Command

Set a custom benchmark command:

```bash
export OPTIMIZER_BENCHMARK_COMMAND="python -m timeit -n 1000 'main()'"
# or
python orchestrator.py --benchmark-command "python benchmark.py"
```

### Thresholds

Adjust acceptance criteria:

```bash
# More stringent: require 5% improvement
python orchestrator.py --improvement-threshold 5.0

# More permissive p-value threshold
python orchestrator.py --significance 0.01
```

## API Reference

### WorkspaceManager

```python
from workspace_manager import WorkspaceManager

ws = WorkspaceManager(repo_root)

# Create isolated worktree
success, worktree = ws.create_isolated_worktree()

# Apply diff
ws.apply_diff(diff_content, worktree)

# Run tests
success, stdout, stderr = ws.run_tests_in_worktree("pytest", worktree)

# Merge or discard
ws.merge_to_main(worktree)
ws.discard_worktree(worktree)
```

### GraveyardManager

```python
from graveyard_manager import GraveyardManager

gm = GraveyardManager()

# Record failure
gm.bury(
    file_path="example.py",
    diff_content=diff,
    failure_type="unit_test",
    failure_reason="Test failed"
)

# Get warnings for prompt
warnings = gm.get_warning_prompt("example.py")

# Check for duplicates
is_dup = gm.is_duplicate_failure(diff)
```

### Benchmark Runner

```python
from tools.run_benchmark import (
    run_alternating_benchmark,
    calculate_stats,
    compare_benchmarks
)

# Run A/B alternating pattern
baseline, candidate = run_alternating_benchmark(
    baseline_command="python old_code.py",
    candidate_command="python new_code.py",
    iterations_per_version=10
)

# Analyze
baseline_stats = calculate_stats(baseline)
candidate_stats = calculate_stats(candidate)
comparison = compare_benchmarks(baseline_stats, candidate_stats, ...)

print(comparison.recommendation)
```

## Contributing

1. Add new optimization types to `propose_patch.py`
2. Add new test generators to `generate_tests.py`
3. Improve statistical analysis in `run_benchmark.py`

## License

MIT
