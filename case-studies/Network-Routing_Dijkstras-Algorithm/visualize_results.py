"""Generate publication-ready benchmark result plots for Case Study 3.

Produces 10 figures (5 plot types x 2 weight types):
  1. Runtime comparison bar chart.
  2. Heap operation counts (horizontal stacked bar).
  3. Peak memory and max heap size comparison.
  4. Scaling plot (runtime vs graph size).
  5. Speedup plot (relative to heapq).

Usage:
  python3 visualize_results.py
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import numpy as np

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
FIG_DIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIG_DIR, exist_ok=True)

plt.rcParams.update({
  "font.family": "serif",
  "font.size": 10,
  "axes.labelsize": 11,
  "axes.titlesize": 12,
  "figure.dpi": 300,
  "savefig.dpi": 300,
  "savefig.pad_inches": 0.15,
  "legend.fontsize": 9,
})

COLORS = {
  "heapx (replace)": "#2ca02c",
  "heapx (lazy)": "#17becf",
  "heapq": "#1f77b4",
  "sortedcontainers": "#d62728",
}
LAZY_METHODS = ["heapx (lazy)", "heapq", "sortedcontainers"]


def load_results() -> list[dict]:
  path = os.path.join(RESULTS_DIR, "benchmark_results.json")
  with open(path) as f:
    return json.load(f)


def _filter(results, wt):
  return [r for r in results if r["weight_type"] == wt]


def _get(data, size, method, key, default=None):
  for r in data:
    if r["num_nodes"] == size and r["method"] == method:
      return r[key]
  return default


def _fmt_nodes(x, _=None):
  if x >= 1e6:
    return f"{x / 1e6:.1f}M"
  if x >= 1e3:
    return f"{x / 1e3:.0f}K"
  return f"{x:.0f}"


# ── 1. Runtime comparison (issues #7) ────────────────────────────────────

def plot_runtime_bars(results, wt="distance"):
  data = _filter(results, wt)
  sizes = sorted(set(r["num_nodes"] for r in data if r["method"] in LAZY_METHODS))

  fig, ax = plt.subplots(figsize=(8, 5.2))
  x = np.arange(len(sizes))
  width = 0.25

  for i, method in enumerate(LAZY_METHODS):
    times = [_get(data, s, method, "elapsed_s", 0) for s in sizes]
    bars = ax.bar(
      x + i * width, times, width,
      label=method, color=COLORS[method], edgecolor="white", linewidth=0.4,
    )
    for bar, t in zip(bars, times):
      if t > 0:
        ax.text(
          bar.get_x() + bar.get_width() / 2,
          bar.get_height() + ax.get_ylim()[1] * 0.005,
          f"{t:.2f}s",
          ha="left", va="bottom", fontsize=7, fontweight="bold",
          rotation=90,
        )

  ax.set_xlabel("Graph Size (nodes)", fontsize=11)
  ax.set_ylabel("Runtime (seconds)", fontsize=11)
  ax.set_title(
    f"Dijkstra Runtime: {wt.title()} Weights",
    fontweight="bold", fontsize=13, pad=10,
  )
  ax.set_xticks(x + width)
  ax.set_xticklabels([_fmt_nodes(s) for s in sizes])
  ax.legend(
    title="Priority Queue", title_fontsize=10,
    fontsize=11, framealpha=0.9, edgecolor="gray",
  )
  ax.grid(axis="y", alpha=0.25, linewidth=0.5)
  ax.set_axisbelow(True)
  # Add headroom for rotated labels
  ymax = max(_get(data, s, m, "elapsed_s", 0) for s in sizes for m in LAZY_METHODS)
  ax.set_ylim(top=ymax * 1.18)

  fig.tight_layout()
  out = os.path.join(FIG_DIR, f"runtime_comparison_{wt}.png")
  fig.savefig(out, bbox_inches="tight")
  plt.close(fig)
  print(f"  Saved {out}")


# ── 2. Operation counts (issue #6) ───────────────────────────────────────

def plot_operation_counts(results, wt="distance"):
  data = _filter(results, wt)
  largest = max(r["num_nodes"] for r in data)
  data = [r for r in data if r["num_nodes"] == largest]
  methods_present = [r["method"] for r in data]

  fig, ax = plt.subplots(figsize=(10, 4.2))

  cat_colors = {
    "insert":      "#4daf4a",
    "extract-min": "#377eb8",
    "stale pops":  "#ff7f00",
    "remove":      "#e41a1c",
  }

  def _get_ops(rec):
    if "replaces" in rec:
      return [
        ("insert", rec["pushes"]),
        ("extract-min", rec["pops"]),
      ]
    elif "stale_pops" in rec:
      return [
        ("insert", rec["pushes"]),
        ("extract-min", rec["pops"] - rec["stale_pops"]),
        ("stale pops", rec["stale_pops"]),
      ]
    else:
      return [
        ("insert", rec["adds"]),
        ("remove", rec["removes"]),
        ("extract-min", rec["pops"]),
      ]

  max_total = 0
  all_ops = []
  for method in methods_present:
    rec = next(r for r in data if r["method"] == method)
    ops = _get_ops(rec)
    total = sum(c for _, c in ops)
    if total > max_total:
      max_total = total
    all_ops.append(ops)

  for i, (method, ops) in enumerate(zip(methods_present, all_ops)):
    bottom = 0
    for label, count in ops:
      color = cat_colors[label]
      ax.barh(i, count, left=bottom, height=0.55,
              color=color, edgecolor="white", linewidth=0.6)
      total = sum(c for _, c in ops)
      if count / total > 0.06:
        ax.text(bottom + count / 2, i, f"{count:,}",
                ha="center", va="center", fontsize=9,
                color="white", fontweight="bold")
      bottom += count

    # Annotate small segments to the right
    right_parts = []
    for label, count in ops:
      total = sum(c for _, c in ops)
      if 0 < count / total <= 0.06:
        right_parts.append(f"{label}: {count:,}")
    if right_parts:
      ax.text(bottom + max_total * 0.01, i, "  ".join(right_parts),
              ha="left", va="center", fontsize=9, fontweight="bold",
              color="#444444")

  ax.set_yticks(range(len(methods_present)))
  ax.set_yticklabels(methods_present, fontsize=10)
  ax.set_xlabel("Total Heap Operations", fontsize=11)
  ax.set_title(
    f"Heap Operation Breakdown: {_fmt_nodes(largest)} Nodes ({wt.title()})",
    fontweight="bold", fontsize=13, pad=10,
  )
  ax.xaxis.set_major_formatter(
    ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else f"{x/1e3:.0f}K"),
  )
  ax.grid(axis="x", alpha=0.25, linewidth=0.5)
  ax.set_axisbelow(True)
  ax.set_xlim(right=max_total * 1.25)

  # Legend without "replace" — only categories actually used
  used_cats = set()
  for ops in all_ops:
    for label, _ in ops:
      used_cats.add(label)
  handles = [
    mpatches.Patch(facecolor=cat_colors[c], edgecolor="white", label=c)
    for c in ["insert", "extract-min", "stale pops", "remove"] if c in used_cats
  ]
  ax.legend(
    handles=handles, title="Heap Operation Type", title_fontsize=9,
    loc="upper center", bbox_to_anchor=(0.5, -0.185),
    framealpha=0.95, edgecolor="gray", fontsize=8, ncol=len(handles),
  )

  fig.subplots_adjust(bottom=0.22)
  out = os.path.join(FIG_DIR, f"operation_counts_{wt}.png")
  fig.savefig(out, bbox_inches="tight")
  plt.close(fig)
  print(f"  Saved {out}")


# ── 3. Memory comparison (issue #5) ──────────────────────────────────────

def plot_memory_comparison(results, wt="distance"):
  data = _filter(results, wt)
  replace_sizes = sorted(set(r["num_nodes"] for r in data if r["method"] == "heapx (replace)"))
  all_sizes = sorted(set(r["num_nodes"] for r in data if r["method"] in LAZY_METHODS))

  fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2))

  if replace_sizes:
    x = np.arange(len(replace_sizes))
    width = 0.2
    for i, method in enumerate(["heapx (replace)", "heapx (lazy)", "heapq", "sortedcontainers"]):
      hs = [_get(data, s, method, "max_heap_size", 0) for s in replace_sizes]
      if any(h > 0 for h in hs):
        ax1.bar(x + i * width, hs, width, label=method, color=COLORS[method],
                edgecolor="white", linewidth=0.4)
    ax1.set_xlabel("Graph Size (nodes)", fontsize=13)
    ax1.set_ylabel("Max Heap Size (entries)", fontsize=13)
    ax1.set_title("(a) Bounded vs Inflated Heap", fontweight="bold", fontsize=12)
    ax1.set_xticks(x + 1.5 * width)
    ax1.set_xticklabels([_fmt_nodes(s) for s in replace_sizes])
    ax1.legend(fontsize=11, framealpha=0.9, edgecolor="gray")
    ax1.grid(axis="y", alpha=0.25, linewidth=0.5)
    ax1.set_axisbelow(True)

  x = np.arange(len(all_sizes))
  width = 0.25
  for i, method in enumerate(LAZY_METHODS):
    mem = [_get(data, s, method, "peak_memory_bytes", 0) / 1e6 for s in all_sizes]
    ax2.bar(x + i * width, mem, width, label=method, color=COLORS[method],
            edgecolor="white", linewidth=0.4)
  ax2.set_xlabel("Graph Size (nodes)", fontsize=13)
  ax2.set_ylabel("Peak Memory (MB)", fontsize=13)
  ax2.set_title("(b) Peak Traced Memory", fontweight="bold", fontsize=12)
  ax2.set_xticks(x + width)
  ax2.set_xticklabels([_fmt_nodes(s) for s in all_sizes])
  ax2.legend(fontsize=11, framealpha=0.9, edgecolor="gray")
  ax2.grid(axis="y", alpha=0.25, linewidth=0.5)
  ax2.set_axisbelow(True)

  fig.suptitle(
    f"Memory and Heap Size Comparison: {wt.title()} Weights",
    fontweight="bold", fontsize=16,
  )
  fig.tight_layout()
  fig.subplots_adjust(top=0.88)

  out = os.path.join(FIG_DIR, f"memory_comparison_{wt}.png")
  fig.savefig(out, bbox_inches="tight")
  plt.close(fig)
  print(f"  Saved {out}")


# ── 4. Scaling (issue #8) ────────────────────────────────────────────────

def plot_scaling(results, wt="distance"):
  data = _filter(results, wt)
  sizes = sorted(set(r["num_nodes"] for r in data if r["method"] in LAZY_METHODS))

  fig, ax = plt.subplots(figsize=(7, 4.5))
  for method in LAZY_METHODS:
    times = [_get(data, s, method, "elapsed_s", 0) for s in sizes]
    ax.plot(sizes, times, "o-", label=method, color=COLORS[method],
            linewidth=2, markersize=5, markeredgecolor="white", markeredgewidth=0.5)

  ax.set_xlabel("Graph Size (nodes)", fontsize=11)
  ax.set_ylabel("Runtime (seconds)", fontsize=11)
  ax.set_title(f"Dijkstra Scaling: {wt.title()} Weights",
               fontweight="bold", fontsize=13, pad=10)
  ax.legend(fontsize=11, framealpha=0.9, edgecolor="gray")
  ax.grid(alpha=0.25, linewidth=0.5)
  ax.set_axisbelow(True)
  ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt_nodes))

  fig.tight_layout()
  out = os.path.join(FIG_DIR, f"scaling_{wt}.png")
  fig.savefig(out, bbox_inches="tight")
  plt.close(fig)
  print(f"  Saved {out}")


# ── 5. Speedup (issue #8) ────────────────────────────────────────────────

def plot_speedup(results, wt="distance"):
  data = _filter(results, wt)
  sizes = sorted(set(r["num_nodes"] for r in data if r["method"] in LAZY_METHODS))

  fig, ax = plt.subplots(figsize=(7, 4.5))
  heapq_times = [_get(data, s, "heapq", "elapsed_s", 1) for s in sizes]

  for method in ["heapx (lazy)", "sortedcontainers"]:
    times = [_get(data, s, method, "elapsed_s", 1) for s in sizes]
    speedup = [hq / t if t > 0 else 1 for hq, t in zip(heapq_times, times)]
    ax.plot(sizes, speedup, "o-", label=method, color=COLORS[method],
            linewidth=2, markersize=5, markeredgecolor="white", markeredgewidth=0.5)

  ax.axhline(y=1.0, color="#555555", linestyle="--", linewidth=1, alpha=0.6,
             label="heapq baseline")
  ax.set_xlabel("Graph Size (nodes)", fontsize=11)
  ax.set_ylabel("Speedup (relative to heapq)", fontsize=11)
  ax.set_title(f"Speedup vs heapq: {wt.title()} Weights",
               fontweight="bold", fontsize=13, pad=10)
  ax.legend(fontsize=11, framealpha=0.9, edgecolor="gray")
  ax.grid(alpha=0.25, linewidth=0.5)
  ax.set_axisbelow(True)
  ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt_nodes))

  fig.tight_layout()
  out = os.path.join(FIG_DIR, f"speedup_{wt}.png")
  fig.savefig(out, bbox_inches="tight")
  plt.close(fig)
  print(f"  Saved {out}")


def main():
  results = load_results()
  print(f"Loaded {len(results)} records")
  for wt in ["distance", "time"]:
    if not _filter(results, wt):
      continue
    print(f"\nPlots for {wt} weights:")
    plot_runtime_bars(results, wt)
    plot_operation_counts(results, wt)
    plot_memory_comparison(results, wt)
    plot_scaling(results, wt)
    plot_speedup(results, wt)
  print("\nDone.")


if __name__ == "__main__":
  main()
