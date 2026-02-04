"""Comprehensive benchmark of optimized pop implementations."""
import subprocess
import sys
import os

os.chdir("/Users/mukhani/Documents/GitHub/heapx")
subprocess.run(["cythonize", "-i", "test_opt.pyx"], capture_output=True)

import heapq
import time
import random
import test_opt

class Custom:
    __slots__ = ('val',)
    def __init__(self, v):
        self.val = v
    def __lt__(self, other):
        return self.val < other.val
    def __gt__(self, other):
        return self.val > other.val

def benchmark(name, pop_func, data_gen, sizes, iterations=3000):
    results = []
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
            pop_func(d2)
            times_opt.append(time.perf_counter() - start)
        
        avg_heapq = sum(times_heapq) / len(times_heapq) * 1e6
        avg_opt = sum(times_opt) / len(times_opt) * 1e6
        speedup = avg_heapq / avg_opt
        results.append((size, avg_heapq, avg_opt, speedup))
    
    print(f"\n{name}:")
    for size, hq, opt, sp in results:
        mark = "✓" if sp >= 1.0 else "✗"
        print(f"  size={size:7d}: heapq={hq:.2f}µs opt={opt:.2f}µs {sp:.2f}x {mark}")
    return results

sizes = [10, 100, 1000, 10000, 100000, 1000000]

print("=" * 70)
print("SEQUENTIAL POP - NATIVE PYTHON < COMPARISON")
print("=" * 70)

# INT
print("\n--- INT ---")
benchmark("Native <", test_opt.pop_native, lambda n: list(range(n, 0, -1)), sizes)
benchmark("Int-specialized", test_opt.pop_int, lambda n: list(range(n, 0, -1)), sizes)
benchmark("Auto-dispatch", test_opt.pop_dispatch, lambda n: list(range(n, 0, -1)), sizes)

# FLOAT
print("\n--- FLOAT ---")
benchmark("Native <", test_opt.pop_native, lambda n: [random.random() for _ in range(n)], sizes)
benchmark("Float-specialized", test_opt.pop_float, lambda n: [random.random() for _ in range(n)], sizes)
benchmark("Auto-dispatch", test_opt.pop_dispatch, lambda n: [random.random() for _ in range(n)], sizes)

# STR
print("\n--- STR ---")
benchmark("Native <", test_opt.pop_native, lambda n: [f"str_{i:08d}" for i in range(n, 0, -1)], sizes[:5])

# BOOL
print("\n--- BOOL ---")
benchmark("Native <", test_opt.pop_native, lambda n: [i % 2 == 0 for i in range(n)], sizes)

# TUPLE
print("\n--- TUPLE ---")
benchmark("Native <", test_opt.pop_native, lambda n: [(i, i+1) for i in range(n, 0, -1)], sizes[:5])

# CUSTOM
print("\n--- CUSTOM ---")
benchmark("Native <", test_opt.pop_native, lambda n: [Custom(i) for i in range(n, 0, -1)], sizes[:5])
