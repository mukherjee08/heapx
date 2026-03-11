"""
Performance comparison visualization suite for Case Study 2.

All figures: 600 DPI PNG, snug fit, centered, legends inside plots.
"""

from __future__ import annotations
import argparse, json, os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import FIG_DPI, FIG_FORMAT, FIG_DIR

C_BLUE = "#0072B2"
C_CYAN = "#56B4E9"
C_RED = "#D55E00"
C_GREEN = "#009E73"
C_ORANGE = "#E69F00"
C_PURPLE = "#CC79A7"
C_ARITY = [C_BLUE, C_GREEN, C_ORANGE, C_PURPLE]

_BASE = {
  "font.family": "sans-serif",
  "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
  "font.size": 9,
  "axes.labelsize": 10,
  "axes.titlesize": 11,
  "axes.titleweight": "bold",
  "legend.fontsize": 8,
  "legend.framealpha": 0.95,
  "legend.edgecolor": "0.8",
  "legend.fancybox": False,
  "xtick.labelsize": 8,
  "ytick.labelsize": 8,
  "figure.dpi": FIG_DPI,
  "savefig.dpi": FIG_DPI,
  "savefig.bbox": "tight",
  "savefig.pad_inches": 0.15,
  "axes.linewidth": 0.6,
  "axes.grid": False,
  "axes.spines.top": False,
  "axes.spines.right": False,
  "xtick.major.width": 0.5,
  "ytick.major.width": 0.5,
  "xtick.major.size": 3,
  "ytick.major.size": 3,
  "lines.linewidth": 1.2,
  "lines.markersize": 5,
}


def _fig_dir(base: str) -> str:
  d = os.path.join(base, FIG_DIR)
  os.makedirs(d, exist_ok=True)
  return d


def _save(fig, fig_dir: str, name: str) -> None:
  out = os.path.join(fig_dir, f"{name}.{FIG_FORMAT}")
  fig.savefig(out, facecolor="white", bbox_inches="tight", pad_inches=0.15)
  plt.close(fig)
  print(f"  {out}")


# ===================================================================
# Fig 7: Alignment throughput
# ===================================================================
def fig07_alignment_throughput(data: dict, fig_dir: str) -> None:
  hx = data["heapx_pairs_per_sec"]
  hq = data["heapq_pairs_per_sec"]
  speedup = data.get("speedup", hx / hq if hq > 0 else 1.0)

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(3.5, 3.2))
    bars = ax.bar(["heapx", "heapq"], [hx, hq],
                  color=[C_BLUE, C_RED], edgecolor="white",
                  linewidth=0.5, width=0.45)
    for bar in bars:
      h = bar.get_height()
      ax.text(bar.get_x() + bar.get_width() / 2, h * 1.01,
              f"{h:.1f}", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("Throughput (pairs / s)")
    ax.set_title("SW beam-search alignment")
    ax.set_ylim(0, max(hx, hq) * 1.14)
    ax.annotate(f"{speedup:.2f}\u00d7", xy=(0.5, max(hx, hq) * 0.45),
                fontsize=13, fontweight="bold", ha="center", color=C_BLUE)

  _save(fig, fig_dir, "fig07_alignment_throughput")


# ===================================================================
# Fig 8: Arity comparison
# ===================================================================
def fig08_arity_comparison(data: dict, fig_dir: str) -> None:
  arities = sorted(int(k) for k in data.keys())
  throughputs = [data[str(a)] for a in arities]
  best_idx = throughputs.index(max(throughputs))

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(4.0, 3.2))
    colors = [C_ARITY[i] for i in range(len(arities))]
    bars = ax.bar(range(len(arities)), throughputs,
                  color=colors, edgecolor="white", linewidth=0.5, width=0.55)
    bars[best_idx].set_edgecolor("black")
    bars[best_idx].set_linewidth(1.2)
    ax.set_xticks(range(len(arities)))
    ax.set_xticklabels([f"d = {a}" for a in arities])
    ax.set_xlabel("Heap arity (d)")
    ax.set_ylabel("Throughput (pairs / s)")
    ax.set_title("Beam-search throughput by heap arity")
    ax.set_ylim(0, max(throughputs) * 1.14)
    for bar, val in zip(bars, throughputs):
      ax.text(bar.get_x() + bar.get_width() / 2, val * 1.01,
              f"{val:.1f}", ha="center", va="bottom", fontsize=7)

  _save(fig, fig_dir, "fig08_arity_comparison")


