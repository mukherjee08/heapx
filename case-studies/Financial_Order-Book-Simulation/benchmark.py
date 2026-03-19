"""
Benchmark harness: heapx vs heapq on identical order-flow streams.

Measures wall-clock time for the full simulation and per-operation
latencies.  For cancellations, the *heap-maintenance* cost is isolated
from the linear-scan lookup cost so that the O(log n) vs O(n) difference
is clearly visible.

Usage:
  python benchmark.py [--events N] [--repeats R] [--output PATH]
"""

from __future__ import annotations

import argparse
import json
import time
import gc
from pathlib import Path
from typing import List

import numpy as np

from order_flow import FlowParams, OrderEvent, generate_order_flow
from order_book import OrderBook
from order_book_heapq import OrderBookHeapq


def _run_engine(engine, events: List[OrderEvent],
                is_heapx: bool) -> dict:
  """Drive *engine* through *events*, returning per-operation timings.

  For cancel events the timing is split into two parts:
    - ``cancel_find_ns``: time to locate the order in the heap (linear
      scan — identical cost for both engines).
    - ``cancel_maintain_ns``: time for the heap-maintenance step after
      removal (heapx.remove vs heapq.heapify — the metric of interest).
  """
  push_ns: List[int] = []
  pop_ns: List[int] = []
  cancel_find_ns: List[int] = []
  cancel_maintain_ns: List[int] = []

  for ev in events:
    if ev.event_type in ("limit_bid", "limit_ask"):
      side = "bid" if ev.event_type == "limit_bid" else "ask"
      t0 = time.perf_counter_ns()
      engine.submit_limit(ev.price, ev.quantity, side, ev.timestamp)
      push_ns.append(time.perf_counter_ns() - t0)

    elif ev.event_type in ("market_buy", "market_sell"):
      side = "buy" if ev.event_type == "market_buy" else "sell"
      t0 = time.perf_counter_ns()
      engine.submit_market(ev.quantity, side, ev.timestamp)
      pop_ns.append(time.perf_counter_ns() - t0)

    elif ev.event_type == "cancel":
      oid = ev.order_id
      side_str = engine._id_to_side.get(oid)
      if side_str is None:
        continue

      heap = engine.bids if side_str == "bid" else engine.asks

      # Phase 1: locate (identical for both engines)
      t0 = time.perf_counter_ns()
      idx = None
      for i, entry in enumerate(heap):
        if entry[2].order_id == oid:
          idx = i
          break
      cancel_find_ns.append(time.perf_counter_ns() - t0)

      if idx is None:
        continue

      # Phase 2: heap maintenance (the metric of interest)
      engine._id_to_side.pop(oid, None)
      t0 = time.perf_counter_ns()
      if is_heapx:
        import heapx
        heapx.remove(heap, indices=idx)
      else:
        import heapq
        heap[idx] = heap[-1]
        heap.pop()
        heapq.heapify(heap)
      cancel_maintain_ns.append(time.perf_counter_ns() - t0)

  return {
    "push_ns": push_ns,
    "pop_ns": pop_ns,
    "cancel_find_ns": cancel_find_ns,
    "cancel_maintain_ns": cancel_maintain_ns,
  }


def _summarise(timings: dict) -> dict:
  """Compute summary statistics from raw nanosecond lists."""
  out = {}
  for key in ("push_ns", "pop_ns", "cancel_find_ns", "cancel_maintain_ns"):
    arr = np.array(timings.get(key, []), dtype=np.float64)
    if len(arr) == 0:
      out[key] = {"n": 0, "mean": 0, "median": 0, "p99": 0, "total_ms": 0}
    else:
      out[key] = {
        "n": int(len(arr)),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "p99": float(np.percentile(arr, 99)),
        "total_ms": float(np.sum(arr) / 1e6),
      }
  return out


def run_benchmark(n_events: int, repeats: int, seed: int) -> dict:
  """Run the full benchmark and return structured results."""
  params = FlowParams()

  print(f"Generating {n_events} events ...")
  events = generate_order_flow(params, n_events, seed)
  actual = len(events)
  print(f"  Materialised {actual} events.")

  counts: dict[str, int] = {}
  for ev in events:
    counts[ev.event_type] = counts.get(ev.event_type, 0) + 1
  print(f"  Event mix: {counts}")

  results: dict = {
    "n_events": actual,
    "event_mix": counts,
    "repeats": repeats,
    "heapx": [],
    "heapq": [],
  }

  for r in range(repeats):
    print(f"\n--- Repeat {r + 1}/{repeats} ---")

    for label, EngineClass, is_hx in [
      ("heapx", OrderBook, True),
      ("heapq", OrderBookHeapq, False),
    ]:
      gc.disable()
      engine = EngineClass()
      t0 = time.perf_counter()
      timings = _run_engine(engine, events, is_heapx=is_hx)
      wall = time.perf_counter() - t0
      gc.enable()
      gc.collect()
      summary = _summarise(timings)
      summary["wall_s"] = wall
      results[label].append(summary)
      print(f"  {label}  wall={wall:.4f}s")

    sx = results["heapx"][-1]["wall_s"]
    sq = results["heapq"][-1]["wall_s"]
    print(f"  speedup={sq / sx:.2f}x")

  return results


def main() -> None:
  ap = argparse.ArgumentParser(description="Order-book benchmark")
  ap.add_argument("--events", type=int, default=500_000,
                  help="Number of events (default: 500000)")
  ap.add_argument("--repeats", type=int, default=5,
                  help="Number of repetitions (default: 5)")
  ap.add_argument("--seed", type=int, default=42)
  ap.add_argument("--output", type=str, default="results.json",
                  help="Output JSON path (default: results.json)")
  args = ap.parse_args()

  results = run_benchmark(args.events, args.repeats, args.seed)

  out_path = Path(args.output)
  out_path.write_text(json.dumps(results, indent=2))
  print(f"\nResults written to {out_path}")


if __name__ == "__main__":
  main()
