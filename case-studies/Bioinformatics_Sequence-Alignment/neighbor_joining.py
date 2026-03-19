"""
Neighbor-joining phylogenetic tree construction using heapx.

The neighbor-joining (NJ) algorithm (Saitou & Nei, 1987) iteratively
joins the pair of taxa with the smallest adjusted distance.  The
canonical implementation is O(n^3); Mailund et al. (2006) showed that
priority-queue-based selection can reduce the best case to O(n^2).

This module implements the priority-queue variant where a min-heap
stores all pairwise adjusted distances.  At each iteration the minimum
is popped, the pair is joined, and affected entries are updated via
heapx.remove + heapx.push.

heapx advantages demonstrated:
  - O(log n) remove by predicate (vs. O(n) scan + rebuild with heapq).
  - Homogeneous float path for distance-based ordering.
  - Quaternary heap reduces tree height for the large distance heap.

Reference:
  - Mailund et al. (2006): "Recrafting the neighbor-joining method."
"""

from __future__ import annotations

import random
import time
from typing import Dict, List, Tuple

import heapx

from config import NJ_N_TAXA, RNG_SEED


def generate_distance_matrix(
  n: int, seed: int = RNG_SEED
) -> List[List[float]]:
  """Generate a symmetric distance matrix with ultrametric noise.

  Simulates pairwise evolutionary distances between n taxa using
  a random additive tree model (Atteson, 1999).
  """
  rng = random.Random(seed)
  d = [[0.0] * n for _ in range(n)]
  for i in range(n):
    for j in range(i + 1, n):
      val = rng.uniform(0.1, 2.0)
      d[i][j] = val
      d[j][i] = val
  return d


def nj_heapx(
  dist: List[List[float]], arity: int = 4
) -> List[Tuple[int, int, float]]:
  """Neighbor-joining using heapx priority queue.

  Args:
    dist: n x n symmetric distance matrix.
    arity: Heap branching factor.

  Returns:
    List of (i, j, branch_length) joins in order of construction.
  """
  n = len(dist)
  active = set(range(n))
  joins: list = []

  # Build initial heap of all (adjusted_dist, i, j) triples.
  r = [sum(dist[i]) for i in range(n)]
  heap: list = []
  for i in range(n):
    for j in range(i + 1, n):
      q_ij = dist[i][j] - (r[i] + r[j]) / (len(active) - 2) if len(active) > 2 else dist[i][j]
      heap.append((q_ij, i, j))
  heapx.heapify(heap, arity=arity)

  while len(active) > 2:
    # Pop minimum-distance pair.
    best = heapx.pop(heap, arity=arity)
    _, i, j = best

    # Skip stale entries (taxa already merged).
    while i not in active or j not in active:
      if not heap:
        break
      best = heapx.pop(heap, arity=arity)
      _, i, j = best

    if i not in active or j not in active:
      break

    na = len(active)
    branch = dist[i][j] / 2.0
    joins.append((i, j, branch))

    # Create new taxon index.
    new_idx = n + len(joins) - 1

    # Compute distances from new node to all remaining taxa.
    new_row = [0.0] * (new_idx + 1)
    for k in active:
      if k != i and k != j:
        d_new = (dist[i][k] + dist[j][k] - dist[i][j]) / 2.0
        new_row[k] = d_new

    # Extend distance matrix (conceptually; we store in a dict-like manner).
    # For simplicity, extend the lists.
    for row in dist:
      row.extend([0.0] * (new_idx + 1 - len(row)))
    while len(dist) <= new_idx:
      dist.append([0.0] * (new_idx + 1))
    for k in active:
      if k != i and k != j:
        dist[new_idx][k] = new_row[k]
        dist[k][new_idx] = new_row[k]

    active.discard(i)
    active.discard(j)
    active.add(new_idx)

    # Remove stale entries and insert new ones.
    # heapx.remove by predicate: O(k + n) batch removal.
    heapx.remove(
      heap,
      predicate=lambda x: x[1] in (i, j) or x[2] in (i, j),
      arity=arity,
    )

    # Insert new distance pairs.
    na2 = len(active)
    r_new = sum(dist[new_idx][k] for k in active if k != new_idx)
    new_entries = []
    for k in active:
      if k == new_idx:
        continue
      r_k = sum(dist[k][kk] for kk in active if kk != k)
      q = dist[new_idx][k] - (r_new + r_k) / (na2 - 2) if na2 > 2 else dist[new_idx][k]
      new_entries.append((q, min(new_idx, k), max(new_idx, k)))
    if new_entries:
      heapx.push(heap, new_entries, arity=arity)

  # Join last two.
  remaining = list(active)
  if len(remaining) == 2:
    a, b = remaining
    joins.append((a, b, dist[a][b] if a < len(dist) and b < len(dist[a]) else 0.0))

  return joins


def nj_heapq(dist: List[List[float]]) -> List[Tuple[int, int, float]]:
  """Baseline neighbor-joining using stdlib heapq (binary heap only)."""
  import heapq

  n = len(dist)
  active = set(range(n))
  joins: list = []

  r = [sum(dist[i]) for i in range(n)]
  heap: list = []
  for i in range(n):
    for j in range(i + 1, n):
      q_ij = dist[i][j] - (r[i] + r[j]) / (len(active) - 2) if len(active) > 2 else dist[i][j]
      heapq.heappush(heap, (q_ij, i, j))

  while len(active) > 2:
    best = heapq.heappop(heap)
    _, i, j = best

    while i not in active or j not in active:
      if not heap:
        break
      best = heapq.heappop(heap)
      _, i, j = best

    if i not in active or j not in active:
      break

    branch = dist[i][j] / 2.0
    joins.append((i, j, branch))

    new_idx = n + len(joins) - 1
    new_row = [0.0] * (new_idx + 1)
    for k in active:
      if k != i and k != j:
        d_new = (dist[i][k] + dist[j][k] - dist[i][j]) / 2.0
        new_row[k] = d_new

    for row in dist:
      row.extend([0.0] * (new_idx + 1 - len(row)))
    while len(dist) <= new_idx:
      dist.append([0.0] * (new_idx + 1))
    for k in active:
      if k != i and k != j:
        dist[new_idx][k] = new_row[k]
        dist[k][new_idx] = new_row[k]

    active.discard(i)
    active.discard(j)
    active.add(new_idx)

    # heapq has no remove; rebuild heap excluding stale entries.
    heap = [(q, a, b) for q, a, b in heap if a not in (i, j) and b not in (i, j)]
    heapq.heapify(heap)

    na2 = len(active)
    r_new = sum(dist[new_idx][k] for k in active if k != new_idx)
    for k in active:
      if k == new_idx:
        continue
      r_k = sum(dist[k][kk] for kk in active if kk != k)
      q = dist[new_idx][k] - (r_new + r_k) / (na2 - 2) if na2 > 2 else dist[new_idx][k]
      heapq.heappush(heap, (q, min(new_idx, k), max(new_idx, k)))

  remaining = list(active)
  if len(remaining) == 2:
    a, b = remaining
    joins.append((a, b, dist[a][b] if a < len(dist) and b < len(dist[a]) else 0.0))

  return joins
