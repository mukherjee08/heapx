#!/usr/bin/env python3
"""ML Algorithm 2: Feature Selection via Heap-Based Top-K.

Isolates the selection step: given a float score array, extract top K.
heapx advantage: homogeneous float max-heap + bulk pop.
"""
from __future__ import annotations
import heapq, json, sys, time
from pathlib import Path
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_SRC = Path(__file__).resolve().parent.parent.parent.parent.parent / "src"
if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))
import heapx

SEED = 42
W, R = 2, 5
DPI = 600
RESULTS = Path(__file__).resolve().parent / "results"
FIGS = Path(__file__).resolve().parent / "figures"

HX = "#0072B2"
HQ = "#D55E00"
NP_C = "#009E73"
PY = "#999999"

plt.rcParams.update({
  "font.family": "serif", "font.size": 9,
  "axes.titlesize": 10, "axes.titleweight": "bold",
  "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
  "legend.fontsize": 8, "figure.dpi": DPI, "savefig.dpi": DPI,
  "savefig.bbox": "tight", "savefig.pad_inches": 0.1,
  "axes.spines.top": False, "axes.spines.right": False,
})


def _med_time(fn):
  ts = []
  for i in range(W + R):
    t0 = time.perf_counter()
    fn()
    t = time.perf_counter() - t0
    if i >= W:
      ts.append(t)
  return float(np.median(ts))


