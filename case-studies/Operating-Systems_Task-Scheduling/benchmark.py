"""
Multi-competitor benchmark suite for Case Study 6.

Compares heapx against four Python priority-queue implementations:
  - heapq          (stdlib, C-accelerated binary min-heap)
  - sortedcontainers.SortedList  (pure-Python B-tree-like sorted list)
  - heapdict       (pure-Python heap with decrease-key via dict index)
  - fibonacci_heap_mod  (pure-Python Fibonacci heap)

Each benchmark isolates a single operation at controlled queue sizes
to produce clean, reproducible data.

Benchmarks:
  B1. Batch push (heapx, heapq, sortedcontainers)
  B2. Single push at varying queue sizes (all 5)
  B3. Single pop at varying queue sizes (all 5)
  B4. Replace / decrease-key at varying queue sizes (all 5)
  B5. Replace-heavy end-to-end workload (all 5)
  B6. Queue size dynamics trace (heapx mixed workload, steady-state)
  B7. End-to-end scheduler throughput (HeapxScheduler vs HeapqScheduler)
"""

from __future__ import annotations

import gc
import json
import time
import sys
from typing import Any, Dict, List, Tuple

import heapx
import heapq
import numpy as np
from sortedcontainers import SortedList
import heapdict
from fibonacci_heap_mod import Fibonacci_heap

from task import Task
from workload import generate_workload
from scheduler_heapx import HeapxScheduler
from scheduler_heapq import HeapqScheduler

SEED = 42
_task_key = lambda t: (t.priority, t.deadline)


# ===================================================================
# Helpers
# ===================================================================
def _make_heap_heapx(tasks: List[Task]) -> List[Task]:
  h = list(tasks)
  heapx.heapify(h, cmp=_task_key)
  return h


def _make_heap_heapq(tasks: List[Task]) -> List:
  h = [(t.priority, t.deadline, i, t) for i, t in enumerate(tasks)]
  heapq.heapify(h)
  return h


def _time_ns(fn, *args, **kwargs) -> int:
  gc.disable()
  t0 = time.perf_counter_ns()
  fn(*args, **kwargs)
  elapsed = time.perf_counter_ns() - t0
  gc.enable()
  return elapsed


# ===================================================================
# B1: Batch push
# ===================================================================
def bench_batch_push(
  tasks: List[Task],
  sizes: List[int],
  reps: int = 5,
) -> Dict[str, Any]:
  """Batch push for heapx, heapq, sortedcontainers, heapdict, fibonacci_heap.

  Rep counts are auto-adapted at very large sizes to keep wall-clock
  reasonable; a single extended workload is generated once for the
  largest requested size, and every batch size takes a prefix slice.
  """
  results: Dict[str, List[List[float]]] = {
    "heapx": [], "heapq": [], "sortedcontainers": [],
    "heapdict": [], "fibonacci_heap": [],
  }
  max_sz = max(sizes)
  if max_sz > len(tasks):
    print(f"  (generating extended workload of {max_sz:,} tasks for B1)")
    tasks = generate_workload(n_tasks=max_sz, seed=SEED)
  for sz in sizes:
    batch = tasks[:sz]
    # Adapt reps: single-shot at >= 100M, 2 at 10M, else nominal.
    local_reps = 1 if sz >= 100_000_000 else (2 if sz >= 10_000_000 else reps)
    for mod in results:
      results[mod].append([])
    for _ in range(local_reps):
      # heapx
      h: List[Task] = []
      results["heapx"][-1].append(_time_ns(heapx.push, h, batch, cmp=_task_key) / 1e6)
      # heapq
      h2: List = []
      gc.disable(); t0 = time.perf_counter_ns()
      for i, t in enumerate(batch):
        heapq.heappush(h2, (t.priority, t.deadline, i, t))
      results["heapq"][-1].append((time.perf_counter_ns() - t0) / 1e6); gc.enable()
      # sortedcontainers
      sl = SortedList(key=_task_key)
      gc.disable(); t0 = time.perf_counter_ns()
      for t in batch:
        sl.add(t)
      results["sortedcontainers"][-1].append((time.perf_counter_ns() - t0) / 1e6); gc.enable()
      # heapdict
      hd = heapdict.heapdict()
      gc.disable(); t0 = time.perf_counter_ns()
      for i, t in enumerate(batch):
        hd[t.task_id] = (t.priority, t.deadline)
      results["heapdict"][-1].append((time.perf_counter_ns() - t0) / 1e6); gc.enable()
      # fibonacci_heap
      if sz <= 10_000_000:
        fh = Fibonacci_heap()
        gc.disable(); t0 = time.perf_counter_ns()
        for t in batch:
          fh.enqueue(t.priority * 1e9 + t.deadline, t.task_id)
        results["fibonacci_heap"][-1].append((time.perf_counter_ns() - t0) / 1e6); gc.enable()
      else:
        results["fibonacci_heap"][-1].append(float("nan"))
  return {"sizes": sizes, **results}


