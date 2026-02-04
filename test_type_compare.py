"""Test type-specialized vs native for sequential pop."""
import subprocess
import sys
import os

os.chdir("/Users/mukhani/Documents/GitHub/heapx")
subprocess.run(["cythonize", "-i", "test_opt.pyx"], capture_output=True)

import heapq
import time
import random
import test_opt

def benchmark(name, pop_funcs, data_gen, sizes, iterations=3000):
    print(f"\n{name}:")
    for size in sizes:
        results = {}
        for func_name, func in pop_funcs.items():
            times = []
            for _ in range(iterations):
                data = data_gen(size)
                heapq.heapify(data)
                start = time.perf_counter()
                func(data)
                times.append(time.perf_counter() - start)
            results[func_name] = sum(times) / len(times) * 1e6
        
        # Get heapq baseline
        times_heapq = []
        for _ in range(iterations):
            data = data_gen(size)
            heapq.heapify(data)
            start = time.perf_counter()
            heapq.heappop(data)
            times_heapq.append(time.perf_counter() - start)
        heapq_time = sum(times_heapq) / len(times_heapq) * 1e6
        
        print(f"  size={size:6d}: heapq={heapq_time:.2f}µs", end="")
        for func_name, t in results.items():
            speedup = heapq_time / t
            mark = "✓" if speedup >= 1.0 else "✗"
            print(f" | {func_name}={t:.2f}µs ({speedup:.2f}x {mark})", end="")
        print()

sizes = [10, 100, 1000, 10000]

# INT
print("=" * 80)
print("INT")
print("=" * 80)
benchmark("INT", {
    "native": test_opt.pop_native,
    "int_spec": test_opt.pop_int,
    "dispatch": test_opt.pop_dispatch
}, lambda n: list(range(n, 0, -1)), sizes)

# FLOAT
print("\n" + "=" * 80)
print("FLOAT")
print("=" * 80)
benchmark("FLOAT", {
    "native": test_opt.pop_native,
    "float_spec": test_opt.pop_float,
    "dispatch": test_opt.pop_dispatch
}, lambda n: [random.random() for _ in range(n)], sizes)

# STR - native only
print("\n" + "=" * 80)
print("STR")
print("=" * 80)
benchmark("STR", {
    "native": test_opt.pop_native,
}, lambda n: [f"str_{i:08d}" for i in range(n, 0, -1)], sizes)

# BOOL - native only
print("\n" + "=" * 80)
print("BOOL")
print("=" * 80)
benchmark("BOOL", {
    "native": test_opt.pop_native,
}, lambda n: [i % 2 == 0 for i in range(n)], sizes)

# TUPLE - native only
print("\n" + "=" * 80)
print("TUPLE")
print("=" * 80)
benchmark("TUPLE", {
    "native": test_opt.pop_native,
}, lambda n: [(i, i+1) for i in range(n, 0, -1)], sizes)

# CUSTOM
class Custom:
    __slots__ = ('val',)
    def __init__(self, v):
        self.val = v
    def __lt__(self, other):
        return self.val < other.val
    def __gt__(self, other):
        return self.val > other.val

print("\n" + "=" * 80)
print("CUSTOM")
print("=" * 80)
benchmark("CUSTOM", {
    "native": test_opt.pop_native,
}, lambda n: [Custom(i) for i in range(n, 0, -1)], sizes)
