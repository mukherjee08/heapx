"""
Domain-specific bioinformatics visualization suite.

All figures: 600 DPI PNG, snug fit, centered, legends inside or in
dedicated right panel via subplots_adjust.
"""

from __future__ import annotations
import os, random
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform
from scipy.stats import gaussian_kde

from config import (
  FIG_DPI, FIG_FORMAT, FIG_DIR,
  SW_MATCH, SW_MISMATCH, SW_GAP_OPEN,
  AMINO_ACIDS, RNG_SEED, BEAM_WIDTH,
)
from seqgen import generate_dataset, _AA_FREQS

C_BLUE = "#0072B2"
C_ORANGE = "#E69F00"
C_GREEN = "#009E73"
C_RED = "#D55E00"
C_PURPLE = "#CC79A7"
C_CYAN = "#56B4E9"

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
  "lines.linewidth": 1.0,
  "lines.markersize": 4,
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


def _score(a: str, b: str) -> int:
  return SW_MATCH if a == b else SW_MISMATCH


# ===================================================================
# Fig 1: SW DP matrix
# ===================================================================
def fig01_sw_dp_matrix(fig_dir: str) -> None:
  pairs = generate_dataset(1, seed=RNG_SEED)
  q, s = pairs[0][0][:25], pairs[0][1][:25]
  m, n = len(q), len(s)

  H = np.zeros((m + 1, n + 1))
  tb = np.zeros((m + 1, n + 1), dtype=int)
  for i in range(1, m + 1):
    for j in range(1, n + 1):
      diag = H[i - 1, j - 1] + _score(q[i - 1], s[j - 1])
      up = H[i - 1, j] + SW_GAP_OPEN
      left = H[i, j - 1] + SW_GAP_OPEN
      vals = [0.0, diag, up, left]
      best = max(vals)
      H[i, j] = best
      tb[i, j] = vals.index(best)

  max_i, max_j = np.unravel_index(np.argmax(H), H.shape)
  path = [(max_i, max_j)]
  ci, cj = max_i, max_j
  while tb[ci, cj] != 0 and ci > 0 and cj > 0:
    t = tb[ci, cj]
    if t == 1: ci, cj = ci - 1, cj - 1
    elif t == 2: ci -= 1
    else: cj -= 1
    path.append((ci, cj))
  path.reverse()

  with plt.rc_context(_BASE):
    fig = plt.figure(figsize=(6.2, 5.0))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1, 0.05], wspace=0.03)
    ax = fig.add_subplot(gs[0])

    im = ax.imshow(H[1:, 1:], cmap="YlOrRd", aspect="auto",
                   interpolation="nearest", origin="upper")

    path_d = [(p[0] - 1, p[1] - 1) for p in path if p[0] > 0 and p[1] > 0]
    if path_d:
      py = [p[0] for p in path_d]
      px = [p[1] for p in path_d]
      ax.plot(px, py, color=C_BLUE, linewidth=2.2, marker="o",
              markersize=3.5, markeredgecolor="white", markeredgewidth=0.3,
              zorder=5, label="Optimal Traceback")

    ax.set_xticks(range(n))
    ax.set_xticklabels(list(s), fontfamily="monospace", fontsize=7)
    ax.set_yticks(range(m))
    ax.set_yticklabels(list(q), fontfamily="monospace", fontsize=7)
    ax.set_xlabel("Subject sequence")
    ax.set_ylabel("Query sequence")
    ax.set_title("Smith\u2013Waterman scoring matrix with Optimal Traceback")
    for spine in ax.spines.values():
      spine.set_visible(True)
      spine.set_linewidth(0.4)

    cax = fig.add_subplot(gs[1])
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label("Alignment score", fontsize=9)
    cbar.ax.tick_params(labelsize=7)
    cbar.outline.set_linewidth(0.4)

    # Place legend below colorbar using figure coordinates
    fig.legend(
      *ax.get_legend_handles_labels(),
      loc="lower right", fontsize=8, frameon=True, edgecolor="0.7",
    )

  _save(fig, fig_dir, "fig01_sw_dp_matrix")