# ===================================================================
# B2: Single push at varying queue sizes
# ===================================================================
def bench_single_push(
  tasks: List[Task],
  queue_sizes: List[int],
  n_ops: int = 20_000,
  reps: int = 5,
) -> Dict[str, Any]:
  """Single-push latency into pre-built structures of varying size."""
  results: Dict[str, List[List[float]]] = {
    "heapx": [], "heapq": [], "sortedcontainers": [],
    "heapdict": [], "fibonacci_heap": [],
  }
  for qsz in queue_sizes:
    base = tasks[:qsz]
    extra = tasks[qsz:qsz + n_ops]
    for name in results:
      results[name].append([])

    for _ in range(reps):
      # heapx
      h = _make_heap_heapx(base)
      gc.disable()
      t0 = time.perf_counter_ns()
      for t in extra:
        heapx.push(h, t, cmp=_task_key)
      results["heapx"][-1].append((time.perf_counter_ns() - t0) / n_ops / 1e3)
      gc.enable()

      # heapq
      h2 = _make_heap_heapq(base)
      seq = qsz
      gc.disable()
      t0 = time.perf_counter_ns()
      for t in extra:
        heapq.heappush(h2, (t.priority, t.deadline, seq, t))
        seq += 1
      results["heapq"][-1].append((time.perf_counter_ns() - t0) / n_ops / 1e3)
      gc.enable()

      # sortedcontainers
      sl = SortedList(key=_task_key)
      for t in base:
        sl.add(t)
      gc.disable()
      t0 = time.perf_counter_ns()
      for t in extra:
        sl.add(t)
      results["sortedcontainers"][-1].append((time.perf_counter_ns() - t0) / n_ops / 1e3)
      gc.enable()

      # heapdict
      hd = heapdict.heapdict()
      for i, t in enumerate(base):
        hd[t.task_id] = (t.priority, t.deadline)
      gc.disable()
      t0 = time.perf_counter_ns()
      for t in extra:
        hd[t.task_id] = (t.priority, t.deadline)
      results["heapdict"][-1].append((time.perf_counter_ns() - t0) / n_ops / 1e3)
      gc.enable()

      # fibonacci_heap (measured at every queue size; op count capped to
      # keep wall-clock bounded, since Fibonacci heap enqueue is pure-Python).
      fh = Fibonacci_heap()
      for t in base:
        fh.enqueue(t.priority * 1e9 + t.deadline, t.task_id)
      ops = min(n_ops, 2000)
      gc.disable()
      t0 = time.perf_counter_ns()
      for t in extra[:ops]:
        fh.enqueue(t.priority * 1e9 + t.deadline, t.task_id)
      results["fibonacci_heap"][-1].append((time.perf_counter_ns() - t0) / ops / 1e3)
      gc.enable()

  return {"queue_sizes": queue_sizes, **results}


