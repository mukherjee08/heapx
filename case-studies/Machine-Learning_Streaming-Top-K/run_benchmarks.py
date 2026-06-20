#!/usr/bin/env python3
"""Comprehensive benchmarks for CS5 — Streaming Top-K.

Collects data for every figure where heapx demonstrates superiority.
All data is saved to ./results/bench_data.json.
"""
from __future__ import annotations
import heapq, json, sys, time
from pathlib import Path
import numpy as np

_SRC = Path(__file__).resolve().parent.parent.parent.parent.parent / "src"
if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))
import heapx

SEED = 42
RESULTS = Path(__file__).resolve().parent / "results"
W, R = 2, 5  # warmup, runs

def _med(fn, *a, **kw):
  ts = []
  res = None
  for i in range(W + R):
    t0 = time.perf_counter()
    res = fn(*a, **kw)
    t = time.perf_counter() - t0
    if i >= W:
      ts.append(t)
  return float(np.median(ts)), res

# ── 1. Bulk heapify: heapx vs heapq vs sortedcontainers ──────────
def bench_heapify():
  print("=== 1. Bulk Heapify (float) ===")
  scores = np.random.default_rng(SEED).standard_normal(10_000_000)
  sizes = [1_000, 5_000, 10_000, 50_000, 100_000, 500_000,
           1_000_000, 5_000_000]
  out = {"sizes": [], "heapx_ms": [], "heapq_ms": [], "speedup": []}
  for sz in sizes:
    d = scores[:sz].tolist()
    t_hx, _ = _med(lambda: heapx.heapify(d[:]))
    t_hq, _ = _med(lambda: heapq.heapify(d[:]))
    sp = t_hq / t_hx if t_hx > 0 else 0
    out["sizes"].append(sz)
    out["heapx_ms"].append(round(t_hx * 1e3, 4))
    out["heapq_ms"].append(round(t_hq * 1e3, 4))
    out["speedup"].append(round(sp, 2))
    print(f"  N={sz:>9,}  hx={t_hx*1e3:8.3f}ms  hq={t_hq*1e3:8.3f}ms  {sp:.2f}×")
  return out

# ── 2. Bulk pop (top-k extraction): heapx vs heapq ───────────────
def bench_bulk_pop():
  print("\n=== 2. Bulk Pop Top-K ===")
  scores = np.random.default_rng(SEED).standard_normal(1_000_000)
  k_vals = [1] + list(range(1_000, 101_000, 1_000))
  out = {"k_values": [], "heapx_ms": [], "heapq_ms": [],
         "numpy_ms": [], "sorted_ms": [], "speedup": []}
  d = scores.tolist()
  d_arr = scores.copy()
  for k in k_vals:
    def hx_pop():
      h = d[:]
      heapx.heapify(h, max_heap=True)
      return heapx.pop(h, n=k, max_heap=True)
    def hq_pop():
      return heapq.nlargest(k, d)
    def np_pop():
      return d_arr[np.argpartition(d_arr, -k)[-k:]]
    def sorted_pop():
      return sorted(d, reverse=True)[:k]
    t_hx, _ = _med(hx_pop)
    t_hq, _ = _med(hq_pop)
    t_np, _ = _med(np_pop)
    t_py, _ = _med(sorted_pop)
    sp = t_hq / t_hx if t_hx > 0 else 0
    out["k_values"].append(k)
    out["heapx_ms"].append(round(t_hx * 1e3, 3))
    out["heapq_ms"].append(round(t_hq * 1e3, 3))
    out["numpy_ms"].append(round(t_np * 1e3, 3))
    out["sorted_ms"].append(round(t_py * 1e3, 3))
    out["speedup"].append(round(sp, 2))
    if k <= 1 or k % 10_000 == 0:
      print(f"  K={k:>7,}  hx={t_hx*1e3:8.2f}  hq={t_hq*1e3:8.2f}  "
            f"np={t_np*1e3:8.2f}  py={t_py*1e3:8.2f}ms  {sp:.2f}×")
  print(f"  … {len(k_vals)} K values benchmarked.")
  return out

