#!/usr/bin/env python3
"""
Orchestrator - Core Infinite Loop Scheduler

This is the "Stateful Orchestrator" that coordinates the entire optimization loop.
The LLM is treated as a "Stateless Function" - called only for specific tasks
with complete context provided each time.

Architecture:
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
                              │
                              ▼
                    ┌─────────────────┐
                    │   LLM (Stateless) │
                    │   - propose_patch │
                    │   - generate_tests│
                    └─────────────────┘

Key Design Principles:
1. Git is the single source of truth for state
2. Each iteration runs in isolated Git worktree
3. Failed optimizations go to graveyard (prevents amnesia loop)
4. Statistical rigor in benchmarking (prevents noise acceptance)
5. Dual-track verification (unit tests + benchmarks)
"""

import os
import sys
import json
import time
import argparse
import signal
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from workspace_manager import WorkspaceManager, WorktreeInfo
from graveyard_manager import GraveyardManager


@dataclass
class OptimizationState:
    """State of the optimization loop"""
    iteration: int = 0
    total_attempted: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    current_target: Optional[str] = None
    current_phase: str = "idle"
    last_error: Optional[str] = None
    started_at: Optional[str] = None
    last_update: Optional[str] = None
    total_improvement: float = 0.0
    baseline_benchmark: Optional[Dict[str, float]] = None
    current_benchmark: Optional[Dict[str, float]] = None


