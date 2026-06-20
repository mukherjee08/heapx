"""
heapq-backed task scheduler (baseline) for the OS scheduling case study.

Mirrors the HeapxScheduler API but uses the standard library heapq
module.  Because heapq lacks native key-function support, tasks must
be wrapped in ``(priority, deadline, counter, Task)`` tuples — the
canonical workaround documented in the Python heapq documentation.

This wrapper overhead (extra tuple allocation per task, manual
packing/unpacking) is precisely the ergonomic and performance cost
that heapx eliminates.
"""

from __future__ import annotations

import heapq
from typing import List, Optional

from task import Task


class HeapqScheduler:
  """Priority-deadline scheduler backed by stdlib heapq.

  Each entry is a tuple ``(priority, deadline, seq, task)`` where
  *seq* is a monotonic counter that breaks ties deterministically
  (heapq cannot compare Task objects directly).
  """

  def __init__(self) -> None:
    self._queue: List = []
    self._seq: int = 0

  @staticmethod
  def _wrap(task: Task, seq: int):
    return (task.priority, task.deadline, seq, task)

  # ---- Core operations ---------------------------------------------------

  def enqueue(self, task: Task) -> None:
    heapq.heappush(self._queue, self._wrap(task, self._seq))
    self._seq += 1

  def enqueue_batch(self, tasks: List[Task]) -> None:
    for t in tasks:
      heapq.heappush(self._queue, self._wrap(t, self._seq))
      self._seq += 1

  def dispatch(self) -> Task:
    return heapq.heappop(self._queue)[3]

  def dispatch_n(self, n: int) -> List[Task]:
    return [heapq.heappop(self._queue)[3] for _ in range(min(n, len(self._queue)))]

  def cancel_expired(self, current_time: float) -> int:
    """Remove expired tasks — requires full scan + rebuild."""
    before = len(self._queue)
    self._queue = [e for e in self._queue if e[3].deadline >= current_time]
    heapq.heapify(self._queue)
    return before - len(self._queue)

  def boost_priority(self, idx: int, new_priority: float) -> None:
    """Change priority — requires removal + re-insert."""
    entry = self._queue[idx]
    task = entry[3]
    updated = Task(
      task_id=task.task_id,
      priority=new_priority,
      deadline=task.deadline,
      arrival_time=task.arrival_time,
      burst=task.burst,
    )
    # Remove old entry, re-heapify, push new
    self._queue[idx] = self._queue[-1]
    self._queue.pop()
    if self._queue:
      heapq.heapify(self._queue)
    heapq.heappush(self._queue, self._wrap(updated, self._seq))
    self._seq += 1

  # ---- Accessors ---------------------------------------------------------

  @property
  def size(self) -> int:
    return len(self._queue)

  @property
  def empty(self) -> bool:
    return len(self._queue) == 0

  def peek(self) -> Optional[Task]:
    return self._queue[0][3] if self._queue else None
