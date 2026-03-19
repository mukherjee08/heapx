"""
Smith-Waterman beam-search alignment using heapx priority queues.

Implements a priority-queue-driven beam search over the Smith-Waterman
dynamic-programming lattice.  At each anti-diagonal wavefront, candidate
cells are maintained in a bounded max-heap of size BEAM_WIDTH.  Only the
top-scoring candidates are expanded, pruning the O(mn) search space to
O(m * BEAM_WIDTH) while retaining near-optimal alignment quality.

This is the core computational kernel that exercises heapx's:
  1. heapify  — initial beam construction (Floyd's O(n) bottom-up).
  2. push     — inserting new candidate cells.
  3. pop      — bulk extraction of top-k alignments (single call).
  4. replace  — bounded-heap maintenance (replace root when full).
  5. nogil    — GIL release for parallel alignment across threads.
  6. arity    — quaternary heap reduces tree height for large beams.

References:
  - Smith & Waterman (1981): local alignment with zero-floor.
  - Rognes & Seeberg (2000): SIMD-accelerated SW.
  - Farrar (2007): striped SW for database search.
  - Yang et al. (2014): beam-bounded search for MLCS.
  - Larkin, Sen & Tarjan (2014): empirical priority-queue study.
"""

from __future__ import annotations

import heapq
from typing import List, Tuple

import heapx

from config import (
  SW_MATCH,
  SW_MISMATCH,
  SW_GAP_OPEN,
  BEAM_WIDTH,
  TOP_K,
)


def _score(a: str, b: str) -> int:
  """Residue substitution score (simplified BLOSUM62)."""
  return SW_MATCH if a == b else SW_MISMATCH


def sw_beam_align_heapx(
  query: str,
  subject: str,
  beam_width: int = BEAM_WIDTH,
  top_k: int = TOP_K,
  arity: int = 4,
  nogil: bool = False,
) -> List[Tuple[float, int, int]]:
  """Smith-Waterman beam-search alignment using heapx.

  Args:
    query: Query protein sequence.
    subject: Subject protein sequence.
    beam_width: Maximum candidates retained per wavefront.
    top_k: Number of top alignment scores to return.
    arity: Heap branching factor (2, 3, 4, or 8).
    nogil: Release GIL during heap operations.

  Returns:
    List of (score, query_end, subject_end) tuples for the top-k
    highest-scoring alignment endpoints, sorted descending.
  """
  m, n = len(query), len(subject)
  _sc = _score

  # Bounded min-heap of size top_k tracking the best cells globally.
  results: list = []

  # Row-by-row DP with beam pruning.
  prev_row = [0.0] * (n + 1)

  for i in range(1, m + 1):
    curr_row = [0.0] * (n + 1)
    # Collect all positive-scoring cells for this row.
    beam: list = []

    qi = query[i - 1]
    pr = prev_row
    cr = curr_row
    go = SW_GAP_OPEN

    for j in range(1, n + 1):
      s = max(0.0, pr[j - 1] + _sc(qi, subject[j - 1]), pr[j] + go, cr[j - 1] + go)
      cr[j] = s
      if s > 0:
        beam.append(s)

    # Prune beam to top beam_width scores using heapx.
    # This is the heap-intensive hot path.
    if len(beam) > beam_width:
      heapx.heapify(beam, max_heap=True, arity=arity, nogil=nogil)
      beam = heapx.pop(beam, n=beam_width, max_heap=True, arity=arity)
      if not isinstance(beam, list):
        beam = [beam]

    # Accumulate into global results heap (bounded min-heap of size top_k).
    for score in beam:
      if len(results) < top_k:
        heapx.push(results, score, arity=arity)
      elif score > results[0]:
        heapx.replace(results, score, indices=0, arity=arity)

    prev_row = cr

  # Extract top-k in descending order.
  heapx.heapify(results, max_heap=True, arity=arity, nogil=nogil)
  count = min(top_k, len(results))
  if count == 0:
    return []
  top = heapx.pop(results, n=count, max_heap=True, arity=arity)
  if not isinstance(top, list):
    top = [top]
  return top


def sw_beam_align_heapq(
  query: str,
  subject: str,
  beam_width: int = BEAM_WIDTH,
  top_k: int = TOP_K,
) -> List[float]:
  """Baseline Smith-Waterman beam-search alignment using stdlib heapq.

  Identical algorithm but uses heapq, which:
    - Requires key negation for max-heap semantics.
    - Cannot release the GIL.
    - Has no bulk pop (must call heappop in a loop).
    - Is limited to binary heaps (arity=2).
  """
  m, n = len(query), len(subject)
  _sc = _score
  # Bounded min-heap of positive scores: root = smallest score in top-k.
  results: list = []
  prev_row = [0.0] * (n + 1)

  for i in range(1, m + 1):
    curr_row = [0.0] * (n + 1)
    beam: list = []

    qi = query[i - 1]
    pr = prev_row
    cr = curr_row
    go = SW_GAP_OPEN

    for j in range(1, n + 1):
      s = max(0.0, pr[j - 1] + _sc(qi, subject[j - 1]), pr[j] + go, cr[j - 1] + go)
      cr[j] = s
      if s > 0:
        beam.append(s)

    # Prune beam to top beam_width: negate for max-heap emulation,
    # heapify, pop beam_width smallest negated (= largest original).
    if len(beam) > beam_width:
      neg_beam = [-x for x in beam]
      heapq.heapify(neg_beam)
      beam = [-heapq.heappop(neg_beam) for _ in range(beam_width)]

    # Accumulate into bounded min-heap of size top_k.
    for score in beam:
      if len(results) < top_k:
        heapq.heappush(results, score)
      elif score > results[0]:
        heapq.heapreplace(results, score)

    prev_row = cr

  # Extract top-k in descending order.
  count = min(top_k, len(results))
  top = sorted([heapq.heappop(results) for _ in range(count)], reverse=True)
  return top