# ── 3. Heapify by data type: int, float, str, tuple ──────────────
def bench_type_specialization():
  print("\n=== 3. Type-Specialized Heapify ===")
  rng = np.random.default_rng(SEED)
  n = 500_000
  datasets = {
    "float": rng.standard_normal(n).tolist(),
    "int": rng.integers(0, 10_000_000, n).tolist(),
    "str": [f"item_{i:08d}" for i in rng.permutation(n)],
    "tuple": [(float(rng.standard_normal()), i) for i in range(n)],
  }
  out = {"types": [], "heapx_ms": [], "heapq_ms": [], "speedup": []}
  for dtype, data in datasets.items():
    t_hx, _ = _med(lambda: heapx.heapify(data[:]))
    t_hq, _ = _med(lambda: heapq.heapify(data[:]))
    sp = t_hq / t_hx if t_hx > 0 else 0
    out["types"].append(dtype)
    out["heapx_ms"].append(round(t_hx * 1e3, 3))
    out["heapq_ms"].append(round(t_hq * 1e3, 3))
    out["speedup"].append(round(sp, 2))
    print(f"  {dtype:>5s}  hx={t_hx*1e3:8.2f}ms  hq={t_hq*1e3:8.2f}ms  {sp:.2f}×")
  return out

# ── 4. Arity comparison (heapx-only feature) ─────────────────────
def bench_arity():
  print("\n=== 4. Arity Comparison (heapx only) ===")
  scores = np.random.default_rng(SEED).standard_normal(1_000_000).tolist()
  arities = [2, 3, 4, 8]
  out = {"arities": [], "heapify_ms": []}
  for a in arities:
    t, _ = _med(lambda: heapx.heapify(scores[:], arity=a))
    out["arities"].append(a)
    out["heapify_ms"].append(round(t * 1e3, 3))
    print(f"  arity={a}  {t*1e3:.2f} ms")
  return out

# ── 5. Streaming top-k end-to-end (heapx vs heapq vs numpy) ──────
def bench_streaming():
  print("\n=== 5. Streaming Top-K End-to-End ===")
  N = 10_000_000
  K = 1_000
  scores = np.random.default_rng(SEED).standard_normal(N)

  def hx_stream():
    h = scores[:K].tolist()
    heapx.heapify(h)
    for i in range(K, N):
      s = float(scores[i])
      if s > h[0]:
        heapx.replace(h, s, indices=0)
    return sorted(h, reverse=True)

  def hq_stream():
    h = scores[:K].tolist()
    heapq.heapify(h)
    for i in range(K, N):
      s = float(scores[i])
      if s > h[0]:
        heapq.heapreplace(h, s)
    return sorted(h, reverse=True)

  def np_batch():
    topk = scores[:K].copy()
    topk.sort()
    for start in range(K, N, 100_000):
      end = min(start + 100_000, N)
      combined = np.concatenate([topk, scores[start:end]])
      topk = combined[np.argpartition(combined, -K)[-K:]]
      topk.sort()
    return sorted(topk.tolist(), reverse=True)

  t_hx, r_hx = _med(hx_stream)
  t_hq, r_hq = _med(hq_stream)
  t_np, r_np = _med(np_batch)
  assert r_hx == r_hq == r_np, "Results mismatch!"
  print("  ✓ All methods agree.")

  out = {}
  for name, t in [("heapx", t_hx), ("heapq", t_hq), ("numpy", t_np)]:
    out[name] = {"wall_s": round(t, 4), "throughput_M": round(N / t / 1e6, 2)}
    print(f"  {name:5s}: {t:.3f}s  ({N/t/1e6:.1f}M scores/s)")
  return out

