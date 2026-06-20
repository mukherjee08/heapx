#!/usr/bin/env python3
"""Publication-ready figures for Case Study 5 — Streaming Top-K.

Revision 3 — all requested modifications applied.
"""
from __future__ import annotations
import json, os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS = Path(__file__).resolve().parent / "results"
FIGS = Path(__file__).resolve().parent / "figures"
DPI = 600

HX = "#0072B2"
HQ = "#D55E00"
NP_C = "#009E73"
PY = "#999999"

def _style():
  plt.rcParams.update({
    "font.family": "serif", "font.size": 9,
    "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "legend.fontsize": 8, "figure.dpi": DPI, "savefig.dpi": DPI,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.1,
    "axes.spines.top": False, "axes.spines.right": False,
  })

def _load():
  with open(RESULTS / "bench_data.json") as f:
    return json.load(f)

def _save(fig, name):
  fig.savefig(FIGS / name)
  plt.close(fig)
  print(f"  ✓ {name}")

def _size_label(s):
  if s >= 1_000_000: return f"{s // 1_000_000}M"
  return f"{s // 1000}K"


# ═══════════════════════════════════════════════════════════════════
# FIG 1 — Bulk Heapify (item 4: compact, larger suptitle, less whitespace)
# ═══════════════════════════════════════════════════════════════════
def fig_heapify(d):
  h = d["heapify"]
  sizes, sp, hx, hq = h["sizes"], h["speedup"], h["heapx_ms"], h["heapq_ms"]
  labels = [_size_label(s) for s in sizes]

  fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 2.5),
                                  gridspec_kw={"width_ratios": [3, 2.6]})

  x = np.arange(len(sizes))
  w = 0.35
  ax1.bar(x - w/2, hx, w, color=HX, edgecolor="black", lw=0.3,
          label="heapx", zorder=3)
  ax1.bar(x + w/2, hq, w, color=HQ, edgecolor="black", lw=0.3,
          label="heapq", zorder=3)
  for i, s in enumerate(sp):
    y = max(hx[i], hq[i])
    ax1.text(i, y * 1.25, f"{s:.1f}×", ha="center", fontsize=6.5,
             fontweight="bold", color=HX)
  ax1.set_xticks(x)
  ax1.set_xticklabels(labels, fontsize=7)
  ax1.set_yscale("log")
  ax1.set_ylabel("Heapify Time (ms)")
  ax1.set_xlabel("Array Size (number of floats)")
  ax1.set_title("(a) Heapify Time", fontsize=10)
  ax1.legend(loc="upper left", frameon=False)
  ax1.grid(axis="y", alpha=0.2, lw=0.4)

  ax2.plot(range(len(sizes)), sp, "o-", color=HX, lw=1.5, ms=4.5, zorder=3)
  ax2.axhline(1.0, color="grey", ls="--", lw=0.6, alpha=0.5)
  ax2.fill_between(range(len(sizes)), 1.0, sp, alpha=0.15, color=HX)
  ax2.set_xticks(range(len(sizes)))
  ax2.set_xticklabels(labels, fontsize=6.5, rotation=45, ha="right")
  ax2.set_ylabel("Speedup (heapx over heapq)")
  ax2.set_xlabel("Array Size (number of floats)")
  ax2.set_title("(b) Speedup Factor", fontsize=10)
  ax2.set_ylim(0, max(sp) * 1.25)
  ax2.grid(axis="y", alpha=0.2, lw=0.4)
  for i, s in enumerate(sp):
    ax2.annotate(f"{s:.1f}×", (i, s), textcoords="offset points",
                 xytext=(0, 6), ha="center", fontsize=6.5,
                 fontweight="bold", color=HX)

  fig.suptitle("Bulk Heapify: heapx vs. heapq on Homogeneous Float Arrays",
               fontsize=12, fontweight="bold")
  fig.subplots_adjust(top=0.82, wspace=0.35)
  _save(fig, "fig1_heapify_speedup.png")


