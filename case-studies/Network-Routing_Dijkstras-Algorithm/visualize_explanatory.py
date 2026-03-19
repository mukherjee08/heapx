"""Generate explanatory figures for Case Study 3.

Produces:
  1. Graph structure summary (nodes vs edges, avg degree).
  2. Decrease-key rate analysis (relaxation rate vs graph size).
  3. Dijkstra wavefront from 15 most populous US cities.

Usage:
  python3 visualize_explanatory.py
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

try:
  import cartopy.crs as ccrs
  import cartopy.feature as cfeature
  HAS_CARTOPY = True
except ImportError:
  HAS_CARTOPY = False

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


def load_results():
  with open(os.path.join(RESULTS_DIR, "benchmark_results.json")) as f:
    return json.load(f)


def _fmt_nodes(x, _=None):
  if x >= 1e6:
    return f"{x / 1e6:.1f}M"
  if x >= 1e3:
    return f"{x / 1e3:.0f}K"
  return f"{x:.0f}"


# ── 1. Graph structure (issue #4: move legend right) ──────────────────────

def plot_graph_structure(results):
  data = sorted(
    [r for r in results if r["weight_type"] == "distance" and r["method"] == "heapq"],
    key=lambda r: r["num_nodes"],
  )
  sizes = [r["num_nodes"] for r in data]
  edges = [r["num_edges"] for r in data]
  avg_deg = [2 * e / n for n, e in zip(sizes, edges)]

  fig, ax1 = plt.subplots(figsize=(7, 4.5))
  c_e, c_d = "#1f77b4", "#d62728"

  ax1.plot(sizes, edges, "s-", color=c_e, linewidth=2, markersize=6,
           markeredgecolor="white", markeredgewidth=0.5, label="Edges")
  ax1.set_xlabel("Graph Size (nodes)", fontsize=11)
  ax1.set_ylabel("Number of Edges", fontsize=11, color=c_e)
  ax1.tick_params(axis="y", labelcolor=c_e)
  ax1.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt_nodes))
  ax1.yaxis.set_major_formatter(
    ticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else f"{x/1e3:.0f}K"))

  ax2 = ax1.twinx()
  ax2.plot(sizes, avg_deg, "o--", color=c_d, linewidth=2, markersize=6,
           markeredgecolor="white", markeredgewidth=0.5, label="Avg Degree")
  ax2.set_ylabel("Average Degree", fontsize=11, color=c_d)
  ax2.tick_params(axis="y", labelcolor=c_d)

  lines1, labels1 = ax1.get_legend_handles_labels()
  lines2, labels2 = ax2.get_legend_handles_labels()
  ax1.legend(lines1 + lines2, labels1 + labels2,
             loc="upper right", bbox_to_anchor=(0.75, 1.0),
             framealpha=0.9, edgecolor="gray")

  ax1.set_title("DIMACS USA Road Network: Subgraph Structure",
                fontweight="bold", fontsize=13, pad=10)
  ax1.grid(alpha=0.25, linewidth=0.5)
  ax1.set_axisbelow(True)

  fig.tight_layout()
  out = os.path.join(FIG_DIR, "graph_structure.png")
  fig.savefig(out, bbox_inches="tight")
  plt.close(fig)
  print(f"  Saved {out}")


# ── 2. Decrease-key analysis (issue #2: tighter spacing, larger fonts) ────

def plot_decrease_key_rate(results):
  fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

  for wt, marker, ls in [("distance", "o", "-"), ("time", "s", "--")]:
    hq_data = sorted(
      [r for r in results if r["weight_type"] == wt and r["method"] == "heapq"],
      key=lambda r: r["num_nodes"],
    )
    sizes = [r["num_nodes"] for r in hq_data]
    dk_rates = [r["stale_pops"] / r["num_nodes"] * 100 for r in hq_data]

    ax1.plot(sizes, dk_rates, f"{marker}{ls}", linewidth=2, markersize=6,
             markeredgecolor="white", markeredgewidth=0.5, label=f"{wt} weights")

    replace_data = sorted(
      [r for r in results if r["weight_type"] == wt and r["method"] == "heapx (replace)"],
      key=lambda r: r["num_nodes"],
    )
    if replace_data:
      r_sizes = [r["num_nodes"] for r in replace_data]
      inflation = []
      for r in replace_data:
        hq_rec = next((h for h in hq_data if h["num_nodes"] == r["num_nodes"]), None)
        if hq_rec:
          inflation.append(hq_rec["max_heap_size"] / r["max_heap_size"])
      ax2.plot(r_sizes, inflation, f"{marker}{ls}", linewidth=2, markersize=6,
               markeredgecolor="white", markeredgewidth=0.5, label=f"{wt} weights")

  ax1.set_xlabel("Graph Size (nodes)", fontsize=13)
  ax1.set_ylabel("Decrease-Key Rate (%)", fontsize=13)
  ax1.set_title("(a) Edge Relaxation Rate", fontweight="bold", fontsize=12)
  ax1.legend(fontsize=13, framealpha=0.9, edgecolor="gray")
  ax1.grid(alpha=0.25, linewidth=0.5)
  ax1.set_axisbelow(True)
  ax1.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt_nodes))

  ax2.set_xlabel("Graph Size (nodes)", fontsize=13)
  ax2.set_ylabel("Heap Inflation Ratio (lazy / bounded)", fontsize=13)
  ax2.set_title("(b) Heap Size Inflation", fontweight="bold", fontsize=12)
  ax2.axhline(y=1.0, color="#555555", linestyle="--", linewidth=1, alpha=0.5)
  ax2.legend(fontsize=13, framealpha=0.9, edgecolor="gray")
  ax2.grid(alpha=0.25, linewidth=0.5)
  ax2.set_axisbelow(True)
  ax2.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt_nodes))

  fig.suptitle(
    "Decrease-Key Analysis: Impact on Heap Behavior",
    fontweight="bold", fontsize=16,
  )
  fig.tight_layout()
  fig.subplots_adjust(top=0.88)

  out = os.path.join(FIG_DIR, "decrease_key_analysis.png")
  fig.savefig(out, bbox_inches="tight")
  plt.close(fig)
  print(f"  Saved {out}")


# ── 3. Dijkstra wavefront from 15 most populous US cities (issue #3) ──────

# Approximate lon/lat for the 15 most populous US cities (2025)
CITIES = [
  ("New York, NY",       -74.006,  40.713),
  ("Los Angeles, CA",   -118.244,  34.052),
  ("Chicago, IL",        -87.630,  41.878),
  ("Houston, TX",        -95.370,  29.760),
  ("Phoenix, AZ",       -112.074,  33.449),
  ("Philadelphia, PA",   -75.165,  39.953),
  ("San Antonio, TX",    -98.494,  29.425),
  ("San Diego, CA",     -117.161,  32.716),
  ("Dallas, TX",         -96.797,  32.777),
  ("Jacksonville, FL",   -81.656,  30.332),
  ("Austin, TX",         -97.743,  30.267),
  ("Fort Worth, TX",     -97.331,  32.755),
  ("Columbus, OH",       -82.999,  39.961),
  ("Charlotte, NC",      -80.843,  35.227),
  ("San Francisco, CA", -122.419,  37.775),
]


def _find_nearest_node(lon_arr, lat_arr, target_lon, target_lat):
  """Find the node index closest to (target_lon, target_lat)."""
  dlat = lat_arr - target_lat
  dlon = lon_arr - target_lon
  dist_sq = dlat * dlat + dlon * dlon
  return int(np.argmin(dist_sq))


def plot_dijkstra_wavefront():
  """Dijkstra wavefront from 15 most populous US cities, 1M nodes each."""
  from dimacs_loader import load_graph, extract_subgraph, load_coordinates
  from dimacs_loader import GR_DIST, CO_FILE
  from dijkstra import dijkstra_heapq

  print("  Loading full graph and coordinates...")
  n_full, off_full, tgt_full, wt_full = load_graph(GR_DIST)
  lon_full, lat_full = load_coordinates(CO_FILE)

  # Collect all nodes from all 15 city subgraphs
  all_lons = []
  all_lats = []
  all_dists = []
  city_coords = []  # (lon, lat) of nearest node for each city

  for city_name, clon, clat in CITIES:
    seed = _find_nearest_node(lon_full, lat_full, clon, clat)
    print(f"  {city_name}: seed node {seed}, extracting 1M-node subgraph...")

    sub_n, sub_off, sub_tgt, sub_wt, sub_src, old_ids = extract_subgraph(
      n_full, off_full, tgt_full, wt_full, seed=seed, max_nodes=1_000_000,
    )

    print(f"    Running Dijkstra ({sub_n:,} nodes)...")
    dist, _ = dijkstra_heapq(sub_n, sub_off, sub_tgt, sub_wt, sub_src)

    sub_lon = lon_full[old_ids]
    sub_lat = lat_full[old_ids]
    dist_arr = np.array(dist, dtype=np.float64)

    reachable = dist_arr < float("inf")
    all_lons.append(sub_lon[reachable])
    all_lats.append(sub_lat[reachable])
    all_dists.append(dist_arr[reachable])

    city_coords.append((lon_full[seed], lat_full[seed]))

  # Merge all into single arrays
  merged_lon = np.concatenate(all_lons)
  merged_lat = np.concatenate(all_lats)
  merged_dist = np.concatenate(all_dists)

  print(f"  Total points: {len(merged_lon):,}")

  # Plot
  proj = ccrs.LambertConformal(
    central_longitude=-96, central_latitude=39,
    standard_parallels=(33, 45),
  )
  extent = [-125, -66.5, 24.4, 49.5]

  fig = plt.figure(figsize=(13, 8))
  ax = fig.add_axes([0.01, 0.01, 0.85, 0.90], projection=proj)
  ax.set_extent(extent, crs=ccrs.PlateCarree())
  ax.add_feature(cfeature.STATES, linewidth=0.25, edgecolor="#aaaaaa")
  ax.add_feature(cfeature.COASTLINE, linewidth=0.4, edgecolor="#777777")
  ax.spines['geo'].set_visible(False)

  sc = ax.scatter(
    merged_lon, merged_lat,
    c=merged_dist, cmap="plasma", s=0.08, alpha=0.4,
    transform=ccrs.PlateCarree(), rasterized=True,
  )

  # Mark cities with neon green "+"
  for (clon, clat) in city_coords:
    ax.plot(
      clon, clat, marker="+", color="#39FF14",
      markersize=9, markeredgewidth=1, zorder=10,
      transform=ccrs.PlateCarree(),
    )

  cbar = plt.colorbar(sc, ax=ax, shrink=0.7, pad=0.015)
  cbar.set_label("Shortest-Path Distance from Source", fontsize=12)

  ax.set_title(
    "Dijkstra Exploration Wavefront: 15 Most Populous US Cities (1M Nodes Each)",
    fontweight="bold", fontsize=15, pad=6,
  )

  # Legend listing all 15 cities
  city_names = [c[0] for c in CITIES]
  legend_text = "Source cities (+ markers):\n" + "\n".join(
    f"  {i+1}. {name}" for i, name in enumerate(city_names)
  )
  ax.text(
    0.01, 0.01, legend_text,
    transform=ax.transAxes, fontsize=7,
    verticalalignment="bottom",
    bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9, edgecolor="gray"),
  )

  out = os.path.join(FIG_DIR, "dijkstra_wavefront.png")
  fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.04)
  plt.close(fig)
  print(f"  Saved {out}")


def main():
  results = load_results()
  print(f"Loaded {len(results)} records")

  print("\nGraph structure plot...")
  plot_graph_structure(results)

  print("\nDecrease-key analysis...")
  plot_decrease_key_rate(results)

  print("\nDijkstra wavefront (15 cities, 1M nodes each)...")
  plot_dijkstra_wavefront()

  print("\nDone.")


if __name__ == "__main__":
  main()
