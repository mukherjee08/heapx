"""
Deterministic workload generator for the OS task scheduling case study.

Synthesises realistic task arrival streams using distributions observed
in production schedulers (Dask, Celery, asyncio event loops).  All
randomness is seeded for full reproducibility.

Workload characteristics:
  - Arrival times follow a Poisson process (exponential inter-arrivals).
  - Priorities are drawn from a discrete distribution modelling four
    OS-style priority classes: CRITICAL (5 %), HIGH (15 %), NORMAL (60 %),
    LOW (20 %).
  - Burst lengths follow a hyper-exponential distribution matching the
    CPU-burst observations in Silberschatz Ch. 5, Fig. 5.2.
  - Deadlines are set relative to arrival + burst with a laxity factor.

References:
  [1] A. Silberschatz et al., "Operating System Concepts," Ch. 5.
  [2] M. Rocklin, "Dask: Parallel Computation with Blocked Algorithms
      and Task Scheduling," SciPy 2015.
  [3] A. Staffolani et al., "RLQ: Workload Allocation with
      Reinforcement Learning in Distributed Queues," IEEE TPDS 34(3),
      2023.
"""

from __future__ import annotations

import numpy as np
from typing import List

from task import Task

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PRIORITY_CLASSES = {
  "CRITICAL": (0, 0.05),   # priority 0, 5 % of tasks
  "HIGH":     (1, 0.15),   # priority 1, 15 %
  "NORMAL":   (2, 0.60),   # priority 2, 60 %
  "LOW":      (3, 0.20),   # priority 3, 20 %
}

MEAN_INTERARRIVAL: float = 0.001   # 1 ms mean inter-arrival (1000 tasks/s)
BURST_SHORT_MEAN:  float = 0.005   # 5 ms  (I/O-bound tasks)
BURST_LONG_MEAN:   float = 0.050   # 50 ms (CPU-bound tasks)
BURST_SHORT_PROB:  float = 0.80    # 80 % short bursts (hyper-exponential)
LAXITY_FACTOR:     float = 3.0     # deadline = arrival + laxity * burst


def generate_workload(
  n_tasks: int = 1_000_000,
  seed: int = 42,
) -> List[Task]:
  """Return a deterministic list of *n_tasks* Task objects.

  Args:
    n_tasks: Number of tasks to generate.
    seed:    RNG seed for reproducibility.

  Returns:
    List of Task instances sorted by arrival_time.
  """
  rng = np.random.default_rng(seed)

  # --- Arrival times (Poisson process) ---
  interarrivals = rng.exponential(MEAN_INTERARRIVAL, size=n_tasks)
  arrivals = np.cumsum(interarrivals)

  # --- Priorities (discrete categorical) ---
  classes = list(PRIORITY_CLASSES.values())
  pri_values = np.array([c[0] for c in classes], dtype=np.float64)
  pri_probs  = np.array([c[1] for c in classes], dtype=np.float64)
  priorities = rng.choice(pri_values, size=n_tasks, p=pri_probs)

  # --- Burst lengths (hyper-exponential) ---
  is_short = rng.random(size=n_tasks) < BURST_SHORT_PROB
  bursts = np.where(
    is_short,
    rng.exponential(BURST_SHORT_MEAN, size=n_tasks),
    rng.exponential(BURST_LONG_MEAN, size=n_tasks),
  )
  bursts = np.clip(bursts, 1e-6, None)  # ensure positive

  # --- Deadlines ---
  deadlines = arrivals + LAXITY_FACTOR * bursts

  # --- Build Task list ---
  tasks: List[Task] = [
    Task(
      task_id=i,
      priority=float(priorities[i]),
      deadline=float(deadlines[i]),
      arrival_time=float(arrivals[i]),
      burst=float(bursts[i]),
    )
    for i in range(n_tasks)
  ]
  return tasks
