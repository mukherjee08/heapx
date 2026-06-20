"""
Publication-ready visualisation suite for Case Study 6.

Generates 11 figures for the SPE paper:

  CONCEPTUAL (explain the simulation):
    fig01 — Workload characterisation (priority + burst distributions)
    fig02 — Scheduler architecture diagram (heapx operation mapping)
    fig03 — Queue size dynamics during mixed workload

  PERFORMANCE (multi-competitor):
    fig04 — Batch push scaling
    fig05 — Single push latency vs queue size
    fig06 — Single pop latency vs queue size
    fig07 — Replace (decrease-key) latency vs queue size  [HERO]
    fig08 — Replace-heavy end-to-end workload             [HERO]
    fig09 — Feature comparison heatmap
    fig10 — Memory overhead comparison
    fig11 — End-to-end scheduler throughput (ops/second)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
from matplotlib.gridspec import GridSpec

# ---------------------------------------------------------------------------
# Global style — Wiley SPE single-column, 600 DPI
# ---------------------------------------------------------------------------
DPI         = 600
FIG_W       = 5.5
FIG_H       = 3.8
FONT        = 9
PAD         = 0.08

C_HEAPX     = "#0072B2"
C_HEAPQ     = "#D55E00"
C_SORTED    = "#009E73"
C_HEAPDICT  = "#CC79A7"
C_FIBONACCI = "#E69F00"
C_CANCEL    = "#56B4E9"

COLORS = {
  "heapx": C_HEAPX, "heapq": C_HEAPQ, "sortedcontainers": C_SORTED,
  "heapdict": C_HEAPDICT, "fibonacci_heap": C_FIBONACCI,
}
MARKERS = {
  "heapx": "o", "heapq": "s", "sortedcontainers": "^",
  "heapdict": "D", "fibonacci_heap": "v",
}
LABELS = {
  "heapx": "heapx", "heapq": "heapq (stdlib)",
  "sortedcontainers": "SortedList", "heapdict": "heapdict",
  "fibonacci_heap": "Fibonacci heap",
}

plt.rcParams.update({
  "font.family":       "sans-serif",
  "font.sans-serif":   ["DejaVu Sans", "Helvetica", "Arial"],
  "font.size":         FONT,
  "axes.titlesize":    FONT + 1,
  "axes.labelsize":    FONT,
  "xtick.labelsize":   FONT - 1,
  "ytick.labelsize":   FONT - 1,
  "legend.fontsize":   FONT - 1.5,
  "legend.framealpha":  0.85,
  "legend.edgecolor":  "0.7",
  "figure.dpi":        DPI,
  "savefig.dpi":       DPI,
  "savefig.bbox":      "tight",
  "savefig.pad_inches": PAD,
  "axes.spines.top":   False,
  "axes.spines.right": False,
  "axes.grid":         True,
  "grid.alpha":        0.25,
  "grid.linewidth":    0.5,
  "lines.linewidth":   1.3,
  "lines.markersize":  4,
})

FDIR = Path(__file__).parent / "figures"


def _save(fig, name):
  FDIR.mkdir(exist_ok=True)
  fig.savefig(FDIR / name)
  plt.close(fig)
  print(f"  \u2713 {name}")


def _med(arr):
  return float(np.nanmedian(arr))


# ===================================================================
# Fig 01 — Workload characterisation
# ===================================================================
def fig01_workload(data: Dict) -> None:
  from workload import generate_workload
  tasks = generate_workload(n_tasks=100_000, seed=42)

  fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FIG_W, FIG_H * 0.85))

  # Panel A: Priority class histogram
  priorities = [t.priority for t in tasks]
  classes = ["CRITICAL\n(0)", "HIGH\n(1)", "NORMAL\n(2)", "LOW\n(3)"]
  counts = [priorities.count(float(i)) for i in range(4)]
  pcts = [c / len(priorities) * 100 for c in counts]
  bars = ax1.bar(classes, pcts, color=[C_HEAPX, C_SORTED, C_HEAPQ, C_HEAPDICT],
                 width=0.6, zorder=3, edgecolor="white", linewidth=0.5)
  ax1.set_xlabel("Priority class")
  ax1.set_ylabel("Fraction of tasks (%)")
  ax1.set_title("(a) Priority class distribution", fontsize=FONT)
  for bar, pct in zip(bars, pcts):
    ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
             f"{pct:.0f}%", ha="center", va="bottom", fontsize=FONT - 2,
             fontweight="bold")
  ax1.set_ylim(0, 72)

  # Panel B: Burst length CDF
  bursts = np.array([t.burst * 1000 for t in tasks])
  sorted_b = np.sort(bursts)
  cdf = np.arange(1, len(sorted_b) + 1) / len(sorted_b)
  ax2.plot(sorted_b, cdf, color=C_HEAPX, linewidth=1.5)
  ax2.set_xlabel("CPU burst length (ms)")
  ax2.set_ylabel("CDF")
  ax2.set_title("(b) Burst length distribution", fontsize=FONT)
  ax2.set_xlim(0, np.percentile(bursts, 99.5))
  ax2.set_ylim(0, 1.02)
  med_val = np.median(bursts)
  ax2.axvline(med_val, color=C_HEAPQ, linestyle="--", linewidth=0.8,
              label=f"Median = {med_val:.1f} ms")
  ax2.legend(loc="lower right")

  fig.suptitle(
    "Synthetic Task Scheduling Workload Characterisation (n = 100,000)",
    fontsize=FONT + 2, fontweight="bold", y=0.98)
  fig.subplots_adjust(top=0.85, wspace=0.35)
  _save(fig, "fig01_workload_characterisation.png")


# ===================================================================
# Fig 02 — Scheduler architecture (conceptual diagram)
# ===================================================================
def fig02_architecture() -> None:
  """Scheduler architecture: horizontal data-flow diagram."""
  fig, ax = plt.subplots(figsize=(FIG_W * 1.6, FIG_H * 1.0))
  ax.set_xlim(-3.2, 19.0)
  ax.set_ylim(-0.2, 6.8)
  ax.axis("off")

  # --- Title ---
  ax.text(7.9, 6.4,
          "heapx-Based Task Scheduler: Operation Mapping and Complexity",
          ha="center", va="center", fontsize=FONT + 1, fontweight="bold")

  # =====================================================================
  # Dimensions
  # =====================================================================
  bw, bh = 3.8, 1.0
  gap = 3.5                    # long arrows

  # Heap box — wide for policy text
  cx, cy, cw, ch = 4.6, 1.3, 6.6, 4.2
  heap_top = cy + ch
  heap_bot = cy
  hcx = cx + cw / 2
  hcy = cy + ch / 2

  lx = cx - gap - bw
  rx = cx + cw + gap

  y_top = heap_top - bh
  y_bot = heap_bot
  y_mid = (y_top + y_bot) / 2

  # =====================================================================
  # CENTRE: heapx priority queue
  # =====================================================================
  heap_box = mpatches.FancyBboxPatch(
    (cx, cy), cw, ch, boxstyle="round,pad=0.3",
    facecolor="#E3EEFA", edgecolor=C_HEAPX, linewidth=2.5)
  ax.add_patch(heap_box)
  ax.text(hcx, hcy + 0.7, "heapx", ha="center", va="center",
          fontsize=FONT + 5, fontweight="bold", color=C_HEAPX)
  ax.text(hcx, hcy + 0.0, "Priority Queue", ha="center", va="center",
          fontsize=FONT + 2, color=C_HEAPX)

  # Policy sub-box — must be fully inside the blue heap box
  pw, ph = cw - 0.5, 0.75
  px = cx + (cw - pw) / 2
  py = cy + 0.2
  policy_box = mpatches.FancyBboxPatch(
    (px, py), pw, ph, boxstyle="round,pad=0.12",
    facecolor="white", edgecolor="0.7", linewidth=0.7, linestyle="--")
  ax.add_patch(policy_box)
  ax.text(px + pw / 2, py + ph / 2,
          "cmp = \u03bbt: (t.priority, t.deadline)",
          ha="center", va="center", fontsize=FONT - 2.5,
          fontstyle="italic", color="0.1", family="monospace")

  # =====================================================================
  # Helpers
  # =====================================================================
  def _box(x, y, label, api, color):
    b = mpatches.FancyBboxPatch(
      (x, y), bw, bh, boxstyle="round,pad=0.12",
      facecolor=color + "15", edgecolor=color, linewidth=1.4)
    ax.add_patch(b)
    ax.text(x + bw / 2, y + bh / 2 + 0.12, label,
            ha="center", va="center", fontsize=FONT,
            fontweight="bold", color="0.1")
    ax.text(x + bw / 2, y + bh / 2 - 0.17, api,
            ha="center", va="center", fontsize=FONT - 2,
            family="monospace", color="0.35")

  def _arrow(x1, y1, x2, y2, label, color, style="->"):
    # Shorten arrow equally at both ends for consistent whitespace
    dx, dy = x2 - x1, y2 - y1
    length = (dx**2 + dy**2) ** 0.5
    ux, uy = dx / length, dy / length
    pad = 0.35  # equal gap from both boxes
    x1s, y1s = x1 + ux * pad, y1 + uy * pad
    x2s, y2s = x2 - ux * pad, y2 - uy * pad
    ax.annotate("", xy=(x2s, y2s), xytext=(x1s, y1s),
                arrowprops=dict(
                  arrowstyle=f"{style},head_width=0.35,head_length=0.2",
                  linewidth=2.5, color=color, alpha=0.8))
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2 + 0.25
    ax.text(mx, my, label,
            fontsize=FONT - 0.5, color=color, fontweight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.1", facecolor="white",
                      edgecolor="none", alpha=0.9))

  # =====================================================================
  # LEFT: Inputs
  # =====================================================================
  _box(lx, y_top, "Task Arrival", "heapx.push(task)", C_SORTED)
  _arrow(lx + bw, y_top + bh / 2, cx, hcy + 0.5, "O(log n)", C_SORTED)

  _box(lx, y_bot, "Batch Arrival", "heapx.push([tasks])", C_SORTED)
  _arrow(lx + bw, y_bot + bh / 2, cx, hcy - 0.5, "O(n+k)", C_SORTED)

  # =====================================================================
  # RIGHT: Outputs / Mutations
  # =====================================================================
  _box(rx, y_top, "Task Dispatch", "heapx.pop()", C_HEAPQ)
  _arrow(cx + cw, hcy + 0.5, rx, y_top + bh / 2, "O(log n)", C_HEAPQ)

  _box(rx, y_mid, "Priority Update", "heapx.replace()", C_HEAPDICT)
  _arrow(cx + cw, hcy, rx, y_mid + bh / 2, "O(log n)", C_HEAPDICT, style="<->")

  _box(rx, y_bot, "Cancel Expired", "heapx.remove(pred)", C_CANCEL)
  _arrow(cx + cw, hcy - 0.5, rx, y_bot + bh / 2, "O(n)", C_CANCEL)

  # =====================================================================
  # Bottom: scheduling policy note
  # =====================================================================
  ax.text(7.9, 0.1,
          "Scheduling policy: fixed-priority ordering with "
          "Earliest-Deadline-First tie-breaking",
          ha="center", va="center", fontsize=FONT - 1.5,
          color="0.45", fontstyle="italic")

  _save(fig, "fig02_scheduler_architecture.png")


# ===================================================================
# Fig 03 — Queue size dynamics (fixed: push-heavy to maintain queue)
# ===================================================================
def fig03_queue_dynamics(data: Dict) -> None:
  """Two-panel figure: (a) queue size over time, (b) operation rate breakdown.

  Panel (a) shows the ready queue fluctuating around a steady state,
  demonstrating the scale at which heapx operates.
  Panel (b) shows the cumulative operation mix as a stacked area,
  making visible the proportion of push/pop/replace/cancel events
  that the scheduler handles.
  """
  d = data["queue_dynamics"]
  ts = np.array(d["timestamps"])
  sizes = np.array(d["sizes"])
  ts = ts - ts[0]

  fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(FIG_W, FIG_H * 1.3),
                                  height_ratios=[2, 1], sharex=True)
  fig.suptitle("Scheduler Queue Dynamics During Simulated Workload",
               fontsize=FONT + 2, fontweight="bold", y=0.97)

  # --- Panel (a): Queue size ---
  ax1.plot(ts, sizes, color=C_HEAPX, linewidth=0.6, alpha=0.85)
  ax1.fill_between(ts, sizes, alpha=0.1, color=C_HEAPX)
  ax1.set_ylabel("Ready queue size")
  ax1.set_title("(a) Queue size over simulation time (steady-state)",
                fontsize=FONT)

  # Auto-scale around observed envelope with modest padding
  lo, hi = int(np.min(sizes)), int(np.max(sizes))
  span = max(1, hi - lo)
  pad = max(200, span // 4)
  ax1.set_ylim(max(0, lo - pad), hi + pad)

  # Tick formatter: when range < 10K use thousand-separated integers,
  # otherwise use the K-suffix formatter.  Avoids all ticks collapsing
  # to the same "50K" label in a tight steady-state window.
  if span < 10_000:
    ax1.yaxis.set_major_formatter(
      ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
  else:
    ax1.yaxis.set_major_formatter(
      ticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}K"))

  median_sz = np.median(sizes)
  ax1.axhline(median_sz, color=C_HEAPQ, linestyle="--", linewidth=0.8, alpha=0.6)
  ax1.text(ts[-1] * 0.98, median_sz + pad * 0.1,
           f"Median = {median_sz:,.0f}",
           fontsize=FONT - 1, color=C_HEAPQ, va="bottom", ha="right",
           fontweight="bold")

  # Operating regime annotation — placed in upper-left to avoid overlap
  ax1.text(ts[3], hi + pad * 0.4,
           f"Operating regime: {lo:,}\u2013{hi:,} tasks (std dev = {np.std(sizes):,.0f})",
           fontsize=FONT - 2, color="0.35", fontstyle="italic")

  # --- Panel (b): Cumulative operation mix ---
  if "cum_push" in d:
    cp = np.array(d["cum_push"], dtype=float)
    co = np.array(d["cum_pop"], dtype=float)
    cr = np.array(d["cum_replace"], dtype=float)

    # Convert to rates (events per sample interval)
    window = 20
    def _rate(arr):
      diff = np.diff(arr, prepend=0)
      return np.convolve(diff, np.ones(window)/window, mode="same")

    rp, ro, rr = _rate(cp), _rate(co), _rate(cr)

    ax2.stackplot(ts, rp, ro, rr,
                  colors=[C_SORTED, C_HEAPQ, C_HEAPDICT],
                  labels=["push", "pop", "replace"],
                  alpha=0.75)
    ax2.set_ylabel("Event rate\n(per sample)")
    ax2.set_xlabel("Simulation time (s)")
    ax2.set_title("(b) Operation mix over time", fontsize=FONT)
    ax2.set_ylim(0, max(rp + ro + rr) * 1.45)
    ax2.legend(loc="upper right", ncol=3, fontsize=FONT - 2,
               frameon=True, framealpha=0.85)

  fig.subplots_adjust(top=0.89, hspace=0.15)
  _save(fig, "fig03_queue_dynamics.png")


# ===================================================================
# Fig 04 — Batch push scaling
# ===================================================================
def fig04_batch_push(data: Dict) -> None:
  d = data["batch_push"]
  sizes = d["sizes"]

  fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
  for mod in ["heapx", "heapq", "sortedcontainers", "heapdict", "fibonacci_heap"]:
    if mod not in d:
      continue
    vals = [_med(v) for v in d[mod]]
    if all(np.isnan(v) for v in vals):
      continue
    ax.plot(sizes, vals, marker=MARKERS[mod], color=COLORS[mod],
            label=LABELS[mod])
  ax.set_xscale("log")
  ax.set_yscale("log")
  ax.set_xlabel("Batch size (tasks)")
  ax.set_ylabel("Time (ms)")
  ax.set_title("Batch Push Scaling")
  ax.legend()
  _save(fig, "fig04_batch_push_scaling.png")


# ===================================================================
# Generic multi-competitor line plot
# ===================================================================
def _plot_multi(
  data: Dict, key: str, ylabel: str, title: str, filename: str,
  use_log_y: bool = False,
  modules: List[str] | None = None,
  annotate_best: bool = True,
  legend_title: str = "Python module",
  legend_ncol: int = 2,
  narrative: str | None = None,
  ymax: float | None = None,
) -> None:
  d = data[key]
  sizes = d["queue_sizes"]
  if modules is None:
    modules = [m for m in d if m != "queue_sizes"]

  fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))

  for mod in modules:
    vals = [_med(v) for v in d[mod]]
    if all(np.isnan(v) for v in vals):
      continue
    ax.plot(sizes, vals, marker=MARKERS.get(mod, "o"),
            color=COLORS.get(mod, "gray"), label=LABELS.get(mod, mod))

  ax.set_xscale("log")
  if use_log_y:
    ax.set_yscale("log")
  if ymax is not None:
    ax.set_ylim(top=ymax)
  ax.set_xlabel("Queue size (tasks)")
  ax.set_ylabel(ylabel)
  ax.set_title(title)
  ax.legend(loc="upper left", ncol=legend_ncol, title=legend_title,
            title_fontsize=FONT - 1.5)

  # Annotate heapx speedup vs heapq at largest size
  if annotate_best and "heapx" in d and "heapq" in d:
    hx = _med(d["heapx"][-1])
    hq = _med(d["heapq"][-1])
    if hx > 0 and not np.isnan(hx) and not np.isnan(hq) and hq / hx > 2:
      sp = hq / hx
      label_txt = f"heapx {sp:,.0f}\u00d7 faster\nthan heapq" if sp >= 10 else f"heapx {sp:.1f}\u00d7 faster\nthan heapq"
      ax.annotate(
        label_txt,
        xy=(sizes[-1], hx),
        xytext=(-100, 45),
        textcoords="offset points",
        fontsize=FONT - 1,
        fontweight="bold",
        color=C_HEAPX,
        arrowprops=dict(arrowstyle="->", color=C_HEAPX, lw=1),
      )

  # Optional narrative footnote — rendered as left-aligned text below
  # the plot so it never overlaps data or legend.
  if narrative is not None:
    fig.text(0.02, 0.005, narrative,
             fontsize=FONT - 2.5, color="0.25",
             fontstyle="italic",
             ha="left", va="bottom")
    # Leave bottom margin for the footnote
    n_lines = narrative.count("\n") + 1
    fig.subplots_adjust(bottom=0.12 + 0.04 * n_lines)

  _save(fig, filename)


# ===================================================================
# Fig 09 — Feature comparison heatmap (fixed: ASCII symbols)
# ===================================================================
def fig09_feature_heatmap() -> None:
  modules = ["heapx", "heapq\n(stdlib)", "Sorted-\nList", "heapdict", "Fibonacci\nheap"]
  features = [
    "Min-heap",
    "Max-heap",
    "Key function (cmp)",
    "Bulk push",
    "Bulk pop (top-k)",
    "Remove by index",
    "Remove by predicate",
    "Replace (decrease-key)",
    "Merge",
    "Multi-arity (d-ary)",
    "GIL release (nogil)",
    "SIMD acceleration",
    "C extension",
  ]
  # 1 = supported, 0 = not, 0.5 = partial
  matrix = np.array([
    [1, 1, 1, 1, 1],
    [1, 0, 1, 0, 0],
    [1, 0, 1, 0, 0],
    [1, 0, 0, 0, 0],
    [1, 0, 0, 0, 0],
    [1, 0, 1, 1, 0],
    [1, 0, 0, 0, 0],
    [1, 0, 0.5, 1, 1],
    [1, 0.5, 0, 0, 0],
    [1, 0, 0, 0, 0],
    [1, 0, 0, 0, 0],
    [1, 0, 0, 0, 0],
    [1, 1, 0, 0, 0],
  ], dtype=float)

  fig, ax = plt.subplots(figsize=(FIG_W, FIG_H * 1.25))

  from matplotlib.colors import ListedColormap
  cmap = ListedColormap(["#FDDEDE", "#FFF3CD", "#D4EDDA"])
  bounds = [-0.25, 0.25, 0.75, 1.25]
  norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)

  ax.imshow(matrix, cmap=cmap, norm=norm, aspect="auto")

  ax.set_xticks(range(len(modules)))
  ax.set_xticklabels(modules, fontsize=FONT - 1)
  ax.set_yticks(range(len(features)))
  ax.set_yticklabels(features, fontsize=FONT - 1)
  ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

  # Use plain ASCII: Y / N / P (no Unicode glyphs)
  for i in range(len(features)):
    for j in range(len(modules)):
      val = matrix[i, j]
      if val == 1:
        symbol, color, weight = "Y", "#155724", "bold"
      elif val == 0.5:
        symbol, color, weight = "P", "#856404", "bold"
      else:
        symbol, color, weight = "N", "#721C24", "normal"
      ax.text(j, i, symbol, ha="center", va="center",
              fontsize=FONT, fontweight=weight, color=color)

  ax.set_title("Feature Support Matrix", fontsize=FONT + 1, pad=40)

  ax.set_xticks(np.arange(-0.5, len(modules)), minor=True)
  ax.set_yticks(np.arange(-0.5, len(features)), minor=True)
  ax.grid(which="minor", color="white", linewidth=2)
  ax.tick_params(which="minor", size=0)

  # Legend
  from matplotlib.patches import Patch
  legend_elements = [
    Patch(facecolor="#D4EDDA", edgecolor="0.7", label="Y = Supported"),
    Patch(facecolor="#FFF3CD", edgecolor="0.7", label="P = Partial"),
    Patch(facecolor="#FDDEDE", edgecolor="0.7", label="N = Not supported"),
  ]
  ax.legend(handles=legend_elements, loc="lower center",
            bbox_to_anchor=(0.5, -0.08), ncol=3, fontsize=FONT - 2,
            frameon=False)

  fig.tight_layout()
  _save(fig, "fig09_feature_heatmap.png")


# ===================================================================
# Fig 10 — Memory overhead comparison
# ===================================================================
def fig10_memory() -> None:
  import sys as _sys
  from task import Task

  sizes = [1_000, 5_000, 10_000, 50_000, 100_000, 500_000]
  task = Task(0, 2.0, 100.0, 0.0, 0.01)
  task_sz = _sys.getsizeof(task)

  results: Dict[str, List[float]] = {
    "heapx": [], "heapq": [], "sortedcontainers": [], "heapdict": [],
  }

  wrapper_tuple = (task.priority, task.deadline, 0, task)
  tuple_sz = _sys.getsizeof(wrapper_tuple)

  for n in sizes:
    list_overhead = _sys.getsizeof([None] * n)
    results["heapx"].append((list_overhead + n * task_sz) / 1e6)
    results["heapq"].append((list_overhead + n * (tuple_sz + task_sz)) / 1e6)
    results["sortedcontainers"].append((list_overhead * 2 + n * task_sz) / 1e6)
    dict_overhead = _sys.getsizeof(dict.fromkeys(range(min(n, 100)))) / 100 * n
    results["heapdict"].append((list_overhead + dict_overhead + n * task_sz) / 1e6)

  fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
  for mod in results:
    ax.plot(sizes, results[mod], marker=MARKERS.get(mod, "o"),
            color=COLORS.get(mod, "gray"), label=LABELS.get(mod, mod))
  ax.set_xscale("log")
  ax.set_xlabel("Number of tasks")
  ax.set_ylabel("Estimated memory (MB)")
  ax.set_title("Heap Memory Overhead Comparison")
  ax.legend(loc="upper left")

  overhead_pct = (results["heapq"][-1] - results["heapx"][-1]) / results["heapx"][-1] * 100
  ax.annotate(
    f"heapq: +{overhead_pct:.0f}%\n(tuple wrapping)",
    xy=(sizes[-1], results["heapq"][-1]),
    xytext=(-100, -30),
    textcoords="offset points",
    fontsize=FONT - 1.5,
    color=C_HEAPQ,
    arrowprops=dict(arrowstyle="->", color=C_HEAPQ, lw=0.8),
  )

  _save(fig, "fig10_memory_overhead.png")


# ===================================================================
# Fig 11 — End-to-end scheduler throughput
# ===================================================================
def fig11_scheduler_throughput(data: Dict) -> None:
  """Bar chart of heapx vs heapq scheduler throughput across queue sizes."""
  if "scheduler_throughput" not in data:
    return
  d = data["scheduler_throughput"]
  sizes = d["queue_sizes"]
  hx = np.array([_med(v) for v in d["heapx"]])
  hq = np.array([_med(v) for v in d["heapq"]])

  # Taller figure to accommodate headroom for speedup labels and a
  # bottom caption with the narrative.
  fig, ax = plt.subplots(figsize=(FIG_W, FIG_H * 1.15))
  x = np.arange(len(sizes))
  width = 0.38
  ax.bar(x - width/2, hx / 1e3, width, color=C_HEAPX,
         edgecolor="white", linewidth=0.6, label=LABELS["heapx"])
  ax.bar(x + width/2, hq / 1e3, width, color=C_HEAPQ,
         edgecolor="white", linewidth=0.6, label=LABELS["heapq"])
  ax.set_xticks(x)
  ax.set_xticklabels([f"{s:,}" for s in sizes], rotation=25)
  ax.set_xlabel("Prefilled queue size (tasks)")
  ax.set_ylabel("Throughput (K ops / second)")
  ax.set_yscale("log")
  ax.set_title("End-to-End Scheduler Throughput (mixed workload)")

  # Compute explicit y-limits to guarantee headroom for speedup labels
  ymin = max(1e-1, np.min(hq) / 1e3 * 0.3)
  ymax = np.max(hx) / 1e3 * 30.0
  ax.set_ylim(ymin, ymax)

  ax.legend(loc="upper left", framealpha=0.9)

  # Speedup labels just above each heapx bar
  for i, (a, b) in enumerate(zip(hx, hq)):
    if b > 0 and a > 0:
      sp = a / b
      label = f"{sp:,.0f}\u00d7" if sp >= 10 else f"{sp:.1f}\u00d7"
      ax.text(x[i], (a / 1e3) * 1.6,
              label, ha="center", va="bottom",
              fontsize=FONT - 1, color=C_HEAPX, fontweight="bold")

  # Left-aligned footnote below the plot (outside axes)
  fig.text(0.02, 0.005,
           "Mixed workload: 40% enqueue, 40% dispatch, 20% boost\u2011priority.   "
           "Drivers: HeapxScheduler / HeapqScheduler.\n"
           "heapq\u2019s lack of decrease\u2011key forces an O(n) heapify on every "
           "priority boost; heapx performs an O(log n) in-place sift.",
           fontsize=FONT - 2.5, color="0.25", fontstyle="italic",
           ha="left", va="bottom")

  # Leave bottom margin for the caption
  fig.subplots_adjust(bottom=0.22)
  _save(fig, "fig11_scheduler_throughput.png")


# ===================================================================
# Main
# ===================================================================
def main() -> None:
  FDIR.mkdir(exist_ok=True)

  results_path = Path(__file__).parent / "results.json"
  if not results_path.exists():
    print("results.json not found \u2014 run benchmark.py first.")
    sys.exit(1)

  with open(results_path) as f:
    data = json.load(f)

  print("Generating figures \u2026\n")

  fig01_workload(data)
  fig02_architecture()
  fig03_queue_dynamics(data)
  fig04_batch_push(data)

  _plot_multi(data, "single_push",
              "Latency per push (\u00b5s)",
              "Single Push Latency vs Queue Size",
              "fig05_single_push.png",
              ymax=0.7)

  _plot_multi(data, "single_pop",
              "Latency per pop (\u00b5s)",
              "Single Pop Latency vs Queue Size",
              "fig06_single_pop.png")

  _plot_multi(data, "replace",
              "Latency per replace (\u00b5s)",
              "Replace (Decrease-Key) Latency vs Queue Size",
              "fig07_replace_latency.png",
              use_log_y=True,
              narrative=(
                "heapq has no decrease-key primitive; "
                "the baseline forces an O(n) re-heapify per update.\n"
                "heapx performs an O(log n) in-place sift via "
                "heapx.replace(indices=...)."
              ))

  _plot_multi(data, "replace_heavy",
              "Total time (s)",
              "Replace-Heavy Workload (5 K Replaces + Push/Pop)",
              "fig08_replace_heavy.png",
              use_log_y=True,
              modules=["heapx", "heapq", "sortedcontainers", "heapdict"],
              narrative=(
                "Each heapq replace = O(n) heapify; total cost grows "
                "quadratically.\n"
                "heapx amortises 5,000 replaces as 5,000 O(log n) sifts."
              ))

  fig09_feature_heatmap()
  fig10_memory()
  fig11_scheduler_throughput(data)

  print(f"\nAll {len(list(FDIR.glob('fig*.png')))} figures saved to {FDIR}/")


if __name__ == "__main__":
  main()
