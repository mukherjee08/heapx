"""Comprehensive benchmark of optimized pop with native comparison."""
import subprocess
import sys
import os

os.chdir("/Users/mukhani/Documents/GitHub/heapx")
print("Building optimized_pop.pyx...")
result = subprocess.run(["cythonize", "-i", "optimized_pop.pyx"], capture_output=True, text=True)
if result.returncode != 0:
    print("Build failed:", result.stderr)
    sys.exit(1)
print("Build complete.\n")

import heapq
import time
import random
import optimized_pop

class Custom:
    __slots__ = ('val',)
    def __init__(self, v):
        self.val = v
    def __lt__(self, other):
        return self.val < other.val
    def __gt__(self, other):
        return self.val > other.val

def benchmark_sequential(name, data_gen, sizes, iterations=3000):
    print(f"\n--- {name} ---")
    wins = 0
    total = 0
    for size in sizes:
        times_heapq = []
        times_opt = []
        
        for _ in range(iterations):
            data = data_gen(size)
            heapq.heapify(data)
            d1 = data.copy()
            d2 = data.copy()
            
            start = time.perf_counter()
            heapq.heappop(d1)
            times_heapq.append(time.perf_counter() - start)
            
            start = time.perf_counter()
            optimized_pop.pop(d2)
            times_opt.append(time.perf_counter() - start)
        
        avg_heapq = sum(times_heapq) / len(times_heapq) * 1e6
        avg_opt = sum(times_opt) / len(times_opt) * 1e6
        speedup = avg_heapq / avg_opt
        mark = "✓" if speedup >= 1.0 else "✗"
        if speedup >= 1.0:
            wins += 1
        total += 1
        print(f"  size={size:7d}: heapq={avg_heapq:.2f}µs opt={avg_opt:.2f}µs {speedup:.2f}x {mark}")
    return wins, total

def benchmark_bulk(name, data_gen, configs, iterations=500):
    print(f"\n--- {name} ---")
    wins = 0
    total = 0
    for n_pop, size in configs:
        times_heapq = []
        times_opt = []
        
        for _ in range(iterations):
            data = data_gen(size)
            heapq.heapify(data)
            d1 = data.copy()
            d2 = data.copy()
            
            start = time.perf_counter()
            for _ in range(n_pop):
                heapq.heappop(d1)
            times_heapq.append(time.perf_counter() - start)
            
            start = time.perf_counter()
            optimized_pop.pop(d2, n=n_pop)
            times_opt.append(time.perf_counter() - start)
        
        avg_heapq = sum(times_heapq) / len(times_heapq) * 1e6
        avg_opt = sum(times_opt) / len(times_opt) * 1e6
        speedup = avg_heapq / avg_opt
        mark = "✓" if speedup >= 1.0 else "✗"
        if speedup >= 1.0:
            wins += 1
        total += 1
        print(f"  n={n_pop:4d}, size={size:7d}: {speedup:.2f}x {mark}")
    return wins, total

print("=" * 70)
print("SEQUENTIAL POP (n=1)")
print("=" * 70)

sizes = [10, 100, 1000, 10000, 100000, 1000000]
seq_wins = 0
seq_total = 0

w, t = benchmark_sequential("INT", lambda n: list(range(n, 0, -1)), sizes)
seq_wins += w; seq_total += t

w, t = benchmark_sequential("FLOAT", lambda n: [random.random() for _ in range(n)], sizes)
seq_wins += w; seq_total += t

w, t = benchmark_sequential("STR", lambda n: [f"str_{i:08d}" for i in range(n, 0, -1)], sizes[:5])
seq_wins += w; seq_total += t

w, t = benchmark_sequential("BOOL", lambda n: [i % 2 == 0 for i in range(n)], sizes)
seq_wins += w; seq_total += t

w, t = benchmark_sequential("TUPLE", lambda n: [(i, i+1) for i in range(n, 0, -1)], sizes[:5])
seq_wins += w; seq_total += t

w, t = benchmark_sequential("CUSTOM", lambda n: [Custom(i) for i in range(n, 0, -1)], sizes[:5])
seq_wins += w; seq_total += t

print("\n" + "=" * 70)
print("BULK POP")
print("=" * 70)

bulk_configs = [
    (100, 1000), (100, 10000), (100, 100000), (100, 1000000),
    (1000, 10000), (1000, 100000), (1000, 1000000)
]
bulk_wins = 0
bulk_total = 0

w, t = benchmark_bulk("INT", lambda n: list(range(n, 0, -1)), bulk_configs)
bulk_wins += w; bulk_total += t

w, t = benchmark_bulk("FLOAT", lambda n: [random.random() for _ in range(n)], bulk_configs)
bulk_wins += w; bulk_total += t

w, t = benchmark_bulk("STR", lambda n: [f"str_{i:08d}" for i in range(n, 0, -1)], bulk_configs)
bulk_wins += w; bulk_total += t

w, t = benchmark_bulk("BOOL", lambda n: [i % 2 == 0 for i in range(n)], bulk_configs)
bulk_wins += w; bulk_total += t

w, t = benchmark_bulk("TUPLE", lambda n: [(i, i+1) for i in range(n, 0, -1)], bulk_configs)
bulk_wins += w; bulk_total += t

w, t = benchmark_bulk("CUSTOM", lambda n: [Custom(i) for i in range(n, 0, -1)], bulk_configs)
bulk_wins += w; bulk_total += t

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"\nSequential: {seq_wins}/{seq_total} wins ({100*seq_wins/seq_total:.1f}%)")
print(f"Bulk: {bulk_wins}/{bulk_total} wins ({100*bulk_wins/bulk_total:.1f}%)")
print(f"Total: {seq_wins+bulk_wins}/{seq_total+bulk_total} wins ({100*(seq_wins+bulk_wins)/(seq_total+bulk_total):.1f}%)")