# ===================================================================
# Fig 9: NJ performance
# ===================================================================
def fig09_nj_performance(data: dict, fig_dir: str) -> None:
  hx_t = data["heapx"]
  hq_t = data["heapq"]
  speedup = data.get("speedup", hq_t / hx_t if hx_t > 0 else 1.0)

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(3.5, 3.2))
    bars = ax.bar(["heapx", "heapq"], [hx_t, hq_t],
                  color=[C_BLUE, C_RED], edgecolor="white",
                  linewidth=0.5, width=0.45)
    for bar in bars:
      h = bar.get_height()
      ax.text(bar.get_x() + bar.get_width() / 2, h * 1.01,
              f"{h:.2f}s", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("Wall-clock time (s)")
    ax.set_title("Neighbor-joining construction")
    ax.set_ylim(0, max(hx_t, hq_t) * 1.16)
    ax.annotate(f"{speedup:.2f}\u00d7", xy=(0.5, max(hx_t, hq_t) * 0.45),
                fontsize=13, fontweight="bold", ha="center", color=C_BLUE)

  _save(fig, fig_dir, "fig09_nj_performance")


# ===================================================================
# Fig 10: Parallel heap ops — legend inside upper-left
# ===================================================================
def fig10_parallel_heap_ops(data: dict, fig_dir: str) -> None:
  threads = sorted(int(k) for k in data["heapx_nogil"].keys())
  hx_nogil = np.array([data["heapx_nogil"][str(t)] for t in threads]) / 1e6
  hx_gil = np.array([data["heapx_gil"][str(t)] for t in threads]) / 1e6
  hq = np.array([data["heapq"][str(t)] for t in threads]) / 1e6

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(5.0, 3.5))

    ax.plot(threads, hx_gil, "s-", color=C_BLUE, zorder=3,
            label="heapx (GIL held)")
    ax.plot(threads, hx_nogil, "o--", color=C_CYAN, zorder=3,
            label="heapx (nogil=True)")
    ax.plot(threads, hq, "^:", color=C_RED, zorder=2,
            label="heapq")

    ax.fill_between(threads, hq, hx_gil, alpha=0.08, color=C_BLUE)
    ax.set_xlabel("Number of threads")
    ax.set_ylabel("Throughput (M ops / s)")
    ax.set_xticks(threads)
    ax.set_title("Heap operations throughput vs. thread count")
    ax.yaxis.grid(True, alpha=0.15, linewidth=0.4)
    ax.set_ylim(0, max(hx_gil.max(), hx_nogil.max()) * 1.15)

    sp = hx_gil[0] / hq[0] if hq[0] > 0 else 1.0
    ax.annotate(
      f"{sp:.1f}\u00d7 at 1 thread",
      xy=(threads[0], (hx_gil[0] + hq[0]) / 2),
      xytext=(threads[0] + 1.5, (hx_gil[0] + hq[0]) / 2),
      fontsize=8, fontweight="bold", color=C_BLUE,
      arrowprops=dict(arrowstyle="->", color="0.5", lw=0.6),
    )

    # Legend inside lower-right
    ax.legend(loc="lower right", fontsize=7, frameon=True, edgecolor="0.7")

  _save(fig, fig_dir, "fig10_parallel_heap_ops")