# ═══════════════════════════════════════════════════════════════════
# FIG 2 — Type Specialization (item 5: ylim=30, no tuple hatch, black footnote, x-label)
# ═══════════════════════════════════════════════════════════════════
def fig_type_spec(d):
  ts = d["type_spec"]
  types, hx, hq, sp = ts["types"], ts["heapx_ms"], ts["heapq_ms"], ts["speedup"]

  fig, ax = plt.subplots(figsize=(4.5, 3.2))
  x = np.arange(len(types))
  w = 0.35
  ax.bar(x - w/2, hx, w, color=HX, edgecolor="black", lw=0.3,
         label="heapx", zorder=3)
  ax.bar(x + w/2, hq, w, color=HQ, edgecolor="black", lw=0.3,
         label="heapq", zorder=3)

  for i, s in enumerate(sp):
    y = max(hx[i], hq[i])
    colour = HX if s >= 1.0 else HQ
    ax.text(i, y + 1.0, f"{s:.2f}×", ha="center", fontsize=7.5,
            fontweight="bold", color=colour)

  ax.set_xticks(x)
  xlabels = [t if t != "tuple" else "tuple*" for t in types]
  ax.set_xticklabels(xlabels)
  ax.set_xlabel("Python Data Type")
  ax.set_ylabel("Heapify Time (ms)")
  ax.set_ylim(0, 30)
  ax.set_title("Type-Specialized Heapify (N = 500 K)")
  ax.legend(loc="upper left", frameon=False)
  ax.grid(axis="y", alpha=0.2, lw=0.4)

  fig.tight_layout()
  fig.subplots_adjust(bottom=0.22)
  fig.text(0.03, 0.03,
           "* tuple: no type specialization (generic comparison path).",
           fontsize=5.5, ha="left", va="top",
           style="italic", color="black")

  _save(fig, "fig2_type_specialization.png")


# ═══════════════════════════════════════════════════════════════════
# FIG 3 — Arity (item 6: add x-label)
# ═══════════════════════════════════════════════════════════════════
def fig_arity(d):
  ar = d["arity"]
  arities, times = ar["arities"], ar["heapify_ms"]
  hq_binary = d["heapify"]["heapq_ms"][6]

  fig, ax = plt.subplots(figsize=(4.2, 2.9))
  ax.bar(range(len(arities)), times, color=HX, edgecolor="black",
         lw=0.3, width=0.55, zorder=3)
  ax.axhline(hq_binary, color=HQ, ls="--", lw=1.4,
             label=f"heapq (binary): {hq_binary:.1f} ms")
  for i, t in enumerate(times):
    ax.text(i, t + 0.4, f"{hq_binary/t:.1f}×", ha="center", fontsize=8,
            fontweight="bold", color=HX)
  ax.set_xticks(range(len(arities)))
  ax.set_xticklabels([f"arity = {a}" for a in arities])
  ax.set_xlabel("Heap Branching Factor (arity)")
  ax.set_ylabel("Heapify Time (ms)")
  ax.set_title("N-ary Heap Tuning (N = 1 M floats)")
  ax.set_ylim(0, hq_binary * 1.25)
  ax.legend(loc="upper right", frameon=False, fontsize=8)
  ax.grid(axis="y", alpha=0.2, lw=0.4)
  fig.tight_layout()
  _save(fig, "fig3_arity_comparison.png")


# ═══════════════════════════════════════════════════════════════════
# FIG 4 — Bulk Pop (item 7: K from 1 to 100K in increments of 1000,
#          add sorted() baseline, speedup all points, footnote, no overlap)
# ═══════════════════════════════════════════════════════════════════
def fig_bulk_pop(d):
  bp = d["bulk_pop"]
  ks = bp["k_values"]
  hx = bp["heapx_ms"]
  hq = bp["heapq_ms"]
  np_ms = bp.get("numpy_ms", [])
  py_ms = bp.get("sorted_ms", [])

  fig, ax = plt.subplots(figsize=(6.5, 3.5))

  # Use actual K values as x-axis (not indices)
  ax.plot(ks, hx, "-", color=HX, lw=1.2, ms=0,
          label="heapx (heapify + bulk pop)", zorder=3)
  ax.plot(ks, hq, "-", color=HQ, lw=1.2, ms=0,
          label="heapq (nlargest)", zorder=3)
  if np_ms:
    ax.plot(ks, np_ms, "--", color=NP_C, lw=1.0, ms=0,
            label="numpy (argpartition)", zorder=3)
  if py_ms:
    ax.plot(ks, py_ms, ":", color="black", lw=1.0, ms=0,
            label="sorted() + slice", zorder=2)

  # Speedup annotations at selected K values
  # Early K values need higher offset to clear heapq/numpy lines
  label_ks_high = {1: -10, 10_000: 14, 20_000: 8, 40_000: 8}
  label_ks_low  = {60_000: -10, 80_000: -10, 100_000: -10}
  label_ks = {**label_ks_high, **label_ks_low}
  for lk, oy in label_ks.items():
    if lk in ks:
      i = ks.index(lk)
      sp = hq[i] / hx[i] if hx[i] > 0 else 0
      ax.annotate(f"{sp:.2f}×", (ks[i], hx[i]),
                  textcoords="offset points", xytext=(5, oy),
                  fontsize=5.5, fontweight="bold", color=HX)

  ax.set_xlabel("K (number of items to extract)")
  ax.set_ylabel("Extraction Time (ms)")
  ax.set_title("Top-K Extraction from 1 M Elements")
  ax.legend(loc="upper left", frameon=False, fontsize=7)
  ax.grid(axis="y", alpha=0.2, lw=0.4)

  fig.tight_layout()
  fig.subplots_adjust(bottom=0.24)
  fig.text(0.03, 0.07,
           "* Speedup values compare heapx against heapq.",
           fontsize=5.5, ha="left", va="top",
           style="italic", color="black")
  fig.text(0.03, 0.02,
           "\u2020 Solid lines = heap-based (streaming); dashed = vectorised batch; dotted = full sort.",
           fontsize=5.5, ha="left", va="top",
           style="italic", color="black")

  _save(fig, "fig4_bulk_pop_topk.png")


