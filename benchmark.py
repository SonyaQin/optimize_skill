import time
import statistics
import random
from bubble_sort import bubble_sort

def benchmark(func, data, iterations=10):
    times = []
    for _ in range(iterations):
        arr = data.copy()  # Fresh copy for each iteration
        start = time.perf_counter()
        func(arr)
        times.append(time.perf_counter() - start)
    return {"mean": statistics.mean(times), "stdev": statistics.stdev(times) if len(times) > 1 else 0}

# Test with different sizes
test_cases = {
    "small_sorted": list(range(100)),
    "small_reverse": list(range(100, 0, -1)),
    "small_random": random.sample(range(1000), 100),
    "medium_random": random.sample(range(10000), 1000),
    "large_random": random.sample(range(100000), 10000)
}

print("=== Baseline Benchmark ===")
results = {}
for name, data in test_cases.items():
    result = benchmark(bubble_sort, data, iterations=10)
    results[name] = result
    print(f"{name}: mean={result['mean']:.6f}s, stdev={result['stdev']:.6f}s")

# Calculate overall score (weighted average)
weights = {"small_sorted": 1, "small_reverse": 1, "small_random": 1, "medium_random": 2, "large_random": 3}
total_weight = sum(weights.values())
overall_mean = sum(results[name]['mean'] * weights[name] for name in weights) / total_weight

print(f"\nOverall score: {overall_mean:.6f}s")