# ===================================================================
# Fig 11: Speedup summary — baseline legend inside upper-left
# ===================================================================
def fig11_speedup_summary(results: dict, fig_dir: str) -> None:
  categories, speedups = [], []

  if "alignment_single" in results:
    categories.append("SW Beam\nAlignment")
    speedups.append(results["alignment_single"].get("speedup", 1.0))

  categories.append("Neighbor\nJoining")
  speedups.append(results["neighbor_joining"].get("speedup", 1.0))

  if "parallel_heap_ops" in results:
    ho = results["parallel_heap_ops"]
    max_t = str(max(int(k) for k in ho["heapx_nogil"].keys()))
    hq1 = ho["heapq"]["1"]

    hxg1 = ho["heapx_gil"]["1"]
    categories.append("Heap Ops\n(GIL, 1T)")
    speedups.append(hxg1 / hq1 if hq1 > 0 else 1.0)

    hx1 = ho["heapx_nogil"]["1"]
    categories.append("Heap Ops\n(nogil, 1T)")
    speedups.append(hx1 / hq1 if hq1 > 0 else 1.0)

    hx_mt = ho["heapx_nogil"][max_t]
    hq_mt = ho["heapq"][max_t]
    categories.append(f"Heap Ops\n(nogil, {max_t}T)")
    speedups.append(hx_mt / hq_mt if hq_mt > 0 else 1.0)

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    x = np.arange(len(categories))
    colors = [C_BLUE if s >= 1.0 else C_RED for s in speedups]
    bars = ax.bar(x, speedups, color=colors, edgecolor="white",
                  linewidth=0.5, width=0.5)

    ax.axhline(y=1.0, color=C_RED, linewidth=0.8, linestyle="--",
               alpha=0.6, label="heapq baseline (1.0\u00d7)")

    for bar, val in zip(bars, speedups):
      ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.04,
              f"{val:.2f}\u00d7", ha="center", va="bottom",
              fontsize=7, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=7)
    ax.set_ylabel("Speedup over heapq")
    ax.set_title("heapx speedup summary across bioinformatics workloads")
    ax.set_ylim(0, max(speedups) * 1.15)

    # Legend inside upper-left
    ax.legend(loc="upper left", fontsize=7, frameon=True, edgecolor="0.7")

  _save(fig, fig_dir, "fig11_speedup_summary")


# ===================================================================
# Fig 12: Multi-library comparison
# ===================================================================
def fig12_multi_library(data: dict, fig_dir: str) -> None:
  libs = ["heapx", "heapq", "sortedcontainers", "PriorityQueue"]
  ops = [data[lib]["ops_per_sec"] / 1e6 for lib in libs]
  labels = ["heapx", "heapq", "sorted\ncontainers", "queue.\nPriorityQueue"]
  colors = [C_BLUE, C_RED, C_GREEN, C_PURPLE]

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(5.0, 3.5))
    bars = ax.bar(range(len(libs)), ops, color=colors,
                  edgecolor="white", linewidth=0.5, width=0.55)

    for bar, val in zip(bars, ops):
      ax.text(bar.get_x() + bar.get_width() / 2, val + max(ops) * 0.02,
              f"{val:.1f}", ha="center", va="bottom", fontsize=8)

    for i in range(1, len(libs)):
      sp = ops[0] / ops[i]
      bar = bars[i]
      if ops[i] > max(ops) * 0.12:
        ax.text(bar.get_x() + bar.get_width() / 2,
                ops[i] * 0.5, f"{sp:.1f}\u00d7\nslower",
                ha="center", va="center", fontsize=7,
                color="white", fontweight="bold")
      else:
        ax.text(bar.get_x() + bar.get_width() / 2,
                ops[i] + max(ops) * 0.08, f"{sp:.0f}\u00d7 slower",
                ha="center", va="bottom", fontsize=7,
                color=colors[i], fontweight="bold")

    ax.set_xticks(range(len(libs)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Throughput (M ops / s)")
    ax.set_title("Heap operations: multi-library comparison")
    ax.set_ylim(0, max(ops) * 1.15)

  _save(fig, fig_dir, "fig12_multi_library")


# ===================================================================
def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--results",
    default=os.path.join(os.path.dirname(__file__), "results.json"))
  args = parser.parse_args()

  with open(args.results) as f:
    results = json.load(f)

  fd = _fig_dir(os.path.dirname(args.results))
  print(f"Generating performance figures in {fd}/\n")

  if "alignment_single" in results:
    fig07_alignment_throughput(results["alignment_single"], fd)
  fig08_arity_comparison(results["arity_comparison"], fd)
  fig09_nj_performance(results["neighbor_joining"], fd)
  if "parallel_heap_ops" in results:
    fig10_parallel_heap_ops(results["parallel_heap_ops"], fd)
  fig11_speedup_summary(results, fd)
  if "multi_library" in results:
    fig12_multi_library(results["multi_library"], fd)

  print("\nPerformance figures complete.")

if __name__ == "__main__":
  main()
