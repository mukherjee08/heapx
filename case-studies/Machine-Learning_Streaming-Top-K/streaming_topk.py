#!/usr/bin/env python3
"""Case Study 5 — Machine Learning: Streaming Top-K.

Benchmarks the bounded-heap streaming top-k pattern used in beam search,
k-nearest-neighbor retrieval, and feature-importance selection.

Workload (per the SPE paper §7.5 specification):
  - Stream of N floating-point scores.
  - Maintain the top K largest scores in a bounded min-heap of size K.
  - Core operation: if new score > heap root, pop root and push new score.

Three benchmark dimensions:
  1. End-to-end streaming throughput (heapx vs heapq vs numpy batch).
  2. Bulk heapify of the initial K elements (where heapx's homogeneous
     float path and SIMD optimisations dominate).
  3. K-scaling: average replace latency as a function of heap size.

Competitors:
  1. heapx (pop + push)          — C-extension with fast-path dispatch.
  2. heapq.heapreplace           — CPython stdlib, fused replace.
  3. numpy.argpartition          — batch baseline (non-streaming).

Outputs (saved to ./results/):
  - throughput.json              — all benchmark data.
  - latency_heapx.npy           — per-replace latency array (heapx).
  - latency_heapq.npy           — per-replace latency array (heapq).

References:
  - Munro & Paterson 1980, "Selection and Sorting with Limited Storage"
  - Mouratidis et al. 2006, "Continuous Monitoring of Top-K Queries"
  - Freitag & Al-Onaizan 2017, "Beam Search Strategies for NMT"
  - Wiseman & Rush 2016, "Seq2Seq as Beam-Search Optimization"
  - Harris et al. 2020, "Array Programming with NumPy"
"""

from __future__ import annotations

import heapq
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

_SRC_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
  sys.path.insert(0, str(_SRC_DIR))

import heapx  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
N: int = 10_000_000
K: int = 1_000
SEED: int = 42
BATCH_SIZE: int = 100_000
WARMUP: int = 2
RUNS: int = 5

RESULTS_DIR: Path = Path(__file__).resolve().parent / "results"


def generate_scores(n: int, seed: int = SEED) -> np.ndarray:
  """Standard-normal scores — realistic for beam search log-probs."""
  return np.random.default_rng(seed).standard_normal(n)


# ===================================================================
# Streaming top-k implementations
# ===================================================================

def topk_heapx(scores: np.ndarray, k: int) -> tuple[list[float], np.ndarray]:
  """heapx streaming top-k using the fused ``replace`` operation.

  Per main.tex §7.5, ``heapx.replace(heap, new_score, indices=0)`` is the
  optimal bounded-heap top-k primitive: a single O(log K) sift-down that
  fuses pop-root and push-new into one call, eliminating one list
  append/pop pair per accepted element.
  """
  heap: list[float] = scores[:k].tolist()
  heapx.heapify(heap)
  latencies: list[float] = []
  for i in range(k, len(scores)):
    s = float(scores[i])
    if s > heap[0]:
      t0 = time.perf_counter_ns()
      heapx.replace(heap, s, indices=0)
      latencies.append((time.perf_counter_ns() - t0) * 1e-9)
  return heap, np.asarray(latencies, dtype=np.float64)


def topk_heapq(scores: np.ndarray, k: int) -> tuple[list[float], np.ndarray]:
  """heapq streaming top-k (fused heapreplace)."""
  heap: list[float] = scores[:k].tolist()
  heapq.heapify(heap)
  latencies: list[float] = []
  for i in range(k, len(scores)):
    s = float(scores[i])
    if s > heap[0]:
      t0 = time.perf_counter_ns()
      heapq.heapreplace(heap, s)
      latencies.append((time.perf_counter_ns() - t0) * 1e-9)
  return heap, np.asarray(latencies, dtype=np.float64)


def topk_numpy(scores: np.ndarray, k: int) -> list[float]:
  """NumPy batch top-k via argpartition."""
  topk = scores[:k].copy()
  topk.sort()
  for start in range(k, len(scores), BATCH_SIZE):
    end = min(start + BATCH_SIZE, len(scores))
    combined = np.concatenate([topk, scores[start:end]])
    topk = combined[np.argpartition(combined, -k)[-k:]]
    topk.sort()
  return topk.tolist()


# ===================================================================
# Benchmark: bulk heapify (where heapx truly excels)
# ===================================================================

