"""Benchmark runner for Case Study 3: Dijkstra's Algorithm.

Loads the full DIMACS USA road network once, extracts connected subgraphs
of increasing size via BFS, and runs Dijkstra implementations.

The heapx-replace method (with position tracking) is only run on smaller
subgraphs due to the O(heap_size) position rebuild overhead.

Usage:
  python3 benchmark.py            # default sizes
  python3 benchmark.py --quick    # small test run
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import time
import tracemalloc
from typing import Any

import numpy as np

from dimacs_loader import load_graph, extract_subgraph, GR_DIST, GR_TIME
from dijkstra import (
  dijkstra_heapx_replace,
  dijkstra_heapx_lazy,
  dijkstra_heapq,
  dijkstra_sortedlist,
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

BFS_SEED = 0

# heapx-replace is only run for subgraphs up to this size
REPLACE_MAX_NODES = 100_000


def _measure(func, *args) -> tuple[Any, float, int]:
  """Run func(*args), return (result, wall_seconds, peak_memory_bytes)."""
  gc.collect()
  gc.disable()
  tracemalloc.start()
  t0 = time.perf_counter()
  result = func(*args)
  elapsed = time.perf_counter() - t0
  _, peak = tracemalloc.get_traced_memory()
  tracemalloc.stop()
  gc.enable()
  return result, elapsed, peak


def run_benchmark(
  sizes: list[int],
  graph_path: str,
  label: str,
) -> list[dict]:
  """Run Dijkstra benchmarks on BFS-extracted subgraphs."""
  print(f"\nLoading full graph: {graph_path}")
  n_full, off_full, tgt_full, wt_full = load_graph(graph_path)
  print(f"  Full graph: {n_full:,} nodes, {int(off_full[n_full]):,} edges")

  results: list[dict] = []

  for target_size in sizes:
    print(f"\n{'='*60}")
    print(f"Extracting subgraph: ~{target_size:,} nodes ({label} weights)")
    print(f"{'='*60}")

    sub_n, sub_off, sub_tgt, sub_wt, sub_src, old_ids = extract_subgraph(
      n_full, off_full, tgt_full, wt_full, BFS_SEED, target_size,
    )
    sub_m = int(sub_off[sub_n])
    print(f"  Subgraph: {sub_n:,} nodes, {sub_m:,} edges, source={sub_src}")

    ref_dist = None

    methods: list[tuple[str, Any]] = []
    if target_size <= REPLACE_MAX_NODES:
      methods.append(("heapx (replace)", dijkstra_heapx_replace))
    methods.extend([
      ("heapx (lazy)", dijkstra_heapx_lazy),
      ("heapq", dijkstra_heapq),
      ("sortedcontainers", dijkstra_sortedlist),
    ])

    for name, func in methods:
      print(f"\n  Running {name}...", end=" ", flush=True)
      (dist, stats), elapsed, peak_mem = _measure(
        func, sub_n, sub_off, sub_tgt, sub_wt, sub_src,
      )

      reachable = sum(1 for d in dist if d < float("inf"))

      if ref_dist is None:
        ref_dist = dist
      else:
        mismatches = sum(
          1 for a, b in zip(ref_dist, dist)
          if abs(a - b) > 1e-9
          and not (a == float("inf") and b == float("inf"))
        )
        if mismatches > 0:
          print(f"\n  WARNING: {mismatches} distance mismatches!")

      rec = {
        "num_nodes": sub_n,
        "num_edges": sub_m,
        "method": name,
        "weight_type": label,
        "source": sub_src,
        "elapsed_s": round(elapsed, 4),
        "peak_memory_bytes": peak_mem,
        "reachable_nodes": reachable,
        **stats,
      }
      results.append(rec)
      print(f"{elapsed:.2f}s  peak_mem={peak_mem / 1e6:.1f}MB  reachable={reachable:,}")
      print(f"    stats: {stats}")

  return results


def main():
  parser = argparse.ArgumentParser(
    description="Dijkstra benchmark on DIMACS USA road network",
  )
  parser.add_argument("--quick", action="store_true", help="Small test run")
  parser.add_argument(
    "--sizes", type=str, default=None,
    help="Comma-separated target node counts",
  )
  args = parser.parse_args()

  if args.sizes:
    sizes = [int(s.strip()) for s in args.sizes.split(",")]
  elif args.quick:
    sizes = [10_000, 50_000]
  else:
    sizes = [10_000, 50_000, 100_000, 500_000, 1_000_000]

  dist_results = run_benchmark(sizes, GR_DIST, "distance")
  time_results = run_benchmark(sizes, GR_TIME, "time")

  all_results = dist_results + time_results

  out_path = os.path.join(RESULTS_DIR, "benchmark_results.json")
  with open(out_path, "w") as f:
    json.dump(all_results, f, indent=2)
  print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
  main()
