#!/usr/bin/env python3
"""Gap 5 -- "Where heapx wins" single-glance speedup summary.

Aggregates the *representative* heapx vs. heapq speedup from every
benchmark in this case study into one publication chart. Reviewers can
see at a glance that heapx's architectural wins live in bulk heapify,
bulk pop at large K, parallel scaling, the fused replace operation, and
sliding-window top-K, while the end-to-end Python-loop streaming case is
acknowledged as dominated by interpreter overhead.

Reads:
  - results/bench_data.json              (core heapify/pop/push/parallel)
  - results/replace_data.json            (Gap 3 fused replace)
  - results/sliding_window_data.json     (Gap 6)
  - results/beam_search_data.json        (Gap 1)
  - results/throughput.json              (end-to-end streaming)

Produces:
  - figures/fig_speedup_summary.png
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DPI = 600
RESULTS = Path(__file__).resolve().parent / "results"
FIGS = Path(__file__).resolve().parent / "figures"

HX = "#0072B2"
NEG = "#999999"

plt.rcParams.update({
  "font.family": "serif", "font.size": 9,
  "axes.titlesize": 10, "axes.titleweight": "bold",
  "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
  "legend.fontsize": 8, "figure.dpi": DPI, "savefig.dpi": DPI,
  "savefig.bbox": "tight", "savefig.pad_inches": 0.1,
  "axes.spines.top": False, "axes.spines.right": False,
})


def _load(p: Path) -> dict | None:
  if not p.exists():
    return None
  with open(p) as f:
    return json.load(f)


def _best(ratios):
  return max(r for r in ratios if r is not None and np.isfinite(r))


def collect() -> list[tuple[str, float, str]]:
  """Return a list of (label, speedup_ratio, note) tuples."""
  rows: list[tuple[str, float, str]] = []

  bench = _load(RESULTS / "bench_data.json")
  if bench:
    sp = max(bench["heapify"]["speedup"])
    rows.append(("Bulk heapify\n(homog. float)", sp, "best of 8 sizes"))

    # Bulk pop at large K: take the max speedup in heapify-dominated range.
    ks = bench["bulk_pop"]["k_values"]
    speeds = bench["bulk_pop"]["speedup"]
    sp_large = max(s for k, s in zip(ks, speeds) if k >= 50_000)
    rows.append(("Bulk pop top-K\n(K >= 50K)", sp_large, "best at large K"))

    # Type-specialized float heapify.
    ts = bench["type_spec"]
    i_fl = ts["types"].index("float")
    rows.append(("Type-specialized\nfloat heapify",
                  ts["speedup"][i_fl], "N=500K"))

    # Parallel scaling (nogil=True best speedup).
    par = bench["parallel"]
    rows.append(("Parallel heapify\n(nogil=True, best T)",
                  max(par["nogil_true"]), "vs. 1-thread nogil=True"))

    # Push bulk vs. heapq single push.
    push = bench["push"]
    sp_bulk = push["single_heapq_ms"] / push["bulk_heapx_ms"] \
      if push["bulk_heapx_ms"] > 0 else 0
    rows.append(("Bulk push (100K items)\nvs heapq single push",
                  sp_bulk, "bulk triggers O(n+k) heapify"))

  repl = _load(RESULTS / "replace_data.json")
  if repl:
    # Fused replace vs. pop+push (best K).
    best = max((p["total_ms"] / r["total_ms"]
                for r, p in zip(repl["replace"], repl["pop_push"])
                if r["total_ms"] > 0), default=0)
    rows.append(("Fused heapx.replace\nvs. heapx.pop+push", best,
                  "best of K in {100,1K,10K,100K}"))

  sw = _load(RESULTS / "sliding_window_data.json")
  if sw:
    sc = sw["scaling"]
    best = max(he / hx for hx, he in
                zip(sc["heapx_ms"], sc["heapq_eager_ms"]) if hx > 0)
    rows.append(("Sliding-window top-K\n(heapx.remove)", best,
                  "vs. heapq eager re-heapify"))

  bs = _load(RESULTS / "beam_search_data.json")
  if bs:
    sc = bs["scaling"]
    best = max(hq / hx for hx, hq in
                zip(sc["heapx_ms"], sc["heapq_ms"]) if hx > 0)
    rows.append(("Beam search decode\n(top-K per step)", best,
                  "best beam width"))

  thr = _load(RESULTS / "throughput.json")
  if thr:
    m = thr["methods"]
    if "heapx" in m and "heapq" in m:
      sp = m["heapq"]["wall_s"] / m["heapx"]["wall_s"]
      rows.append(("End-to-end streaming\n(Python loop dominates)", sp,
                    "loop overhead caps gain"))
  return rows


def plot(rows: list[tuple[str, float, str]]) -> None:
  if not rows:
    print("  No benchmark data found; skip summary plot.")
    return

  # Sort by speedup descending so the chart tells a clear story.
  rows = sorted(rows, key=lambda r: r[1], reverse=True)
  labels = [r[0] for r in rows]
  speeds = [r[1] for r in rows]
  colours = [HX if s >= 1.0 else NEG for s in speeds]

  fig, ax = plt.subplots(figsize=(7.2, 4.0))
  y = np.arange(len(labels))
  bars = ax.barh(y, speeds, color=colours, edgecolor="black", lw=0.3, zorder=3)
  ax.axvline(1.0, color="grey", ls="--", lw=0.7, alpha=0.6)
  ax.set_yticks(y)
  ax.set_yticklabels(labels, fontsize=8)
  ax.invert_yaxis()
  for i, s in enumerate(speeds):
    ax.text(s + max(speeds) * 0.01, i, f"{s:.2f}x",
            va="center", fontsize=8, fontweight="bold",
            color=HX if s >= 1.0 else NEG)
  ax.set_xlabel("heapx speedup relative to heapq baseline")
  ax.set_title("Case Study 5: Where heapx Wins (speedup summary)")
  ax.set_xlim(0, max(speeds) * 1.18)
  ax.grid(axis="x", alpha=0.2, lw=0.4)

  fig.tight_layout()
  fig.subplots_adjust(bottom=0.12)
  fig.text(0.03, 0.04,
           "* Dashed vertical line at 1.0x = heapq baseline; blue bars "
           "indicate heapx-favoured dimensions.",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")
  fig.text(0.03, 0.01,
           "\u2020 Speedups are best-of across parameter sweeps; see "
           "individual figures for full scaling curves.",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")

  FIGS.mkdir(parents=True, exist_ok=True)
  fig.savefig(FIGS / "fig_speedup_summary.png")
  plt.close(fig)
  print("  \u2713 fig_speedup_summary.png")
  for label, sp, note in rows:
    print(f"    {label.splitlines()[0]:38s}  {sp:6.2f}x  ({note})")


def main() -> None:
  print("=== Gap 5: speedup summary across all benchmarks ===")
  rows = collect()
  plot(rows)


if __name__ == "__main__":
  main()