# ── 6. Parallel heapify scaling ───────────────────────────────────
def bench_parallel():
  print("\n=== 6. Parallel Heapify ===")
  import threading
  N_ARR, N_PER = 8, 2_000_000
  rng = np.random.default_rng(100)
  template = [rng.standard_normal(N_PER).tolist() for _ in range(N_ARR)]

  def run_par(nt, nogil):
    arrays = [a[:] for a in template]
    chunks = [[] for _ in range(nt)]
    for i in range(N_ARR):
      chunks[i % nt].append(i)
    barrier = threading.Barrier(nt)
    def worker(idxs):
      barrier.wait()
      for i in idxs:
        heapx.heapify(arrays[i], nogil=nogil)
    threads = [threading.Thread(target=worker, args=(chunks[t],))
               for t in range(nt)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    return time.perf_counter() - t0

  out = {"threads": [1, 2, 4, 8], "nogil_true": [], "nogil_false": []}
  base_t = base_f = 0
  for nt in out["threads"]:
    ts_t = [run_par(nt, True) for _ in range(R)]
    ts_f = [run_par(nt, False) for _ in range(R)]
    mt = float(np.median(ts_t))
    mf = float(np.median(ts_f))
    if nt == 1:
      base_t, base_f = mt, mf
    out["nogil_true"].append(round(base_t / mt, 2))
    out["nogil_false"].append(round(base_f / mf, 2))
    print(f"  {nt}T  nogil=True: {mt:.3f}s ({base_t/mt:.2f}×)  "
          f"nogil=False: {mf:.3f}s ({base_f/mf:.2f}×)")

  # Single-threaded baselines: heapq and sorted() processing all 8 arrays
  def run_heapq_seq():
    for a in template:
      d = a[:]
      heapq.heapify(d)

  def run_sorted_seq():
    for a in template:
      sorted(a)

  ts_hq = [0.0] * (W + R)
  ts_py = [0.0] * (W + R)
  for i in range(W + R):
    t0 = time.perf_counter(); run_heapq_seq(); ts_hq[i] = time.perf_counter() - t0
    t0 = time.perf_counter(); run_sorted_seq(); ts_py[i] = time.perf_counter() - t0
  t_hq = float(np.median(ts_hq[W:]))
  t_py = float(np.median(ts_py[W:]))
  # Express as speedup relative to heapx nogil=True 1-thread baseline
  out["heapq_speedup"] = round(base_t / t_hq, 2) if t_hq > 0 else 0
  out["sorted_speedup"] = round(base_t / t_py, 2) if t_py > 0 else 0
  print(f"  heapq seq: {t_hq:.3f}s (rel speedup={out['heapq_speedup']:.2f}×)")
  print(f"  sorted seq: {t_py:.3f}s (rel speedup={out['sorted_speedup']:.2f}×)")

  return out

# ── 7. Push throughput: single + bulk ─────────────────────────────
def bench_push():
  print("\n=== 7. Push Throughput ===")
  rng = np.random.default_rng(SEED)
  n_push = 100_000
  items = rng.standard_normal(n_push).tolist()

  # Single push into existing heap of 100K
  base = rng.standard_normal(100_000).tolist()

  def hx_single():
    h = base[:]
    heapx.heapify(h)
    for x in items:
      heapx.push(h, x)

  def hq_single():
    h = base[:]
    heapq.heapify(h)
    for x in items:
      heapq.heappush(h, x)

  # SortedList: maintains sorted order on each add
  from sortedcontainers import SortedList
  def sl_single():
    s = SortedList(base)
    for x in items:
      s.add(x)

  # list.append + re-sort: naive baseline
  def naive_single():
    h = base[:]
    for x in items:
      h.append(x)
    h.sort()

  t_hx, _ = _med(hx_single)
  t_hq, _ = _med(hq_single)
  t_sl, _ = _med(sl_single)
  t_naive, _ = _med(naive_single)
  sp_single = t_hq / t_hx if t_hx > 0 else 0

  # Bulk push
  def hx_bulk():
    h = base[:]
    heapx.heapify(h)
    heapx.push(h, items)

  t_hx_b, _ = _med(hx_bulk)
  sp_bulk = t_hq / t_hx_b if t_hx_b > 0 else 0

  out = {
    "n_push": n_push,
    "single_heapx_ms": round(t_hx * 1e3, 2),
    "single_heapq_ms": round(t_hq * 1e3, 2),
    "single_sortedlist_ms": round(t_sl * 1e3, 2),
    "naive_append_sort_ms": round(t_naive * 1e3, 2),
    "single_speedup": round(sp_single, 2),
    "bulk_heapx_ms": round(t_hx_b * 1e3, 2),
    "bulk_speedup_vs_heapq_single": round(sp_bulk, 2),
  }
  print(f"  Single: hx={t_hx*1e3:.1f}ms  hq={t_hq*1e3:.1f}ms  {sp_single:.2f}×")
  print(f"  SortedList: {t_sl*1e3:.1f}ms  naive: {t_naive*1e3:.1f}ms")
  print(f"  Bulk:   hx={t_hx_b*1e3:.1f}ms  vs heapq single: {sp_bulk:.2f}×")
  return out

# ── Main ──────────────────────────────────────────────────────────
def main():
  data = {}
  data["heapify"] = bench_heapify()
  data["bulk_pop"] = bench_bulk_pop()
  data["type_spec"] = bench_type_specialization()
  data["arity"] = bench_arity()
  data["streaming"] = bench_streaming()
  data["parallel"] = bench_parallel()
  data["push"] = bench_push()

  RESULTS.mkdir(parents=True, exist_ok=True)
  with open(RESULTS / "bench_data.json", "w") as f:
    json.dump(data, f, indent=2)
  print(f"\nAll data → {RESULTS / 'bench_data.json'}")

if __name__ == "__main__":
  main()
