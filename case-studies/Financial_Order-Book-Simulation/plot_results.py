"""
Visualisation suite for Case Study 1: Financial Order Book Simulation.

Generates publication-quality PNG figures for the SPE paper.

Figures produced:
  1. Midprice trajectory with bid-ask spread band.
  2. Bid-ask spread distribution.
  3. Order-book depth over time (bid vs ask).
  4. Cumulative traded volume.
  5. Log-return distribution (non-zero returns only) with normal overlay.
  6. Autocorrelation of absolute returns (volatility clustering).
  7. Per-operation latency comparison (push, pop, cancel maintenance).
  8. Wall-clock speedup bar chart.
  9. Cancellation heap-maintenance cost: heapx O(log n) vs heapq O(n).
  10. Event-type distribution bar chart.

Usage:
  python plot_results.py [--sim PATH] [--bench PATH] [--outdir DIR]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

# ── Style ──────────────────────────────────────────────────────────
plt.rcParams.update({
  "figure.figsize": (6.5, 3.5),
  "figure.dpi": 300,
  "font.size": 9,
  "font.family": "serif",
  "axes.labelsize": 9,
  "axes.titlesize": 10,
  "legend.fontsize": 8,
  "xtick.labelsize": 8,
  "ytick.labelsize": 8,
  "lines.linewidth": 1.0,
  "savefig.bbox": "tight",
  "savefig.pad_inches": 0.05,
})

HEAPX_COLOR = "#2166ac"
HEAPQ_COLOR = "#b2182b"


def _save(fig: plt.Figure, outdir: Path, name: str) -> None:
  path = outdir / f"{name}.png"
  fig.savefig(path, dpi=300)
  plt.close(fig)
  print(f"  Saved {path}")


# ── Simulation figures ─────────────────────────────────────────────

def fig_midprice(df: pd.DataFrame, outdir: Path) -> None:
  """Fig 1: Midprice trajectory with spread band."""
  fig, ax = plt.subplots(figsize=(7.0, 3.5))
  valid = df.dropna(subset=["midprice"])
  t = valid["timestamp"]
  mid = valid["midprice"]
  sp = valid["spread"].fillna(0)
  ax.fill_between(t, mid - sp / 2, mid + sp / 2,
                  alpha=0.18, color=HEAPX_COLOR, label="Bid–ask spread",
                  linewidth=0)
  ax.plot(t, mid, color=HEAPX_COLOR, linewidth=0.35, label="Midprice")
  ax.set_xlabel("Simulation time (s)")
  ax.set_ylabel("Price ($)")
  ax.set_title("Simulated Midprice Trajectory (Cont–Stoikov–Talreja Model)")
  ax.legend(loc="lower right", framealpha=0.9, fontsize=7)
  ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
  ax.ticklabel_format(axis="y", style="plain")
  ax.grid(True, alpha=0.2, linewidth=0.4)
  _save(fig, outdir, "fig01_midprice")


def fig_spread_dist(df: pd.DataFrame, outdir: Path) -> None:
  """Fig 2: Spread distribution."""
  fig, ax = plt.subplots()
  sp = df["spread"].dropna()
  ax.hist(sp, bins=50, density=True, alpha=0.75, color=HEAPX_COLOR,
          edgecolor="white", linewidth=0.3)
  ax.set_xlabel("Bid–ask spread ($)")
  ax.set_ylabel("Density")
  ax.set_title("Distribution of Bid–Ask Spread")
  _save(fig, outdir, "fig02_spread_dist")


def fig_depth(df: pd.DataFrame, outdir: Path) -> None:
  """Fig 3: Order-book depth over time."""
  fig, ax = plt.subplots()
  t = df["timestamp"]
  ax.plot(t, df["bid_depth"], color=HEAPX_COLOR, linewidth=0.35,
          label="Bid depth", alpha=0.85)
  ax.plot(t, df["ask_depth"], color=HEAPQ_COLOR, linewidth=0.35,
          label="Ask depth", alpha=0.85)
  ax.set_xlabel("Simulation time (s)")
  ax.set_ylabel("Number of outstanding orders")
  ax.set_title("Order-Book Depth Over Time")
  ax.legend(framealpha=0.9)
  _save(fig, outdir, "fig03_depth")


def fig_volume(df: pd.DataFrame, outdir: Path) -> None:
  """Fig 4: Cumulative traded volume."""
  fig, ax = plt.subplots()
  ax.plot(df["timestamp"], df["cum_volume"], color=HEAPX_COLOR,
          linewidth=0.8)
  ax.set_xlabel("Simulation time (s)")
  ax.set_ylabel("Cumulative volume (shares)")
  ax.set_title("Cumulative Traded Volume")
  max_v = df["cum_volume"].max()
  if max_v >= 1e6:
    ax.yaxis.set_major_formatter(
      plt.FuncFormatter(lambda x, _: f"{x / 1e6:.1f}M"))
  elif max_v >= 1e3:
    ax.yaxis.set_major_formatter(
      plt.FuncFormatter(lambda x, _: f"{x / 1e3:.0f}K"))
  _save(fig, outdir, "fig04_volume")


def fig_returns(df: pd.DataFrame, outdir: Path) -> None:
  """Fig 5: Log-return distribution showing fat tails vs normal."""
  mid = df["midprice"].dropna().values
  log_ret = np.diff(np.log(mid))
  log_ret = log_ret[np.isfinite(log_ret)]
  nonzero = log_ret[log_ret != 0.0]
  if len(nonzero) < 10:
    return

  mu, sigma = np.mean(nonzero), np.std(nonzero)
  if sigma <= 0:
    return

  # Use log-scale y-axis so the fat tails are clearly visible.
  fig, ax = plt.subplots(figsize=(6.5, 3.8))
  clip = 4.5 * sigma
  clipped = nonzero[(nonzero > mu - clip) & (nonzero < mu + clip)]
  ax.hist(clipped, bins=120, density=True, alpha=0.7,
          color=HEAPX_COLOR, edgecolor="white", linewidth=0.15,
          label="Simulated", zorder=2)
  x = np.linspace(mu - clip, mu + clip, 500)
  normal_pdf = (1 / (sigma * np.sqrt(2 * np.pi))) * \
               np.exp(-0.5 * ((x - mu) / sigma) ** 2)
  ax.plot(x, normal_pdf, color=HEAPQ_COLOR, linewidth=1.2,
          label="Normal fit (same μ, σ)", zorder=3)
  ax.set_yscale("log")
  ax.set_xlabel("Log return (non-zero only)")
  ax.set_ylabel("Density (log scale)")
  ax.set_title("Fat Tails in Simulated Returns vs. Normal Distribution")
  ax.legend(framealpha=0.9)
  ax.grid(True, alpha=0.15, linewidth=0.3)
  _save(fig, outdir, "fig05_returns")


def fig_autocorr(df: pd.DataFrame, outdir: Path) -> None:
  """Fig 6: Autocorrelation of absolute returns."""
  mid = df["midprice"].dropna().values
  log_ret = np.diff(np.log(mid))
  log_ret = log_ret[np.isfinite(log_ret)]
  abs_ret = np.abs(log_ret)
  if len(abs_ret) < 20:
    return

  max_lag = min(500, len(abs_ret) // 4)
  mean_ar = np.mean(abs_ret)
  var_ar = np.var(abs_ret)
  if var_ar == 0:
    return
  acf = np.array([
    np.mean((abs_ret[:len(abs_ret) - lag] - mean_ar) *
            (abs_ret[lag:] - mean_ar)) / var_ar
    for lag in range(1, max_lag + 1)
  ])

  fig, ax = plt.subplots()
  ax.bar(range(1, max_lag + 1), acf, color=HEAPX_COLOR, alpha=0.6,
         width=1.0, edgecolor="none")
  ax.axhline(0, color="gray", linewidth=0.5)
  ax.set_xlabel("Lag (events)")
  ax.set_ylabel("Autocorrelation")
  ax.set_title("Autocorrelation of |Returns| (Volatility Clustering)")
  _save(fig, outdir, "fig06_autocorr")


# ── Benchmark figures ──────────────────────────────────────────────

def fig_latency_bars(bench: dict, outdir: Path) -> None:
  """Fig 7: Per-operation mean latency — grouped bars including cancel."""
  ops = ["push_ns", "pop_ns", "cancel_maintain_ns"]
  labels = ["Push\n(limit order)", "Pop\n(market order)",
            "Cancel\n(heap maint.)"]

  hx_means = [np.mean([r[op]["mean"] for r in bench["heapx"]
                        if r[op]["n"] > 0]) for op in ops]
  hq_means = [np.mean([r[op]["mean"] for r in bench["heapq"]
                        if r[op]["n"] > 0]) for op in ops]

  x = np.arange(len(labels))
  w = 0.32
  fig, ax = plt.subplots(figsize=(5.5, 3.5))
  bars_x = ax.bar(x - w / 2, hx_means, w, label="heapx",
                  color=HEAPX_COLOR, alpha=0.85, edgecolor="white")
  bars_q = ax.bar(x + w / 2, hq_means, w, label="heapq",
                  color=HEAPQ_COLOR, alpha=0.85, edgecolor="white")
  # Annotate the cancel bars with the speedup ratio.
  if hx_means[2] > 0:
    ratio = hq_means[2] / hx_means[2]
    ax.annotate(f"{ratio:.0f}×",
                xy=(x[2] - w / 2, hx_means[2]),
                xytext=(x[2] - w / 2, hq_means[2] * 0.55),
                ha="center", fontsize=8, fontweight="bold",
                color=HEAPX_COLOR,
                arrowprops=dict(arrowstyle="->", color=HEAPX_COLOR,
                                lw=0.8))
  ax.set_xticks(x)
  ax.set_xticklabels(labels)
  ax.set_ylabel("Mean latency (ns)")
  ax.set_title("Per-Operation Latency: heapx vs heapq")
  ax.legend(framealpha=0.9)
  ax.set_yscale("log")
  _save(fig, outdir, "fig07_latency_bars")


def fig_wall_speedup(bench: dict, outdir: Path) -> None:
  """Fig 8: Wall-clock speedup bar chart."""
  hx_walls = [r["wall_s"] for r in bench["heapx"]]
  hq_walls = [r["wall_s"] for r in bench["heapq"]]
  speedups = [q / x if x > 0 else 0 for x, q in zip(hx_walls, hq_walls)]

  fig, ax = plt.subplots(figsize=(4.5, 3.0))
  x = np.arange(len(speedups))
  ax.bar(x, speedups, color=HEAPX_COLOR, alpha=0.85, edgecolor="white")
  ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.6,
             label="Parity (1×)")
  mean_sp = np.mean(speedups)
  ax.axhline(mean_sp, color=HEAPX_COLOR, linestyle=":", linewidth=0.8,
             label=f"Mean {mean_sp:.2f}×")
  ax.set_xlabel("Trial")
  ax.set_ylabel("Speedup (heapq time / heapx time)")
  ax.set_title("End-to-End Wall-Clock Speedup")
  ax.set_xticks(x)
  ax.set_xticklabels([f"R{i + 1}" for i in x])
  ax.legend(fontsize=7, framealpha=0.9)
  _save(fig, outdir, "fig08_wall_speedup")


def fig_cancel_maintenance(bench: dict, outdir: Path) -> None:
  """Fig 9: Cancellation heap-maintenance cost (the key insight)."""
  key = "cancel_maintain_ns"
  hx = [r[key]["mean"] for r in bench["heapx"] if r[key]["n"] > 0]
  hq = [r[key]["mean"] for r in bench["heapq"] if r[key]["n"] > 0]
  if not hx or not hq:
    return

  fig, ax = plt.subplots(figsize=(4.5, 3.2))
  x = np.arange(len(hx))
  w = 0.32
  ax.bar(x - w / 2, hx, w, label="heapx  (remove)", color=HEAPX_COLOR,
         alpha=0.85, edgecolor="white")
  ax.bar(x + w / 2, hq, w, label="heapq  (heapify)", color=HEAPQ_COLOR,
         alpha=0.85, edgecolor="white")
  ratio = np.mean(hq) / np.mean(hx) if np.mean(hx) > 0 else 0
  ax.set_xlabel("Trial")
  ax.set_ylabel("Mean heap-maintenance cost (ns)")
  ax.set_title(
    f"Cancel Heap Maintenance: O(log n) vs O(n)  —  {ratio:.0f}× faster")
  ax.set_xticks(x)
  ax.set_xticklabels([f"R{i + 1}" for i in x])
  ax.legend(fontsize=7, framealpha=0.9)
  _save(fig, outdir, "fig09_cancel_maintenance")


def fig_event_mix(bench: dict, outdir: Path) -> None:
  """Fig 10: Event-type distribution — horizontal bar chart."""
  mix = bench["event_mix"]
  total = sum(mix.values())
  items = sorted(mix.items(), key=lambda kv: kv[1], reverse=True)
  labels = [k.replace("_", " ").title() for k, _ in items]
  pcts = [100 * v / total for _, v in items]

  fig, ax = plt.subplots(figsize=(5.0, 2.8))
  colors = [HEAPX_COLOR, "#4393c3", HEAPQ_COLOR, "#f4a582", "#92c5de"]
  y = np.arange(len(labels))
  bars = ax.barh(y, pcts, color=colors[:len(labels)], alpha=0.85,
                 edgecolor="white")
  ax.set_yticks(y)
  ax.set_yticklabels(labels)
  ax.set_xlabel("Share of total events (%)")
  ax.set_title(f"Event-Type Distribution  (n = {total:,})")
  for bar, pct in zip(bars, pcts):
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
            f"{pct:.1f}%", va="center", fontsize=7)
  ax.invert_yaxis()
  _save(fig, outdir, "fig10_event_mix")


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
  ap = argparse.ArgumentParser(description="Generate case-study figures")
  ap.add_argument("--sim", type=str, default="simulation.parquet")
  ap.add_argument("--bench", type=str, default="results.json")
  ap.add_argument("--outdir", type=str, default="figures")
  args = ap.parse_args()

  outdir = Path(args.outdir)
  outdir.mkdir(parents=True, exist_ok=True)

  sim_path = Path(args.sim)
  if sim_path.exists():
    print(f"Loading simulation data from {sim_path} ...")
    df = pd.read_parquet(sim_path)
    fig_midprice(df, outdir)
    fig_spread_dist(df, outdir)
    fig_depth(df, outdir)
    fig_volume(df, outdir)
    fig_returns(df, outdir)
    fig_autocorr(df, outdir)
  else:
    print(f"WARNING: {sim_path} not found — skipping simulation figures.")

  bench_path = Path(args.bench)
  if bench_path.exists():
    print(f"Loading benchmark data from {bench_path} ...")
    bench = json.loads(bench_path.read_text())
    fig_latency_bars(bench, outdir)
    fig_wall_speedup(bench, outdir)
    fig_cancel_maintenance(bench, outdir)
    fig_event_mix(bench, outdir)
  else:
    print(f"WARNING: {bench_path} not found — skipping benchmark figures.")

  print("\nDone.")


if __name__ == "__main__":
  main()
