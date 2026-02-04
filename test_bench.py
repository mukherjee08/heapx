"""Benchmark different sift implementations."""
import subprocess
import sys

# Build
subprocess.run([sys.executable, "-c", 
    "from Cython.Build import cythonize; import pyximport; "
    "from distutils.core import setup; "
    "setup(ext_modules=cythonize('test_sift.pyx', language_level=3, "
    "compiler_directives={'boundscheck': False, 'wraparound': False}))"],
    cwd="/Users/mukhani/Documents/GitHub/heapx", capture_output=True)

subprocess.run(["cythonize", "-i", "test_sift.pyx"], 
    cwd="/Users/mukhani/Documents/GitHub/heapx", capture_output=True)

import heapq
import time
import random
import test_sift

def benchmark(name, pop_func, data_gen, sizes, iterations=5000):
    print(f"\n{name}:")
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
        mark = "✓" if speedup >= 1.0 else "✗"
        print(f"  size={size:6d}: heapq={avg_heapq:.2f}µs opt={avg_opt:.2f}µs {speedup:.2f}x {mark}")

# Test INT
print("=" * 60)
print("INT COMPARISONS")
print("=" * 60)
sizes = [100, 1000, 10000]

benchmark("V1: PyObject_RichCompareBool", test_sift.test_v1, 
          lambda n: list(range(n, 0, -1)), sizes)
benchmark("V2: Native Python <", test_sift.test_v2,
          lambda n: list(range(n, 0, -1)), sizes)
benchmark("V3: Int-specialized (PyLong_AsLong)", test_sift.test_v3_int,
          lambda n: list(range(n, 0, -1)), sizes)

# Test FLOAT
print("\n" + "=" * 60)
print("FLOAT COMPARISONS")
print("=" * 60)

benchmark("V1: PyObject_RichCompareBool", test_sift.test_v1,
          lambda n: [random.random() for _ in range(n)], sizes)
benchmark("V2: Native Python <", test_sift.test_v2,
          lambda n: [random.random() for _ in range(n)], sizes)
benchmark("V4: Float-specialized (PyFloat_AS_DOUBLE)", test_sift.test_v4_float,
          lambda n: [random.random() for _ in range(n)], sizes)