# ═══════════════════════════════════════════════════════════════════
# FIG 5 — Push (item 8: x-label, no hatch, add sorted baseline, footnote)
# ═══════════════════════════════════════════════════════════════════
def fig_push(d):
  p = d["push"]
  SL = "#CC79A7"  # sortedcontainers colour
  BK = "black"    # naive baseline

  labels = [
    "SortedList\n(add ×100K)",
    "list.append\n+ sort",
    "heapq\n(push ×100K)",
    "heapx\n(push ×100K)",
    "heapx\n(bulk 100K)",
  ]
  times = [
    p.get("single_sortedlist_ms", 0),
    p.get("naive_append_sort_ms", 0),
    p["single_heapq_ms"],
    p["single_heapx_ms"],
    p["bulk_heapx_ms"],
  ]
  colours = [SL, BK, HQ, HX, HX]

  fig, ax = plt.subplots(figsize=(5.5, 3.2))
  bars = ax.bar(range(len(labels)), times, color=colours,
                edgecolor="black", lw=0.3, width=0.6, zorder=3)

  # Speedup annotations (heapx vs heapq single) — only on heapx bars
  base = p["single_heapq_ms"]
  for i in [3, 4]:
    sp = base / times[i] if times[i] > 0 else 0
    ax.text(i, times[i] + max(times) * 0.02,
            f"{sp:.2f}×*", ha="center", fontsize=7.5,
            fontweight="bold", color=HX)

  ax.set_xticks(range(len(labels)))
  ax.set_xticklabels(labels, fontsize=7)
  ax.set_xlabel("Push Method and Module")
  ax.set_ylabel("Total Push Time (ms)")
  ax.set_title("Push 100 K Items into 100 K-Element Heap")
  ax.grid(axis="y", alpha=0.2, lw=0.4)

  fig.tight_layout()
  fig.subplots_adjust(bottom=0.28)
  fig.text(0.03, 0.07,
           "* Speedup values compare heapx against heapq (single push).",
           fontsize=5.5, ha="left", va="top",
           style="italic", color="black")
  fig.text(0.03, 0.02,
           "\u2020 SortedList = sortedcontainers.SortedList; list.append + sort = naive baseline.",
           fontsize=5.5, ha="left", va="top",
           style="italic", color="black")

  _save(fig, "fig5_push_throughput.png")