# ===================================================================
# B3: Single pop at varying queue sizes
# ===================================================================
def bench_single_pop(
  tasks: List[Task],
  queue_sizes: List[int],
  n_ops: int = 20_000,
  reps: int = 5,
) -> Dict[str, Any]:
  """Single-pop latency from pre-built structures of varying size."""
  results: Dict[str, List[List[float]]] = {
    "heapx": [], "heapq": [], "sortedcontainers": [],
    "heapdict": [], "fibonacci_heap": [],
  }
  for qsz in queue_sizes:
    base = tasks[:qsz]
    actual_ops = min(n_ops, qsz - 1)
    for name in results:
      results[name].append([])

    for _ in range(reps):
      # heapx
      h = _make_heap_heapx(base)
      gc.disable()
      t0 = time.perf_counter_ns()
      for _ in range(actual_ops):
        heapx.pop(h, cmp=_task_key)
      results["heapx"][-1].append((time.perf_counter_ns() - t0) / actual_ops / 1e3)
      gc.enable()

      # heapq
      h2 = _make_heap_heapq(base)
      gc.disable()
      t0 = time.perf_counter_ns()
      for _ in range(actual_ops):
        heapq.heappop(h2)
      results["heapq"][-1].append((time.perf_counter_ns() - t0) / actual_ops / 1e3)
      gc.enable()

      # sortedcontainers
      sl = SortedList(key=_task_key)
      for t in base:
        sl.add(t)
      gc.disable()
      t0 = time.perf_counter_ns()
      for _ in range(actual_ops):
        sl.pop(0)
      results["sortedcontainers"][-1].append((time.perf_counter_ns() - t0) / actual_ops / 1e3)
      gc.enable()

      # heapdict
      hd = heapdict.heapdict()
      for i, t in enumerate(base):
        hd[t.task_id] = (t.priority, t.deadline)
      gc.disable()
      t0 = time.perf_counter_ns()
      for _ in range(actual_ops):
        hd.popitem()
      results["heapdict"][-1].append((time.perf_counter_ns() - t0) / actual_ops / 1e3)
      gc.enable()

      # fibonacci_heap
      if qsz <= 50_000:
        fh = Fibonacci_heap()
        for t in base:
          fh.enqueue(t.priority * 1e9 + t.deadline, t.task_id)
        ops = min(actual_ops, 2000)
        gc.disable()
        t0 = time.perf_counter_ns()
        for _ in range(ops):
          fh.dequeue_min()
        results["fibonacci_heap"][-1].append((time.perf_counter_ns() - t0) / ops / 1e3)
        gc.enable()
      else:
        results["fibonacci_heap"][-1].append(float("nan"))

  return {"queue_sizes": queue_sizes, **results}


# ===================================================================
# B4: Replace / decrease-key at varying queue sizes
# ===================================================================
def bench_replace(
  tasks: List[Task],
  queue_sizes: List[int],
  n_ops: int = 5_000,
  reps: int = 5,
) -> Dict[str, Any]:
  """Replace (decrease-key) at random indices."""
  rng = np.random.default_rng(SEED + 20)
  results: Dict[str, List[List[float]]] = {
    "heapx": [], "heapq": [], "sortedcontainers": [],
    "heapdict": [], "fibonacci_heap": [],
  }
  for qsz in queue_sizes:
    base = tasks[:qsz]
    indices = rng.integers(0, qsz, size=n_ops)
    for name in results:
      results[name].append([])

    for _ in range(reps):
      # heapx: O(log n) replace
      h = _make_heap_heapx(base)
      gc.disable()
      t0 = time.perf_counter_ns()
      for idx in indices:
        idx = int(idx) % len(h)
        old = h[idx]
        new_t = Task(old.task_id, 0.0, old.deadline, old.arrival_time, old.burst)
        heapx.replace(h, new_t, indices=idx, cmp=_task_key)
      elapsed = time.perf_counter_ns() - t0
      gc.enable()
      results["heapx"][-1].append(elapsed / n_ops / 1e3)

      # heapq: remove + re-heapify + push = O(n)
      h2 = _make_heap_heapq(base)
      seq = qsz
      gc.disable()
      t0 = time.perf_counter_ns()
      for idx in indices:
        idx = int(idx) % len(h2)
        old_entry = h2[idx]
        old_task = old_entry[3]
        new_t = Task(old_task.task_id, 0.0, old_task.deadline,
                     old_task.arrival_time, old_task.burst)
        h2[idx] = h2[-1]
        h2.pop()
        if h2:
          heapq.heapify(h2)
        heapq.heappush(h2, (new_t.priority, new_t.deadline, seq, new_t))
        seq += 1
      elapsed = time.perf_counter_ns() - t0
      gc.enable()
      results["heapq"][-1].append(elapsed / n_ops / 1e3)

      # sortedcontainers: remove + add = O(log n) each
      sl = SortedList(key=_task_key)
      task_list = list(base)
      for t in task_list:
        sl.add(t)
      gc.disable()
      t0 = time.perf_counter_ns()
      for idx in indices:
        idx = int(idx) % len(task_list)
        old = task_list[idx]
        new_t = Task(old.task_id, 0.0, old.deadline, old.arrival_time, old.burst)
        sl.discard(old)
        sl.add(new_t)
        task_list[idx] = new_t
      elapsed = time.perf_counter_ns() - t0
      gc.enable()
      results["sortedcontainers"][-1].append(elapsed / n_ops / 1e3)

      # heapdict: O(log n) decrease-key via dict assignment
      hd = heapdict.heapdict()
      for i, t in enumerate(base):
        hd[t.task_id] = (t.priority, t.deadline)
      task_ids = [t.task_id for t in base]
      gc.disable()
      t0 = time.perf_counter_ns()
      for idx in indices:
        tid = task_ids[int(idx) % len(task_ids)]
        hd[tid] = (0.0, hd[tid][1])  # boost priority to 0
      elapsed = time.perf_counter_ns() - t0
      gc.enable()
      results["heapdict"][-1].append(elapsed / n_ops / 1e3)

      # fibonacci_heap: O(1) amortized decrease-key
      if qsz <= 50_000:
        fh = Fibonacci_heap()
        entries = []
        for t in base:
          entries.append(fh.enqueue(t.priority * 1e9 + t.deadline, t.task_id))
        ops = min(n_ops, 2000)
        gc.disable()
        t0 = time.perf_counter_ns()
        for idx in indices[:ops]:
          idx = int(idx) % len(entries)
          e = entries[idx]
          try:
            fh.decrease_key(e, 0.0)
          except Exception:
            pass  # already at minimum
        elapsed = time.perf_counter_ns() - t0
        gc.enable()
        results["fibonacci_heap"][-1].append(elapsed / ops / 1e3)
      else:
        results["fibonacci_heap"][-1].append(float("nan"))

  return {"queue_sizes": queue_sizes, **results}


