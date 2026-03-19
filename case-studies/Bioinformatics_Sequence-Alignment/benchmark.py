"""
Benchmark harness for Case Study 2: Bioinformatics Sequence Alignment.

Executes four sub-benchmarks that map directly to the main.tex comments:

  1. SW Beam-Search Alignment — heapx vs heapq end-to-end comparison,
     single-threaded.  Measures alignment throughput (pairs/second).

  2. Heap Arity Comparison — quaternary vs binary vs ternary vs octonary
     heaps on the beam-search workload.

  3. Neighbor-Joining Tree Construction — heapx (with O(log n) remove)
     vs heapq (with O(n) rebuild) on phylogenetic distance matrices.

  4. Parallel Heap Operations — heapx(nogil=True) vs heapx(GIL) vs heapq
     on homogeneous float arrays (heapify + bulk pop + bounded replace)
     across 1, 2, 4, 8 threads.  This isolates the GIL-release advantage
     on the heap-intensive kernel that would be used in a production
     multi-threaded alignment pipeline where DP is done in C/Cython.

All results are written to JSON for consumption by the visualization
scripts.  Timing uses time.perf_counter for wall-clock precision.

Usage:
  python benchmark.py            # Run all benchmarks
  python benchmark.py --quick    # Reduced dataset for CI / smoke test
"""

from __future__ import annotations

import argparse
import copy
import heapq
import json
import os
import random
import time
import threading
from typing import Any, Dict, List

import heapx

from config import (
  N_PAIRS,
  BEAM_WIDTH,
  TOP_K,
  THREAD_COUNTS,
  ARITY_VALUES,
  NJ_N_TAXA,
  RNG_SEED,
)
from seqgen import generate_dataset
from alignment import sw_beam_align_heapx, sw_beam_align_heapq
from neighbor_joining import (
  generate_distance_matrix,
  nj_heapx,
  nj_heapq,
)


def _time_fn(fn, *args, **kwargs) -> tuple[Any, float]:
  """Time a function call, return (result, elapsed_seconds)."""
  t0 = time.perf_counter()
  result = fn(*args, **kwargs)
  t1 = time.perf_counter()
  return result, t1 - t0


# -----------------------------------------------------------------------
# Benchmark 1: SW beam-search alignment (single-threaded, end-to-end)
# -----------------------------------------------------------------------

def bench_alignment_single_thread(pairs: List) -> Dict[str, float]:
  """End-to-end alignment: heapx vs heapq, single-threaded."""
  n = len(pairs)

  t0 = time.perf_counter()
  for q, s in pairs:
    sw_beam_align_heapx(q, s, arity=4)
  t_hx = time.perf_counter() - t0

  t0 = time.perf_counter()
  for q, s in pairs:
    sw_beam_align_heapq(q, s)
  t_hq = time.perf_counter() - t0

  hx_tp = n / t_hx
  hq_tp = n / t_hq
  print(f"  heapx: {hx_tp:.1f} pairs/s ({t_hx:.2f}s)")
  print(f"  heapq: {hq_tp:.1f} pairs/s ({t_hq:.2f}s)")
  print(f"  speedup: {hx_tp / hq_tp:.2f}x")

  return {
    "heapx_pairs_per_sec": hx_tp,
    "heapq_pairs_per_sec": hq_tp,
    "heapx_time": t_hx,
    "heapq_time": t_hq,
    "speedup": hx_tp / hq_tp,
  }


# -----------------------------------------------------------------------
# Benchmark 2: Heap arity comparison
# -----------------------------------------------------------------------

def bench_arity_comparison(
  pairs: List, arities: List[int],
) -> Dict[int, float]:
  """Benchmark alignment time across heap arities (single-threaded)."""
  results: Dict[int, float] = {}
  for arity in arities:
    t0 = time.perf_counter()
    for q, s in pairs:
      sw_beam_align_heapx(q, s, arity=arity)
    elapsed = time.perf_counter() - t0
    results[arity] = len(pairs) / elapsed
    print(f"  arity={arity}: {results[arity]:.1f} pairs/s ({elapsed:.2f}s)")
  return results


# -----------------------------------------------------------------------
# Benchmark 3: Neighbor-joining
# -----------------------------------------------------------------------

def bench_neighbor_joining(n_taxa: int) -> Dict[str, float]:
  """Benchmark NJ tree construction: heapx vs heapq."""
  results: Dict[str, float] = {}

  dist_hx = generate_distance_matrix(n_taxa)
  dist_hq = copy.deepcopy(dist_hx)

  print(f"  NJ heapx (n={n_taxa})...")
  _, t_hx = _time_fn(nj_heapx, dist_hx, arity=4)
  results["heapx"] = t_hx
  print(f"    heapx: {t_hx:.3f}s")

  print(f"  NJ heapq (n={n_taxa})...")
  _, t_hq = _time_fn(nj_heapq, dist_hq)
  results["heapq"] = t_hq
  print(f"    heapq: {t_hq:.3f}s")

  results["speedup"] = t_hq / t_hx if t_hx > 0 else float("inf")
  print(f"    speedup: {results['speedup']:.2f}x")
  return results


# -----------------------------------------------------------------------
# Benchmark 4: Parallel heap operations (GIL-release demonstration)
# -----------------------------------------------------------------------

