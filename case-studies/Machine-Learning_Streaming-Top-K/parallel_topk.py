#!/usr/bin/env python3
"""Parallel heapify benchmark — GIL-release demonstration.

Measures wall-time to heapify a FIXED total workload (8 arrays) using
1, 2, 4, or 8 threads.  With nogil=True, threads run in parallel;
with nogil=False, the GIL serialises them.

Speedup = wall_time(1 thread) / wall_time(T threads), where the
1-thread baseline processes all 8 arrays sequentially.

Outputs (saved to ./results/):
  - parallel_scaling.json
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import numpy as np

_SRC_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
  sys.path.insert(0, str(_SRC_DIR))

import heapx  # noqa: E402

N_ARRAYS: int = 8
N_PER_ARRAY: int = 2_000_000
SEED_BASE: int = 100
THREAD_COUNTS: list[int] = [1, 2, 4, 8, 12]
RUNS: int = 5

RESULTS_DIR: Path = Path(__file__).resolve().parent / "results"


def _make_arrays() -> list[list[float]]:
  """Generate N_ARRAYS fresh unsorted float lists."""
  rng = np.random.default_rng(SEED_BASE)
  return [rng.standard_normal(N_PER_ARRAY).tolist()
          for _ in range(N_ARRAYS)]


def _worker(arrays: list[list[float]], indices: list[int],
            use_nogil: bool, barrier: threading.Barrier) -> None:
  """Heapify the arrays at the given indices."""
  barrier.wait()
  for i in indices:
    heapx.heapify(arrays[i], nogil=use_nogil)


def bench(n_threads: int, template: list[list[float]],
          use_nogil: bool) -> float:
  """Heapify all N_ARRAYS arrays using n_threads threads.
  Returns median wall-time over RUNS trials."""
  times: list[float] = []
  for _ in range(RUNS):
    # Fresh copies each trial.
    arrays = [a[:] for a in template]
    # Partition array indices across threads.
    chunks: list[list[int]] = [[] for _ in range(n_threads)]
    for i in range(N_ARRAYS):
      chunks[i % n_threads].append(i)

    barrier = threading.Barrier(n_threads)
    threads = [
      threading.Thread(target=_worker,
                       args=(arrays, chunks[t], use_nogil, barrier))
      for t in range(n_threads)
    ]
    t0 = time.perf_counter()
    for t in threads:
      t.start()
    for t in threads:
      t.join()
    times.append(time.perf_counter() - t0)
  return float(np.median(times))


def run() -> dict:
  print(f"Generating {N_ARRAYS} arrays × {N_PER_ARRAY:,} floats …")
  template = _make_arrays()

  results: dict = {
    "parameters": {"n_arrays": N_ARRAYS, "n_per_array": N_PER_ARRAY},
    "nogil_true": {},
    "nogil_false": {},
  }

  for use_nogil in [True, False]:
    label = "nogil=True" if use_nogil else "nogil=False"
    key = "nogil_true" if use_nogil else "nogil_false"
    print(f"\n=== {label} ===")
    baseline: float = 0.0

    for nt in THREAD_COUNTS:
      t = bench(nt, template, use_nogil)
      if nt == 1:
        baseline = t
      sp = baseline / t if t > 0 else 0
      results[key][str(nt)] = {
        "wall_time_s": round(t, 4),
        "speedup": round(sp, 2),
      }
      print(f"  {nt} thread(s): {t:.3f} s  speedup={sp:.2f}×")

  # Compat key for visualiser.
  results["scaling"] = results["nogil_true"]

  RESULTS_DIR.mkdir(parents=True, exist_ok=True)
  with open(RESULTS_DIR / "parallel_scaling.json", "w") as f:
    json.dump(results, f, indent=2)
  print(f"\nSaved to {RESULTS_DIR}/parallel_scaling.json")
  return results


if __name__ == "__main__":
  run()