# ===================================================================
# B5: Replace-heavy end-to-end workload
# ===================================================================
def bench_replace_heavy(
  tasks: List[Task],
  queue_sizes: List[int],
  n_replaces: int = 5_000,
  reps: int = 5,
) -> Dict[str, Any]:
  """End-to-end workload with frequent priority updates."""
  rng = np.random.default_rng(SEED + 40)
  results: Dict[str, List[List[float]]] = {
    "heapx": [], "heapq": [], "sortedcontainers": [],
    "heapdict": [],
  }
  for qsz in queue_sizes:
    base = tasks[:qsz]
    extra = tasks[qsz:qsz + n_replaces]
    for name in results:
      results[name].append([])

    for _ in range(reps):
      # heapx
      h = _make_heap_heapx(base)
      gc.disable()
      t0 = time.perf_counter_ns()
      for i in range(n_replaces):
        idx = int(rng.integers(0, len(h)))
        old = h[idx]
        new_t = Task(old.task_id, 0.0, old.deadline, old.arrival_time, old.burst)
        heapx.replace(h, new_t, indices=idx, cmp=_task_key)
        if i < len(extra):
          heapx.push(h, extra[i], cmp=_task_key)
          heapx.pop(h, cmp=_task_key)
      elapsed = time.perf_counter_ns() - t0
      gc.enable()
      results["heapx"][-1].append(elapsed / 1e9)

      # heapq
      h2 = _make_heap_heapq(base)
      seq = qsz
      gc.disable()
      t0 = time.perf_counter_ns()
      for i in range(n_replaces):
        idx = int(rng.integers(0, len(h2)))
        old_entry = h2[idx]
        old_task = old_entry[3]
        new_t = Task(old_task.task_id, 0.0, old_task.deadline,
                     old_task.arrival_time, old_task.burst)
        h2[idx] = h2[-1]; h2.pop()
        if h2: heapq.heapify(h2)
        heapq.heappush(h2, (new_t.priority, new_t.deadline, seq, new_t)); seq += 1
        if i < len(extra):
          t = extra[i]
          heapq.heappush(h2, (t.priority, t.deadline, seq, t)); seq += 1
          heapq.heappop(h2)
      elapsed = time.perf_counter_ns() - t0
      gc.enable()
      results["heapq"][-1].append(elapsed / 1e9)

      # sortedcontainers
      sl = SortedList(key=_task_key)
      task_list = list(base)
      for t in task_list: sl.add(t)
      gc.disable()
      t0 = time.perf_counter_ns()
      for i in range(n_replaces):
        idx = int(rng.integers(0, len(task_list)))
        old = task_list[idx]
        new_t = Task(old.task_id, 0.0, old.deadline, old.arrival_time, old.burst)
        sl.discard(old); sl.add(new_t); task_list[idx] = new_t
        if i < len(extra):
          sl.add(extra[i]); task_list.append(extra[i])
          sl.pop(0)
      elapsed = time.perf_counter_ns() - t0
      gc.enable()
      results["sortedcontainers"][-1].append(elapsed / 1e9)

      # heapdict
      hd = heapdict.heapdict()
      for j, t in enumerate(base):
        hd[t.task_id] = (t.priority, t.deadline)
      gc.disable()
      t0 = time.perf_counter_ns()
      task_ids = list(hd.keys())
      for i in range(n_replaces):
        idx = int(rng.integers(0, len(task_ids)))
        tid = task_ids[idx]
        if tid in hd:
          hd[tid] = (0.0, hd[tid][1])
        if i < len(extra):
          t = extra[i]
          hd[t.task_id] = (t.priority, t.deadline)
          task_ids.append(t.task_id)
          hd.popitem()
      elapsed = time.perf_counter_ns() - t0
      gc.enable()
      results["heapdict"][-1].append(elapsed / 1e9)

  return {"queue_sizes": queue_sizes, **results}


