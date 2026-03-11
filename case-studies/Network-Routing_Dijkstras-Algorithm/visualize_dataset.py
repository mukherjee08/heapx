"""Visualize the DIMACS USA road-network dataset."""
from __future__ import annotations
import argparse, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

try:
  import cartopy.crs as ccrs
  import cartopy.feature as cfeature
  HAS_CARTOPY = True
except ImportError:
  HAS_CARTOPY = False

from dimacs_loader import load_coordinates, load_graph, CO_FILE, GR_DIST, GR_TIME

FIG_DIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIG_DIR, exist_ok=True)

PROJ = ccrs.LambertConformal(central_longitude=-96, central_latitude=39,
                              standard_parallels=(33, 45))
DATA_CRS = ccrs.PlateCarree()
EXTENT = [-125, -66.5, 24.4, 49.5]
DPI = 400


def _truncate_cmap(name, lo=0.2, hi=1.0, n=256):
  base = plt.cm.get_cmap(name, n)
  return mcolors.LinearSegmentedColormap.from_list(
    f"{name}_d", base(np.linspace(lo, hi, n)), n)


def plot_coordinates(lon, lat, sample=None):
  if sample and sample < len(lon):
    idx = np.random.default_rng(42).choice(len(lon), sample, replace=False)
    lon, lat = lon[idx], lat[idx]
  fig = plt.figure(figsize=(14, 9))
  ax = fig.add_axes([0.01, 0.0, 0.98, 0.95], projection=PROJ)
  ax.set_extent(EXTENT, crs=DATA_CRS)
  ax.add_feature(cfeature.STATES, linewidth=0.2, edgecolor="#aaaaaa")
  ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor="#777777")
  ax.spines['geo'].set_visible(False)
  projected = PROJ.transform_points(DATA_CRS, lon, lat)
  px, py = projected[:, 0], projected[:, 1]
  v = np.isfinite(px) & np.isfinite(py)
  ax.hexbin(px[v], py[v], gridsize=800, cmap="Blues", mincnt=1,
            norm=mcolors.LogNorm(vmin=1), linewidths=0)
  ax.set_title(f"DIMACS 9th Challenge: USA Road Network ({len(lon):,} Nodes)",
               fontweight="bold", fontsize=18, pad=4)
  out = os.path.join(FIG_DIR, "usa_road_network_nodes.png")
  fig.savefig(out, dpi=DPI, bbox_inches="tight", pad_inches=0.02)
  plt.close(fig)
  print(f"  Saved {out}")


def plot_edge_density(lon, lat, n, offsets, targets, weights,
                      weight_label, weight_unit, cmap_name, filename,
                      sample_edges=None):
  rng = np.random.default_rng(42)
  total_edges = int(offsets[n])
  if sample_edges and sample_edges < total_edges:
    edge_indices = rng.choice(total_edges, sample_edges, replace=False)
    edge_indices.sort()
  else:
    edge_indices = np.arange(total_edges)

  src_nodes = np.searchsorted(offsets[1:n + 1], edge_indices, side="right")
  dst_nodes = targets[edge_indices]
  valid = (src_nodes < len(lon)) & (dst_nodes < len(lon))
  src_nodes, dst_nodes = src_nodes[valid], dst_nodes[valid]
  sampled_wt = weights[edge_indices[valid]].astype(np.float64)
  mid_lon = (lon[src_nodes] + lon[dst_nodes]) / 2
  mid_lat = (lat[src_nodes] + lat[dst_nodes]) / 2

  nbins = 3000
  lon_range, lat_range = (-125.0, -66.5), (24.4, 49.5)
  H, _, _ = np.histogram2d(mid_lon, mid_lat, bins=nbins,
                            range=[lon_range, lat_range])
  H_masked = np.ma.masked_where(H.T == 0, H.T)
  cmap = _truncate_cmap(cmap_name)

  fig, ax = plt.subplots(figsize=(14, 8))

  im = ax.imshow(H_masked, origin="lower", aspect="equal",
                 extent=[*lon_range, *lat_range],
                 cmap=cmap, norm=mcolors.LogNorm(vmin=1),
                 interpolation="nearest")

  # No outline - just the density data
  for spine in ax.spines.values():
    spine.set_visible(False)
  ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

  # Title: sits just above the axes (aligned with colorbar top)
  ax.set_title(
    f"USA Road Network: Edge Density by {weight_label} ({weight_unit})",
    fontweight="bold", fontsize=18, pad=2)

  # Colorbar: use make_axes_locatable for perfect alignment with axes
  from mpl_toolkits.axes_grid1 import make_axes_locatable
  divider = make_axes_locatable(ax)
  cax = divider.append_axes("right", size="2%", pad=0.08)
  cbar = fig.colorbar(im, cax=cax)
  cbar.set_label("Edge Count (log scale)", fontsize=15)

  # Legend: below axes, aligned with axes bottom
  mean_wt, median_wt = np.mean(sampled_wt), np.median(sampled_wt)
  if "time" in weight_label.lower():
    ms, mds = f"{mean_wt/10:,.1f}", f"{median_wt/10:,.1f}"
  else:
    ms, mds = f"{mean_wt:,.0f}", f"{median_wt:,.0f}"
  ax.text(0.5, -0.02,
          f"Edges sampled: {len(sampled_wt):,}  |  "
          f"Mean {weight_label.lower()}: {ms} {weight_unit}  |  "
          f"Median {weight_label.lower()}: {mds} {weight_unit}",
          transform=ax.transAxes, fontsize=12,
          ha="center", va="top",
          bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                    alpha=0.9, edgecolor="gray"))

  fig.tight_layout()
  out = os.path.join(FIG_DIR, filename)
  fig.savefig(out, dpi=DPI, bbox_inches="tight", pad_inches=0.06)
  plt.close(fig)
  print(f"  Saved {out}")


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--sample", type=int, default=2_000_000)
  parser.add_argument("--sample-edges", type=int, default=5_000_000)
  args = parser.parse_args()
  sample = args.sample if args.sample > 0 else None
  sample_edges = args.sample_edges if args.sample_edges > 0 else None

  print("Loading coordinates...")
  lon, lat = load_coordinates(CO_FILE)
  print(f"  {len(lon):,} nodes")
  print("Plotting node coordinates...")
  plot_coordinates(lon, lat, sample=sample)

  print("Loading distance graph...")
  n_d, off_d, tgt_d, wt_d = load_graph(GR_DIST)
  print("Plotting distance edge density...")
  plot_edge_density(lon, lat, n_d, off_d, tgt_d, wt_d,
                    "Distance", "meters", "YlOrRd",
                    "usa_edge_density_distance.png", sample_edges)

  print("Loading travel-time graph...")
  n_t, off_t, tgt_t, wt_t = load_graph(GR_TIME)
  print("Plotting travel-time edge density...")
  plot_edge_density(lon, lat, n_t, off_t, tgt_t, wt_t,
                    "Travel Time", "seconds", "YlGnBu",
                    "usa_edge_density_traveltime.png", sample_edges)
  print("\nDone.")

if __name__ == "__main__":
  main()