def bench_selection_scaling():
  print("  Selection time vs N_features …")
  K = 100
  nf_vals = [1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
  rng = np.random.default_rng(SEED)
  full = rng.random(max(nf_vals)).tolist()
  full_arr = np.array(full)

  out = {"nf_vals": nf_vals, "k": K,
         "heapx_ms": [], "heapx_a4_ms": [],
         "heapq_ms": [], "numpy_ms": [], "sorted_ms": []}

  for nf in nf_vals:
    sl = full[:nf]
    sa = full_arr[:nf]
    t_hx = _med_time(lambda: (lambda d: (heapx.heapify(d, max_heap=True), heapx.pop(d, n=K, max_heap=True)))(sl[:]))
    t_hx4 = _med_time(lambda: (lambda d: (heapx.heapify(d, max_heap=True, arity=4), heapx.pop(d, n=K, max_heap=True, arity=4)))(sl[:]))
    t_hq = _med_time(lambda: heapq.nlargest(K, sl))
    t_np = _med_time(lambda: sa[np.argpartition(sa, -K)[-K:]])
    t_py = _med_time(lambda: sorted(sl, reverse=True)[:K])

    out["heapx_ms"].append(round(t_hx * 1e3, 3))
    out["heapx_a4_ms"].append(round(t_hx4 * 1e3, 3))
    out["heapq_ms"].append(round(t_hq * 1e3, 3))
    out["numpy_ms"].append(round(t_np * 1e3, 3))
    out["sorted_ms"].append(round(t_py * 1e3, 3))
    sp = t_hq / t_hx if t_hx > 0 else 0
    print(f"    F={nf:>9,}  hx={t_hx*1e3:8.2f}  hx4={t_hx4*1e3:8.2f}  "
          f"hq={t_hq*1e3:8.2f}  np={t_np*1e3:8.2f}  "
          f"py={t_py*1e3:8.2f} ms  hx/hq={sp:.2f}×")
  return out


def bench_correctness():
  print("  Correctness check …")
  rng = np.random.default_rng(SEED)
  scores = rng.random(10_000).tolist()
  K = 50
  d1 = scores[:]
  heapx.heapify(d1, max_heap=True)
  top_hx = sorted(heapx.pop(d1, n=K, max_heap=True), reverse=True)
  top_hq = sorted(heapq.nlargest(K, scores), reverse=True)
  assert top_hx == top_hq, "Selection mismatch!"
  print("    ✓ All methods agree.")


def plot_selection_time(data):
  nf = data["nf_vals"]
  fig, ax = plt.subplots(figsize=(5.5, 3.0))
  x = range(len(nf))
  ax.plot(x, data["heapx_ms"], "o-", color=HX, lw=1.5, ms=5,
          label="heapx (binary)")
  ax.plot(x, data["heapx_a4_ms"], "D-", color=HX, lw=1.2, ms=4,
          alpha=0.65, label="heapx (arity=4)")
  ax.plot(x, data["heapq_ms"], "s-", color=HQ, lw=1.5, ms=5,
          label="heapq (nlargest)")
  ax.plot(x, data["numpy_ms"], "^--", color=NP_C, lw=1.3, ms=5,
          label="numpy (argpartition)")
  ax.plot(x, data["sorted_ms"], "x--", color=PY, lw=1.0, ms=5,
          label="sorted() + slice")

  ax.set_xticks(x)
  ax.set_xticklabels([f"{f//1000}K" if f < 1e6 else f"{f//1_000_000}M"
                       for f in nf], fontsize=7)
  ax.set_xlabel("Number of Feature Scores")
  ax.set_ylabel("Top-K Selection Time (ms)")
  ax.set_yscale("log")
  ax.set_title(f"Feature Selection: Top-{data['k']} from Score Array")
  ax.legend(loc="upper left", frameon=False, fontsize=7)
  ax.grid(axis="y", alpha=0.2, lw=0.4)
  fig.tight_layout()
  fig.savefig(FIGS / "fs_selection_time.png")
  plt.close(fig)
  print("  ✓ fs_selection_time.png")


def plot_speedup(data):
  """Speedup bar chart: heapx vs heapq for feature selection."""
  nf = data["nf_vals"]
  sp2 = [data["heapq_ms"][i] / data["heapx_ms"][i]
         if data["heapx_ms"][i] > 0 else 0 for i in range(len(nf))]
  sp4 = [data["heapq_ms"][i] / data["heapx_a4_ms"][i]
         if data["heapx_a4_ms"][i] > 0 else 0 for i in range(len(nf))]

  fig, ax = plt.subplots(figsize=(5.5, 3.2))
  x = np.arange(len(nf))
  w = 0.25
  ax.bar(x - w, [1.0] * len(nf), w, color=HQ, edgecolor="black", lw=0.3,
         label="heapq (baseline = 1.0\u00d7)", zorder=3)
  ax.bar(x, sp2, w, color=HX, edgecolor="black", lw=0.3,
         label="heapx (binary)", zorder=3)
  ax.bar(x + w, sp4, w, color=HX, edgecolor="black", lw=0.3,
         alpha=0.65, hatch="//", label="heapx (arity=4)", zorder=3)
  ax.axhline(1.0, color="grey", ls="--", lw=0.6)

  for i in range(len(nf)):
    ax.text(i, sp2[i] + 0.08, f"{sp2[i]:.1f}\u00d7", ha="center",
            fontsize=4, fontweight="bold", color=HX)
    ax.text(i + w, sp4[i] + 0.08, f"{sp4[i]:.1f}\u00d7", ha="center",
            fontsize=4, fontweight="bold", color=HX)

  ax.set_xticks(x)
  ax.set_xticklabels([f"{f//1000}K" if f < 1e6 else f"{f//1_000_000}M"
                       for f in nf], fontsize=7)
  ax.set_xlabel("Number of Feature Scores")
  ax.set_ylabel("Selection Speedup\n(heapx relative to heapq)")
  ax.set_title("Top-K Feature Selection: Heap-Based Extraction Speedup")
  ax.legend(loc="upper right", frameon=False, fontsize=6.5)
  ax.set_ylim(0, max(max(sp2), max(sp4)) * 1.25)
  ax.grid(axis="y", alpha=0.2, lw=0.4)
  fig.tight_layout()
  fig.savefig(FIGS / "fs_speedup_bar.png")
  plt.close(fig)
  print("  ✓ fs_speedup_bar.png")


def main():
  RESULTS.mkdir(parents=True, exist_ok=True)
  FIGS.mkdir(parents=True, exist_ok=True)

  print("=== ML Algorithm 2: Feature Selection ===\n")
  bench_correctness()
  sel_data = bench_selection_scaling()

  with open(RESULTS / "fs_data.json", "w") as f:
    json.dump(sel_data, f, indent=2)

  print("\n  Generating figures:")
  plot_selection_time(sel_data)
  plot_speedup(sel_data)
  print(f"\n  Done.")

if __name__ == "__main__":
  main()