# ===================================================================
# B6: Queue size dynamics trace
# ===================================================================
def bench_queue_dynamics(
  tasks: List[Task],
  n_events: int = 100_000,
) -> Dict[str, Any]:
  """Record queue size and event counts during a mixed workload.

  Simulates a steady-state scheduler: push and pop rates are matched
  (47.5% each) with a small replace fraction (5%) that does not affect
  queue size.  The queue therefore fluctuates stochastically around the
  prefill size rather than drifting.  This models a loaded scheduler
  at equilibrium.
  """
  rng = np.random.default_rng(SEED + 50)
  # Balanced push / pop (47.5% each) with 5% replace -> steady state.
  probs = np.array([0.475, 0.475, 0.05])
  boundaries = np.cumsum(probs)
  event_seq = np.searchsorted(boundaries, rng.random(n_events)).astype(np.int8)

  prefill = 50_000
  h: List[Task] = list(tasks[:prefill])
  heapx.heapify(h, cmp=_task_key)
  cursor = prefill

  timestamps: List[float] = []
  sizes: List[int] = []
  cum_push: List[int] = []
  cum_pop: List[int] = []
  cum_replace: List[int] = []
  cp, co, cr = 0, 0, 0

  sample_every = 50

  for i, ev in enumerate(event_seq):
    if ev == 0 and cursor < len(tasks):
      t = tasks[cursor]; cursor += 1
      heapx.push(h, t, cmp=_task_key)
      cp += 1
    elif ev == 1 and h:
      heapx.pop(h, cmp=_task_key)
      co += 1
    elif ev == 2 and len(h) > 1:
      idx = int(rng.integers(0, len(h)))
      old = h[idx]
      new_t = Task(old.task_id, 0.0, old.deadline, old.arrival_time, old.burst)
      heapx.replace(h, new_t, indices=idx, cmp=_task_key)
      cr += 1

    if i % sample_every == 0:
      sim_time = tasks[min(cursor - 1, len(tasks) - 1)].arrival_time
      timestamps.append(float(sim_time))
      sizes.append(len(h))
      cum_push.append(cp)
      cum_pop.append(co)
      cum_replace.append(cr)

  return {
    "timestamps": timestamps,
    "sizes": sizes,
    "cum_push": cum_push,
    "cum_pop": cum_pop,
    "cum_replace": cum_replace,
  }


