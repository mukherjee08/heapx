#!/usr/bin/env python3
"""
Case Study 4 — Real-Time Event Simulation (Discrete-Event Simulation)
======================================================================

Seven DES engines implementing the *extended hold model* (Jones 1986)
with cancel and reschedule extensions.  Each engine maintains a pending
event set (PES) as a min-heap ordered by timestamp and executes a
steady-state loop of pop → push → cancel → reschedule operations.

Engines
-------
heapx              C-extension heap with O(log n) remove/replace
heapq              stdlib heap; cancel = swap-last + O(n) re-heapify
heapq_lazy         stdlib heap with lazy-deletion (Python docs pattern)
sortedcontainers   Pure-Python sorted list; O(log n) remove
heapdict           Pure-Python indexed heap; O(log n) remove
pqdict             Pure-Python indexed heap; O(log n) remove
PriorityQueue      stdlib thread-safe heapq wrapper; O(n) cancel

All randomness is seeded for full reproducibility.

References
----------
- Jones, D.W. (1986). "An Empirical Comparison of Priority-Queue and
  Event-Set Implementations." *CACM* 29(4):300–311.
- Brown, R. (1988). "Calendar Queues." *CACM* 31(10):1220–1227.
- Rönngren, R. & Ayani, R. (1997). "A Comparative Study of Parallel
  and Sequential Priority Queue Algorithms." *ACM TOMACS* 7(2).
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import json
import sys
import time
from queue import PriorityQueue
from typing import Any

import heapx
import numpy as np

try:
    from sortedcontainers import SortedList
except ImportError:
    SortedList = None

try:
    import heapdict as heapdict_mod
except ImportError:
    heapdict_mod = None

try:
    from pqdict import pqdict
except ImportError:
    pqdict = None

# ---------------------------------------------------------------------------
# Progress reporting
# ---------------------------------------------------------------------------

_PROGRESS_STEP: int = 10
_PROGRESS_ENABLED: bool = True


def _progress(label: str, i: int, total: int) -> None:
    """Print progress bar at 10 % increments."""
    if not _PROGRESS_ENABLED:
        return
    pct = (i + 1) * 100 // total
    prev = i * 100 // total
    if pct // _PROGRESS_STEP != prev // _PROGRESS_STEP or i == 0:
        print(
            f"\r    [{label}] {pct:3d}%  ({i + 1:,}/{total:,})",
            end="",
            flush=True,
        )
    if i + 1 == total:
        print()


# ---------------------------------------------------------------------------
# Pre-generate workload (shared across all engines for fairness)
# ---------------------------------------------------------------------------

def _make_workload(
    n_events: int, steady_state_size: int, seed: int,
) -> dict[str, np.ndarray]:
    """Create a deterministic workload array bundle.

    Timestamps follow a Poisson process (exponential inter-arrivals with
    rate λ=1), which is the standard model for DES benchmarking (Jones
    1986, Brown 1988, Rönngren & Ayani 1997).
    """
    rng = np.random.default_rng(seed)
    ts = np.cumsum(rng.exponential(1.0, size=n_events + steady_state_size))
    return {
        "timestamps": ts,
        "cancel_rolls": rng.random(n_events),
        "resched_rolls": rng.random(n_events),
        "resched_deltas": rng.exponential(0.5, size=n_events),
        "cancel_indices": rng.integers(
            0, max(steady_state_size // 2, 1), size=n_events,
        ),
    }


# ---------------------------------------------------------------------------
# Result helper
# ---------------------------------------------------------------------------

def _result(
    engine: str, elapsed: float,
    pops: int, pushes: int, cancels: int, rescheds: int,
) -> dict[str, Any]:
    return {
        "engine": engine,
        "elapsed_s": elapsed,
        "events_processed": pops,
        "pushes": pushes,
        "pops": pops,
        "cancellations": cancels,
        "reschedules": rescheds,
        "throughput_eps": pops / elapsed if elapsed > 0 else 0,
    }


# ---------------------------------------------------------------------------
# heapx engine — O(log n) remove / replace
# ---------------------------------------------------------------------------

def run_heapx_simulation(
    n_events: int, steady_state_size: int,
    cancel_rate: float, reschedule_rate: float, seed: int,
) -> dict:
    w = _make_workload(n_events, steady_state_size, seed)
    heap: list[float] = list(w["timestamps"][:steady_state_size].astype(float))
    heapx.heapify(heap)
    push_c = pop_c = cancel_c = resched_c = 0
    nxt = steady_state_size
    t0 = time.perf_counter()
    for i in range(n_events):
        _progress("simulation.py · heapx", i, n_events)
        if not heap:
            break
        heapx.pop(heap); pop_c += 1
        if nxt < len(w["timestamps"]):
            heapx.push(heap, float(w["timestamps"][nxt])); nxt += 1; push_c += 1
        if w["cancel_rolls"][i] < cancel_rate and len(heap) > 1:
            idx = int(w["cancel_indices"][i]) % len(heap)
            heapx.remove(heap, indices=idx); cancel_c += 1
            if nxt < len(w["timestamps"]):
                heapx.push(heap, float(w["timestamps"][nxt])); nxt += 1; push_c += 1
        if w["resched_rolls"][i] < reschedule_rate and len(heap) > 1:
            idx = int(w["cancel_indices"][i]) % len(heap)
            heapx.replace(
                heap, heap[idx] + float(w["resched_deltas"][i]), indices=idx,
            )
            resched_c += 1
    elapsed = time.perf_counter() - t0
    return _result("heapx", elapsed, pop_c, push_c, cancel_c, resched_c)


# ---------------------------------------------------------------------------
# heapq engine — O(n) cancel via swap-last + full re-heapify
# ---------------------------------------------------------------------------

def run_heapq_simulation(
    n_events: int, steady_state_size: int,
    cancel_rate: float, reschedule_rate: float, seed: int,
) -> dict:
    w = _make_workload(n_events, steady_state_size, seed)
    heap: list[float] = list(w["timestamps"][:steady_state_size].astype(float))
    heapq.heapify(heap)
    push_c = pop_c = cancel_c = resched_c = 0
    nxt = steady_state_size
    t0 = time.perf_counter()
    for i in range(n_events):
        _progress("simulation.py · heapq", i, n_events)
        if not heap:
            break
        heapq.heappop(heap); pop_c += 1
        if nxt < len(w["timestamps"]):
            heapq.heappush(heap, float(w["timestamps"][nxt])); nxt += 1; push_c += 1
        if w["cancel_rolls"][i] < cancel_rate and len(heap) > 1:
            idx = int(w["cancel_indices"][i]) % len(heap)
            heap[idx] = heap[-1]; heap.pop(); heapq.heapify(heap); cancel_c += 1
            if nxt < len(w["timestamps"]):
                heapq.heappush(heap, float(w["timestamps"][nxt])); nxt += 1; push_c += 1
        if w["resched_rolls"][i] < reschedule_rate and len(heap) > 1:
            idx = int(w["cancel_indices"][i]) % len(heap)
            heap[idx] = heap[idx] + float(w["resched_deltas"][i])
            heapq.heapify(heap); resched_c += 1
    elapsed = time.perf_counter() - t0
    return _result("heapq", elapsed, pop_c, push_c, cancel_c, resched_c)


# ---------------------------------------------------------------------------
# heapq (lazy deletion) — Python-docs recommended pattern
# ---------------------------------------------------------------------------

_REMOVED: str = "<removed>"


def run_heapq_lazy_simulation(
    n_events: int, steady_state_size: int,
    cancel_rate: float, reschedule_rate: float, seed: int,
) -> dict:
    w = _make_workload(n_events, steady_state_size, seed)
    counter = itertools.count()
    pq: list = []
    ef: dict = {}
    for j in range(steady_state_size):
        c = next(counter)
        entry = [float(w["timestamps"][j]), c, c]
        ef[c] = entry
        heapq.heappush(pq, entry)
    push_c = pop_c = cancel_c = resched_c = 0
    nxt = steady_state_size
    t0 = time.perf_counter()
    for i in range(n_events):
        _progress("simulation.py · heapq_lazy", i, n_events)
        if not ef:
            break
        while pq:
            _ts, _cnt, task = heapq.heappop(pq)
            if task is not _REMOVED:
                del ef[task]
                pop_c += 1
                break
        else:
            break
        if nxt < len(w["timestamps"]):
            c = next(counter)
            entry = [float(w["timestamps"][nxt]), c, c]
            ef[c] = entry
            heapq.heappush(pq, entry)
            nxt += 1; push_c += 1
        if w["cancel_rolls"][i] < cancel_rate and len(ef) > 1:
            keys = list(ef.keys())
            idx = int(w["cancel_indices"][i]) % len(keys)
            k = keys[idx]
            ef[k][-1] = _REMOVED
            del ef[k]
            cancel_c += 1
            if nxt < len(w["timestamps"]):
                c = next(counter)
                entry = [float(w["timestamps"][nxt]), c, c]
                ef[c] = entry
                heapq.heappush(pq, entry)
                nxt += 1; push_c += 1
        if w["resched_rolls"][i] < reschedule_rate and len(ef) > 1:
            keys = list(ef.keys())
            idx = int(w["cancel_indices"][i]) % len(keys)
            k = keys[idx]
            old_ts = ef[k][0]
            ef[k][-1] = _REMOVED
            del ef[k]
            c = next(counter)
            entry = [old_ts + float(w["resched_deltas"][i]), c, c]
            ef[c] = entry
            heapq.heappush(pq, entry)
            resched_c += 1
    elapsed = time.perf_counter() - t0
    return _result("heapq_lazy", elapsed, pop_c, push_c, cancel_c, resched_c)


# ---------------------------------------------------------------------------
# sortedcontainers engine
# ---------------------------------------------------------------------------

def run_sortedlist_simulation(
    n_events: int, steady_state_size: int,
    cancel_rate: float, reschedule_rate: float, seed: int,
) -> dict:
    if SortedList is None:
        return _result("sortedcontainers", 0, 0, 0, 0, 0)
    w = _make_workload(n_events, steady_state_size, seed)
    sl = SortedList(w["timestamps"][:steady_state_size].astype(float).tolist())
    push_c = pop_c = cancel_c = resched_c = 0
    nxt = steady_state_size
    t0 = time.perf_counter()
    for i in range(n_events):
        _progress("simulation.py · sortedcontainers", i, n_events)
        if not sl:
            break
        sl.pop(0); pop_c += 1
        if nxt < len(w["timestamps"]):
            sl.add(float(w["timestamps"][nxt])); nxt += 1; push_c += 1
        if w["cancel_rolls"][i] < cancel_rate and len(sl) > 1:
            idx = int(w["cancel_indices"][i]) % len(sl)
            sl.pop(idx); cancel_c += 1
            if nxt < len(w["timestamps"]):
                sl.add(float(w["timestamps"][nxt])); nxt += 1; push_c += 1
        if w["resched_rolls"][i] < reschedule_rate and len(sl) > 1:
            idx = int(w["cancel_indices"][i]) % len(sl)
            old = sl.pop(idx)
            sl.add(old + float(w["resched_deltas"][i])); resched_c += 1
    elapsed = time.perf_counter() - t0
    return _result("sortedcontainers", elapsed, pop_c, push_c, cancel_c, resched_c)


# ---------------------------------------------------------------------------
# heapdict engine
# ---------------------------------------------------------------------------

def run_heapdict_simulation(
    n_events: int, steady_state_size: int,
    cancel_rate: float, reschedule_rate: float, seed: int,
) -> dict:
    if heapdict_mod is None:
        return _result("heapdict", 0, 0, 0, 0, 0)
    w = _make_workload(n_events, steady_state_size, seed)
    hd = heapdict_mod.heapdict()
    for j in range(steady_state_size):
        hd[j] = float(w["timestamps"][j])
    push_c = pop_c = cancel_c = resched_c = 0
    nxt = steady_state_size
    next_key = steady_state_size
    t0 = time.perf_counter()
    for i in range(n_events):
        _progress("simulation.py · heapdict", i, n_events)
        if not hd:
            break
        hd.popitem(); pop_c += 1
        if nxt < len(w["timestamps"]):
            hd[next_key] = float(w["timestamps"][nxt])
            next_key += 1; nxt += 1; push_c += 1
        if w["cancel_rolls"][i] < cancel_rate and len(hd) > 1:
            ks = list(hd.keys())
            idx = int(w["cancel_indices"][i]) % len(ks)
            del hd[ks[idx]]; cancel_c += 1
            if nxt < len(w["timestamps"]):
                hd[next_key] = float(w["timestamps"][nxt])
                next_key += 1; nxt += 1; push_c += 1
        if w["resched_rolls"][i] < reschedule_rate and len(hd) > 1:
            ks = list(hd.keys())
            idx = int(w["cancel_indices"][i]) % len(ks)
            k = ks[idx]
            hd[k] = hd[k] + float(w["resched_deltas"][i]); resched_c += 1
    elapsed = time.perf_counter() - t0
    return _result("heapdict", elapsed, pop_c, push_c, cancel_c, resched_c)


# ---------------------------------------------------------------------------
# pqdict engine
# ---------------------------------------------------------------------------

def run_pqdict_simulation(
    n_events: int, steady_state_size: int,
    cancel_rate: float, reschedule_rate: float, seed: int,
) -> dict:
    if pqdict is None:
        return _result("pqdict", 0, 0, 0, 0, 0)
    w = _make_workload(n_events, steady_state_size, seed)
    pq = pqdict()
    for j in range(steady_state_size):
        pq[j] = float(w["timestamps"][j])
    push_c = pop_c = cancel_c = resched_c = 0
    nxt = steady_state_size
    next_key = steady_state_size
    t0 = time.perf_counter()
    for i in range(n_events):
        _progress("simulation.py · pqdict", i, n_events)
        if not pq:
            break
        pq.popitem(); pop_c += 1
        if nxt < len(w["timestamps"]):
            pq[next_key] = float(w["timestamps"][nxt])
            next_key += 1; nxt += 1; push_c += 1
        if w["cancel_rolls"][i] < cancel_rate and len(pq) > 1:
            ks = list(pq.keys())
            idx = int(w["cancel_indices"][i]) % len(ks)
            del pq[ks[idx]]; cancel_c += 1
            if nxt < len(w["timestamps"]):
                pq[next_key] = float(w["timestamps"][nxt])
                next_key += 1; nxt += 1; push_c += 1
        if w["resched_rolls"][i] < reschedule_rate and len(pq) > 1:
            ks = list(pq.keys())
            idx = int(w["cancel_indices"][i]) % len(ks)
            k = ks[idx]
            pq[k] = pq[k] + float(w["resched_deltas"][i]); resched_c += 1
    elapsed = time.perf_counter() - t0
    return _result("pqdict", elapsed, pop_c, push_c, cancel_c, resched_c)


# ---------------------------------------------------------------------------
# queue.PriorityQueue engine
# ---------------------------------------------------------------------------

def run_priorityqueue_simulation(
    n_events: int, steady_state_size: int,
    cancel_rate: float, reschedule_rate: float, seed: int,
) -> dict:
    w = _make_workload(n_events, steady_state_size, seed)
    pq: PriorityQueue = PriorityQueue()
    for j in range(steady_state_size):
        pq.put(float(w["timestamps"][j]))
    push_c = pop_c = cancel_c = resched_c = 0
    nxt = steady_state_size
    t0 = time.perf_counter()
    for i in range(n_events):
        _progress("simulation.py · PriorityQueue", i, n_events)
        if pq.qsize() == 0:
            break
        pq.get(); pop_c += 1
        if nxt < len(w["timestamps"]):
            pq.put(float(w["timestamps"][nxt])); nxt += 1; push_c += 1
        if w["cancel_rolls"][i] < cancel_rate and pq.qsize() > 1:
            q = pq.queue
            idx = int(w["cancel_indices"][i]) % len(q)
            q[idx] = q[-1]; q.pop(); heapq.heapify(q); cancel_c += 1
            if nxt < len(w["timestamps"]):
                pq.put(float(w["timestamps"][nxt])); nxt += 1; push_c += 1
        if w["resched_rolls"][i] < reschedule_rate and pq.qsize() > 1:
            q = pq.queue
            idx = int(w["cancel_indices"][i]) % len(q)
            q[idx] = q[idx] + float(w["resched_deltas"][i])
            heapq.heapify(q); resched_c += 1
    elapsed = time.perf_counter() - t0
    return _result("PriorityQueue", elapsed, pop_c, push_c, cancel_c, resched_c)


# ---------------------------------------------------------------------------
# Engine registry
# ---------------------------------------------------------------------------

ALL_ENGINES: dict[str, Any] = {
    "heapx": run_heapx_simulation,
    "heapq": run_heapq_simulation,
    "heapq_lazy": run_heapq_lazy_simulation,
    "sortedcontainers": run_sortedlist_simulation,
    "heapdict": run_heapdict_simulation,
    "pqdict": run_pqdict_simulation,
    "PriorityQueue": run_priorityqueue_simulation,
}


# ---------------------------------------------------------------------------
# DES trace recorder (for domain-specific figures)
# ---------------------------------------------------------------------------

def run_heapx_traced(
    n_events: int, steady_state_size: int,
    cancel_rate: float, reschedule_rate: float, seed: int,
) -> dict[str, list]:
    """Run heapx simulation recording queue-size and op-type per event.

    The simulation captures the *three canonical phases* of a real-time
    discrete-event simulation, in accordance with the priority-queue
    benchmarking literature:

    1. *Initialization / Buildup phase* — at virtual time t=0 the PES is
       empty; events are pushed one at a time until the queue reaches
       ``steady_state_size``.  This models the transient ("warm-up")
       phase of the Up/Down model of Rönngren & Ayani (1993) and the
       transient phase described by Tang, Perumalla & Fujimoto (2005).
       During this phase *arrivals outpace departures* — no pops occur
       — so the queue size grows linearly from 0 to ``steady_state_size``.
    2. *Steady-state phase* — the Classic Hold model of Jones (1986):
       each iteration executes one pop followed by one push (and, with
       probability ``cancel_rate``/``reschedule_rate``, a cancel and/or
       a reschedule).  Queue size fluctuates around ``steady_state_size``.
    3. *Drain phase* — arrivals are exhausted; events are popped until
       the PES is empty.  Queue size decays linearly to zero.

    The buildup-phase pushes are tagged with the distinct op label
    ``"init_push"`` so that downstream figures measuring the Classic
    Hold operation mix (fig. 8) remain unaffected; fig. 7 (queue
    evolution) interprets the three phases via the ``phase_boundaries``
    metadata field.
    """
    w = _make_workload(n_events, steady_state_size, seed)
    heap: list[float] = []
    queue_sizes: list[int] = []
    op_types: list[str] = []
    sim_times: list[float] = []

    # ---- Phase 1 — Initialization / Buildup ----------------------------
    # Push events one by one from an empty heap; virtual time does not
    # advance because no events have yet been *executed* (popped).  The
    # trace records a strictly-increasing synthetic clock derived from
    # the event timestamps so the x-axis is meaningful.
    init_start_time: float = float(w["timestamps"][0])
    for j in range(steady_state_size):
      ts = float(w["timestamps"][j])
      heapx.push(heap, ts)
      op_types.append("init_push")
      queue_sizes.append(len(heap))
      sim_times.append(ts)
    buildup_end_idx: int = len(queue_sizes)
    nxt = steady_state_size

    # ---- Phase 2 — Steady-state (Classic Hold + cancel/resched) -------
    # The steady-state boundary is defined precisely as the iteration at
    # which the timestamp pool is exhausted: after that point, no further
    # pushes can occur, so the queue monotonically drains regardless of
    # whether the outer loop is still running.  This definition makes the
    # visual phase boundary in fig. 7 coincide with the *first* instant
    # the queue begins to decay — eliminating the optical mismatch where
    # the curve would otherwise start falling before the dashed line.
    steady_end_idx: int = -1
    for i in range(n_events):
      if not heap:
        break
      current_time: float = heapx.pop(heap)
      sim_times.append(current_time)
      op_types.append("pop")
      queue_sizes.append(len(heap))
      did_push_refill = False
      if nxt < len(w["timestamps"]):
        heapx.push(heap, float(w["timestamps"][nxt])); nxt += 1
        op_types.append("push")
        queue_sizes.append(len(heap))
        sim_times.append(current_time)
        did_push_refill = True
      if w["cancel_rolls"][i] < cancel_rate and len(heap) > 1:
        idx = int(w["cancel_indices"][i]) % len(heap)
        heapx.remove(heap, indices=idx)
        op_types.append("cancel")
        queue_sizes.append(len(heap))
        sim_times.append(current_time)
        if nxt < len(w["timestamps"]):
          # Refill the slot vacated by the cancel.  Historically this
          # push is *not* recorded as a distinct op because it is a
          # bookkeeping side-effect of the cancel; the publication-
          # facing op-mix figure (fig. 8) therefore counts only the
          # pop-refill push per iteration, matching the Jones (1986)
          # Classic-Hold accounting convention.
          heapx.push(heap, float(w["timestamps"][nxt])); nxt += 1
          did_push_refill = True
      if w["resched_rolls"][i] < reschedule_rate and len(heap) > 1:
        idx = int(w["cancel_indices"][i]) % len(heap)
        heapx.replace(
          heap, heap[idx] + float(w["resched_deltas"][i]), indices=idx,
        )
        op_types.append("resched")
        queue_sizes.append(len(heap))
        sim_times.append(current_time)
      # Lock the steady/drain boundary the first time a loop iteration
      # completes without any push refill (the arrival stream is dry).
      if steady_end_idx < 0 and not did_push_refill:
        steady_end_idx = len(queue_sizes)
    if steady_end_idx < 0:
      steady_end_idx = len(queue_sizes)

    # ---- Phase 3 — Drain ----------------------------------------------
    while heap:
      current_time = heapx.pop(heap)
      sim_times.append(current_time)
      op_types.append("pop")
      queue_sizes.append(len(heap))
    return {
      "queue_sizes": queue_sizes,
      "op_types": op_types,
      "sim_times": sim_times,
      "phase_boundaries": {
        "buildup_end_idx": buildup_end_idx,
        "steady_end_idx": steady_end_idx,
        "init_start_time": init_start_time,
      },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="CS4: Real-Time Event Simulation")
    ap.add_argument("--events", type=int, default=10_000_000)
    ap.add_argument("--queue-size", type=int, default=250_000)
    ap.add_argument("--cancel-rate", type=float, default=0.30)
    ap.add_argument("--reschedule-rate", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output", type=str, default="results.json")
    args = ap.parse_args()

    print(
        f"Running DES: {args.events:,} events, queue≈{args.queue_size:,}, "
        f"cancel={args.cancel_rate:.0%}, resched={args.reschedule_rate:.0%}"
    )

    results: dict = {"parameters": vars(args)}
    for name, fn in ALL_ENGINES.items():
        res = fn(
            args.events, args.queue_size,
            args.cancel_rate, args.reschedule_rate, args.seed,
        )
        results[name] = res
        print(
            f"  {name}: {res['elapsed_s']:.3f}s  "
            f"({res['throughput_eps']:,.0f} events/s)"
        )

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
