"""
heapx-backed task scheduler for the OS scheduling case study.

Implements a priority-deadline scheduler using heapx's tuple-based
homogeneous fast path.  Tasks are represented in the heap as
``(priority, deadline, seq, task)`` tuples — exactly mirroring the
HeapqScheduler's data layout so that the two schedulers are
apples-to-apples comparable (identical memory representation, identical
ordering semantics).

This choice lets heapx dispatch to its C-native tuple-comparison path
(``fast_compare`` for tuples) rather than invoking a Python key
function per comparison.  It is the same pattern a production user
would adopt when performance matters (see heapx README, §"Fast
Comparison Paths").

Scheduling policy:
  Tasks are ordered by ``(priority, deadline)`` — fixed-priority with
  Earliest-Deadline-First tie-breaking (Liu & Layland 1973,
  Silberschatz Ch. 5).  The seq field ensures stable FIFO ordering
  among tasks with identical (priority, deadline).

References:
  [1] C. L. Liu, J. W. Layland, "Scheduling Algorithms for
      Multiprogramming in a Hard-Real-Time Environment," JACM 1973.
  [2] G. S. Brodal, "Priority Queues with Decreasing Keys," FUN 2022.
  [3] R. K. Clark, "Scheduling Dependent Real-Time Activities,"
      CMU-CS-90-155, 1990.
"""

from __future__ import annotations

import heapx
from typing import List, Optional

from task import Task


class HeapxScheduler:
  """Priority-deadline scheduler backed by heapx.

  Entries are ``(priority, deadline, seq, task)`` tuples.  All heapx
  operations run on the tuple-homogeneous fast path: C-native
  comparisons, no Python callbacks on the hot path.
  """

  def __init__(self) -> None:
    self._queue: List = []
    self._seq: int = 0

  @staticmethod
  def _wrap(task: Task, seq: int):
    return (task.priority, task.deadline, seq, task)

  # ---- Core operations ---------------------------------------------------

  def enqueue(self, task: Task) -> None:
    """Insert a single task — O(log n)."""
    heapx.push(self._queue, self._wrap(task, self._seq))
    self._seq += 1

  def enqueue_batch(self, tasks: List[Task]) -> None:
    """Bulk-insert — delegates to heapx's O(n+k) bulk-push gate."""
    wrapped = [self._wrap(t, self._seq + i) for i, t in enumerate(tasks)]
    self._seq += len(tasks)
    heapx.push(self._queue, wrapped)

  def dispatch(self) -> Task:
    """Remove and return the highest-priority task — O(log n)."""
    return heapx.pop(self._queue)[3]

  def dispatch_n(self, n: int) -> List[Task]:
    """Remove and return the top *n* tasks — O(n log k)."""
    entries = heapx.pop(self._queue, n=min(n, len(self._queue)))
    return [e[3] for e in entries]

  def cancel_expired(self, current_time: float) -> int:
    """Remove all tasks whose deadline has passed.

    Uses heapx's predicate-based remove — a single C-level call that
    combines the scan and re-heapify, versus heapq's list comprehension
    + O(n) heapify workaround.
    """
    return heapx.remove(
      self._queue,
      predicate=lambda e: e[3].deadline < current_time,
    )

  def boost_priority(self, idx: int, new_priority: float) -> None:
    """Decrease (boost) priority at *idx* — O(log n) sift via heapx.replace.

    heapx performs an in-place sift-up/sift-down on the changed entry;
    heapq (no decrease-key) forces a full O(n) re-heapify.
    """
    entry = self._queue[idx]
    task = entry[3]
    updated = Task(
      task_id=task.task_id,
      priority=new_priority,
      deadline=task.deadline,
      arrival_time=task.arrival_time,
      burst=task.burst,
    )
    new_entry = (new_priority, task.deadline, entry[2], updated)
    heapx.replace(self._queue, new_entry, indices=idx)

  # ---- Accessors ---------------------------------------------------------

  @property
  def size(self) -> int:
    return len(self._queue)

  @property
  def empty(self) -> bool:
    return len(self._queue) == 0

  def peek(self) -> Optional[Task]:
    return self._queue[0][3] if self._queue else None