# ===================================================================
# Fig 2: Dot plot — legend inside lower-right
# ===================================================================
def fig02_dot_plot(fig_dir: str) -> None:
  pairs = generate_dataset(1, seed=RNG_SEED)
  q, s = pairs[0][0][:100], pairs[0][1][:100]
  m, n = len(q), len(s)
  window = 3

  dots_i, dots_j = [], []
  for i in range(m - window + 1):
    for j in range(n - window + 1):
      matches = sum(1 for k in range(window) if q[i + k] == s[j + k])
      if matches >= window:
        dots_i.append(i + window // 2)
        dots_j.append(j + window // 2)

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(4.5, 4.5))

    ax.scatter(dots_j, dots_i, s=6.0, c=C_BLUE, marker="s",
               linewidths=0, alpha=0.85, zorder=3,
               label="k-mer match (k = 3)")

    diag_len = min(m, n)
    ax.plot([0, diag_len - 1], [0, diag_len - 1], color=C_RED,
            linewidth=0.8, linestyle="--", alpha=0.7,
            label="Identity Diagonal", zorder=2)

    ax.set_xlim(-2, n + 1)
    ax.set_ylim(m + 1, -2)
    ax.set_xlabel("Subject position")
    ax.set_ylabel("Query position")
    ax.set_title("Sequence dot plot (k-mer window = 3)")
    ax.set_aspect("equal")
    for spine in ax.spines.values():
      spine.set_visible(True)
      spine.set_linewidth(0.4)

    # Legend inside the plot, lower-right
    ax.legend(
      loc="lower right", fontsize=7, frameon=True, edgecolor="0.7",
      markerscale=1.5,
    )

  _save(fig, fig_dir, "fig02_dot_plot")


# ===================================================================
# Fig 3: AA frequency — legend inside upper-right
# ===================================================================
def fig03_aa_frequency(fig_dir: str) -> None:
  pairs = generate_dataset(500, seed=RNG_SEED)
  all_res = "".join(q + s for q, s in pairs)
  total = len(all_res)
  counts = Counter(all_res)
  observed = [counts.get(aa, 0) / total for aa in AMINO_ACIDS]
  expected = list(_AA_FREQS)
  x = np.arange(len(AMINO_ACIDS))
  width = 0.35

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(6.5, 3.5))

    ax.bar(x - width / 2, expected, width, label="Swiss-Prot reference",
           color=C_BLUE, edgecolor="white", linewidth=0.3)
    ax.bar(x + width / 2, observed, width, label="Synthetic dataset",
           color=C_ORANGE, edgecolor="white", linewidth=0.3)

    ax.set_xticks(x)
    ax.set_xticklabels(list(AMINO_ACIDS), fontfamily="monospace", fontsize=8)
    ax.set_xlabel("Amino acid")
    ax.set_ylabel("Relative frequency")
    ax.set_title("Amino-acid frequency: synthetic data vs. Swiss-Prot")
    ax.legend(loc="upper right", fontsize=8, frameon=True, edgecolor="0.7")
    ax.set_ylim(0, max(max(expected), max(observed)) * 1.15)

  _save(fig, fig_dir, "fig03_aa_frequency")


# ===================================================================
# Fig 4: Score distribution — legend inside upper-left
# ===================================================================
def fig04_score_distribution(fig_dir: str) -> None:
  from alignment import sw_beam_align_heapx

  pairs = generate_dataset(300, seed=RNG_SEED)
  scores = []
  for q, s in pairs:
    top = sw_beam_align_heapx(q[:120], s[:120], beam_width=100, top_k=1, arity=4)
    if top:
      scores.append(top[0])
  scores = np.array(scores)

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(5.5, 3.5))

    ax.hist(scores, bins=35, color=C_BLUE, edgecolor="white",
            linewidth=0.3, alpha=0.8, density=True, label="Empirical density")

    kde = gaussian_kde(scores)
    xs = np.linspace(scores.min() - 5, scores.max() + 5, 300)
    ax.plot(xs, kde(xs), color=C_RED, linewidth=1.3, label="KDE")

    mean_s = np.mean(scores)
    std_s = np.std(scores)
    ax.axvline(mean_s, color=C_GREEN, linewidth=1.2, linestyle="--",
               label=f"\u03bc = {mean_s:.1f}, \u03c3 = {std_s:.1f}")

    ax.set_xlabel("Top alignment score")
    ax.set_ylabel("Density")
    ax.set_title("Distribution of alignment scores (n = 300)")
    ax.legend(loc="upper left", fontsize=8, frameon=True, edgecolor="0.7")

  _save(fig, fig_dir, "fig04_score_distribution")