class OptimizerOrchestrator:
    """
    Core orchestrator for the infinite optimization loop.

    This class manages:
    - State persistence via .optimizer_state.json
    - Git worktree isolation for each attempt
    - Graveyard of failed optimizations
    - Statistical benchmark comparison
    - Parallel optimization proposals (future)
    """

    def __init__(
        self,
        target_path: Path,
        state_file: Optional[Path] = None,
        graveyard_file: Optional[Path] = None,
        max_iterations: Optional[int] = None,
        benchmark_iterations: int = 10,
        significance_threshold: float = 0.05,
        improvement_threshold: float = 2.0,
        test_command: Optional[str] = None,
        benchmark_command: Optional[str] = None
    ):
        self.target_path = Path(target_path).resolve()
        self.repo_root = self._find_repo_root(self.target_path)

        # State file path
        if state_file is None:
            state_file = self.repo_root / ".optimizer_state.json"
        self.state_file = Path(state_file)

        # Initialize managers
        self.workspace = WorkspaceManager(self.repo_root)
        self.graveyard = GraveyardManager(graveyard_file or self.repo_root / "optimization_graveyard.json")

        # Configuration
        self.max_iterations = max_iterations
        self.benchmark_iterations = benchmark_iterations
        self.significance_threshold = significance_threshold
        self.improvement_threshold = improvement_threshold
        self.test_command = test_command
        self.benchmark_command = benchmark_command

        # State
        self.state = OptimizationState()
        self.running = True

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _find_repo_root(self, path: Path) -> Path:
        """Find Git repository root"""
        current = path
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return path

    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        print("\n\nShutdown signal received. Saving state and exiting...")
        self.running = False
        self._save_state()
        sys.exit(0)

    def _load_state(self):
        """Load state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                self.state = OptimizationState(**data)
            except (json.JSONDecodeError, TypeError):
                self.state = OptimizationState()

        if self.state.started_at is None:
            self.state.started_at = datetime.now().isoformat()

    def _save_state(self):
        """Save state to file"""
        self.state.last_update = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(asdict(self.state), f, indent=2)

    def get_status_report(self) -> str:
        """Generate human-readable status report"""
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║               AUTO-OPTIMIZER STATUS REPORT                    ║
╠══════════════════════════════════════════════════════════════╣
║ Iteration:      {self.state.iteration:>6}                                    ║
║ Status:         {self.state.current_phase:<40}║
║ Target:         {str(self.state.current_target or 'None'):<40}║
╠══════════════════════════════════════════════════════════════╣
║ STATISTICS                                                    ║
║   Attempted:    {self.state.total_attempted:>6}                                    ║
║   Accepted:     {self.state.total_accepted:>6}                                    ║
║   Rejected:     {self.state.total_rejected:>6}                                    ║
║   Improvement:  {self.state.total_improvement:>6.1f}%                                  ║
╠══════════════════════════════════════════════════════════════╣
║ Started:        {self.state.started_at or 'N/A'}                    ║
║ Last Update:    {self.state.last_update or 'N/A'}                    ║
╚══════════════════════════════════════════════════════════════╝
"""
        return report

    # ========== PHASE 1: Environment Preparation ==========

    def phase_prepare_environment(self) -> bool:
        """
        Phase 1: Prepare environment and verify tests exist.

        Returns:
            True if environment is ready, False otherwise
        """
        self.state.current_phase = "preparing_environment"
        self._save_state()

        print("\n" + "="*60)
        print("PHASE 1: Environment Preparation")
        print("="*60)

        # Check target exists
        if not self.target_path.exists():
            print(f"Error: Target path does not exist: {self.target_path}")
            return False

        self.state.current_target = str(self.target_path)
        print(f"Target: {self.target_path}")

        # Check for unit tests
        unit_test_dir = self.repo_root / ".unit_tests"
        perf_test_dir = self.repo_root / ".perf_tests"

        if not unit_test_dir.exists():
            print("Warning: No .unit_tests directory found")
            print("Generating unit tests...")
            # Would call generate_tests.py here
            # For now, we proceed without

        if not perf_test_dir.exists():
            print("Warning: No .perf_tests directory found")
            print("Generating performance tests...")
            # Would call generate_tests.py here

        # Create checkpoint
        print("\nCreating checkpoint...")
        success, msg = self.workspace.create_checkpoint("checkpoint: before optimization")
        if success:
            print(f"Checkpoint created: {self.workspace.get_current_commit()[:8]}")
        else:
            print(f"Warning: {msg}")

        # Run baseline benchmark
        if self.benchmark_command:
            print("\nRunning baseline benchmark...")
            self.state.baseline_benchmark = self._run_benchmark()
            self.state.current_benchmark = self.state.baseline_benchmark

        self._save_state()
        return True

    # ========== PHASE 2: Propose Optimization ==========

    def phase_propose_optimization(self) -> Optional[str]:
        """
        Phase 2: Generate optimization proposal via LLM.

        Returns:
            Diff content if proposal generated, None otherwise
        """
        self.state.current_phase = "proposing_optimization"
        self._save_state()

        print("\n" + "="*60)
        print("PHASE 2: Propose Optimization")
        print("="*60)

        # Get graveyard warnings
        graveyard_warning = self.graveyard.get_warning_prompt(
            str(self.target_path),
            max_entries=5
        )

        # In a real implementation, this would call an LLM API
        # For now, we use a placeholder that the skill will replace
        print("\nRequesting optimization proposal...")
        print("(This is where the LLM would be called with context)")

        # The actual LLM call would happen here
        # For the skill implementation, we return None and let
        # the SKILL.md handle the LLM interaction

        return None

    # ========== PHASE 3: Apply and Verify ==========

    def phase_apply_and_verify(self, diff_content: str) -> tuple[bool, str]:
        """
        Phase 3: Apply diff and verify semantics.

        Returns:
            Tuple of (success, message)
        """
        self.state.current_phase = "applying_and_verifying"
        self._save_state()

        print("\n" + "="*60)
        print("PHASE 3: Apply and Verify Semantics")
        print("="*60)

        # Check if this diff was already tried
        if self.graveyard.is_duplicate_failure(diff_content):
            print("Error: This optimization was already tried and failed")
            return False, "Duplicate of previously failed optimization"

        # Create isolated worktree
        print("\nCreating isolated worktree...")
        success, worktree = self.workspace.create_isolated_worktree()
        if not success:
            return False, "Failed to create worktree"

        print(f"Worktree created at: {worktree.path}")

        # Apply diff
        print("\nApplying diff...")
        success, msg = self.workspace.apply_diff(diff_content, worktree)
        if not success:
            self.workspace.discard_worktree(worktree)
            return False, f"Failed to apply diff: {msg}"

        print("Diff applied successfully")

        # Run unit tests
        if self.test_command:
            print("\nRunning unit tests in worktree...")
            success, stdout, stderr = self.workspace.run_tests_in_worktree(
                self.test_command,
                worktree
            )

            if not success:
                error_msg = stderr or stdout
                print(f"Unit tests FAILED:\n{error_msg[:500]}")

                # Bury in graveyard
                self.graveyard.bury(
                    file_path=str(self.target_path),
                    diff_content=diff_content,
                    failure_type="unit_test",
                    failure_reason="Unit tests failed after applying optimization",
                    error_details=error_msg[:1000]
                )

                self.workspace.discard_worktree(worktree)
                return False, "Unit tests failed"

            print("Unit tests passed")

        self._save_state()
        return True, "Verification passed"

    # ========== PHASE 4: Benchmark ==========

    def phase_benchmark(self, diff_content: str) -> tuple[bool, float, str]:
        """
        Phase 4: Run statistical benchmark comparison.

        Returns:
            Tuple of (is_improvement, improvement_percent, message)
        """
        self.state.current_phase = "benchmarking"
        self._save_state()

        print("\n" + "="*60)
        print("PHASE 4: Statistical Benchmark")
        print("="*60)

        if not self.benchmark_command:
            print("No benchmark command configured, skipping benchmark phase")
            return True, 0.0, "No benchmark configured"

        # Run A/B benchmark
        # In production, this would use the tools/run_benchmark.py
        # with alternating A/B pattern

        print(f"\nRunning {self.benchmark_iterations} benchmark iterations...")
        print("(This would use statistical hypothesis testing)")

        # Placeholder - actual implementation would use run_benchmark.py
        improvement = 0.0
        is_improvement = False
        message = "Benchmark not implemented"

        return is_improvement, improvement, message

    # ========== PHASE 5: Persist or Rollback ==========

    def phase_persist_or_rollback(
        self,
        is_improvement: bool,
        improvement_percent: float,
        diff_content: str,
        optimization_type: str,
        description: str
    ) -> bool:
        """
        Phase 5: Persist successful optimization or rollback.

        Returns:
            True if optimization was persisted
        """
        self.state.current_phase = "persisting_or_rolling_back"
        self._save_state()

        print("\n" + "="*60)
        print("PHASE 5: Persist or Rollback")
        print("="*60)

        if is_improvement:
            print(f"\n✅ Optimization accepted: {improvement_percent:.1f}% improvement")

            # Commit in worktree
            self.workspace.commit_in_worktree(
                f"optimize: {description}",
                self.workspace.current_worktree
            )

            # Merge to main
            success, msg = self.workspace.merge_to_main(
                commit_message=f"optimize: {description} (+{improvement_percent:.1f}%)"
            )

            if success:
                print("Merged to main branch")

                # Update state
                self.state.total_accepted += 1
                self.state.total_improvement += improvement_percent

                # Clear graveyard for this file (old failures may now be valid)
                self.graveyard.clear_for_file(str(self.target_path))

                self._save_state()
                return True
            else:
                print(f"Merge failed: {msg}")
                return False
        else:
            print("\n❌ Optimization rejected")

            # Add to graveyard
            self.graveyard.bury(
                file_path=str(self.target_path),
                diff_content=diff_content,
                failure_type="benchmark" if improvement_percent <= 0 else "no_improvement",
                failure_reason=f"No significant improvement ({improvement_percent:.1f}%)",
                optimization_type=optimization_type
            )

            # Discard worktree
            self.workspace.discard_worktree()

            self.state.total_rejected += 1
            self._save_state()

            return False

    # ========== Main Loop ==========

    def run(self):
        """
        Run the infinite optimization loop.

        This is the main entry point that coordinates all phases.
        """
        self._load_state()

        print("\n" + "="*60)
        print("   AUTO-OPTIMIZER DAEMON STARTED")
        print("="*60)
        print(self.get_status_report())

        # Phase 1: Prepare environment (run once)
        if self.state.iteration == 0:
            if not self.phase_prepare_environment():
                print("Failed to prepare environment. Exiting.")
                return 1

        # Main loop
        while self.running:
            self.state.iteration += 1
            self.state.total_attempted += 1

            print(f"\n{'='*60}")
            print(f"ITERATION {self.state.iteration}")
            print(f"{'='*60}")

            # Phase 2: Propose optimization
            diff_content = self.phase_propose_optimization()

            if diff_content is None:
                # In skill mode, this is where we pause for LLM input
                # The skill will resume after getting LLM response
                print("\nWaiting for optimization proposal...")
                print("(In skill mode, this is handled by the SKILL.md)")
                break

            # Phase 3: Apply and verify
            success, msg = self.phase_apply_and_verify(diff_content)
            if not success:
                print(f"Verification failed: {msg}")
                self.state.total_rejected += 1
                self._save_state()
                continue

            # Phase 4: Benchmark
            is_improvement, improvement, msg = self.phase_benchmark(diff_content)

            # Phase 5: Persist or rollback
            self.phase_persist_or_rollback(
                is_improvement,
                improvement,
                diff_content,
                "unknown",
                "Optimization"
            )

            # Check max iterations
            if self.max_iterations and self.state.iteration >= self.max_iterations:
                print(f"\nReached max iterations ({self.max_iterations})")
                break

            # Brief pause between iterations
            time.sleep(1)

        print("\n" + "="*60)
        print("   OPTIMIZATION LOOP ENDED")
        print("="*60)
        print(self.get_status_report())

        return 0

    def _run_benchmark(self) -> Optional[Dict[str, float]]:
        """Run benchmark and return results"""
        if not self.benchmark_command:
            return None

        try:
            result = subprocess.run(
                self.benchmark_command,
                shell=True,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=300
            )

            # Try to parse JSON output
            try:
                return json.loads(result.stdout)
            except:
                return {"output": result.stdout}

        except Exception as e:
            print(f"Benchmark error: {e}")
            return None


