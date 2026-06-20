#!/usr/bin/env python3
"""
Case Study 4 — Publication-Quality Visualizations (600 DPI)
============================================================

Generates 11 figures for the SPE paper Case Study 4.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import numpy as np

# ---------------------------------------------------------------------------
# Global style
# ---------------------------------------------------------------------------

COLORS: dict[str, str] = {
    "heapx": "#1a56db",
    "heapq": "#dc2626",
    "heapq_lazy": "#f97316",
    "sortedcontainers": "#d97706",
    "heapdict": "#7c3aed",
    "pqdict": "#059669",
    "PriorityQueue": "#be185d",
}
MARKERS: dict[str, str] = {
    "heapx": "o", "heapq": "s", "heapq_lazy": "X",
    "sortedcontainers": "^", "heapdict": "D",
    "pqdict": "v", "PriorityQueue": "P",
}
SPEEDUP_COLOR = "#047857"
THEORY_HEAPX = "#1a56db"
THEORY_HEAPQ = "#dc2626"

RC: dict = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
    "font.size": 9,
    "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.labelsize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
    "legend.fontsize": 8, "legend.framealpha": 0.9,
    "figure.dpi": 600, "savefig.dpi": 600,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.12,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.4,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "lines.linewidth": 1.3, "lines.markersize": 4.5,
}
plt.rcParams.update(RC)


def _save(fig: plt.Figure, outdir: Path, name: str) -> None:
    path = outdir / name
    fig.savefig(path)
    plt.close(fig)
    print(f"  Saved {path}")


def _fmt_throughput(x: float, _: Any) -> str:
    if x >= 1e6: return f"{x / 1e6:.1f}M"
    if x >= 1e3: return f"{x / 1e3:.0f}K"
    return f"{x:.0f}"


def _fmt_queue(x: float, _: Any) -> str:
    if x >= 1e6: return f"{x / 1e6:.0f}M"
    if x >= 1e3: return f"{x / 1e3:.0f}K"
    return f"{x:.0f}"


# ===================================================================
# FIG 01 — DO NOT CHANGE
# ===================================================================

def plot_cancel_sweep(data: list[dict], outdir: Path) -> None:
    engines = [e for e in COLORS if f"{e}_median" in data[0]]
    rates = [d["cancel_rate"] * 100 for d in data]
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    for eng in engines:
        medians = [d[f"{eng}_median"] for d in data]
        lo = [max(0, d[f"{eng}_median"] - d[f"{eng}_q1"]) for d in data]
        hi = [max(0, d[f"{eng}_q3"] - d[f"{eng}_median"]) for d in data]
        ax.errorbar(rates, medians, yerr=[lo, hi],
                     marker=MARKERS[eng], color=COLORS[eng],
                     capsize=2, capthick=0.6, label=eng, zorder=5)
    ax.set_xlabel("Cancellation Rate (%)")
    ax.set_ylabel("Throughput (events/s)")
    ax.set_title("Simulation Throughput Under Varying Cancellation Rates")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(_fmt_throughput))
    ax.legend(frameon=True, fancybox=False, edgecolor="0.85",
              loc="best", ncol=2, title="Module", title_fontsize=8)
    fig.tight_layout()
    _save(fig, outdir, "fig01_cancel_sweep.png")


# ===================================================================
# FIG 02 — Legend outside plot, single column, top-aligned
# ===================================================================

def plot_scaling(data: list[dict], outdir: Path) -> None:
    sizes = [d["queue_size"] for d in data]
    fig, ax = plt.subplots(figsize=(5.8, 3.2))
    engines = [e for e in COLORS if f"{e}_median" in data[0]]
    for eng in engines:
        medians = [d[f"{eng}_median"] for d in data]
        ax.plot(sizes, medians, marker=MARKERS[eng], color=COLORS[eng],
                label=eng, zorder=5)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Steady-State Queue Size")
    ax.set_ylabel("Throughput (events/s)")
    ax.set_title("Throughput Scaling with Pending Event Set Size")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt_queue))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(_fmt_throughput))
    # Legend outside plot, top-right, single column, top-aligned with axes
    ax.legend(frameon=True, fancybox=False, edgecolor="0.85",
              loc="upper left", bbox_to_anchor=(1.02, 1.0),
              ncol=1, title="Module", title_fontsize=8,
              borderaxespad=0)
    fig.tight_layout(rect=[0, 0, 0.78, 1])
    _save(fig, outdir, "fig02_scaling.png")


# ===================================================================
# FIG 03 — Footer note: left-aligned, closer to x-axis, black, *Please note
# ===================================================================

def plot_speedup_cancel(data: list[dict], outdir: Path) -> None:
    rates = [d["cancel_rate"] * 100 for d in data]
    speedup = [d["heapx_median"] / max(d["heapq_median"], 1) for d in data]
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    w = 4.0 if len(rates) <= 8 else 3.0
    bars = ax.bar(rates, speedup, width=w, color=SPEEDUP_COLOR,
                  alpha=0.85, edgecolor="white", linewidth=0.4)
    ax.axhline(1.0, color="0.6", ls="--", lw=0.6, zorder=1)
    ax.set_xlabel("Cancellation Rate (%)")
    ax.set_ylabel("Speedup (heapx / heapq)")
    ax.set_title("Relative Speedup as a Function of Cancellation Rate")
    ymax = max(speedup) * 1.18
    ax.set_ylim(0, ymax)
    for bar, s in zip(bars, speedup):
        ax.text(bar.get_x() + bar.get_width() / 2, s + ymax * 0.015,
                f"{s:.0f}×", ha="center", va="bottom", fontsize=6.5,
                fontweight="bold")
    fig.text(0.04, 0.01,
             "*Please note: heapq uses O(n) re-heapify per cancel; "
             "heapx uses O(log n) index-based remove. "
             "Gap grows with queue size (n ≈ 250 K).",
             ha="left", va="bottom", fontsize=6, color="black",
             style="italic")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, outdir, "fig03_speedup_cancel.png")


# ===================================================================
# FIG 04 — DO NOT CHANGE
# ===================================================================

def plot_speedup_scaling(data: list[dict], outdir: Path) -> None:
    sizes = [d["queue_size"] for d in data]
    speedup = [d["heapx_median"] / max(d["heapq_median"], 1) for d in data]
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    ax.plot(sizes, speedup, marker="D", ms=5, lw=1.5,
            color=SPEEDUP_COLOR, zorder=5)
    ax.axhline(1.0, color="0.6", ls="--", lw=0.6, zorder=1)
    ax.set_xscale("log")
    ax.set_xlabel("Steady-State Queue Size")
    ax.set_ylabel("Speedup (heapx / heapq)")
    ax.set_title("Relative Speedup as a Function of Queue Size")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt_queue))
    ymax = max(speedup) * 1.22
    ax.set_ylim(bottom=0, top=ymax)
    for s_val, sp in zip(sizes, speedup):
        ax.annotate(f"{sp:,.0f}×", (s_val, sp),
                    textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=7, fontweight="bold")
    fig.tight_layout()
    _save(fig, outdir, "fig04_speedup_scaling.png")


# ===================================================================
# FIG 05 — Legend font size +2
# ===================================================================

def plot_latency_bars(data: dict, outdir: Path) -> None:
    ops = ["push", "pop", "remove", "replace"]
    engines = [e for e in COLORS if e in data]
    n_eng = len(engines)
    x = np.arange(len(ops))
    w = 0.72 / n_eng
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    for ei, eng in enumerate(engines):
        vals = [data[eng].get(op, 0) for op in ops]
        offset = (ei - (n_eng - 1) / 2) * w
        bars = ax.bar(x + offset, vals, w * 0.92, color=COLORS[eng],
                      label=eng, edgecolor="white", linewidth=0.3)
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                if h >= 1e6:   lbl = f"{h / 1e6:.1f}M"
                elif h >= 1e3: lbl = f"{h / 1e3:.0f}K"
                else:          lbl = f"{h:.0f}"
                y_pos = h * 1.3 if h < 1e5 else h * 1.15
                ax.text(bar.get_x() + bar.get_width() / 2, y_pos,
                        lbl, ha="center", va="bottom", fontsize=5,
                        fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([op.capitalize() for op in ops])
    ax.set_xlabel("Heap Operation")
    ax.set_ylabel("Latency per Operation (ns)")
    ax.set_title("Per-Operation Latency Across Priority Queue Implementations")
    ax.set_yscale("log")
    ax.set_ylim(top=ax.get_ylim()[1] * 15)
    ax.legend(frameon=True, fancybox=False, edgecolor="0.85",
              loc="upper left", ncol=2, fontsize=10, title="Module",
              title_fontsize=10)
    fig.tight_layout()
    _save(fig, outdir, "fig05_latency_bars.png")


# ===================================================================
# FIG 06 — Vertical line at benchmark queue size
# ===================================================================

def plot_complexity(outdir: Path, latency: dict | None = None) -> None:
    n = np.logspace(2, 6, 300)
    log_n = np.log2(n) / np.log2(n[0])
    lin_n = n / n[0]
    q_bench = 250_000

    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    ax.plot(n, log_n, lw=2, color=THEORY_HEAPX,
            label=r"heapx remove/replace: $O(\log\,n)$")
    ax.plot(n, lin_n, lw=2, ls="--", color=THEORY_HEAPQ,
            label=r"heapq cancel (scan + re-heapify): $O(n)$")

    # Vertical line at benchmark queue size
    ax.axvline(q_bench, color="0.4", ls=":", lw=0.8, zorder=1)

    if latency and "heapx" in latency and "heapq" in latency:
        heapx_rm = latency["heapx"].get("remove", 0)
        heapq_rm = latency["heapq"].get("remove", 0)
        if heapx_rm > 0 and heapq_rm > 0:
            ax.scatter([q_bench], [np.log2(q_bench) / np.log2(100)], s=50,
                       color=THEORY_HEAPX, zorder=10, marker="*",
                       label=f"heapx measured ({heapx_rm:.0f} ns)")
            ax.scatter([q_bench], [q_bench / 100], s=50, color=THEORY_HEAPQ,
                       zorder=10, marker="*",
                       label=f"heapq measured ({heapq_rm:.0f} ns)")

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Queue Size ($n$)")
    ax.set_ylabel("Relative Cost (normalized)")
    ax.set_title("Asymptotic Cost of Event Cancellation and Rescheduling")

    # Add benchmark queue size to x-axis ticks
    xticks = [1e2, 1e3, 1e4, 1e5, 1e6]
    xticklabels = ["$10^2$", "$10^3$", "$10^4$", "$10^5$", "$10^6$"]
    xticks.insert(4, q_bench)
    xticklabels.insert(4, "250K")
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels)
    ax.xaxis.set_minor_locator(ticker.NullLocator())
    ax.yaxis.set_minor_locator(ticker.NullLocator())

    ax.legend(frameon=True, fancybox=False, edgecolor="0.85", fontsize=7)
    fig.tight_layout()
    _save(fig, outdir, "fig06_complexity.png")



# ===================================================================
# FIG 07 — Full lifecycle: warm start → steady state → drain to 0
# ===================================================================

def plot_queue_evolution(trace: dict, outdir: Path) -> None:
    """Render the full DES lifecycle: buildup → steady-state → drain.

    The three-phase decomposition is grounded in the priority-queue
    benchmarking literature: the buildup phase corresponds to the
    transient regime of the Up/Down model (Rönngren & Ayani 1993);
    the steady-state phase is the Classic Hold model (Jones 1986);
    the drain phase captures the tail behaviour when arrivals cease.
    """
    sizes_raw = np.array(trace["queue_sizes"], dtype=float)
    pb = trace.get("phase_boundaries") or {}
    n_all = len(sizes_raw)
    b_end = int(pb.get("buildup_end_idx", 0))
    s_end = int(pb.get("steady_end_idx", n_all))

    # The raw sim_time series is non-monotone across phase boundaries
    # (buildup timestamps reach ~n·λ⁻¹ but the steady phase begins by
    # popping t=t₀ ≈ 0), so we re-index onto a single monotonically
    # increasing virtual-time axis.  Each phase occupies a contiguous
    # x-interval whose width is proportional to the number of events
    # generated in that phase — preserving the reader's intuition that
    # all three phases together trace out the simulation's entire life.
    times_raw = np.array(trace["sim_times"], dtype=float)
    steady_duration = float(max(
      times_raw[b_end:s_end].max() - times_raw[b_end:s_end].min()
      if s_end > b_end else 1.0, 1.0,
    ))
    drain_duration = float(max(
      times_raw[s_end:].max() - times_raw[s_end:].min()
      if n_all > s_end else 1.0, 1.0,
    ))
    # Buildup is allocated a window proportional to its event count
    # relative to the steady phase's event density.
    buildup_width = (steady_duration * b_end / max(s_end - b_end, 1)) \
      if b_end > 0 else 0.0

    t = np.empty(n_all, dtype=float)
    if b_end > 0:
      t[:b_end] = np.linspace(0.0, buildup_width, b_end, endpoint=False)
    if s_end > b_end:
      off = buildup_width
      seg = times_raw[b_end:s_end]
      t[b_end:s_end] = off + (seg - seg[0])
    if n_all > s_end:
      off = buildup_width + steady_duration
      seg = times_raw[s_end:]
      t[s_end:] = off + (seg - seg[0])

    # Down-sample per phase to keep buildup's near-vertical rise crisp.
    def _ds(lo: int, hi: int, target: int) -> np.ndarray:
      if hi <= lo:
        return np.array([], dtype=int)
      step = max(1, (hi - lo) // max(1, target))
      idx = np.arange(lo, hi, step)
      if idx[-1] != hi - 1:
        idx = np.append(idx, hi - 1)
      return idx

    idx = np.concatenate([
      _ds(0, b_end, 600),
      _ds(b_end, s_end, 1800),
      _ds(s_end, n_all, 600),
    ]) if b_end > 0 else _ds(0, n_all, 3000)
    t_ds = t[idx]
    s_ds = sizes_raw[idx]
    max_q = float(np.max(sizes_raw))

    t_buildup_end = buildup_width
    t_drain_start = buildup_width + steady_duration
    t_end = buildup_width + steady_duration + drain_duration

    fig, ax = plt.subplots(figsize=(7.2, 3.6))

    # Phase shading -----------------------------------------------------
    ax.axvspan(0.0, t_buildup_end, alpha=0.07, color="#059669", zorder=0)
    ax.axvspan(t_buildup_end, t_drain_start, alpha=0.06, color="#1a56db",
               zorder=0)
    ax.axvspan(t_drain_start, t_end, alpha=0.06, color="#dc2626", zorder=0)

    # Queue-size curve --------------------------------------------------
    ax.fill_between(t_ds, s_ds, alpha=0.18, color=COLORS["heapx"], linewidth=0)
    ax.plot(t_ds, s_ds, lw=0.9, color=COLORS["heapx"])

    # Vertical phase separators ----------------------------------------
    ax.axvline(t_buildup_end, color="0.4", ls="--", lw=0.6)
    ax.axvline(t_drain_start, color="0.4", ls="--", lw=0.6)

    # Phase labels (pure text — no arrow, no leader) --------------------
    y_lbl = max_q * 1.08
    mid_build = t_buildup_end / 2
    mid_ss = (t_buildup_end + t_drain_start) / 2
    mid_drain = (t_drain_start + t_end) / 2
    ax.text(mid_build, y_lbl,
            "Buildup Phase\n(push only, PES grows 0 → n)",
            fontsize=7, ha="center", va="bottom", color="#059669",
            fontweight="bold", linespacing=1.25)
    ax.text(mid_ss, y_lbl,
            "Steady-State Phase\n(pop + push + cancel + resched)",
            fontsize=7, ha="center", va="bottom", color="#1a56db",
            fontweight="bold", linespacing=1.25)
    ax.text(mid_drain, y_lbl,
            "Drain Phase\n(pop only, no new events)",
            fontsize=7, ha="center", va="bottom", color="#dc2626",
            fontweight="bold", linespacing=1.25)

    ax.set_xlabel("Simulation Time (virtual)")
    ax.set_ylabel("Pending Event Set Size")
    ax.set_title("Pending Event Set Size Over Simulation Time")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(_fmt_queue))
    # Extra headroom so the phase labels do not collide with the curve.
    ax.set_ylim(bottom=0, top=max_q * 1.32)
    ax.set_xlim(0.0, t_end)
    fig.tight_layout()
    _save(fig, outdir, "fig07_queue_evolution.png")


# ===================================================================
# FIG 08 — Fixed label positioning, tighter vertical spacing
# ===================================================================

def plot_operation_mix(trace: dict, outdir: Path) -> None:
    # Only the four canonical ops enter the mix figure; buildup-phase
    # "init_push" events are excluded so this figure continues to depict
    # the Classic Hold operation distribution.
    canonical_ops = {"pop", "push", "cancel", "resched"}
    counts = Counter(
      o for o in trace["op_types"] if o in canonical_ops
    )
    labels = ["Pop (dequeue)", "Push (enqueue)", "Cancel (remove)",
              "Reschedule (replace)"]
    keys = ["pop", "push", "cancel", "resched"]
    vals = [counts.get(k, 0) for k in keys]
    colors_pie = ["#3b82f6", "#22c55e", "#ef4444", "#f59e0b"]
    total = sum(vals)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.2, 3.0),
                                    gridspec_kw={"width_ratios": [1, 1.2]})
    fig.suptitle("Heap Operation Mix (Proportional Distribution + Absolute Counts)",
                 fontsize=10, fontweight="bold", y=0.96)

    explode = [0.02 if v / total > 0.05 else 0.06 for v in vals]
    wedges, texts, autotexts = ax1.pie(
        vals, labels=None, autopct=lambda p: f"{p:.1f}%" if p > 4 else "",
        startangle=90, colors=colors_pie, pctdistance=0.72,
        explode=explode,
        wedgeprops={"linewidth": 0.5, "edgecolor": "white"})
    for t in autotexts:
        t.set_fontsize(7)

    # Label small slices with shorter leader lines
    for i, (k, v) in enumerate(zip(keys, vals)):
        pct = v / total * 100
        if pct <= 4:
            ang = (wedges[i].theta2 + wedges[i].theta1) / 2
            x_pt = 1.2 * np.cos(np.radians(ang))
            y_pt = 1.2 * np.sin(np.radians(ang))
            ax1.annotate(
                f"{pct:.1f}%",
                xy=(0.9 * np.cos(np.radians(ang)),
                    0.9 * np.sin(np.radians(ang))),
                xytext=(x_pt, y_pt), fontsize=6.5, ha="center", va="center",
                arrowprops=dict(arrowstyle="-", color="0.4", lw=0.5))

    ax1.set_title("Proportional Distribution", fontsize=9, fontweight="bold",
                  pad=2)
    ax1.legend(wedges, labels, loc="lower center", fontsize=6,
               bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)

    # Stacked bar
    bottom = 0
    for k, lbl, v, c in zip(keys, labels, vals, colors_pie):
        ax2.barh(0, v, left=bottom, height=0.5, color=c, edgecolor="white",
                 linewidth=0.5, label=lbl)
        pct = v / total
        if pct > 0.05:
            ax2.text(bottom + v / 2, 0, f"{v:,}\n({pct:.0%})",
                     ha="center", va="center", fontsize=6.5, fontweight="bold")
        else:
            # Leader-line annotation: place the label ABOVE the bar so it
            # never collides with the x-axis label below.
            ax2.annotate(
              f"{v:,}\n({pct:.1%})",
              xy=(bottom + v / 2, 0.25),
              xytext=(bottom + v / 2, 0.75),
              ha="center", va="bottom", fontsize=5.5, fontweight="bold",
              color="0.25",
              arrowprops=dict(arrowstyle="-", color="0.45", lw=0.5),
            )
        bottom += v
    ax2.set_xlim(0, total)
    ax2.set_ylim(-0.5, 1.1)
    ax2.set_yticks([])
    ax2.set_xlabel("Number of Operations")
    ax2.set_title("Absolute Counts", fontsize=9, fontweight="bold", pad=2)
    ax2.xaxis.set_major_formatter(ticker.FuncFormatter(
        lambda x, _: f"{x / 1e3:.0f}K" if x >= 1e3 else f"{x:.0f}"))

    fig.subplots_adjust(top=0.84, bottom=0.18, left=0.05, right=0.98,
                        wspace=0.15)
    _save(fig, outdir, "fig08_operation_mix.png")


# ===================================================================
# FIG 09 — Inter-arrival time distribution (unchanged)
# ===================================================================

def plot_inter_arrival(trace: dict, outdir: Path) -> None:
    times = np.array(trace["sim_times"])
    ops = trace["op_types"]
    pop_times = [times[i] for i in range(len(ops)) if ops[i] == "pop"]
    if len(pop_times) < 2:
        return
    iat = np.diff(pop_times)
    iat = iat[iat > 0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.0, 3.2))
    fig.suptitle("Inter-Event Time Distribution (PDF + CDF with Exponential Fit)",
                 fontsize=10, fontweight="bold", y=0.96)

    ax1.hist(iat, bins=80, density=True, color=COLORS["heapx"],
             alpha=0.7, edgecolor="white", linewidth=0.3)
    lam = 1.0 / np.mean(iat)
    x_th = np.linspace(0, np.percentile(iat, 99), 200)
    ax1.plot(x_th, lam * np.exp(-lam * x_th), "r-", lw=1.2,
             label=f"Exp(λ={lam:.2f})")
    ax1.set_xlabel("Inter-Arrival Time")
    ax1.set_ylabel("Density")
    ax1.set_title("Probability Density", fontsize=9, fontweight="bold",
                  pad=2)
    ax1.legend(frameon=True, fancybox=False, edgecolor="0.85", fontsize=7)

    sorted_iat = np.sort(iat)
    cdf = np.arange(1, len(sorted_iat) + 1) / len(sorted_iat)
    step = max(1, len(sorted_iat) // 1000)
    ax2.plot(sorted_iat[::step], cdf[::step], lw=1.0,
             color=COLORS["heapx"], label="Empirical CDF")
    ax2.plot(x_th, 1 - np.exp(-lam * x_th), "r--", lw=1.0,
             label="Theoretical CDF")
    ax2.set_xlabel("Inter-Arrival Time")
    ax2.set_ylabel("Cumulative Probability")
    ax2.set_title("Cumulative Distribution", fontsize=9, fontweight="bold",
                  pad=2)
    ax2.legend(frameon=True, fancybox=False, edgecolor="0.85", fontsize=7)

    fig.subplots_adjust(top=0.84, bottom=0.15, left=0.1, right=0.97,
                        wspace=0.3)
    _save(fig, outdir, "fig09_inter_arrival.png")



# ===================================================================
# FIG 10 — NEW: DES Event Lifecycle Timeline
# Replaces the old architecture box diagram with a concrete,
# intuitive visualization showing how a DES processes events
# over time — what happens at each step of the simulation loop.
# ===================================================================

def plot_des_architecture(outdir: Path) -> None:
    """Non-expert friendly illustration of a discrete-event simulation.

    The figure tells a self-contained story in three visually
    separated layers:

    1. *Top layer* A horizontal wall-clock with five concrete events
       (t = 1.2, 2.8, 4.3, 5.9, 7.1).  A "Now" arrow sits at t = 1.2
       to make clear the simulation is event-driven: the clock jumps
       from one event to the next rather than ticking uniformly.
    2. *Middle layer* The "pending event set", drawn as a sorted list
       whose first cell is highlighted as the next-to-process event.
       The heap metaphor (heapx keeps the list sorted in O(log n))
       is stated plainly inside the box.
    3. *Bottom layer* Three labelled callout cards, each with a plain-
       English description of the corresponding heapx operation
       (process / schedule / cancel / reschedule), so the reader can
       see exactly how the pending event set is manipulated as the
       simulation advances.

    The design avoids jargon, abstract boxes, and crossing arrows; a
    reader who has never heard of DES can parse the figure left-to-
    right, top-to-bottom and understand the mechanics in about ten
    seconds.
    """
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("How a Discrete-Event Simulation Processes Events Over Time",
                 fontsize=11, fontweight="bold", pad=6)

    C_CLOCK = "#475569"
    C_PES = "#d97706"
    C_PROC = "#047857"
    C_SCHED = "#1a56db"
    C_CANCEL = "#dc2626"
    C_RESCHED = "#7c3aed"
    C_TEXT = "#1e3a5f"

    # --------------------------------------------------------------
    # Layer 1 (top): horizontal wall-clock with five concrete events
    # --------------------------------------------------------------
    y_axis = 8.2
    ax.annotate("", xy=(13.2, y_axis), xytext=(0.8, y_axis),
                arrowprops=dict(arrowstyle="->", color=C_CLOCK, lw=1.4))
    ax.text(13.4, y_axis, "time", ha="left", va="center",
            fontsize=8, color=C_CLOCK, style="italic")
    event_ts = [1.2, 2.8, 4.3, 5.9, 7.1]
    event_x = [1.8, 4.1, 6.4, 8.7, 11.0]
    for tx, t in zip(event_x, event_ts):
      ax.plot([tx, tx], [y_axis - 0.18, y_axis + 0.18], color=C_CLOCK,
              lw=1.2)
      ax.text(tx, y_axis + 0.38, f"t = {t}", ha="center", va="bottom",
              fontsize=7.5, color=C_CLOCK, fontweight="bold")
      ax.plot(tx, y_axis, marker="o", color=C_PES, ms=6.5,
              markeredgecolor="white", mew=0.8, zorder=5)
    # "Now" pointer at the first event
    ax.annotate("", xy=(event_x[0], y_axis - 0.45),
                xytext=(event_x[0], y_axis - 1.2),
                arrowprops=dict(arrowstyle="->", color=C_PROC, lw=1.6))
    ax.text(event_x[0], y_axis - 1.45, "Now", ha="center", va="top",
            fontsize=8.5, color=C_PROC, fontweight="bold")
    ax.text(13.1, y_axis - 1.0,
            "the clock jumps\nfrom event\nto event",
            ha="right", va="top", fontsize=7, color=C_CLOCK,
            style="italic", linespacing=1.3)

    # --------------------------------------------------------------
    # Layer 2 (middle): the pending event set as a sorted ordered list
    # --------------------------------------------------------------
    y_pes = 5.3
    pes_box = mpatches.FancyBboxPatch(
      (0.8, y_pes - 0.75), 12.4, 1.8, boxstyle="round,pad=0.12",
      facecolor="#fffbeb", edgecolor=C_PES, lw=1.4, zorder=2,
    )
    ax.add_patch(pes_box)
    ax.text(7.0, y_pes + 0.9,
            "Pending Event Set (heapx keeps it sorted in O(log n))",
            ha="center", va="bottom", fontsize=9, fontweight="bold",
            color=C_PES)
    # Cells: next-up (highlighted green) then the rest.
    cell_ts = event_ts[:]
    cell_x = [2.2, 4.3, 6.4, 8.5, 10.6]
    cell_w, cell_h = 1.7, 0.95
    for i, (cx, t) in enumerate(zip(cell_x, cell_ts)):
      fc = "#dcfce7" if i == 0 else "white"
      ec = C_PROC if i == 0 else C_PES
      lw = 1.5 if i == 0 else 0.9
      cell = mpatches.FancyBboxPatch(
        (cx - cell_w / 2, y_pes - cell_h / 2), cell_w, cell_h,
        boxstyle="round,pad=0.05", facecolor=fc, edgecolor=ec, lw=lw,
        zorder=3,
      )
      ax.add_patch(cell)
      ax.text(cx, y_pes + 0.06, f"t = {t}", ha="center", va="center",
              fontsize=8, fontweight="bold", color=C_TEXT)
      ax.text(cx, y_pes - 0.28, f"event {chr(ord('A') + i)}",
              ha="center", va="center", fontsize=6.8, color="0.35",
              style="italic")
      if i < len(cell_x) - 1:
        ax.annotate("", xy=(cell_x[i + 1] - cell_w / 2 - 0.05, y_pes),
                    xytext=(cx + cell_w / 2 + 0.05, y_pes),
                    arrowprops=dict(arrowstyle="->", color="0.55",
                                     lw=0.9))
    # Ellipsis cell: more events to the right.
    ax.text(12.4, y_pes, "...", ha="center", va="center",
            fontsize=14, color="0.5")
    # Highlight pointer on the next-up cell.
    ax.annotate("next to\nprocess", xy=(cell_x[0], y_pes + cell_h / 2 + 0.02),
                xytext=(cell_x[0], y_pes + cell_h / 2 + 0.6),
                ha="center", va="bottom", fontsize=7, color=C_PROC,
                fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=C_PROC, lw=0.9),
                linespacing=1.25)

    # --------------------------------------------------------------
    # Layer 3 (bottom): four plain-English operation cards
    # --------------------------------------------------------------
    y_ops = 1.9
    cards = [
      ("Process", "pop the earliest event\nadvance the clock",
       C_PROC),
      ("Schedule", "add a new future event\ninserted in order",
       C_SCHED),
      ("Cancel", "drop a pending event\n(no longer needed)",
       C_CANCEL),
      ("Reschedule", "change an event's time\n(shift it in place)",
       C_RESCHED),
    ]
    card_w, card_h = 2.9, 1.7
    card_x = [1.9, 5.0, 8.1, 11.2]
    for (cx, (title, desc, col)) in zip(card_x, cards):
      card = mpatches.FancyBboxPatch(
        (cx - card_w / 2, y_ops - card_h / 2), card_w, card_h,
        boxstyle="round,pad=0.1", facecolor=col, edgecolor=col, lw=1.1,
        zorder=3,
      )
      ax.add_patch(card)
      ax.text(cx, y_ops + 0.38, title, ha="center", va="center",
              fontsize=9.5, fontweight="bold", color="white", zorder=4)
      ax.text(cx, y_ops - 0.25, desc, ha="center", va="center",
              fontsize=7.5, color="white", zorder=4, linespacing=1.3)
      # Arrow from PES down to the card.
      ax.annotate("", xy=(cx, y_ops + card_h / 2 + 0.05),
                  xytext=(cx, y_pes - 0.55),
                  arrowprops=dict(arrowstyle="->", color=col, lw=1.0,
                                   alpha=0.55))

    # Footer one-liner.
    ax.text(7.0, 0.35,
            "Every operation that touches the Pending Event Set runs in "
            "O(log n) time with heapx; heapq degrades cancel and "
            "reschedule to O(n).",
            ha="center", va="center", fontsize=7.8, color="0.3",
            style="italic")

    fig.tight_layout()
    _save(fig, outdir, "fig10_des_architecture.png")


# ===================================================================
# FIG 11 — NEW: End-to-End DES Execution Time (all modules)
# ===================================================================

def plot_e2e_timing(e2e_data: dict, e2e_params: dict, outdir: Path) -> None:
    """Horizontal bar chart of wall-clock time for a complete DES run
    across all 7 priority-queue modules."""

    engines = list(COLORS.keys())
    engines_present = [e for e in engines if e in e2e_data]
    times = [e2e_data[e]["elapsed_s"] for e in engines_present]

    # Sort by time (fastest first)
    order = np.argsort(times)
    engines_sorted = [engines_present[i] for i in order]
    times_sorted = [times[i] for i in order]
    colors_sorted = [COLORS[e] for e in engines_sorted]

    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    y = np.arange(len(engines_sorted))
    bars = ax.barh(y, times_sorted, height=0.6, color=colors_sorted,
                   edgecolor="white", linewidth=0.4)

    # Labels on bars
    max_t = max(times_sorted)
    for bar, t, eng in zip(bars, times_sorted, engines_sorted):
        if t < max_t * 0.3:
            ax.text(t + max_t * 0.015, bar.get_y() + bar.get_height() / 2,
                    f"{t:.2f}s" if t < 1 else f"{t:.1f}s",
                    ha="left", va="center", fontsize=7, fontweight="bold")
        else:
            ax.text(t - max_t * 0.015, bar.get_y() + bar.get_height() / 2,
                    f"{t:.1f}s", ha="right", va="center", fontsize=7,
                    fontweight="bold", color="white")

    ax.set_yticks(y)
    ax.set_yticklabels(engines_sorted, fontsize=8)
    ax.set_xlabel("Wall-Clock Time (seconds)")
    ax.set_title("End-to-End DES Execution Time by Priority Queue Module")
    ax.invert_yaxis()

    # Standardised footnote (same style as fig03).  The workload
    # parameters are given first, followed by a concise operational
    # definition of each term so the figure is self-contained.
    n_ev = e2e_params.get("n_events", 0)
    qs = e2e_params.get("queue_size", 0)
    cr = e2e_params.get("cancel_rate", 0)
    fig.text(
      0.04, 0.01,
      f"*Please note: Workload {n_ev:,} events, queue \u2248 {qs:,}, "
      f"cancel = {cr:.0%}.  Workload is the number of Classic-Hold "
      f"iterations (pop + push, plus probabilistic cancel/resched); "
      f"the queue exceeds the workload because the PES is warm-started "
      f"with {qs:,} pending events before the loop begins.  "
      f"Cancel = {cr:.0%} is the per-iteration cancellation probability "
      f"(Jones 1986; R\u00f6nngren & Ayani 1997), a standard stress point "
      f"at which heapq's O(n) re-heapify cost becomes dominant.",
      ha="left", va="bottom", fontsize=6, color="black", style="italic",
      wrap=True,
    )

    fig.tight_layout(rect=[0, 0.11, 1, 1])
    _save(fig, outdir, "fig11_e2e_timing.png")


# ===================================================================
# CLI
# ===================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description="CS4: Generate figures")
    ap.add_argument("--bench", type=str, default="bench_results.json")
    ap.add_argument("--outdir", type=str, default="figures")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with open(args.bench) as f:
        bench = json.load(f)

    print("Generating figures...")
    plot_cancel_sweep(bench["cancel_sweep"], outdir)
    plot_scaling(bench["scaling"], outdir)
    plot_speedup_cancel(bench["cancel_sweep"], outdir)
    plot_speedup_scaling(bench["scaling"], outdir)
    plot_latency_bars(bench["latency"], outdir)
    plot_complexity(outdir, latency=bench.get("latency"))
    plot_queue_evolution(bench["trace"], outdir)
    plot_operation_mix(bench["trace"], outdir)
    plot_inter_arrival(bench["trace"], outdir)
    plot_des_architecture(outdir)
    if "e2e_timing" in bench:
        plot_e2e_timing(bench["e2e_timing"], bench.get("e2e_params", {}), outdir)
    print("All figures generated.")


if __name__ == "__main__":
    main()
