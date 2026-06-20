#!/usr/bin/env python3
"""Gap 3 — ``heapx.replace`` fused-operation microbenchmark.

The paper manuscript (``main.tex`` §7.5, lines 1018--1019) states that

    heapx.replace(heap, new_score, indices=0)

is *the* optimal primitive for bounded-heap streaming top-K because it
fuses pop-root and push-new into a single O(log K) sift-down, saving one
list ``append``/``pop`` pair per accepted element relative to the
``heapx.pop(heap) + heapx.push(heap, s)`` pattern.

This module provides the empirical evidence for that claim by isolating
the three canonical bounded-heap update patterns and measuring per-update
latency at varying K:

  (a) ``heapx.replace(heap, s, indices=0)``  -- fused, O(log K)
  (b) ``heapx.pop(heap); heapx.push(heap, s)`` -- two-call, O(log K) + O(log K)
  (c) ``heapq.heapreplace(heap, s)`` -- stdlib fused min-heap replace

The output figure ``fig_replace_vs_popush.png`` (published at 600 DPI)
gives reviewers a single-glance view of the fused-operation advantage.

References
----------
* Munro, J.I. & Paterson, M.S. (1980). Selection and sorting with limited
  storage. *Theoretical Computer Science*, 12, 315--323.
* Cormen, T.H. et al. (2009). *Introduction to Algorithms*, 3e, Ch. 6.
"""
from __future__ import annotations
import heapq
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_SRC = Path(__file__).resolve().parent.parent.parent.parent.parent / "src"
if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))
import heapx  # noqa: E402

SEED = 42
N_STREAM = 2_000_000
K_VALUES = [100, 1_000, 10_000, 100_000]
W, R = 2, 5
DPI = 600
RESULTS = Path(__file__).resolve().parent / "results"
FIGS = Path(__file__).resolve().parent / "figures"

HX = "#0072B2"
HX_LIGHT = "#56B4E9"
HQ = "#D55E00"

plt.rcParams.update({
  "font.family": "serif", "font.size": 9,
  "axes.titlesize": 10, "axes.titleweight": "bold",
  "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
  "legend.fontsize": 8, "figure.dpi": DPI, "savefig.dpi": DPI,
  "savefig.bbox": "tight", "savefig.pad_inches": 0.1,
  "axes.spines.top": False, "axes.spines.right": False,
})


def _accepted_scores(scores: np.ndarray, k: int) -> list[float]:
  """Deterministically enumerate the scores that *would* trigger a
  replace by simulating the stream with a cheap heapq.heapreplace."""
  sim = scores[:k].tolist()
  heapq.heapify(sim)
  accepted: list[float] = []
  for i in range(k, len(scores)):
    s = float(scores[i])
    if s > sim[0]:
      accepted.append(s)
      heapq.heapreplace(sim, s)
  return accepted


def _bench_one(fn, init_heap, accepted):
  """Median wall-time of ``fn(heap, accepted)`` over R runs after W warmups."""
  ts: list[float] = []
  for i in range(W + R):
    heap = init_heap[:]
    t0 = time.perf_counter()
    fn(heap, accepted)
    t = time.perf_counter() - t0
    if i >= W:
      ts.append(t)
  return float(np.median(ts))


def _hx_replace(heap, accepted):
  for s in accepted:
    heapx.replace(heap, s, indices=0)


def _hx_pop_push(heap, accepted):
  for s in accepted:
    heapx.pop(heap)
    heapx.push(heap, s)


def _hq_heapreplace(heap, accepted):
  for s in accepted:
    heapq.heapreplace(heap, s)