def bench_heapify(scores: np.ndarray) -> dict[str, Any]:
  """Benchmark heapify of float arrays at various sizes.

  This is the operation where heapx's homogeneous-float detection,
  SIMD child selection, and bottom-up Floyd's algorithm provide the
  largest advantage over heapq.
  """
  sizes = [1_000, 10_000, 100_000, 1_000_000, 5_000_000]
  results: dict[str, Any] = {"sizes": sizes, "heapx": [], "heapq": []}

  for sz in sizes:
    data = scores[:sz].tolist()

    # heapx
    times_hx: list[float] = []
    for _ in range(WARMUP + RUNS):
      d = data[:]
      t0 = time.perf_counter()
      heapx.heapify(d)
      times_hx.append(time.perf_counter() - t0)
    med_hx = float(np.median(times_hx[WARMUP:]))

    # heapq
    times_hq: list[float] = []
    for _ in range(WARMUP + RUNS):
      d = data[:]
      t0 = time.perf_counter()
      heapq.heapify(d)
      times_hq.append(time.perf_counter() - t0)
    med_hq = float(np.median(times_hq[WARMUP:]))

    speedup = med_hq / med_hx if med_hx > 0 else 0
    results["heapx"].append({"n": sz, "time_ms": round(med_hx * 1e3, 3)})
    results["heapq"].append({"n": sz, "time_ms": round(med_hq * 1e3, 3)})
    print(f"  N={sz:>9,}  heapx={med_hx*1e3:7.2f} ms  "
          f"heapq={med_hq*1e3:7.2f} ms  speedup={speedup:.2f}×")

  return results


# ===================================================================
# Benchmark: K-scaling (replace latency vs heap size)
# ===================================================================

def bench_k_scaling(scores: np.ndarray) -> dict[str, Any]:
  """Replace latency as a function of K."""
  k_values = [10, 50, 100, 500, 1_000, 5_000, 10_000, 50_000, 100_000]
  results: dict[str, Any] = {"k_values": k_values, "heapx": [], "heapq": []}

  for kv in k_values:
    if kv > len(scores):
      break

    # Pre-compute which scores trigger replacement.
    sim = sorted(scores[:kv].tolist())
    heapq.heapify(sim)
    rs: list[float] = []
    for i in range(kv, len(scores)):
      s = float(scores[i])
      if s > sim[0]:
        rs.append(s)
        heapq.heapreplace(sim, s)
    nr = len(rs)
    if nr == 0:
      continue

    # heapx (fused replace)
    times_hx: list[float] = []
    for _ in range(WARMUP + RUNS):
      heap = scores[:kv].tolist()
      heapx.heapify(heap)
      t0 = time.perf_counter()
      for s in rs:
        heapx.replace(heap, s, indices=0)
      times_hx.append(time.perf_counter() - t0)
    med_hx = float(np.median(times_hx[WARMUP:]))

    # heapq (fused heapreplace)
    times_hq: list[float] = []
    for _ in range(WARMUP + RUNS):
      heap = scores[:kv].tolist()
      heapq.heapify(heap)
      t0 = time.perf_counter()
      for s in rs:
        heapq.heapreplace(heap, s)
      times_hq.append(time.perf_counter() - t0)
    med_hq = float(np.median(times_hq[WARMUP:]))

    ratio = med_hq / med_hx if med_hx > 0 else 0
    results["heapx"].append({
      "k": kv, "n_replaces": nr,
      "avg_ns": round(med_hx / nr * 1e9, 1),
    })
    results["heapq"].append({
      "k": kv, "n_replaces": nr,
      "avg_ns": round(med_hq / nr * 1e9, 1),
    })
    print(f"  K={kv:>6,}  n={nr:>8,}  "
          f"heapx={med_hx/nr*1e9:6.0f} ns  "
          f"heapq={med_hq/nr*1e9:6.0f} ns  "
          f"ratio={ratio:.2f}×")

  return results


# ===================================================================
# Benchmark: isolated replace-only
# ===================================================================

def bench_replace_only(scores: np.ndarray, k: int) -> dict[str, Any]:
  """Isolated replace benchmark (no Python iteration overhead)."""
  sim = sorted(scores[:k].tolist())
  heapq.heapify(sim)
  rs: list[float] = []
  for i in range(k, len(scores)):
    s = float(scores[i])
    if s > sim[0]:
      rs.append(s)
      heapq.heapreplace(sim, s)
  nr = len(rs)
  results: dict[str, Any] = {"n_replaces": nr}

  # heapx (fused replace)
  times: list[float] = []
  for _ in range(WARMUP + RUNS):
    heap = scores[:k].tolist()
    heapx.heapify(heap)
    t0 = time.perf_counter()
    for s in rs:
      heapx.replace(heap, s, indices=0)
    times.append(time.perf_counter() - t0)
  med = float(np.median(times[WARMUP:]))
  results["heapx"] = {
    "time_s": round(med, 6),
    "avg_ns": round(med / nr * 1e9, 1) if nr else 0,
    "ops_per_s": round(nr / med) if med > 0 else 0,
  }

  # heapq
  times = []
  for _ in range(WARMUP + RUNS):
    heap = scores[:k].tolist()
    heapq.heapify(heap)
    t0 = time.perf_counter()
    for s in rs:
      heapq.heapreplace(heap, s)
    times.append(time.perf_counter() - t0)
  med = float(np.median(times[WARMUP:]))
  results["heapq"] = {
    "time_s": round(med, 6),
    "avg_ns": round(med / nr * 1e9, 1) if nr else 0,
    "ops_per_s": round(nr / med) if med > 0 else 0,
  }

  hx_t = results["heapx"]["time_s"]
  hq_t = results["heapq"]["time_s"]
  results["speedup"] = round(hq_t / hx_t, 2) if hx_t > 0 else 0
  return results


