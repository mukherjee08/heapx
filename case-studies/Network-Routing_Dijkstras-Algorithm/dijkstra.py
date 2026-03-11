"""Dijkstra's algorithm — four priority-queue implementations.

Implements single-source shortest paths using:
  1. heapx_replace — heapx with O(log n) replace for decrease-key.
     Uses a position-tracking array rebuilt after each mutation.
     Demonstrates bounded heap size (max n entries).
  2. heapx_lazy   — heapx with lazy deletion (same strategy as heapq).
     Demonstrates raw C-extension speed advantage.
  3. heapq        — Standard library heapq with lazy deletion.
  4. sortedcontainers — SortedList with explicit remove + add.

Each returns (dist, stats) for empirical analysis.
"""
from __future__ import annotations

import heapx
import heapq
import numpy as np

try:
  from sortedcontainers import SortedList
except ImportError:
  SortedList = None

INF = float("inf")


# ---------------------------------------------------------------------------
# 1. heapx with replace (decrease-key) — bounded heap
# ---------------------------------------------------------------------------

def dijkstra_heapx_replace(
  n: int,
  offsets: np.ndarray,
  targets: np.ndarray,
  weights: np.ndarray,
  source: int,
) -> tuple[list[float], dict[str, int]]:
  """Dijkstra with heapx.replace for decrease-key.

  Heap size is bounded at <= n entries.  Position tracking via full
  rebuild after each mutation adds O(heap_size) overhead per operation.
  """
  dist = [INF] * n
  dist[source] = 0.0
  settled = [False] * n
  heap_pos = [-1] * n

  heap: list[tuple[float, int]] = [(0.0, source)]
  heap_pos[source] = 0

  pushes = 1
  pops = 0
  replaces = 0
  max_heap_size = 1

  def _rebuild_pos():
    for i, (_, v) in enumerate(heap):
      heap_pos[v] = i

  while heap:
    d_u, u = heapx.pop(heap)
    pops += 1
    heap_pos[u] = -1
    _rebuild_pos()

    if settled[u]:
      continue
    settled[u] = True

    start = int(offsets[u])
    end = int(offsets[u + 1])
    for idx in range(start, end):
      v = int(targets[idx])
      w = int(weights[idx])
      nd = d_u + w
      if nd < dist[v]:
        dist[v] = nd
        if heap_pos[v] >= 0:
          heapx.replace(heap, (nd, v), indices=heap_pos[v])
          replaces += 1
          _rebuild_pos()
        elif not settled[v]:
          heapx.push(heap, (nd, v))
          pushes += 1
          _rebuild_pos()
          if len(heap) > max_heap_size:
            max_heap_size = len(heap)

  return dist, {
    "pushes": pushes,
    "pops": pops,
    "replaces": replaces,
    "max_heap_size": max_heap_size,
    "total_ops": pushes + pops + replaces,
  }


# ---------------------------------------------------------------------------
# 2. heapx with lazy deletion — raw speed comparison
# ---------------------------------------------------------------------------

def dijkstra_heapx_lazy(
  n: int,
  offsets: np.ndarray,
  targets: np.ndarray,
  weights: np.ndarray,
  source: int,
) -> tuple[list[float], dict[str, int]]:
  """Dijkstra with heapx using lazy deletion (same strategy as heapq).

  Demonstrates the raw speed advantage of heapx's C-extension pop/push
  over heapq's Python-level operations.
  """
  dist = [INF] * n
  dist[source] = 0.0

  heap: list[tuple[float, int]] = [(0.0, source)]
  pushes = 1
  pops = 0
  stale_pops = 0
  max_heap_size = 1

  while heap:
    d_u, u = heapx.pop(heap)
    pops += 1

    if d_u > dist[u]:
      stale_pops += 1
      continue

    start = int(offsets[u])
    end = int(offsets[u + 1])
    for idx in range(start, end):
      v = int(targets[idx])
      w = int(weights[idx])
      nd = d_u + w
      if nd < dist[v]:
        dist[v] = nd
        heapx.push(heap, (nd, v))
        pushes += 1
        if len(heap) > max_heap_size:
          max_heap_size = len(heap)

  return dist, {
    "pushes": pushes,
    "pops": pops,
    "stale_pops": stale_pops,
    "max_heap_size": max_heap_size,
    "total_ops": pushes + pops,
  }


# ---------------------------------------------------------------------------
# 3. heapq with lazy deletion
# ---------------------------------------------------------------------------

def dijkstra_heapq(
  n: int,
  offsets: np.ndarray,
  targets: np.ndarray,
  weights: np.ndarray,
  source: int,
) -> tuple[list[float], dict[str, int]]:
  """Dijkstra with heapq using lazy deletion.

  Standard approach: every relaxation pushes a new entry.  Stale entries
  (popped distance > current best) are discarded.  Heap grows to O(m).
  """
  dist = [INF] * n
  dist[source] = 0.0

  heap: list[tuple[float, int]] = [(0.0, source)]
  pushes = 1
  pops = 0
  stale_pops = 0
  max_heap_size = 1

  while heap:
    d_u, u = heapq.heappop(heap)
    pops += 1

    if d_u > dist[u]:
      stale_pops += 1
      continue

    start = int(offsets[u])
    end = int(offsets[u + 1])
    for idx in range(start, end):
      v = int(targets[idx])
      w = int(weights[idx])
      nd = d_u + w
      if nd < dist[v]:
        dist[v] = nd
        heapq.heappush(heap, (nd, v))
        pushes += 1
        if len(heap) > max_heap_size:
          max_heap_size = len(heap)

  return dist, {
    "pushes": pushes,
    "pops": pops,
    "stale_pops": stale_pops,
    "max_heap_size": max_heap_size,
    "total_ops": pushes + pops,
  }


# ---------------------------------------------------------------------------
# 4. sortedcontainers SortedList
# ---------------------------------------------------------------------------

def dijkstra_sortedlist(
  n: int,
  offsets: np.ndarray,
  targets: np.ndarray,
  weights: np.ndarray,
  source: int,
) -> tuple[list[float], dict[str, int]]:
  """Dijkstra with SortedList — decrease-key via remove + add."""
  if SortedList is None:
    raise ImportError("sortedcontainers is required")

  dist = [INF] * n
  dist[source] = 0.0
  in_queue = [False] * n
  in_queue[source] = True

  sl = SortedList([(0.0, source)])
  adds = 1
  removes = 0
  sl_pops = 0
  max_sl_size = 1

  while sl:
    d_u, u = sl.pop(0)
    sl_pops += 1
    in_queue[u] = False

    start = int(offsets[u])
    end = int(offsets[u + 1])
    for idx in range(start, end):
      v = int(targets[idx])
      w = int(weights[idx])
      nd = d_u + w
      if nd < dist[v]:
        if in_queue[v]:
          sl.remove((dist[v], v))
          removes += 1
        dist[v] = nd
        sl.add((nd, v))
        adds += 1
        in_queue[v] = True
        if len(sl) > max_sl_size:
          max_sl_size = len(sl)

  return dist, {
    "adds": adds,
    "removes": removes,
    "pops": sl_pops,
    "max_heap_size": max_sl_size,
    "total_ops": adds + removes + sl_pops,
  }