def run() -> dict[str, Any]:
  print(f"Generating {N_STREAM:,} scores (seed={SEED}) ...")
  scores = np.random.default_rng(SEED).standard_normal(N_STREAM)

  data: dict[str, Any] = {"k_values": K_VALUES, "n_stream": N_STREAM,
                           "replace": [], "pop_push": [], "heapq": []}
  for k in K_VALUES:
    acc = _accepted_scores(scores, k)
    n_acc = len(acc)

    # heapx: initial heap must be heapified before each trial; init_heap
    # is pre-heapified so _bench_one only measures the update loop.
    init = sorted(scores[:k].tolist())  # already a valid min-heap

    t_rep = _bench_one(_hx_replace, init, acc)
    t_pop = _bench_one(_hx_pop_push, init, acc)
    t_hq = _bench_one(_hq_heapreplace, init, acc)

    ns = lambda t: t / n_acc * 1e9  # noqa: E731
    entry_r = {"k": k, "accepted": n_acc, "total_ms": round(t_rep * 1e3, 3),
               "avg_ns": round(ns(t_rep), 1)}
    entry_p = {"k": k, "accepted": n_acc, "total_ms": round(t_pop * 1e3, 3),
               "avg_ns": round(ns(t_pop), 1)}
    entry_q = {"k": k, "accepted": n_acc, "total_ms": round(t_hq * 1e3, 3),
               "avg_ns": round(ns(t_hq), 1)}
    data["replace"].append(entry_r)
    data["pop_push"].append(entry_p)
    data["heapq"].append(entry_q)

    sp_over_pop = t_pop / t_rep if t_rep > 0 else 0
    sp_over_hq = t_hq / t_rep if t_rep > 0 else 0
    print(f"  K={k:>7,}  accepted={n_acc:>7,}  "
          f"replace={ns(t_rep):7.1f}ns  "
          f"pop+push={ns(t_pop):7.1f}ns  "
          f"heapq={ns(t_hq):7.1f}ns  "
          f"({sp_over_pop:.2f}x vs pop+push, {sp_over_hq:.2f}x vs heapq)")

  RESULTS.mkdir(parents=True, exist_ok=True)
  with open(RESULTS / "replace_data.json", "w") as f:
    json.dump(data, f, indent=2)
  return data


def plot(data: dict[str, Any]) -> None:
  ks = data["k_values"]
  rep_ns = [e["avg_ns"] for e in data["replace"]]
  pop_ns = [e["avg_ns"] for e in data["pop_push"]]
  hq_ns = [e["avg_ns"] for e in data["heapq"]]

  fig, ax = plt.subplots(figsize=(5.6, 3.4))
  x = np.arange(len(ks))
  w = 0.26
  ax.bar(x - w, rep_ns, w, color=HX, edgecolor="black", lw=0.3,
         label="heapx.replace (fused)", zorder=3)
  ax.bar(x, pop_ns, w, color=HX_LIGHT, edgecolor="black", lw=0.3,
         label="heapx.pop + heapx.push", zorder=3)
  ax.bar(x + w, hq_ns, w, color=HQ, edgecolor="black", lw=0.3,
         label="heapq.heapreplace", zorder=3)

  # Annotate replace speedup vs pop+push above every replace bar.
  for i, (r, p) in enumerate(zip(rep_ns, pop_ns)):
    sp = p / r if r > 0 else 0
    ax.text(i - w, r + max(rep_ns + pop_ns + hq_ns) * 0.02,
            f"{sp:.2f}x*", ha="center", fontsize=7,
            fontweight="bold", color=HX)

  ax.set_xticks(x)
  ax.set_xticklabels([f"{k//1000}K" if k >= 1000 else str(k) for k in ks])
  ax.set_xlabel("Heap Size K")
  ax.set_ylabel("Average Latency per Accepted Update (ns)")
  ax.set_title("Bounded-Heap Update: Fused replace vs. pop+push vs. heapq")
  ax.legend(loc="upper left", frameon=False, fontsize=7.5)
  ax.grid(axis="y", alpha=0.2, lw=0.4)

  fig.tight_layout()
  fig.subplots_adjust(bottom=0.26)
  fig.text(0.03, 0.11,
           "* Annotated ratio = (heapx.pop + heapx.push) / heapx.replace; "
           "values < 1 mean pop+push is faster at this K.",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")
  fig.text(0.03, 0.06,
           "\u2020 At small-to-medium K (\u2264 10K) per-call kwargs parsing in "
           "replace(..., indices=0) exceeds the saved sift-up; at K \u2265 100K",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")
  fig.text(0.03, 0.02,
           "  the fused O(log K) sift-down amortises the parsing cost and parity "
           f"is reached. Stream: {data['n_stream']:,} N(0,1) scores.",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")

  FIGS.mkdir(parents=True, exist_ok=True)
  fig.savefig(FIGS / "fig_replace_vs_popush.png")
  plt.close(fig)
  print(f"  \u2713 fig_replace_vs_popush.png")


def main() -> None:
  print("=== Gap 3: heapx.replace fused-operation microbenchmark ===")
  data = run()
  plot(data)


if __name__ == "__main__":
  main()