def main():
    parser = argparse.ArgumentParser(
        description="Auto-Optimizer Orchestrator - Infinite optimization loop"
    )
    parser.add_argument(
        "target",
        type=Path,
        help="File or directory to optimize"
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        help="Path to state file (default: .optimizer_state.json)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        help="Maximum number of iterations (default: infinite)"
    )
    parser.add_argument(
        "--benchmark-iterations",
        type=int,
        default=10,
        help="Number of benchmark iterations (default: 10)"
    )
    parser.add_argument(
        "--significance",
        type=float,
        default=0.05,
        help="P-value threshold for significance (default: 0.05)"
    )
    parser.add_argument(
        "--improvement-threshold",
        type=float,
        default=2.0,
        help="Minimum improvement percent (default: 2.0)"
    )
    parser.add_argument(
        "--test-command",
        type=str,
        help="Command to run tests"
    )
    parser.add_argument(
        "--benchmark-command",
        type=str,
        help="Command to run benchmark"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Just print current status and exit"
    )

    args = parser.parse_args()

    orchestrator = OptimizerOrchestrator(
        target_path=args.target,
        state_file=args.state_file,
        max_iterations=args.max_iterations,
        benchmark_iterations=args.benchmark_iterations,
        significance_threshold=args.significance,
        improvement_threshold=args.improvement_threshold,
        test_command=args.test_command,
        benchmark_command=args.benchmark_command
    )

    if args.status:
        print(orchestrator.get_status_report())
        return 0

    return orchestrator.run()


if __name__ == "__main__":
    sys.exit(main())
