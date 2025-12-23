#!/usr/bin/env python3
"""Benchmark heapx vs heapq."""

import heapx, heapq, time, random, sys

SIZES = [100, 1000, 10000, 100000]
ITERS = 5

def gen(n, seed=42):
    random.seed(seed)
    return [random.randint(-1000000, 1000000) for _ in range(n)]

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
print(" HEAPIFY")
print("="*80)
for n in SIZES:
    hq = bench(heapq.heapify, lambda n=n: gen(n))
    hx = bench(heapx.heapify, lambda n=n: gen(n))
    row(f"heapify n={n:,}", hq, hx)

print("\n--- Max Heap ---")
for n in [1000, 10000, 100000]:
    hq = bench(lambda d: (d.__setitem__(slice(None), [-x for x in d]), heapq.heapify(d)), lambda n=n: gen(n))
    hx = bench(lambda d: heapx.heapify(d, max_heap=True), lambda n=n: gen(n))
    row(f"max-heap n={n:,}", hq, hx)

print("\n--- Ternary (arity=3) ---")
for n in [1000, 10000, 100000]:
    hq = bench(heapq.heapify, lambda n=n: gen(n))
    hx = bench(lambda d: heapx.heapify(d, arity=3), lambda n=n: gen(n))
    row(f"ternary n={n:,}", hq, hx)

print("\n--- Quaternary (arity=4) ---")
for n in [1000, 10000, 100000]:
    hq = bench(heapq.heapify, lambda n=n: gen(n))
    hx = bench(lambda d: heapx.heapify(d, arity=4), lambda n=n: gen(n))
    row(f"quaternary n={n:,}", hq, hx)

print("\n--- With Key (cmp=abs) ---")
for n in [1000, 10000]:
    hq = bench(lambda d: heapq.heapify([(abs(x),x) for x in d]), lambda n=n: gen(n))
    hx = bench(lambda d: heapx.heapify(d, cmp=abs), lambda n=n: gen(n))
    row(f"with key n={n:,}", hq, hx)

print("\n" + "="*80)
print(" PUSH")
print("="*80)
for n in [1000, 10000, 100000]:
    def setup_hq(n=n):
        d = gen(n); heapq.heapify(d); return d
    def setup_hx(n=n):
        d = gen(n); heapx.heapify(d); return d
    hq = bench(lambda d: heapq.heappush(d, 0), setup_hq)
    hx = bench(lambda d: heapx.push(d, 0), setup_hx)
    row(f"push n={n:,}", hq, hx)

print("\n--- Bulk Push (100 items) ---")
items = list(range(100))
for n in [1000, 10000]:
    def setup_hq(n=n):
        d = gen(n); heapq.heapify(d); return d
    def setup_hx(n=n):
        d = gen(n); heapx.heapify(d); return d
    hq = bench(lambda d: [heapq.heappush(d, i) for i in items], setup_hq)
    hx = bench(lambda d: heapx.push(d, items), setup_hx)
    row(f"bulk push 100, n={n:,}", hq, hx)

print("\n" + "="*80)
print(" POP")
print("="*80)
for n in [1000, 10000, 100000]:
    def setup_hq(n=n):
        d = gen(n); heapq.heapify(d); return d
    def setup_hx(n=n):
        d = gen(n); heapx.heapify(d); return d
    hq = bench(lambda d: heapq.heappop(d), setup_hq)
    hx = bench(lambda d: heapx.pop(d), setup_hx)
    row(f"pop n={n:,}", hq, hx)

print("\n--- Bulk Pop (100 items) ---")
for n in [1000, 10000]:
    def setup_hq(n=n):
        d = gen(n); heapq.heapify(d); return d
    def setup_hx(n=n):
        d = gen(n); heapx.heapify(d); return d
    hq = bench(lambda d: [heapq.heappop(d) for _ in range(100)], setup_hq)
    hx = bench(lambda d: heapx.pop(d, n=100), setup_hx)
    row(f"bulk pop 100, n={n:,}", hq, hx)

print("\n" + "="*80)
print(" REMOVE (heapx exclusive - O(log n) vs naive O(n))")
print("="*80)
for n in [1000, 10000, 100000]:
    def setup(n=n):
        d = gen(n); heapx.heapify(d); return d
    naive = bench(lambda d: (d.pop(n//2), heapx.heapify(d)), setup)
    hx = bench(lambda d: heapx.remove(d, indices=n//2), setup)
    row(f"remove idx n={n:,}", naive, hx)

print("\n" + "="*80)
print(" REPLACE (heapx exclusive - O(log n) vs naive O(n))")
print("="*80)
for n in [1000, 10000, 100000]:
    def setup(n=n):
        d = gen(n); heapx.heapify(d); return d
    naive = bench(lambda d: (d.__setitem__(n//2, -999), heapx.heapify(d)), setup)
    hx = bench(lambda d: heapx.replace(d, -999, indices=n//2), setup)
    row(f"replace idx n={n:,}", naive, hx)

print("\n" + "="*80)
print(" MERGE")
print("="*80)
for n in [1000, 10000, 50000]:
    def setup_hq(n=n):
        d1, d2 = gen(n, 42), gen(n, 43)
        heapq.heapify(d1); heapq.heapify(d2)
        return (d1, d2)
    def setup_hx(n=n):
        d1, d2 = gen(n, 42), gen(n, 43)
        heapx.heapify(d1); heapx.heapify(d2)
        return (d1, d2)
    hq = bench(lambda h: heapq.heapify(h[0] + h[1]), setup_hq)
    hx = bench(lambda h: heapx.merge(h[0], h[1]), setup_hx)
    row(f"merge 2×{n:,}", hq, hx)

print("\n" + "="*80)
print(" SORT")
print("="*80)
for n in [1000, 10000, 100000]:
    py = bench(sorted, lambda n=n: gen(n))
    hx = bench(heapx.sort, lambda n=n: gen(n))
    row(f"sort n={n:,} (sorted vs heapx.sort)", py, hx)

print("\n" + "="*80)
print(f"Python: {sys.version}")
print(f"heapx: {heapx.__version__}")
