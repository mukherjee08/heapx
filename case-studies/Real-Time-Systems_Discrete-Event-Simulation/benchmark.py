#!/usr/bin/env python3
"""
Case Study 4 — Benchmark Suite (Multi-Module, Parallelized)
============================================================

Four benchmarks exercising the extended hold model (Jones 1986) with
cancel/reschedule extensions across seven priority-queue modules.

Benchmarks
----------
1. Cancellation-rate sweep (0 %–50 %) — all engines, fixed queue 250 K.
2. Queue-size scaling (1 K–1 M) — all engines, 30 % cancel.
3. Per-operation latency micro-benchmark — all modules, queue 250 K.
4. DES trace — queue-size evolution and operation mix (heapx only).

Usage::

    python benchmark.py [--repeats R] [--seed S] [--output FILE] [--workers N]
    python benchmark.py --quick          # ~2-5 min debug run
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import json
import multiprocessing as mp
import os
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
# Worker function (top-level for pickling)
# ---------------------------------------------------------------------------

def _run_single_sim(args_tuple: tuple) -> dict:
    """Run one simulation in a worker process."""
    eng_name, n_events, queue_size, cancel_rate, reschedule_rate, seed = args_tuple
    import simulation
    simulation._PROGRESS_ENABLED = False
    fn = simulation.ALL_ENGINES[eng_name]
    res = fn(n_events, queue_size, cancel_rate, reschedule_rate, seed)
    return {
        "engine": eng_name,
        "cancel_rate": cancel_rate,
        "queue_size": queue_size,
        "seed": seed,
        "throughput_eps": res["throughput_eps"],
    }


# ---------------------------------------------------------------------------
# Per-operation latency micro-benchmarks
# ---------------------------------------------------------------------------

def _bench_latency(queue_size: int, n_ops: int, seed: int) -> dict[str, dict[str, float]]:
    """Measure per-operation latency (ns) for all modules."""
    rng = np.random.default_rng(seed)
    base = np.sort(rng.random(queue_size)).tolist()
    results: dict[str, dict[str, float]] = {}

    # --- heapx ---
    timings: dict[str, float] = {}
    heap = list(base); heapx.heapify(heap)
    vals = rng.random(n_ops).tolist()
    t0 = time.perf_counter()
    for v in vals:
        heapx.push(heap, v)
    timings["push"] = (time.perf_counter() - t0) / n_ops * 1e9

    heap = list(base); heapx.heapify(heap)
    heapx.push(heap, rng.random(n_ops).tolist())
    actual = min(n_ops, len(heap))
    t0 = time.perf_counter()
    for _ in range(actual):
        heapx.pop(heap)
    timings["pop"] = (time.perf_counter() - t0) / actual * 1e9

    heap = list(base); heapx.heapify(heap)
    idxs = rng.integers(0, max(len(heap) // 2, 1), size=n_ops)
    t0 = time.perf_counter()
    done = 0
    for idx in idxs:
        if len(heap) > 1:
            heapx.remove(heap, indices=int(idx) % len(heap)); done += 1
        else:
            break
    timings["remove"] = (time.perf_counter() - t0) / max(done, 1) * 1e9

    heap = list(base); heapx.heapify(heap)
    new_vals = rng.random(n_ops).tolist()
    t0 = time.perf_counter()
    for j in range(n_ops):
        if len(heap) > 1:
            idx = int(rng.integers(0, len(heap)))
            heapx.replace(heap, new_vals[j], indices=idx)
    timings["replace"] = (time.perf_counter() - t0) / n_ops * 1e9
    results["heapx"] = timings

    # --- heapq ---
    timings = {}
    heap = list(base); heapq.heapify(heap)
    vals = rng.random(n_ops).tolist()
    t0 = time.perf_counter()
    for v in vals:
        heapq.heappush(heap, v)
    timings["push"] = (time.perf_counter() - t0) / n_ops * 1e9

    heap = list(base); heapq.heapify(heap)
    for v in rng.random(n_ops).tolist():
        heapq.heappush(heap, v)
    actual = min(n_ops, len(heap))
    t0 = time.perf_counter()
    for _ in range(actual):
        heapq.heappop(heap)
    timings["pop"] = (time.perf_counter() - t0) / actual * 1e9

    heap = list(base); heapq.heapify(heap)
    idxs = rng.integers(0, max(len(heap) // 2, 1), size=n_ops)
    t0 = time.perf_counter()
    done = 0
    for idx in idxs:
        if len(heap) > 1:
            i = int(idx) % len(heap)
            heap[i] = heap[-1]; heap.pop(); heapq.heapify(heap); done += 1
        else:
            break
    timings["remove"] = (time.perf_counter() - t0) / max(done, 1) * 1e9

    heap = list(base); heapq.heapify(heap)
    new_vals = rng.random(n_ops).tolist()
    t0 = time.perf_counter()
    for j in range(n_ops):
        if len(heap) > 1:
            idx = int(rng.integers(0, len(heap)))
            heap[idx] = new_vals[j]; heapq.heapify(heap)
    timings["replace"] = (time.perf_counter() - t0) / n_ops * 1e9
    results["heapq"] = timings

    # --- heapq_lazy ---
    from simulation import _REMOVED
    timings = {}
    counter = itertools.count()
    pq_l: list = []; ef: dict = {}
    for v in base:
        c = next(counter); entry = [v, c, c]; ef[c] = entry; heapq.heappush(pq_l, entry)
    vals = rng.random(n_ops).tolist()
    t0 = time.perf_counter()
    for v in vals:
        c = next(counter); entry = [v, c, c]; ef[c] = entry; heapq.heappush(pq_l, entry)
    timings["push"] = (time.perf_counter() - t0) / n_ops * 1e9

    counter = itertools.count(); pq_l = []; ef = {}
    for v in base:
        c = next(counter); entry = [v, c, c]; ef[c] = entry; heapq.heappush(pq_l, entry)
    for v in rng.random(n_ops).tolist():
        c = next(counter); entry = [v, c, c]; ef[c] = entry; heapq.heappush(pq_l, entry)
    actual = min(n_ops, len(ef))
    t0 = time.perf_counter()
    for _ in range(actual):
        while pq_l:
            _ts, _cnt, task = heapq.heappop(pq_l)
            if task is not _REMOVED:
                del ef[task]; break
    timings["pop"] = (time.perf_counter() - t0) / actual * 1e9

    counter = itertools.count(); pq_l = []; ef = {}
    for v in base:
        c = next(counter); entry = [v, c, c]; ef[c] = entry; heapq.heappush(pq_l, entry)
    t0 = time.perf_counter()
    done = 0
    for _ in range(min(n_ops, len(base) - 1)):
        keys = list(ef.keys())
        if len(keys) > 1:
            k = keys[0]; ef[k][-1] = _REMOVED; del ef[k]; done += 1
        else:
            break
    timings["remove"] = (time.perf_counter() - t0) / max(done, 1) * 1e9

    counter = itertools.count(); pq_l = []; ef = {}
    for v in base:
        c = next(counter); entry = [v, c, c]; ef[c] = entry; heapq.heappush(pq_l, entry)
    new_vals = rng.random(n_ops).tolist()
    t0 = time.perf_counter()
    for j in range(min(n_ops, len(base))):
        keys = list(ef.keys())
        if len(keys) > 1:
            k = keys[j % len(keys)]
            ef[k][-1] = _REMOVED; del ef[k]
            c = next(counter); entry = [new_vals[j], c, c]; ef[c] = entry
            heapq.heappush(pq_l, entry)
    timings["replace"] = (time.perf_counter() - t0) / min(n_ops, len(base)) * 1e9
    results["heapq_lazy"] = timings

    # --- sortedcontainers ---
    if SortedList is not None:
        timings = {}
        sl = SortedList(base)
        vals = rng.random(n_ops).tolist()
        t0 = time.perf_counter()
        for v in vals:
            sl.add(v)
        timings["push"] = (time.perf_counter() - t0) / n_ops * 1e9

        sl = SortedList(base)
        for v in rng.random(n_ops).tolist():
            sl.add(v)
        actual = min(n_ops, len(sl))
        t0 = time.perf_counter()
        for _ in range(actual):
            sl.pop(0)
        timings["pop"] = (time.perf_counter() - t0) / actual * 1e9

        sl = SortedList(base)
        idxs = rng.integers(0, max(len(sl) // 2, 1), size=n_ops)
        t0 = time.perf_counter()
        done = 0
        for idx in idxs:
            if len(sl) > 1:
                sl.pop(int(idx) % len(sl)); done += 1
            else:
                break
        timings["remove"] = (time.perf_counter() - t0) / max(done, 1) * 1e9

        sl = SortedList(base)
        new_vals = rng.random(n_ops).tolist()
        t0 = time.perf_counter()
        for j in range(n_ops):
            if len(sl) > 1:
                idx = int(rng.integers(0, len(sl)))
                sl.pop(idx); sl.add(new_vals[j])
        timings["replace"] = (time.perf_counter() - t0) / n_ops * 1e9
        results["sortedcontainers"] = timings

    # --- heapdict ---
    if heapdict_mod is not None:
        timings = {}
        hd = heapdict_mod.heapdict()
        for j, v in enumerate(base): hd[j] = v
        nk = len(base)
        vals = rng.random(n_ops).tolist()
        t0 = time.perf_counter()
        for v in vals: hd[nk] = v; nk += 1
        timings["push"] = (time.perf_counter() - t0) / n_ops * 1e9

        hd = heapdict_mod.heapdict()
        for j, v in enumerate(base): hd[j] = v
        actual = min(n_ops, len(hd))
        t0 = time.perf_counter()
        for _ in range(actual): hd.popitem()
        timings["pop"] = (time.perf_counter() - t0) / actual * 1e9

        hd = heapdict_mod.heapdict()
        for j, v in enumerate(base): hd[j] = v
        t0 = time.perf_counter()
        done = 0
        for _ in range(min(n_ops, len(base) - 1)):
            ks = list(hd.keys())
            if len(ks) > 1: del hd[ks[0]]; done += 1
            else: break
        timings["remove"] = (time.perf_counter() - t0) / max(done, 1) * 1e9

        hd = heapdict_mod.heapdict()
        for j, v in enumerate(base): hd[j] = v
        new_vals = rng.random(n_ops).tolist()
        t0 = time.perf_counter()
        for j in range(min(n_ops, len(base))): hd[j] = new_vals[j]
        timings["replace"] = (time.perf_counter() - t0) / min(n_ops, len(base)) * 1e9
        results["heapdict"] = timings

    # --- pqdict ---
    if pqdict is not None:
        timings = {}
        pq = pqdict()
        for j, v in enumerate(base): pq[j] = v
        nk = len(base)
        vals = rng.random(n_ops).tolist()
        t0 = time.perf_counter()
        for v in vals: pq[nk] = v; nk += 1
        timings["push"] = (time.perf_counter() - t0) / n_ops * 1e9

        pq = pqdict()
        for j, v in enumerate(base): pq[j] = v
        actual = min(n_ops, len(pq))
        t0 = time.perf_counter()
        for _ in range(actual): pq.popitem()
        timings["pop"] = (time.perf_counter() - t0) / actual * 1e9

        pq = pqdict()
        for j, v in enumerate(base): pq[j] = v
        t0 = time.perf_counter()
        done = 0
        for _ in range(min(n_ops, len(base) - 1)):
            ks = list(pq.keys())
            if len(ks) > 1: del pq[ks[0]]; done += 1
            else: break
        timings["remove"] = (time.perf_counter() - t0) / max(done, 1) * 1e9

        pq = pqdict()
        for j, v in enumerate(base): pq[j] = v
        new_vals = rng.random(n_ops).tolist()
        t0 = time.perf_counter()
        for j in range(min(n_ops, len(base))): pq[j] = new_vals[j]
        timings["replace"] = (time.perf_counter() - t0) / min(n_ops, len(base)) * 1e9
        results["pqdict"] = timings

    # --- PriorityQueue ---
    timings = {}
    pq_obj: PriorityQueue = PriorityQueue()
    for v in base: pq_obj.put(v)
    vals = rng.random(n_ops).tolist()
    t0 = time.perf_counter()
    for v in vals: pq_obj.put(v)
    timings["push"] = (time.perf_counter() - t0) / n_ops * 1e9

    pq_obj = PriorityQueue()
    for v in base: pq_obj.put(v)
    for v in rng.random(n_ops).tolist(): pq_obj.put(v)
    actual = min(n_ops, pq_obj.qsize())
    t0 = time.perf_counter()
    for _ in range(actual): pq_obj.get()
    timings["pop"] = (time.perf_counter() - t0) / actual * 1e9

    pq_obj = PriorityQueue()
    for v in base: pq_obj.put(v)
    idxs = rng.integers(0, max(len(base) // 2, 1), size=n_ops)
    t0 = time.perf_counter()
    done = 0
    for idx in idxs:
        q = pq_obj.queue
        if len(q) > 1:
            i = int(idx) % len(q); q[i] = q[-1]; q.pop(); heapq.heapify(q); done += 1
        else: break
    timings["remove"] = (time.perf_counter() - t0) / max(done, 1) * 1e9

    pq_obj = PriorityQueue()
    for v in base: pq_obj.put(v)
    new_vals = rng.random(n_ops).tolist()
    t0 = time.perf_counter()
    for j in range(n_ops):
        q = pq_obj.queue
        if len(q) > 1:
            idx = int(rng.integers(0, len(q))); q[idx] = new_vals[j]; heapq.heapify(q)
    timings["replace"] = (time.perf_counter() - t0) / n_ops * 1e9
    results["PriorityQueue"] = timings

    return results


# ---------------------------------------------------------------------------
# Parallel cancel-rate sweep
# ---------------------------------------------------------------------------

def _bench_cancel_sweep_parallel(
    n_events: int, queue_size: int,
    cancel_rates: list[float], repeats: int, seed: int,
    pool: mp.Pool,
) -> list[dict]:
    from simulation import ALL_ENGINES
    engine_names = list(ALL_ENGINES.keys())
    tasks = [
        (eng, n_events, queue_size, cr, 0.05, seed + r)
        for cr in cancel_rates
        for eng in engine_names
        for r in range(repeats)
    ]
    print(f"  Dispatching {len(tasks)} tasks across workers...")
    raw = pool.map(_run_single_sim, tasks)

    rows: list[dict] = []
    idx = 0
    for cr in cancel_rates:
        row: dict = {"cancel_rate": cr}
        for eng in engine_names:
            arr = np.array([raw[idx + r]["throughput_eps"] for r in range(repeats)])
            row[f"{eng}_median"] = float(np.median(arr))
            row[f"{eng}_q1"] = float(np.percentile(arr, 25))
            row[f"{eng}_q3"] = float(np.percentile(arr, 75))
            idx += repeats
        rows.append(row)
        summary = ", ".join(f"{e}={row[f'{e}_median']:,.0f}" for e in engine_names)
        print(f"  cancel_rate={cr:.0%}: {summary}")
    return rows


# ---------------------------------------------------------------------------
# Parallel queue-size scaling
# ---------------------------------------------------------------------------

def _bench_scaling_parallel(
    n_events_per_size: int, queue_sizes: list[int],
    cancel_rate: float, repeats: int, seed: int,
    pool: mp.Pool,
) -> list[dict]:
    from simulation import ALL_ENGINES
    engine_names = list(ALL_ENGINES.keys())
    tasks = [
        (eng, min(n_events_per_size, qs * 4), qs, cancel_rate, 0.05, seed + r)
        for qs in queue_sizes
        for eng in engine_names
        for r in range(repeats)
    ]
    print(f"  Dispatching {len(tasks)} tasks across workers...")
    raw = pool.map(_run_single_sim, tasks)

    rows: list[dict] = []
    idx = 0
    for qs in queue_sizes:
        row: dict = {"queue_size": qs}
        for eng in engine_names:
            arr = np.array([raw[idx + r]["throughput_eps"] for r in range(repeats)])
            row[f"{eng}_median"] = float(np.median(arr))
            row[f"{eng}_q1"] = float(np.percentile(arr, 25))
            row[f"{eng}_q3"] = float(np.percentile(arr, 75))
            idx += repeats
        rows.append(row)
        summary = ", ".join(f"{e}={row[f'{e}_median']:,.0f}" for e in engine_names)
        print(f"  queue_size={qs:>8,}: {summary}")
    return rows


# ---------------------------------------------------------------------------
# DES trace
# ---------------------------------------------------------------------------

def _collect_trace(n_events: int, queue_size: int, seed: int) -> dict:
    from simulation import run_heapx_traced
    print("  Collecting DES trace...")
    return run_heapx_traced(n_events, queue_size, 0.30, 0.05, seed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="CS4: Benchmark suite")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output", type=str, default="bench_results.json")
    ap.add_argument("--workers", type=int, default=0,
                    help="Worker processes (0 = all cores)")
    ap.add_argument("-q", "--quick", action="store_true",
                    help="Quick mode: reduced events for debugging (~2-5 min)")
    args = ap.parse_args()

    if args.quick:
        repeats = 1
        sweep_events = 50_000
        sweep_queue = 250_000
        scale_events = 200_000
        scale_sizes = [1_000, 5_000, 10_000, 50_000, 250_000]
        latency_queue = 250_000
        latency_ops = 10_000
        trace_events = 100_000
        trace_queue = 250_000
        print("*** QUICK MODE ***\n")
    else:
        repeats = args.repeats
        sweep_events = 500_000
        sweep_queue = 250_000
        scale_events = 10_000_000
        scale_sizes = [1_000, 5_000, 10_000, 50_000, 100_000,
                       250_000, 500_000, 1_000_000]
        latency_queue = 250_000
        latency_ops = 100_000
        # Trace workload sized to produce an operation mix that matches
        # the Classic-Hold benchmarking literature (Jones 1986) while
        # keeping runtime tractable: with n_events=100,000 events the
        # buildup/steady/drain phases each cover a meaningful portion
        # of the virtual-time axis in fig. 7, and the op-count ratios
        # in fig. 8 remain interpretable at print resolution.
        trace_events = 100_000
        trace_queue = 250_000

    n_workers = args.workers if args.workers > 0 else os.cpu_count() or 4
    print(f"Using {n_workers} worker processes\n")

    pool = mp.Pool(processes=n_workers)
    try:
        print("=" * 60)
        print("Benchmark 1: Cancellation-rate sweep")
        print("=" * 60)
        cancel_sweep = _bench_cancel_sweep_parallel(
            n_events=sweep_events, queue_size=sweep_queue,
            cancel_rates=[0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30,
                          0.35, 0.40, 0.45, 0.50],
            repeats=repeats, seed=args.seed, pool=pool,
        )

        print("\n" + "=" * 60)
        print("Benchmark 2: Queue-size scaling (30 % cancel)")
        print("=" * 60)
        scaling = _bench_scaling_parallel(
            n_events_per_size=scale_events, queue_sizes=scale_sizes,
            cancel_rate=0.30, repeats=repeats, seed=args.seed, pool=pool,
        )
    finally:
        pool.close(); pool.join()

    print("\n" + "=" * 60)
    print("Benchmark 3: Per-operation latency")
    print("=" * 60)
    latency = _bench_latency(queue_size=latency_queue, n_ops=latency_ops,
                              seed=args.seed)
    for eng, ops in latency.items():
        print(f"  {eng}: " + ", ".join(f"{k}={v:.0f}ns" for k, v in ops.items()))

    print("\n" + "=" * 60)
    print("Benchmark 4: DES trace")
    print("=" * 60)
    trace = _collect_trace(trace_events, trace_queue, args.seed)

    results = {
        "cancel_sweep": cancel_sweep,
        "scaling": scaling,
        "latency": latency,
        "trace": {
            "queue_sizes": trace["queue_sizes"],
            "op_types": trace["op_types"],
            "sim_times": [float(t) for t in trace["sim_times"]],
            "phase_boundaries": trace.get("phase_boundaries", {}),
        },
        "meta": {"repeats": repeats, "seed": args.seed},
    }

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nAll results saved to {args.output}")


if __name__ == "__main__":
    main()