def _heap_worker_heapx(
  arrays: List[List[float]], out: list, idx: int,
  arity: int, nogil: bool,
) -> None:
  """Worker: heapify + bulk pop + bounded replace on float arrays."""
  t0 = time.perf_counter()
  for arr in arrays:
    h = list(arr)
    heapx.heapify(h, max_heap=True, arity=arity, nogil=nogil)
    k = min(100, len(h))
    if k > 0:
      heapx.pop(h, n=k, max_heap=True, arity=arity)
    for v in range(500):
      if h:
        heapx.replace(h, float(v * 0.001), indices=0, max_heap=True, arity=arity)
  out[idx] = time.perf_counter() - t0


def _heap_worker_heapq(
  arrays: List[List[float]], out: list, idx: int,
) -> None:
  """Worker: heapify + individual pops + heapreplace (heapq baseline)."""
  t0 = time.perf_counter()
  for arr in arrays:
    h = [-x for x in arr]
    heapq.heapify(h)
    k = min(100, len(h))
    for _ in range(k):
      if h:
        heapq.heappop(h)
    for v in range(500):
      if h:
        heapq.heapreplace(h, -float(v * 0.001))
  out[idx] = time.perf_counter() - t0


def bench_parallel_heap_ops(
  n_threads_list: List[int],
  n_arrays: int = 200,
  array_size: int = 50000,
) -> Dict[str, Any]:
  """Parallel heap operations on large homogeneous float arrays.

  This benchmark isolates the heap-operation throughput from the
  Python DP loop, demonstrating the GIL-release advantage for
  production pipelines where alignment DP is implemented in C/Cython
  and the heap operations are the remaining Python bottleneck.
  """
  rng = random.Random(RNG_SEED)
  arrays = [[rng.random() * 1e6 for _ in range(array_size)] for _ in range(n_arrays)]

  ops_per_array = array_size + 100 + 500
  total_ops = n_arrays * ops_per_array

  results: Dict[str, dict] = {"heapx_nogil": {}, "heapx_gil": {}, "heapq": {}}

  for nt in n_threads_list:
    chunk = n_arrays // nt
    chunks = [arrays[i * chunk:(i + 1) * chunk] for i in range(nt)]
    if n_arrays % nt:
      chunks[-1] = arrays[(nt - 1) * chunk:]

    # heapx nogil=True
    out = [0.0] * nt
    threads = [threading.Thread(target=_heap_worker_heapx, args=(chunks[i], out, i, 4, True)) for i in range(nt)]
    w0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    wall = time.perf_counter() - w0
    results["heapx_nogil"][nt] = total_ops / wall

    # heapx nogil=False
    out = [0.0] * nt
    threads = [threading.Thread(target=_heap_worker_heapx, args=(chunks[i], out, i, 4, False)) for i in range(nt)]
    w0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    wall = time.perf_counter() - w0
    results["heapx_gil"][nt] = total_ops / wall

    # heapq
    out = [0.0] * nt
    threads = [threading.Thread(target=_heap_worker_heapq, args=(chunks[i], out, i)) for i in range(nt)]
    w0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    wall = time.perf_counter() - w0
    results["heapq"][nt] = total_ops / wall

    print(f"  threads={nt}: "
          f"heapx_nogil={results['heapx_nogil'][nt]:.0f} ops/s, "
          f"heapx_gil={results['heapx_gil'][nt]:.0f} ops/s, "
          f"heapq={results['heapq'][nt]:.0f} ops/s")

  return results


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

def main() -> None:
  parser = argparse.ArgumentParser(
    description="Bioinformatics sequence alignment benchmark (heapx vs heapq)."
  )
  parser.add_argument(
    "--quick", action="store_true",
    help="Reduced dataset for quick smoke test.",
  )
  args = parser.parse_args()

  n_pairs = 100 if args.quick else N_PAIRS
  nj_taxa = 80 if args.quick else NJ_N_TAXA
  thread_counts = [1, 2] if args.quick else THREAD_COUNTS
  n_heap_arrays = 20 if args.quick else 200
  heap_array_size = 5000 if args.quick else 50000

  print(f"Generating {n_pairs} sequence pairs (seed={RNG_SEED})...")
  pairs = generate_dataset(n_pairs)
  print(f"  Mean query length: {sum(len(q) for q, _ in pairs) / len(pairs):.0f}")

  all_results: Dict[str, Any] = {
    "config": {
      "n_pairs": n_pairs,
      "beam_width": BEAM_WIDTH,
      "top_k": TOP_K,
      "rng_seed": RNG_SEED,
      "nj_taxa": nj_taxa,
    }
  }

  # Benchmark 1: Single-threaded alignment.
  print("\n=== Benchmark 1: Alignment Throughput (single-threaded) ===")
  all_results["alignment_single"] = bench_alignment_single_thread(pairs)

  # Benchmark 2: Arity comparison.
  print("\n=== Benchmark 2: Heap Arity Comparison ===")
  arity_pairs = pairs[:max(50, n_pairs // 4)]
  all_results["arity_comparison"] = bench_arity_comparison(
    arity_pairs, ARITY_VALUES,
  )

  # Benchmark 3: Neighbor-joining.
  print("\n=== Benchmark 3: Neighbor-Joining Tree Construction ===")
  all_results["neighbor_joining"] = bench_neighbor_joining(nj_taxa)

  # Benchmark 4: Parallel heap operations.
  print("\n=== Benchmark 4: Parallel Heap Operations (GIL-release) ===")
  all_results["parallel_heap_ops"] = bench_parallel_heap_ops(
    thread_counts, n_arrays=n_heap_arrays, array_size=heap_array_size,
  )

  # Write results.
  out_path = os.path.join(os.path.dirname(__file__), "results.json")
  with open(out_path, "w") as f:
    json.dump(all_results, f, indent=2, default=str)
  print(f"\nResults written to {out_path}")


if __name__ == "__main__":
  main()
