"""DIMACS 9th Challenge graph loader.

Parses DIMACS .gr (graph) and .co (coordinate) files into compact
NumPy-backed CSR structures suitable for Dijkstra benchmarking.

File format reference:
  https://www.diag.uniroma1.it/challenge9/format.shtml

  .gr files:  'p sp <nodes> <arcs>'  header, then 'a <u> <v> <w>' arc lines.
  .co files:  'p aux sp co <nodes>'  header, then 'v <id> <lon> <lat>' lines.

Coordinates are TIGER/Line format: integer lon/lat scaled by 1e6.
"""
from __future__ import annotations

import os
from collections import deque
from typing import Optional

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

GR_DIST = os.path.join(DATA_DIR, "USA-road-d.USA.gr")
GR_TIME = os.path.join(DATA_DIR, "USA-road-t.USA.gr")
CO_FILE = os.path.join(DATA_DIR, "USA-road-d.USA.co")


def load_graph(path: str) -> tuple[int, np.ndarray, np.ndarray, np.ndarray]:
  """Load a DIMACS .gr file into CSR arrays (full graph).

  Returns:
    (n, offsets, targets, weights) where:
      offsets[u] .. offsets[u+1] index into targets/weights for node u.
      Nodes are 0-indexed (DIMACS 1-indexed ids shifted by -1).
  """
  srcs: list[int] = []
  dsts: list[int] = []
  wts: list[int] = []
  n = 0

  with open(path, "r") as f:
    for line in f:
      if line.startswith("p "):
        parts = line.split()
        n = int(parts[2])
      elif line.startswith("a "):
        parts = line.split()
        srcs.append(int(parts[1]) - 1)
        dsts.append(int(parts[2]) - 1)
        wts.append(int(parts[3]))

  src_arr = np.array(srcs, dtype=np.int32)
  dst_arr = np.array(dsts, dtype=np.int32)
  wt_arr = np.array(wts, dtype=np.int32)

  offsets = np.zeros(n + 1, dtype=np.int64)
  np.add.at(offsets[1:], src_arr, 1)
  np.cumsum(offsets, out=offsets)

  order = np.argsort(src_arr, kind="mergesort")
  targets = dst_arr[order]
  weights = wt_arr[order]

  return n, offsets, targets, weights


def extract_subgraph(
  n: int,
  offsets: np.ndarray,
  targets: np.ndarray,
  weights: np.ndarray,
  seed: int,
  max_nodes: int,
) -> tuple[int, np.ndarray, np.ndarray, np.ndarray, int, np.ndarray]:
  """Extract a connected subgraph via BFS from seed, up to max_nodes.

  Returns:
    (sub_n, sub_offsets, sub_targets, sub_weights, sub_source, old_ids)
    where old_ids[new_id] = original_id for coordinate lookup.
  """
  visited = set()
  queue = deque([seed])
  visited.add(seed)

  while queue and len(visited) < max_nodes:
    u = queue.popleft()
    start = int(offsets[u])
    end = int(offsets[u + 1])
    for idx in range(start, end):
      v = int(targets[idx])
      if v not in visited:
        visited.add(v)
        queue.append(v)
        if len(visited) >= max_nodes:
          break

  # Build remapping: old_id -> new_id
  old_ids = np.array(sorted(visited), dtype=np.int32)
  remap = {old: new for new, old in enumerate(old_ids)}
  sub_n = len(old_ids)

  # Collect edges within the subgraph
  sub_srcs: list[int] = []
  sub_dsts: list[int] = []
  sub_wts: list[int] = []

  for old_u in old_ids:
    new_u = remap[old_u]
    start = int(offsets[old_u])
    end = int(offsets[old_u + 1])
    for idx in range(start, end):
      old_v = int(targets[idx])
      if old_v in remap:
        sub_srcs.append(new_u)
        sub_dsts.append(remap[old_v])
        sub_wts.append(int(weights[idx]))

  sub_src_arr = np.array(sub_srcs, dtype=np.int32)
  sub_dst_arr = np.array(sub_dsts, dtype=np.int32)
  sub_wt_arr = np.array(sub_wts, dtype=np.int32)

  sub_offsets = np.zeros(sub_n + 1, dtype=np.int64)
  np.add.at(sub_offsets[1:], sub_src_arr, 1)
  np.cumsum(sub_offsets, out=sub_offsets)

  order = np.argsort(sub_src_arr, kind="mergesort")
  sub_targets = sub_dst_arr[order]
  sub_weights = sub_wt_arr[order]

  sub_source = remap[seed]
  return sub_n, sub_offsets, sub_targets, sub_weights, sub_source, old_ids


def load_coordinates(path: str) -> tuple[np.ndarray, np.ndarray]:
  """Load a DIMACS .co file into lon/lat arrays (degrees).

  Returns:
    (lon, lat) arrays of float64, indexed by 0-based node id.
    Coordinates converted from TIGER/Line integer format (×1e6) to degrees.
  """
  n = 0
  with open(path, "r") as f:
    for line in f:
      if line.startswith("p "):
        parts = line.split()
        n = int(parts[4])
        break

  lon = np.zeros(n, dtype=np.float64)
  lat = np.zeros(n, dtype=np.float64)

  with open(path, "r") as f:
    for line in f:
      if line.startswith("v "):
        parts = line.split()
        vid = int(parts[1]) - 1
        lon[vid] = int(parts[2]) / 1e6
        lat[vid] = int(parts[3]) / 1e6

  return lon, lat