# ===================================================================
# Main harness
# ===================================================================

def _bench(fn, scores, k):
  """Run fn for WARMUP+RUNS iterations, return (median_time, last_result)."""
  result = None
  times: list[float] = []
  for i in range(WARMUP + RUNS):
    t0 = time.perf_counter()
    result = fn(scores, k)
    t = time.perf_counter() - t0
    if i >= WARMUP:
      times.append(t)
  return float(np.median(times)), result


def run_benchmarks() -> dict[str, Any]:
  print(f"Generating {N:,} scores (seed={SEED}) …")
  scores = generate_scores(N, SEED)
  print(f"  range=[{scores.min():.3f}, {scores.max():.3f}]  "
        f"mean={scores.mean():.4f}\n")

  out: dict[str, Any] = {
    "parameters": {"N": N, "K": K, "seed": SEED},
    "methods": {},
  }

  # --- 1. End-to-end streaming ---
  print("=== End-to-End Streaming Top-K ===\n")

  t_hx, (h_hx, lat_hx) = _bench(topk_heapx, scores, K)
  t_hq, (h_hq, lat_hq) = _bench(topk_heapq, scores, K)
  t_np, h_np = _bench(topk_numpy, scores, K)

  for name, t, extra in [
    ("heapx", t_hx, {"n_replaces": len(lat_hx),
                      "p50_us": round(float(np.percentile(lat_hx, 50)) * 1e6, 3) if len(lat_hx) else 0,
                      "p99_us": round(float(np.percentile(lat_hx, 99)) * 1e6, 3) if len(lat_hx) else 0}),
    ("heapq", t_hq, {"n_replaces": len(lat_hq),
                      "p50_us": round(float(np.percentile(lat_hq, 50)) * 1e6, 3) if len(lat_hq) else 0,
                      "p99_us": round(float(np.percentile(lat_hq, 99)) * 1e6, 3) if len(lat_hq) else 0}),
    ("numpy", t_np, {"batch_size": BATCH_SIZE}),
  ]:
    tput = N / t
    out["methods"][name] = {
      "wall_s": round(t, 6), "throughput": round(tput), **extra,
    }
    print(f"  [{name:5s}] {t:.3f} s  ({tput:,.0f} scores/s)")

  # Correctness
  ref = sorted(scores.tolist(), reverse=True)[:K]
  assert sorted(h_hx, reverse=True) == ref, "heapx mismatch"
  assert sorted(h_hq, reverse=True) == ref, "heapq mismatch"
  assert sorted(h_np, reverse=True) == ref, "numpy mismatch"
  print("  ✓ All methods agree.\n")

  # --- 2. Bulk heapify ---
  print("=== Bulk Heapify (homogeneous float) ===\n")
  out["heapify"] = bench_heapify(scores)

  # --- 3. Isolated replace ---
  print("\n=== Isolated Replace (K=1000) ===\n")
  out["replace_only"] = bench_replace_only(scores, K)
  ro = out["replace_only"]
  print(f"  {ro['n_replaces']:,} ops  "
        f"heapx={ro['heapx']['avg_ns']:.0f} ns  "
        f"heapq={ro['heapq']['avg_ns']:.0f} ns  "
        f"ratio={ro['speedup']:.2f}×")

  # --- 4. K-scaling ---
  print("\n=== K-Scaling ===\n")
  out["k_scaling"] = bench_k_scaling(scores)

  # --- Save ---
  RESULTS_DIR.mkdir(parents=True, exist_ok=True)
  with open(RESULTS_DIR / "throughput.json", "w") as f:
    json.dump(out, f, indent=2)
  np.save(RESULTS_DIR / "latency_heapx.npy", lat_hx)
  np.save(RESULTS_DIR / "latency_heapq.npy", lat_hq)
  print(f"\nSaved to {RESULTS_DIR}/")
  return out


if __name__ == "__main__":
  run_benchmarks()
