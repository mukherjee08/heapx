"""
Task data model for the OS task scheduling case study.

Defines the Task dataclass used by both the heapx and heapq scheduler
implementations.  Tasks carry a priority, deadline, arrival time, and
estimated burst length — the four attributes most commonly used by
real-world OS schedulers (Silberschatz Ch. 5; Liu & Layland 1973).

References:
  [1] A. Silberschatz, P. B. Galvin, G. Gagne, "Operating System
      Concepts," 10th ed., Wiley, 2018, Chapter 5.
  [2] C. L. Liu, J. W. Layland, "Scheduling Algorithms for
      Multiprogramming in a Hard-Real-Time Environment," JACM 20(1),
      1973.
  [3] G. S. Brodal, "Priority Queues with Decreasing Keys," FUN 2022.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Task:
  """A schedulable task in the simulated operating system.

  Attributes:
    task_id:      Unique monotonic identifier.
    priority:     Numeric priority (lower = more urgent).
    deadline:     Absolute wall-clock deadline for completion.
    arrival_time: Wall-clock time the task entered the ready queue.
    burst:        Estimated CPU burst length in time units.
    cancelled:    Whether the task has been cancelled.
  """
  task_id: int
  priority: float
  deadline: float
  arrival_time: float
  burst: float
  cancelled: bool = field(default=False, repr=False)
