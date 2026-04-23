#!/usr/bin/env python3
"""
Run Benchmark - Statistical Benchmark Execution

This tool implements rigorous statistical benchmarking to avoid the
"Benchmark Noise" pitfall. Key features:

1. Multiple iterations with warmup runs
2. A/B/A/B alternating pattern to eliminate time-based noise
3. Statistical hypothesis testing (Welch's t-test)
4. Configurable significance thresholds

Statistical Rigor:
- Uses Welch's t-test for comparing means with unequal variances
- Requires p-value < 0.05 AND improvement > threshold
- Reports confidence intervals and effect sizes
"""

import os
import sys
import json
import time
import statistics
import subprocess
import argparse
import random
from pathlib import Path
from typing import Callable, List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Try to import scipy for statistical tests
try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("Warning: scipy not installed. Statistical tests will be limited.")


@dataclass
class BenchmarkResult:
    """Single benchmark run result"""
    iteration: int
    duration: float
    timestamp: str


@dataclass
class BenchmarkStats:
    """Statistical summary of benchmark results"""
    mean: float
    stdev: float
    min: float
    max: float
    median: float
    p95: float
    p99: float
    samples: int
    standard_error: float
    confidence_interval_95: Tuple[float, float]


@dataclass
class ComparisonResult:
    """Result of comparing two benchmark sets"""
    baseline_mean: float
    candidate_mean: float
    improvement_percent: float
    improvement_absolute: float
    p_value: float
    is_significant: bool
    is_improvement: bool
    confidence_level: str
    effect_size: float  # Cohen's d
    recommendation: str


def run_single_benchmark(
    benchmark_command: str,
    cwd: Optional[Path] = None,
    timeout: int = 600,
    capture_output: bool = True
) -> Tuple[float, str]:
    """
    Run a single benchmark execution.

    Returns:
        Tuple of (duration_seconds, output)
    """
    start = time.perf_counter()

    try:
        result = subprocess.run(
            benchmark_command,
            shell=True,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            timeout=timeout
        )
        duration = time.perf_counter() - start
        return duration, result.stdout + result.stderr

    except subprocess.TimeoutExpired:
        return timeout, "Benchmark timed out"

    except Exception as e:
        return -1, str(e)


