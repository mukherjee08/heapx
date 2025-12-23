#!/usr/bin/env python3
"""Benchmark heapx vs heapq."""

import heapx, heapq, time, random, sys

SIZES = [100, 1000, 10000, 100000]
ITERS = 5

def gen(n, seed=42):
    random.seed(seed)
    return [random.randint(-1000000, 1000000) for _ in range(n)]

def gen_floats(n, seed=42):
    random.seed(seed)
    return [random.uniform(-1000000, 1000000) for _ in range(n)]

def bench(func, setup, iters=ITERS):
    times = []
    for _ in range(iters):
        d = setup()
        t0 = time.perf_counter()
        func(d)
        times.append((time.perf_counter() - t0) * 1000)
    return sum(times)/len(times)

def row(name, hq, hx):
    print(f"{name:45} | heapq:{hq:8.3f}ms | heapx:{hx:8.3f}ms | {hq/hx if hx>0 else 0:5.2f}x")

print("="*80)
print(" HEAPIFY - Integers (homogeneous)")
print("="*80)
for n in SIZES:
    hq = bench(heapq.heapify, lambda n=n: gen(n))
    hx = bench(heapx.heapify, lambda n=n: gen(n))
    row(f"heapify int n={n:,}", hq, hx)

print("\n" + "="*80)
print(" HEAPIFY - Floats (homogeneous)")
print("="*80)
for n in SIZES:
    hq = bench(heapq.heapify, lambda n=n: gen_floats(n))
    hx = bench(heapx.heapify, lambda n=n: gen_floats(n))
    row(f"heapify float n={n:,}", hq, hx)

print("\n" + "="*80)
print(" HEAPIFY - Quaternary with Floats (SIMD path)")
print("="*80)
for n in [1000, 10000, 100000]:
    hq = bench(heapq.heapify, lambda n=n: gen_floats(n))
    hx = bench(lambda d: heapx.heapify(d, arity=4), lambda n=n: gen_floats(n))
    row(f"quaternary float n={n:,}", hq, hx)

print("\n" + "="*80)
print(" REMOVE (O(log n) vs naive O(n))")
print("="*80)
for n in [1000, 10000, 100000]:
    def setup(n=n):
        d = gen(n); heapx.heapify(d); return d
    naive = bench(lambda d: (d.pop(n//2), heapx.heapify(d)), setup)
    hx = bench(lambda d: heapx.remove(d, indices=n//2), setup)
    row(f"remove idx n={n:,}", naive, hx)

print("\n" + "="*80)
print(" REPLACE (O(log n) vs naive O(n))")
print("="*80)
for n in [1000, 10000, 100000]:
    def setup(n=n):
        d = gen(n); heapx.heapify(d); return d
    naive = bench(lambda d: (d.__setitem__(n//2, -999), heapx.heapify(d)), setup)
    hx = bench(lambda d: heapx.replace(d, -999, indices=n//2), setup)
    row(f"replace idx n={n:,}", naive, hx)

print("\n" + "="*80)
print(f"Python: {sys.version}")
print(f"heapx: {heapx.__version__}")
