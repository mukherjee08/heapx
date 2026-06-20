#!/usr/bin/env python3
"""Gap 2 -- Per-replace latency distribution (p50/p99) visualisation.

The manuscript ``main.tex`` (§7.5, line 1032) explicitly requires a
"Latency distribution (p50, p99) for individual replace operations" as
evidence for Case Study 5. ``streaming_topk.py`` already saves per-update
latencies to ``results/latency_heapx.npy`` and ``latency_heapq.npy``, and
``results/throughput.json`` carries the aggregate p50/p99 values, but no
figure in the published suite renders this distribution. This module
closes that gap with a side-by-side CDF and a kernel-density histogram
with annotated p50/p99 markers.

Why a CDF? For latency data the CDF is the canonical publication plot
(e.g., Dean & Barroso 2013, "The Tail at Scale", CACM 56:2, 74-80)
because it exposes tail behaviour (p99, p99.9) directly; histograms
obscure the long tail.

This script is read-only with respect to the streaming benchmark: it
loads ``.npy`` artefacts emitted by ``streaming_topk.py`` and produces
``fig_latency_cdf.png``.
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
HQ = "#D55E00"

plt.rcParams.update({
  "font.family": "serif", "font.size": 9,
  "axes.titlesize": 10, "axes.titleweight": "bold",
  "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
  "legend.fontsize": 8, "figure.dpi": DPI, "savefig.dpi": DPI,
  "savefig.bbox": "tight", "savefig.pad_inches": 0.1,
  "axes.spines.top": False, "axes.spines.right": False,
})


def _percentile_us(arr: np.ndarray, q: float) -> float:
  """Return the q-th percentile of ``arr`` (seconds) converted to microseconds."""
  return float(np.percentile(arr, q) * 1e6)


def plot() -> None:
  lat_hx_path = RESULTS / "latency_heapx.npy"
  lat_hq_path = RESULTS / "latency_heapq.npy"
  if not lat_hx_path.exists() or not lat_hq_path.exists():
    print("  latency_*.npy artefacts missing; run streaming_topk.py first.")
    return

  lat_hx_s = np.load(lat_hx_path)
  lat_hq_s = np.load(lat_hq_path)
  # Convert to microseconds for readability.
  lat_hx = lat_hx_s * 1e6
  lat_hq = lat_hq_s * 1e6

  fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.8, 3.2))

  # ── Panel (a): Kernel-density histogram with p50/p99 markers. ───
  # Log-spaced bins expose the long tail; clip at 0.001-100 us.
  lo = max(min(lat_hx.min(), lat_hq.min()), 1e-3)
  hi = min(max(lat_hx.max(), lat_hq.max()), 1e2)
  bins = np.logspace(np.log10(lo), np.log10(hi), 80)
  ax1.hist(lat_hx, bins=bins, alpha=0.6, color=HX, edgecolor="white",
           lw=0.1, label="heapx", density=True, zorder=3)
  ax1.hist(lat_hq, bins=bins, alpha=0.5, color=HQ, edgecolor="white",
           lw=0.1, label="heapq", density=True, zorder=3)
  ax1.set_xscale("log")
  ax1.set_xlabel(r"Per-Replace Latency ($\mu$s, log scale)")
  ax1.set_ylabel("Probability Density")
  ax1.set_title("(a) Latency Density")
  ax1.legend(loc="upper right", frameon=False, fontsize=7.5)
  ax1.grid(axis="y", alpha=0.2, lw=0.4)

  # ── Panel (b): Empirical CDF with p50/p99 markers. ──────────────
  def _cdf(x):
    xs = np.sort(x)
    ys = np.arange(1, len(xs) + 1) / len(xs)
    return xs, ys

  xs_hx, ys_hx = _cdf(lat_hx)
  xs_hq, ys_hq = _cdf(lat_hq)
  ax2.plot(xs_hx, ys_hx, color=HX, lw=1.4, label="heapx", zorder=3)
  ax2.plot(xs_hq, ys_hq, color=HQ, lw=1.4, label="heapq", zorder=3)
  ax2.set_xscale("log")

  p50_hx = _percentile_us(lat_hx_s, 50)
  p99_hx = _percentile_us(lat_hx_s, 99)
  p50_hq = _percentile_us(lat_hq_s, 50)
  p99_hq = _percentile_us(lat_hq_s, 99)

  for p, style, lbl in [(50, "--", "p50"), (99, ":", "p99")]:
    ax2.axhline(p / 100.0, color="grey", ls=style, lw=0.6, alpha=0.6)
    ax2.text(xs_hx.min() * 1.2, p / 100.0 + 0.01, lbl, fontsize=6.5,
             color="grey")

  ax2.plot([p50_hx], [0.50], "o", color=HX, ms=5, zorder=4)
  ax2.plot([p99_hx], [0.99], "o", color=HX, ms=5, zorder=4)
  ax2.plot([p50_hq], [0.50], "s", color=HQ, ms=5, zorder=4)
  ax2.plot([p99_hq], [0.99], "s", color=HQ, ms=5, zorder=4)

  ax2.annotate(f"heapx p50={p50_hx:.2f}\u00b5s\nheapx p99={p99_hx:.2f}\u00b5s",
               xy=(p99_hx, 0.99), xytext=(12, -24),
               textcoords="offset points", fontsize=6.5,
               color=HX, fontweight="bold",
               arrowprops=dict(arrowstyle="->", color=HX, lw=0.5))
  ax2.annotate(f"heapq p50={p50_hq:.2f}\u00b5s\nheapq p99={p99_hq:.2f}\u00b5s",
               xy=(p99_hq, 0.99), xytext=(12, -44),
               textcoords="offset points", fontsize=6.5,
               color=HQ, fontweight="bold",
               arrowprops=dict(arrowstyle="->", color=HQ, lw=0.5))

  ax2.set_xlabel(r"Per-Replace Latency ($\mu$s, log scale)")
  ax2.set_ylabel("Empirical CDF")
  ax2.set_title("(b) Empirical CDF with p50 / p99")
  ax2.set_ylim(0, 1.02)
  ax2.legend(loc="lower right", frameon=False, fontsize=7.5)
  ax2.grid(alpha=0.2, lw=0.4)

  fig.suptitle(
    f"Per-Replace Latency Distribution "
    f"(n = {len(lat_hx):,} replaces, K = 1{chr(44)}000)",
    fontsize=11, fontweight="bold")
  fig.tight_layout()
  fig.subplots_adjust(top=0.86, bottom=0.18)
  fig.text(0.03, 0.06,
           "* Latency per accepted heapx.replace / heapq.heapreplace call; "
           "measured with time.perf_counter_ns().",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")
  fig.text(0.03, 0.02,
           "\u2020 Source: results/latency_{heapx,heapq}.npy emitted by streaming_topk.py.",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")

  FIGS.mkdir(parents=True, exist_ok=True)
  fig.savefig(FIGS / "fig_latency_cdf.png")
  plt.close(fig)
  print(f"  \u2713 fig_latency_cdf.png  "
        f"(heapx p50={p50_hx:.2f}\u00b5s p99={p99_hx:.2f}\u00b5s | "
        f"heapq p50={p50_hq:.2f}\u00b5s p99={p99_hq:.2f}\u00b5s)")


def main() -> None:
  print("=== Gap 2: per-replace latency distribution ===")
  plot()


if __name__ == "__main__":
  main()