# ===================================================================
# Fig 5: Beam pruning — legend + stats inside upper-right
# ===================================================================
def fig05_beam_pruning(fig_dir: str) -> None:
  pairs = generate_dataset(1, seed=RNG_SEED)
  q, s = pairs[0]
  m, n = len(q), len(s)
  beam_width = 50

  total_cells, retained_cells = [], []
  prev_row = [0.0] * (n + 1)
  for i in range(1, m + 1):
    curr_row = [0.0] * (n + 1)
    positive = 0
    qi = q[i - 1]
    for j in range(1, n + 1):
      sc = max(0.0, prev_row[j - 1] + _score(qi, s[j - 1]),
               prev_row[j] + SW_GAP_OPEN, curr_row[j - 1] + SW_GAP_OPEN)
      curr_row[j] = sc
      if sc > 0: positive += 1
    total_cells.append(positive)
    retained_cells.append(min(positive, beam_width))
    prev_row = curr_row

  rows = np.arange(1, m + 1)
  total_arr = np.array(total_cells)
  retained_arr = np.array(retained_cells)
  total_sum = sum(total_cells)
  retained_sum = sum(retained_cells)
  pruned_pct = (1.0 - retained_sum / total_sum) * 100 if total_sum > 0 else 0

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(6.0, 3.5))

    ax.fill_between(rows, total_arr, alpha=0.3, color=C_RED, linewidth=0)
    ax.plot(rows, total_arr, color=C_RED, linewidth=0.7, alpha=0.8,
            label="Positive-scoring cells")
    ax.fill_between(rows, retained_arr, alpha=0.5, color=C_BLUE, linewidth=0)
    ax.plot(rows, retained_arr, color=C_BLUE, linewidth=0.8,
            label=f"Retained by beam (w = {beam_width})")

    ax.set_xlabel("Query row index")
    ax.set_ylabel("Number of cells")
    ax.set_title("Beam-search pruning: heap-bounded search space")

    # Legend inside upper-left
    ax.legend(loc="upper left", fontsize=7, frameon=True, edgecolor="0.7")

    # Stats box inside upper-right
    stats_text = (
      f"{pruned_pct:.1f}% of cells pruned\n"
      f"{total_sum:,} \u2192 {retained_sum:,}"
    )
    ax.annotate(
      stats_text,
      xy=(0.98, 0.95), xycoords="axes fraction",
      ha="right", va="top", fontsize=7,
      bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                edgecolor="0.7", alpha=0.95),
    )

  _save(fig, fig_dir, "fig05_beam_pruning")


# ===================================================================
# Fig 6: NJ dendrogram
# ===================================================================
def fig06_nj_dendrogram(fig_dir: str) -> None:
  from neighbor_joining import generate_distance_matrix

  n_taxa = 20
  dist = generate_distance_matrix(n_taxa, seed=RNG_SEED)
  dist_arr = np.array(dist)
  condensed = squareform(dist_arr)
  Z = linkage(condensed, method="average")
  labels = [f"T{i}" for i in range(n_taxa)]

  with plt.rc_context(_BASE):
    fig, ax = plt.subplots(figsize=(6.0, 3.8))

    dendrogram(Z, labels=labels, ax=ax, leaf_rotation=90,
               leaf_font_size=7, color_threshold=0,
               above_threshold_color=C_BLUE)

    ax.set_ylabel("Evolutionary distance")
    ax.set_title("Neighbor-joining phylogenetic dendrogram (20 taxa)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.4)
    ax.spines["left"].set_linewidth(0.4)
    ax.tick_params(axis="x", length=0)

  _save(fig, fig_dir, "fig06_nj_dendrogram")


# ===================================================================
def main() -> None:
  base = os.path.dirname(__file__)
  fd = _fig_dir(base)
  print(f"Generating domain-specific figures in {fd}/\n")
  fig01_sw_dp_matrix(fd)
  fig02_dot_plot(fd)
  fig03_aa_frequency(fd)
  fig04_score_distribution(fd)
  fig05_beam_pruning(fd)
  fig06_nj_dendrogram(fd)
  print("\nDomain-specific figures complete.")

if __name__ == "__main__":
  main()
