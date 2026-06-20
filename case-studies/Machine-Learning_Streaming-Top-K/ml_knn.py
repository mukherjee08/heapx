#!/usr/bin/env python3
"""ML Algorithm 1: KNN — Heap-Based Selection Phase.

Benchmarks heapify of homogeneous float distance arrays and bulk pop
K smallest — the heap-critical portion of the KNN pipeline.
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


def bench_heapify_distances():
  print("  Heapify distance array (float) …")
  n_vals = [10_000, 50_000, 100_000, 500_000, 1_000_000, 5_000_000]
  rng = np.random.default_rng(SEED)
  full = rng.random(max(n_vals)).tolist()
  full_arr = np.array(full)
  out = {"n_vals": n_vals,
         "heapx_ms": [], "heapq_ms": [],
         "sorted_ms": [], "np_sort_ms": [], "np_partition_ms": [],
         "speedup": []}
  for n in n_vals:
    d = full[:n]
    a = full_arr[:n].copy()
    t_hx = _med_time(lambda: heapx.heapify(d[:]))
    t_hq = _med_time(lambda: heapq.heapify(d[:]))
    t_py = _med_time(lambda: sorted(d))
    t_nps = _med_time(lambda: np.sort(a))
    t_npp = _med_time(lambda: np.partition(a, 10))  # partial sort, K=10
    sp = t_hq / t_hx if t_hx > 0 else 0
    out["heapx_ms"].append(round(t_hx * 1e3, 3))
    out["heapq_ms"].append(round(t_hq * 1e3, 3))
    out["sorted_ms"].append(round(t_py * 1e3, 3))
    out["np_sort_ms"].append(round(t_nps * 1e3, 3))
    out["np_partition_ms"].append(round(t_npp * 1e3, 3))
    out["speedup"].append(round(sp, 2))
    print(f"    N={n:>9,}  hx={t_hx*1e3:8.2f}  hq={t_hq*1e3:8.2f}  "
          f"py={t_py*1e3:8.2f}  nps={t_nps*1e3:8.2f}  "
          f"npp={t_npp*1e3:8.2f} ms  hx/hq={sp:.2f}×")
  return out


def bench_pop_k_smallest():
  print("  Pop K smallest (K = 10 to 10^7) …")
  N = 10_000_000
  k_vals = [10, 100, 1_000, 10_000, 100_000, 1_000_000]
  rng = np.random.default_rng(SEED)
  full_arr = rng.random(N)
  full = full_arr.tolist()
  out = {"n": N, "k_vals": k_vals,
         "heapx_ms": [], "heapq_ms": [], "numpy_ms": [],
         "sorted_ms": [], "speedup": []}
  for k in k_vals:
    def hx_fn():
      d = full[:]
      heapx.heapify(d)
      return heapx.pop(d, n=k)
    def hq_fn():
      return heapq.nsmallest(k, full)
    def np_fn():
      kk = min(k, N - 1)  # partition requires kth < len
      return np.partition(full_arr, kk)[:k]
    def py_fn():
      return sorted(full)[:k]

    t_hx = _med_time(hx_fn)
    t_hq = _med_time(hq_fn)
    t_np = _med_time(np_fn)
    t_py = _med_time(py_fn)  # include K=1M: sorted() scales with N, not K.
    sp = t_hq / t_hx if t_hx > 0 else 0
    out["heapx_ms"].append(round(t_hx * 1e3, 1))
    out["heapq_ms"].append(round(t_hq * 1e3, 1))
    out["numpy_ms"].append(round(t_np * 1e3, 1))
    out["sorted_ms"].append(round(t_py * 1e3, 1))
    out["speedup"].append(round(sp, 2))
    print(f"    K={k:>10,}  hx={t_hx*1e3:9.1f}  hq={t_hq*1e3:9.1f}  "
          f"np={t_np*1e3:9.1f}  py={t_py*1e3:9.1f} ms  hx/hq={sp:.2f}×")
  return out


def bench_correctness():
  print("  Correctness check …")
  rng = np.random.default_rng(SEED)
  dists = rng.random(10_000).tolist()
  K = 50
  d1 = dists[:]
  heapx.heapify(d1)
  top_hx = sorted(heapx.pop(d1, n=K))
  top_hq = sorted(heapq.nsmallest(K, dists))
  top_np = sorted(np.partition(np.array(dists), K)[:K].tolist())
  assert top_hx == top_hq, "heapx vs heapq mismatch!"
  assert np.allclose(top_hx, top_np), "heapx vs numpy mismatch!"
  print("    ✓ All methods agree.")


# ── Figures ───────────────────────────────────────────────────────

def plot_heapify_dists(data):
  n_vals = data["n_vals"]
  sp = data["speedup"]
  hx = data["heapx_ms"]
  hq = data["heapq_ms"]
  py_ms = data.get("sorted_ms", [])
  nps = data.get("np_sort_ms", [])
  npp = data.get("np_partition_ms", [])

  fig, ax = plt.subplots(figsize=(5.8, 3.4))
  x = np.arange(len(n_vals))

  # Line plot for all methods (cleaner than bars at 6 data points with 5 series)
  ax.plot(x, hx, "o-", color=HX, lw=1.5, ms=5,
          label="heapx (heapify)", zorder=4)
  ax.plot(x, hq, "s-", color=HQ, lw=1.5, ms=5,
          label="heapq (heapify)", zorder=3)
  if npp:
    ax.plot(x, npp, "D--", color=NP_C, lw=1.2, ms=4,
            label="numpy (partition, K=10)", zorder=3)
  if nps:
    ax.plot(x, nps, "^--", color=NP_C, lw=1.0, ms=4, alpha=0.6,
            label="numpy (full sort)", zorder=2)
  if py_ms:
    ax.plot(x, py_ms, "x:", color="black", lw=1.0, ms=5,
            label="sorted() (full sort)", zorder=2)

  # Speedup annotations — all placed ABOVE heapx points (log scale gives
  # ample space between heapx and the sorted/numpy-sort lines above)
  offsets = {
    0: (-14, 4),   # 10K
    1: (8, 8),     # 50K
    2: (0, -14),   # 100K
    3: (0, -22),   # 500K
    4: (0, -22),   # 1M
    5: (0, -22),   # 5M
  }
  for i, s in enumerate(sp):
    ox, oy = offsets.get(i, (10, 6))
    ax.annotate(f"{s:.1f}\u00d7*", (i, hx[i]),
                textcoords="offset points", xytext=(ox, oy),
                fontsize=6, fontweight="bold", color=HX)

  ax.set_xticks(x)
  ax.set_xticklabels([f"{n//1000}K" if n < 1e6 else f"{n//1_000_000}M"
                       for n in n_vals], fontsize=7)
  ax.set_yscale("log")
  ax.set_ylabel("Processing Time (ms)")
  ax.set_xlabel("Distance Array Size (number of floats)")
  ax.set_title("KNN: Distance Array Ordering Methods Compared")
  ax.legend(loc="upper left", frameon=False, fontsize=6.5)
  ax.grid(axis="y", alpha=0.2, lw=0.4)

  fig.tight_layout()
  fig.subplots_adjust(bottom=0.24)
  fig.text(0.03, 0.07,
           "* Speedup values compare heapx against heapq.",
           fontsize=5.5, ha="left", va="top",
           style="italic", color="black")
  fig.text(0.03, 0.02,
           "\u2020 Solid = heap-based; dashed = vectorised (numpy); dotted = full sort (Python).",
           fontsize=5.5, ha="left", va="top",
           style="italic", color="black")

  fig.savefig(FIGS / "knn_heapify_dists.png")
  plt.close(fig)
  print("  ✓ knn_heapify_dists.png")


def plot_pop_k(data):
  """K-smallest extraction: heapx vs heapq vs numpy vs sorted."""
  k_vals = data["k_vals"]
  hx = data["heapx_ms"]
  hq = data["heapq_ms"]
  np_ms = data["numpy_ms"]
  py_ms = data.get("sorted_ms", [])
  sp = data["speedup"]
  N = data["n"]

  fig, ax = plt.subplots(figsize=(6.0, 3.5))
  x = range(len(k_vals))

  ax.plot(x, hx, "o-", color=HX, lw=1.5, ms=5,
          label="heapx (heapify + pop K)", zorder=4)
  ax.plot(x, hq, "s-", color=HQ, lw=1.5, ms=5,
          label="heapq (nsmallest)", zorder=3)
  ax.plot(x, np_ms, "D--", color=NP_C, lw=1.2, ms=4,
          label="numpy (partition)", zorder=3)
  # sorted — only where measured (non-zero)
  if py_ms:
    py_plot = [(i, v) for i, v in enumerate(py_ms) if v > 0]
    if py_plot:
      px, py = zip(*py_plot)
      ax.plot(px, py, "x:", color="black", lw=1.0, ms=5,
              label="sorted() + slice", zorder=2)

  # Speedup annotations — alternate above/below to avoid overlap
  for i, s in enumerate(sp):
    oy = 8 if i % 2 == 0 else -12
    ax.annotate(f"{s:.2f}\u00d7*", (i, hx[i]),
                textcoords="offset points", xytext=(6, oy),
                fontsize=5, fontweight="bold", color=HX)

  ax.set_xticks(x)
  xlabels = []
  for k in k_vals:
    if k < 1_000:
      xlabels.append(str(k))
    elif k < 1_000_000:
      xlabels.append(f"{k//1_000}K")
    elif k < 1_000_000_000:
      xlabels.append(f"{k//1_000_000}M")
  ax.set_xticklabels(xlabels, fontsize=7)
  ax.set_xlabel("K (number of nearest neighbours to extract)")
  ax.set_ylabel("Extraction Time (ms)")
  ax.set_yscale("log")
  ax.set_title(f"KNN: Extract K Smallest from {N//1_000_000}M Distances")
  ax.legend(loc="upper left", frameon=False, fontsize=6,
            ncol=2, title="Selection Method", title_fontsize=7)
  ax.grid(axis="y", alpha=0.2, lw=0.4)

  fig.tight_layout()
  fig.subplots_adjust(bottom=0.22)
  fig.text(0.03, 0.04,
           "* Speedup values compare heapx against heapq.",
           fontsize=5.5, ha="left", va="top",
           style="italic", color="black")

  fig.savefig(FIGS / "knn_pop_k_smallest.png")
  plt.close(fig)
  print("  \u2713 knn_pop_k_smallest.png")


def plot_speedup_bar(data):
  """Item 12: add heapq bars alongside heapx speedup."""
  n_vals = data["n_vals"]
  sp = data["speedup"]

  fig, ax = plt.subplots(figsize=(5.0, 3.8))
  x = np.arange(len(n_vals))
  w = 0.35
  # heapq baseline = 1.0
  ax.bar(x - w/2, [1.0] * len(n_vals), w, color=HQ, edgecolor="black",
         lw=0.3, label="heapq (baseline = 1.0×)", zorder=3)
  ax.bar(x + w/2, sp, w, color=HX, edgecolor="black",
         lw=0.3, label="heapx (speedup)", zorder=3)
  ax.axhline(1.0, color="grey", ls="--", lw=0.6)

  for i, s in enumerate(sp):
    ax.text(i + w/2, s + 0.03, f"{s:.2f}×", ha="center", fontsize=7,
            fontweight="bold", color=HX)

  ax.set_xticks(x)
  ax.set_xticklabels([f"{n//1000}K" if n < 1e6 else f"{n//1_000_000}M"
                       for n in n_vals], fontsize=7)
  ax.set_xlabel("Distance Array Size (number of floats)")
  ax.set_ylabel("Heapify Speedup\n(heapx relative to heapq)")
  ax.set_title("KNN Heapify Speedup: heapx vs. heapq")
  ax.set_ylim(0, max(sp) * 1.35)
  ax.legend(loc="upper left", frameon=False, fontsize=7)
  ax.grid(axis="y", alpha=0.2, lw=0.4)
  fig.tight_layout()
  fig.savefig(FIGS / "knn_speedup_bar.png")
  plt.close(fig)
  print("  ✓ knn_speedup_bar.png")


def main():
  RESULTS.mkdir(parents=True, exist_ok=True)
  FIGS.mkdir(parents=True, exist_ok=True)

  print("=== ML Algorithm 1: KNN Selection Phase ===\n")
  bench_correctness()
  heapify_data = bench_heapify_distances()
  pop_data = bench_pop_k_smallest()

  out = {"heapify_dists": heapify_data, "pop_k": pop_data}
  with open(RESULTS / "knn_data.json", "w") as f:
    json.dump(out, f, indent=2)

  print("\n  Generating figures:")
  plot_heapify_dists(heapify_data)
  plot_pop_k(pop_data)
  plot_speedup_bar(heapify_data)
  print(f"\n  Done.")

if __name__ == "__main__":
  main()