def run_benchmark_series(
    benchmark_command: str,
    iterations: int = 10,
    warmup: int = 3,
    cwd: Optional[Path] = None,
    timeout: int = 600,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[BenchmarkResult]:
    """
    Run multiple benchmark iterations with warmup.

    Args:
        benchmark_command: Command to run
        iterations: Number of iterations
        warmup: Number of warmup runs (not counted)
        cwd: Working directory
        timeout: Timeout per iteration
        progress_callback: Callback for progress updates

    Returns:
        List of BenchmarkResult objects
    """
    results = []

    # Warmup runs
    for i in range(warmup):
        run_single_benchmark(benchmark_command, cwd, timeout, capture_output=False)

    # Actual measurements
    for i in range(iterations):
        if progress_callback:
            progress_callback(i + 1, iterations)

        duration, output = run_single_benchmark(benchmark_command, cwd, timeout)

        if duration < 0:
            continue  # Skip failed runs

        results.append(BenchmarkResult(
            iteration=i + 1,
            duration=duration,
            timestamp=datetime.now().isoformat()
        ))

    return results


def run_alternating_benchmark(
    baseline_command: str,
    candidate_command: str,
    iterations_per_version: int = 5,
    warmup: int = 2,
    cwd: Optional[Path] = None,
    timeout: int = 600
) -> Tuple[List[BenchmarkResult], List[BenchmarkResult]]:
    """
    Run A/B/A/B alternating benchmark pattern.

    This pattern eliminates time-based noise by alternating between
    baseline and candidate versions.

    Pattern: warmup -> A -> B -> A -> B -> A -> B ...

    Args:
        baseline_command: Command for baseline (A)
        candidate_command: Command for candidate (B)
        iterations_per_version: Number of iterations per version
        warmup: Warmup runs before each version

    Returns:
        Tuple of (baseline_results, candidate_results)
    """
    baseline_results = []
    candidate_results = []

    # Total iterations
    total_rounds = iterations_per_version

    for round_num in range(total_rounds):
        # Run baseline (A)
        for _ in range(warmup):
            run_single_benchmark(baseline_command, cwd, timeout, capture_output=False)

        duration_a, _ = run_single_benchmark(baseline_command, cwd, timeout)
        if duration_a >= 0:
            baseline_results.append(BenchmarkResult(
                iteration=len(baseline_results) + 1,
                duration=duration_a,
                timestamp=datetime.now().isoformat()
            ))

        # Run candidate (B)
        for _ in range(warmup):
            run_single_benchmark(candidate_command, cwd, timeout, capture_output=False)

        duration_b, _ = run_single_benchmark(candidate_command, cwd, timeout)
        if duration_b >= 0:
            candidate_results.append(BenchmarkResult(
                iteration=len(candidate_results) + 1,
                duration=duration_b,
                timestamp=datetime.now().isoformat()
            ))

        print(f"Round {round_num + 1}/{total_rounds}: "
              f"Baseline={duration_a:.4f}s, Candidate={duration_b:.4f}s")

    return baseline_results, candidate_results


def calculate_stats(results: List[BenchmarkResult]) -> BenchmarkStats:
    """Calculate statistical summary from benchmark results"""
    if not results:
        raise ValueError("No results to analyze")

    durations = [r.duration for r in results]

    mean = statistics.mean(durations)
    stdev = statistics.stdev(durations) if len(durations) > 1 else 0

    sorted_durations = sorted(durations)
    n = len(sorted_durations)

    # Standard error
    standard_error = stdev / (n ** 0.5) if n > 1 else 0

    # 95% confidence interval (t-distribution)
    if n > 1 and HAS_SCIPY:
        t_value = stats.t.ppf(0.975, n - 1)
        margin = t_value * standard_error
        ci = (mean - margin, mean + margin)
    else:
        ci = (mean - 1.96 * standard_error, mean + 1.96 * standard_error)

    return BenchmarkStats(
        mean=mean,
        stdev=stdev,
        min=min(durations),
        max=max(durations),
        median=statistics.median(durations),
        p95=sorted_durations[int(n * 0.95)] if n >= 20 else sorted_durations[-1],
        p99=sorted_durations[int(n * 0.99)] if n >= 100 else sorted_durations[-1],
        samples=n,
        standard_error=standard_error,
        confidence_interval_95=ci
    )


def compare_benchmarks(
    baseline_stats: BenchmarkStats,
    candidate_stats: BenchmarkStats,
    baseline_results: List[BenchmarkResult],
    candidate_results: List[BenchmarkResult],
    significance_threshold: float = 0.05,
    improvement_threshold: float = 2.0
) -> ComparisonResult:
    """
    Compare two benchmark sets using statistical hypothesis testing.

    Uses Welch's t-test for comparing means with unequal variances.

    Args:
        baseline_stats: Statistics for baseline
        candidate_stats: Statistics for candidate
        baseline_results: Raw results for baseline
        candidate_results: Raw results for candidate
        significance_threshold: p-value threshold (default 0.05)
        improvement_threshold: Minimum improvement percent to accept (default 2%)

    Returns:
        ComparisonResult with statistical analysis
    """
    # Calculate improvement
    improvement_percent = (baseline_stats.mean - candidate_stats.mean) / baseline_stats.mean * 100
    improvement_absolute = baseline_stats.mean - candidate_stats.mean

    # Perform Welch's t-test
    if HAS_SCIPY and len(baseline_results) > 1 and len(candidate_results) > 1:
        baseline_durations = [r.duration for r in baseline_results]
        candidate_durations = [r.duration for r in candidate_results]

        t_stat, p_value = stats.ttest_ind(
            baseline_durations,
            candidate_durations,
            equal_var=False  # Welch's t-test
        )
    else:
        # Fallback: simple z-test approximation
        se_diff = (baseline_stats.stdev**2/len(baseline_results) +
                   candidate_stats.stdev**2/len(candidate_results))**0.5
        z_score = (baseline_stats.mean - candidate_stats.mean) / se_diff if se_diff > 0 else 0
        p_value = 2 * (1 - 0.5 * (1 + abs(z_score)))  # Approximate p-value
        if p_value <= 0:
            p_value = 0.001

    # Calculate Cohen's d (effect size)
    pooled_stdev = ((baseline_stats.stdev**2 + candidate_stats.stdev**2) / 2)**0.5
    cohens_d = improvement_absolute / pooled_stdev if pooled_stdev > 0 else 0

    # Determine significance
    is_significant = p_value < significance_threshold
    is_improvement = improvement_percent > improvement_threshold and is_significant

    # Confidence level
    if p_value < 0.001:
        confidence_level = "very_high"
    elif p_value < 0.01:
        confidence_level = "high"
    elif p_value < 0.05:
        confidence_level = "moderate"
    else:
        confidence_level = "low"

    # Generate recommendation
    if is_improvement:
        recommendation = f"ACCEPT: Significant improvement of {improvement_percent:.1f}% (p={p_value:.4f})"
    elif improvement_percent > 0 and not is_significant:
        recommendation = f"REJECT: Improvement not statistically significant (p={p_value:.4f})"
    elif improvement_percent < -improvement_threshold:
        recommendation = f"REJECT: Performance degraded by {-improvement_percent:.1f}%"
    else:
        recommendation = f"NEUTRAL: No significant change ({improvement_percent:+.1f}%)"

    return ComparisonResult(
        baseline_mean=baseline_stats.mean,
        candidate_mean=candidate_stats.mean,
        improvement_percent=improvement_percent,
        improvement_absolute=improvement_absolute,
        p_value=p_value,
        is_significant=is_significant,
        is_improvement=is_improvement,
        confidence_level=confidence_level,
        effect_size=cohens_d,
        recommendation=recommendation
    )


def print_benchmark_report(
    baseline_stats: BenchmarkStats,
    candidate_stats: BenchmarkStats,
    comparison: ComparisonResult
):
    """Print a detailed benchmark report"""
    print("\n" + "="*70)
    print("BENCHMARK COMPARISON REPORT")
    print("="*70)

    print("\n📊 BASELINE (Original Code)")
    print(f"   Mean:   {baseline_stats.mean:.6f}s")
    print(f"   Stdev:  {baseline_stats.stdev:.6f}s")
    print(f"   Min:    {baseline_stats.min:.6f}s")
    print(f"   Max:    {baseline_stats.max:.6f}s")
    print(f"   95% CI: [{baseline_stats.confidence_interval_95[0]:.6f}, "
          f"{baseline_stats.confidence_interval_95[1]:.6f}]")
    print(f"   Samples: {baseline_stats.samples}")

    print("\n📊 CANDIDATE (Optimized Code)")
    print(f"   Mean:   {candidate_stats.mean:.6f}s")
    print(f"   Stdev:  {candidate_stats.stdev:.6f}s")
    print(f"   Min:    {candidate_stats.min:.6f}s")
    print(f"   Max:    {candidate_stats.max:.6f}s")
    print(f"   95% CI: [{candidate_stats.confidence_interval_95[0]:.6f}, "
          f"{candidate_stats.confidence_interval_95[1]:.6f}]")
    print(f"   Samples: {candidate_stats.samples}")

    print("\n📈 COMPARISON")
    print(f"   Improvement:     {comparison.improvement_percent:+.2f}%")
    print(f"   Absolute:        {comparison.improvement_absolute:.6f}s")
    print(f"   P-value:         {comparison.p_value:.6f}")
    print(f"   Effect size (d): {comparison.effect_size:.3f}")
    print(f"   Significance:    {'Yes' if comparison.is_significant else 'No'}")
    print(f"   Confidence:      {comparison.confidence_level}")

    print("\n" + "-"*70)
    print(f"   RECOMMENDATION: {comparison.recommendation}")
    print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Run statistical benchmarks with rigorous analysis"
    )
    parser.add_argument(
        "benchmark_command",
        help="Command to benchmark"
    )
    parser.add_argument(
        "--candidate-command",
        help="Command for candidate version (for A/B comparison)"
    )
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=10,
        help="Number of benchmark iterations (default: 10)"
    )
    parser.add_argument(
        "--warmup", "-w",
        type=int,
        default=3,
        help="Number of warmup runs (default: 3)"
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        help="Working directory for benchmark"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout per iteration in seconds (default: 600)"
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
        help="Minimum improvement percent to accept (default: 2.0)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file for JSON results"
    )
    parser.add_argument(
        "--alternating",
        action="store_true",
        help="Use A/B/A/B alternating pattern"
    )

    args = parser.parse_args()

    print(f"Running benchmark: {args.benchmark_command}")
    print(f"Iterations: {args.iterations}, Warmup: {args.warmup}")

    if args.alternating and args.candidate_command:
        # A/B alternating pattern
        print("\nUsing A/B/A/B alternating pattern...")

        baseline_results, candidate_results = run_alternating_benchmark(
            args.benchmark_command,
            args.candidate_command,
            iterations_per_version=args.iterations,
            warmup=args.warmup,
            cwd=args.cwd,
            timeout=args.timeout
        )

        baseline_stats = calculate_stats(baseline_results)
        candidate_stats = calculate_stats(candidate_results)
        comparison = compare_benchmarks(
            baseline_stats, candidate_stats,
            baseline_results, candidate_results,
            args.significance, args.improvement_threshold
        )

        print_benchmark_report(baseline_stats, candidate_stats, comparison)

        # Save results
        results = {
            "timestamp": datetime.now().isoformat(),
            "baseline": asdict(baseline_stats),
            "candidate": asdict(candidate_stats),
            "comparison": asdict(comparison),
            "config": {
                "iterations": args.iterations,
                "warmup": args.warmup,
                "significance_threshold": args.significance,
                "improvement_threshold": args.improvement_threshold
            }
        }

    else:
        # Single benchmark run
        def progress(current, total):
            print(f"  Iteration {current}/{total}")

        results_list = run_benchmark_series(
            args.benchmark_command,
            iterations=args.iterations,
            warmup=args.warmup,
            cwd=args.cwd,
            timeout=args.timeout,
            progress_callback=progress
        )

        stats = calculate_stats(results_list)

        print(f"\n📊 Results:")
        print(f"   Mean:   {stats.mean:.6f}s")
        print(f"   Stdev:  {stats.stdev:.6f}s")
        print(f"   Min:    {stats.min:.6f}s")
        print(f"   Max:    {stats.max:.6f}s")
        print(f"   95% CI: [{stats.confidence_interval_95[0]:.6f}, "
              f"{stats.confidence_interval_95[1]:.6f}]")

        results = {
            "timestamp": datetime.now().isoformat(),
            "stats": asdict(stats),
            "raw_results": [asdict(r) for r in results_list],
            "config": {
                "iterations": args.iterations,
                "warmup": args.warmup
            }
        }

    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