# ===================================================================
# B7: End-to-end scheduler throughput
# ===================================================================
def bench_scheduler_throughput(
  tasks: List[Task],
  queue_sizes: List[int],
  n_ops: int = 50_000,
  reps: int = 3,
) -> Dict[str, Any]:
  """Realistic scheduler loop: enqueue arrivals, dispatch, boost_priority.

  Uses the HeapxScheduler and HeapqScheduler abstractions to measure
  end-to-end throughput (tasks/second) of a production-style priority
  scheduler under a mixed workload that exercises the operations
  common to asyncio / Dask / Celery style schedulers.

  Mix per operation batch: 40% enqueue, 40% dispatch, 20% boost_priority.
  The boost_priority component exercises decrease-key — heapx's
  decisive advantage (O(log n) in-place sift vs heapq's O(n) heapify
  workaround).  Reported metric is aggregate throughput
  (ops per second).
  """
  rng = np.random.default_rng(SEED + 60)
  results: Dict[str, List[List[float]]] = {"heapx": [], "heapq": []}

  for qsz in queue_sizes:
    base = tasks[:qsz]
    extra = tasks[qsz:qsz + n_ops]
    op_types = rng.choice([0, 1, 2], size=n_ops, p=[0.40, 0.40, 0.20])
    for name in results:
      results[name].append([])

    for _ in range(reps):
      for SchedCls, key in [(HeapxScheduler, "heapx"),
                            (HeapqScheduler, "heapq")]:
        sched = SchedCls()
        sched.enqueue_batch(list(base))

        gc.disable()
        t0 = time.perf_counter_ns()
        cursor = 0
        ops_done = 0
        for op in op_types:
          if op == 0 and cursor < len(extra):                      # enqueue
            sched.enqueue(extra[cursor]); cursor += 1
          elif op == 1 and not sched.empty:                        # dispatch
            sched.dispatch()
          elif op == 2 and sched.size > 0:                         # boost
            idx = int(rng.integers(0, sched.size))
            sched.boost_priority(idx, 0.0)
          ops_done += 1
        elapsed_ns = time.perf_counter_ns() - t0
        gc.enable()
        throughput = ops_done / (elapsed_ns / 1e9)
        results[key][-1].append(throughput)

  return {"queue_sizes": queue_sizes, **results}


# ===================================================================
# Main
# ===================================================================
def main() -> None:
  print("Generating workload …")
  tasks = generate_workload(n_tasks=10_500_000, seed=SEED)

  queue_sizes = [1_000, 5_000, 10_000, 50_000, 100_000, 250_000]
  # 8-point batch range matches existing fig04 visual extent and is a strict
  # superset of the typical 5-point queue_sizes range (fixes results.json/code sync).
  batch_sizes = [10, 100, 1_000, 10_000, 100_000,
                 1_000_000, 10_000_000, 100_000_000]

  print("\n[B1] Batch push …")
  b1 = bench_batch_push(tasks, batch_sizes)

  print("[B2] Single push …")
  b2 = bench_single_push(tasks, queue_sizes)

  print("[B3] Single pop …")
  b3 = bench_single_pop(tasks, queue_sizes)

  print("[B4] Replace (decrease-key) …")
  b4 = bench_replace(tasks, queue_sizes)

  print("[B5] Replace-heavy workload …")
  b5 = bench_replace_heavy(tasks, queue_sizes)

  print("[B6] Queue dynamics trace …")
  b6 = bench_queue_dynamics(tasks)

  print("[B7] Scheduler throughput …")
  b7 = bench_scheduler_throughput(
    tasks, queue_sizes=[1_000, 5_000, 10_000, 50_000, 100_000], n_ops=20_000)

  results = {
    "batch_push": b1,
    "single_push": b2,
    "single_pop": b3,
    "replace": b4,
    "replace_heavy": b5,
    "queue_dynamics": b6,
    "scheduler_throughput": b7,
  }

  out_path = "results.json"
  with open(out_path, "w") as f:
    json.dump(results, f, indent=2, default=float)
  print(f"\nAll results saved to {out_path}")

  # Summary
  print("\n" + "=" * 72)
  print("SUMMARY (median at largest queue size)")
  print("=" * 72)
  for bname, bdata in [("B4 Replace (µs/op)", b4), ("B5 Replace-heavy (s)", b5),
                       ("B7 Throughput (ops/s)", b7)]:
    print(f"\n  {bname}:")
    for mod in bdata:
      if mod == "queue_sizes":
        continue
      vals = bdata[mod][-1]
      med = float(np.nanmedian(vals))
      print(f"    {mod:<22} {med:.4f}")
  print("=" * 72)


if __name__ == "__main__":
  main()