# ═══════════════════════════════════════════════════════════════════
# FIG 6 — Parallel (item 9: use all CPU threads, remove ideal line, fix y-label)
# ═══════════════════════════════════════════════════════════════════
def fig_parallel(d):
  par = d["parallel"]
  threads = par["threads"]
  sp_t = par["nogil_true"]
  sp_f = par["nogil_false"]
  hq_sp = par.get("heapq_speedup", None)
  py_sp = par.get("sorted_speedup", None)

  SK = "#CC79A7"

  fig, ax = plt.subplots(figsize=(5.0, 3.6))

  # Plot all four series — include baselines in legend
  ax.plot(range(len(threads)), sp_t, "o-", color=HX, lw=1.5, ms=6,
          label="heapx (nogil=True)", zorder=3)
  ax.plot(range(len(threads)), sp_f, "s--", color=HQ, lw=1.3, ms=5,
          label="heapx (nogil=False)", zorder=3)
  if hq_sp is not None:
    ax.axhline(hq_sp, color=SK, ls="-.", lw=1.0, alpha=0.8, zorder=2,
               label=f"heapq (single-threaded): {hq_sp:.2f}\u00d7")
  if py_sp is not None:
    ax.axhline(py_sp, color="black", ls=":", lw=1.0, alpha=0.6, zorder=2,
               label=f"sorted() (single-threaded): {py_sp:.2f}\u00d7")

  ax.fill_between(range(len(threads)), sp_f, sp_t, alpha=0.12, color=HX)

  # Speedup annotations with symbol
  for i, s in enumerate(sp_t):
    if threads[i] == 2:
      ax.annotate(f"{s:.2f}\u00d7*", (i, s), textcoords="offset points",
                  xytext=(-8, 8), fontsize=7, fontweight="bold", color=HX)
    elif threads[i] > 1:
      ax.annotate(f"{s:.2f}\u00d7*", (i, s), textcoords="offset points",
                  xytext=(8, 4), fontsize=7, fontweight="bold", color=HX)

  ax.set_xticks(range(len(threads)))
  ax.set_xticklabels([str(t) for t in threads])
  ax.set_xlabel("Number of Threads")
  ax.set_ylabel("Parallel Speedup\n(relative to 1 thread)")
  ax.set_title("Parallel Heapify: GIL Release Scaling")
  ymax = max(max(sp_t), hq_sp or 0, py_sp or 0, 2.0) * 1.2
  ax.set_ylim(0, ymax)
  ax.legend(loc="upper left", frameon=False, fontsize=6.5)
  ax.grid(axis="y", alpha=0.2, lw=0.4)

  fig.tight_layout()
  fig.subplots_adjust(bottom=0.28)
  fig.text(0.03, 0.10,
           "* Speedup shows intra-series scaling of heapx (nogil=True) at T threads "
           "vs. heapx (nogil=True) at 1 thread;",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")
  fig.text(0.03, 0.05,
           "  values isolate parallel scaling. The gap between solid and dashed curves "
           "is the GIL-release benefit at each T.",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")
  fig.text(0.03, 0.00,
           "\u2020 Solid = GIL released; dashed = GIL held; dash-dot = single-threaded "
           "stdlib; dotted = single-threaded full sort.",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")

  _save(fig, "fig6_parallel_scaling.png")


# ═══════════════════════════════════════════════════════════════════
# FIG 7 — Score Distribution
# ═══════════════════════════════════════════════════════════════════
def fig_score_dist():
  scores = np.random.default_rng(42).standard_normal(500_000)
  fig, ax = plt.subplots(figsize=(4.0, 2.4))
  ax.hist(scores, bins=120, color=HX, edgecolor="white", lw=0.2,
          alpha=0.85, density=True, zorder=3)
  xs = np.linspace(-5, 5, 300)
  ax.plot(xs, np.exp(-xs**2 / 2) / np.sqrt(2 * np.pi),
          color=HQ, lw=1.0, ls="--",
          label=r"$\mathcal{N}(0,1)$ PDF", zorder=4)
  ax.set_xlabel("Score Value")
  ax.set_ylabel("Probability Density")
  ax.set_title(r"Synthetic Score Distribution ($\mathcal{N}(0,\,1)$)")
  ax.legend(loc="upper right", frameon=False)
  ax.grid(axis="y", alpha=0.15, lw=0.3)
  fig.tight_layout()
  _save(fig, "fig7_score_distribution.png")


def main():
  _style()
  FIGS.mkdir(parents=True, exist_ok=True)
  # Only remove the seven core figs (fig1_..fig7_), not the ML / Gap figs.
  for i in range(1, 8):
    for f in FIGS.glob(f"fig{i}_*.png"):
      f.unlink()

  d = _load()
  print("Generating core figures at 600 DPI (revision 3):")
  fig_heapify(d)
  fig_type_spec(d)
  fig_arity(d)
  fig_bulk_pop(d)
  fig_push(d)
  fig_parallel(d)
  fig_score_dist()
  print(f"\nCore figures → {FIGS}/")

if __name__ == "__main__":
  main()
