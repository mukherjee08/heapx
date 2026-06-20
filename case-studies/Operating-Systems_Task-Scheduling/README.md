# Case Study 6 — Operating Systems: Task Scheduling

## 1. Introduction

This case study benchmarks `heapx` as the ready queue of a priority-based
operating-system task scheduler, against `heapq`, `sortedcontainers.SortedList`,
`heapdict`, and a pure-Python Fibonacci heap. An OS scheduler holds every
runnable task in a ready queue ordered by urgency and repeatedly dispatches
the most urgent one. Beyond plain enqueue and dispatch, a realistic scheduler
must also cancel tasks whose deadlines have passed and boost the priority of
waiting tasks. Those last two operations (predicate-based removal and
priority change) are where the implementations diverge sharply: on a
priority boost `heapx` is over three orders of magnitude faster than `heapq`.

The workload is a synthetic task stream modelling Poisson arrivals,
hyper-exponential CPU bursts, and four priority classes, following the
scheduling literature (Silberschatz et al., Operating System Concepts,
Chapter 5; Liu and Layland 1973). All runs are seeded (`seed=42`).

## 2. Background: Priority-Based Scheduling

### 2.1 The ready queue

A scheduler keeps the set of runnable tasks in a ready queue. The scheduling
policy decides which task runs next by defining an ordering over tasks. This
study uses fixed-priority scheduling with Earliest-Deadline-First (EDF)
tie-breaking: tasks are ordered first by priority (lower number means more
urgent) and, among equal priorities, by deadline (sooner first). A stable
sequence counter breaks remaining ties to give FIFO order among
otherwise-identical tasks.

```
   ready queue ordered by (priority, deadline, seq):

      (0, 12.4, 7)   <- most urgent: priority 0, earliest deadline
      (1,  9.1, 3)
      (1, 15.8, 5)
      (2,  8.0, 1)
      ...
        ^ dispatch always removes the top entry
```

This is exactly the priority-queue interface, so the ready queue is a heap
keyed by the tuple `(priority, deadline, seq)`.

### 2.2 What the scheduler must do

| Operation | Scheduler meaning | Frequency |
|---|---|---|
| enqueue | A task arrives and becomes runnable | high |
| dispatch | Run the most urgent task (extract-min) | high |
| cancel_expired | Drop tasks whose deadline has passed | periodic |
| boost_priority | Raise a waiting task's priority (decrease-key) | frequent |

`enqueue` and `dispatch` are the textbook push and extract-min. The two that
strain a plain heap are `cancel_expired` (remove every task matching a
predicate) and `boost_priority` (change a task's key in place, the classic
decrease-key operation). A binary heap with no decrease-key support handles
neither directly.

### 2.3 The synthetic workload (`workload.py`)

The workload generator models realistic task arrivals:

- Arrivals: a Poisson process with mean inter-arrival 0.001 s (1,000 tasks
  per second). Inter-arrival gaps are exponential, accumulated with
  `np.cumsum`.
- Priority classes: CRITICAL (priority 0, 5% of tasks), HIGH (1, 15%),
  NORMAL (2, 60%), LOW (3, 20%), drawn by `rng.choice` with those
  probabilities.
- CPU bursts: a hyper-exponential mixture matching the CPU-burst observations
  in Silberschatz Chapter 5. With probability 0.80 a task is I/O-bound with a
  short burst (mean 5 ms); otherwise it is CPU-bound with a long burst (mean
  50 ms).
- Deadlines: `arrival + 3.0 * burst` (a laxity factor of 3).

```python
# workload.py (parameters)
MEAN_INTERARRIVAL = 0.001   # 1 ms mean inter-arrival
BURST_SHORT_MEAN  = 0.005   # 5 ms  (I/O-bound)
BURST_LONG_MEAN   = 0.050   # 50 ms (CPU-bound)
BURST_SHORT_PROB  = 0.80    # 80% short bursts
LAXITY_FACTOR     = 3.0     # deadline = arrival + 3 * burst
```

The hyper-exponential burst (a mixture of two exponentials) reproduces the
empirical shape of real CPU bursts: many short bursts and a long tail of
rare long ones, which a single exponential cannot capture.

### 2.4 The Task record (`task.py`)

```python
@dataclass(slots=True)
class Task:
    task_id: int          # unique monotonic identifier
    priority: float       # numeric priority (lower = more urgent)
    deadline: float       # absolute deadline for completion
    arrival_time: float   # time the task entered the ready queue
    burst: float          # estimated CPU burst length
    cancelled: bool = field(default=False, repr=False)
```

`slots=True` keeps each task compact. The four scheduling attributes
(priority, deadline, arrival, burst) are the ones real schedulers use.

## 3. The Two Hard Operations

### 3.1 Predicate-based cancellation

`cancel_expired` must drop every task whose deadline is in the past. With
`heapq` there is no targeted removal, so the only correct approach is to scan
all n entries, build a new survivor list, and rebuild the heap from scratch:

```python
# scheduler_heapq.py, cancel_expired  (O(n) per call)
self._queue = [e for e in self._queue if e[3].deadline >= current_time]
heapq.heapify(self._queue)
```

That allocates a new list and re-heapifies all survivors every call. `heapx`
exposes a predicate remove that performs the scan and the heap repair in a
single C-level call with no Python-level comprehension and no extra
allocation:

```python
# scheduler_heapx.py, cancel_expired
heapx.remove(self._queue, predicate=lambda e: e[3].deadline < current_time)
```

### 3.2 Priority boosting (decrease-key)

`boost_priority` lowers a waiting task's priority number so it runs sooner.
This is decrease-key. `heapq` has no decrease-key primitive, so the baseline
must remove the entry by swapping in the tail, re-heapify the whole array,
and push the updated entry back:

```python
# scheduler_heapq.py, boost_priority  (O(n) re-heapify)
self._queue[idx] = self._queue[-1]
self._queue.pop()
if self._queue:
    heapq.heapify(self._queue)        # O(n)
heapq.heappush(self._queue, self._wrap(updated, self._seq))
```

`heapx.replace` writes the new entry into its slot and sifts that one entry
up or down, a single root-to-leaf path:

```python
# scheduler_heapx.py, boost_priority  (O(log n) in-place sift)
new_entry = (new_priority, task.deadline, entry[2], updated)
heapx.replace(self._queue, new_entry, indices=idx)
```

The asymptotic gap is O(log n) versus O(n) per boost. Section 5 shows this
becoming a 6,000x latency difference at a queue of 250,000 tasks.

### 3.3 How the entries are compared

Both schedulers pack tasks into comparable tuples `(priority, deadline, seq,
task)` so the heap orders them without a Python key callback. `heapx` then
dispatches to its C-native tuple-comparison path rather than calling back into
Python for every comparison. `heapq` requires the same tuple wrapping, which
is the workaround documented in the Python `heapq` manual; without it,
two tasks with equal priority would force a comparison of `Task` objects,
which is not defined. (The standalone benchmark file exercises `heapx`'s
alternative `cmp=` key mode, storing bare `Task` objects; the scheduler
classes use the tuple form.)

## 4. Code Architecture

### 4.1 File overview

| File | Role |
|---|---|
| `task.py` | The `Task` dataclass |
| `workload.py` | Synthetic workload generator (Poisson arrivals, hyper-exponential bursts) |
| `scheduler_heapx.py` | The `heapx`-backed scheduler |
| `scheduler_heapq.py` | The `heapq`-backed baseline scheduler |
| `benchmark.py` | Seven benchmarks (B1 to B7) against five competitors |
| `plot_results.py` | Figure generation (600 DPI) |
| `run_all.py` | Orchestrator |
| `results.json` | Benchmark output |

### 4.2 The seven benchmarks (`benchmark.py`)

Competitors: `heapq`, `sortedcontainers.SortedList`, `heapdict`, and a
pure-Python Fibonacci heap (`fibonacci_heap_mod`). Workload is 10,500,000
tasks at `seed=42`. Timing uses `time.perf_counter_ns` with garbage
collection disabled around each measured region.

| ID | Benchmark | What it measures |
|---|---|---|
| B1 | Batch push | Loading many tasks at once |
| B2 | Single push | Per-insert latency into a pre-built queue |
| B3 | Single pop | Per-dispatch latency |
| B4 | Replace (decrease-key) | Per-boost latency at random indices [hero] |
| B5 | Replace-heavy workload | End-to-end loop with frequent priority updates [hero] |
| B6 | Queue dynamics | heapx-only trace of queue size and operation mix |
| B7 | Scheduler throughput | Realistic mixed loop, 40% enqueue, 40% dispatch, 20% boost [hero] |

B6's steady-state mix matches push and pop at 47.5% each with 5% replaces,
prefilling 50,000 tasks and sampling every 50 events.

### 4.3 Figures

`plot_results.py` produces eleven figures: workload characterization
(`fig01`), the scheduler architecture and complexity diagram (`fig02`), queue
dynamics (`fig03`), the per-operation latency plots (`fig04` batch push,
`fig05` single push, `fig06` single pop, `fig07` replace latency,
`fig08` replace-heavy), a feature-support matrix (`fig09`), memory overhead
(`fig10`), and end-to-end scheduler throughput (`fig11`). All are 600 DPI with
a colour-blind-safe palette (heapx blue, heapq orange, SortedList green,
heapdict pink, Fibonacci amber).

## 5. Results

All numbers are read from the committed `results.json` (medians across reps).
Speedups are computed from those raw values.

### 5.1 Replace / decrease-key latency (microseconds per operation) [B4]

| Queue size | heapx | heapq | sortedcontainers | heapdict |
|---|---|---|---|---|
| 1,000 | 0.68 | 34.6 | 1.45 | 3.00 |
| 10,000 | 0.75 | 341.1 | 1.72 | 3.60 |
| 100,000 | 0.97 | 3,754.7 | 2.75 | 5.76 |
| 250,000 | 1.63 | 10,132.0 | 3.77 | 8.13 |

This is the headline. `heapx` boosts a priority in about 1.6 microseconds
regardless of queue size, because it sifts one entry. `heapq` must re-heapify
the whole array, so its latency grows linearly with the queue, reaching 10.1
ms at 250,000 tasks, a 6,203x gap. The pure-Python O(log n) structures
(`sortedcontainers`, `heapdict`) stay close to `heapx` asymptotically but run
2x to 5x slower from interpreter overhead.

### 5.2 Replace-heavy end-to-end workload (seconds) [B5]

| Queue size | heapx | heapq | sortedcontainers | heapdict |
|---|---|---|---|---|
| 1,000 | 0.013 | 0.185 | 0.016 | 0.023 |
| 10,000 | 0.015 | 1.793 | 0.018 | 0.045 |
| 100,000 | 0.021 | 20.718 | 0.027 | 0.073 |
| 250,000 | 0.026 | 52.773 | 0.034 | 0.093 |

A workload of 5,000 priority updates plus push/pop runs in 26 ms with `heapx`
and 52.8 s with `heapq`, a 2,036x difference at 250,000 tasks. `heapx` also
edges out the pure-Python structures (1.3x over `sortedcontainers`, 3.6x over
`heapdict`).

### 5.3 Scheduler throughput (operations per second) [B7]

| Queue size | heapx | heapq | speedup |
|---|---|---|---|
| 1,000 | 1,931,434 | 114,523 | 17x |
| 10,000 | 1,389,359 | 13,197 | 105x |
| 50,000 | 1,157,075 | 2,084 | 555x |
| 100,000 | 1,125,698 | 942 | 1,195x |

On the realistic mixed loop (40% enqueue, 40% dispatch, 20% boost), `heapx`
sustains over a million operations per second at every queue size, while
`heapq` throughput collapses to under a thousand per second at 100,000 tasks
because every boost triggers an O(n) re-heapify. The advantage grows with the
queue, from 17x at 1,000 to 1,195x at 100,000.

### 5.4 Where heapx does not win

The case study reports the operations `heapx` does not lead, rather than
hiding them:

- Single push [B2]: `heapq` is about 3x faster (0.07 vs 0.23 microseconds),
  because its push is a minimal C path.
- Single pop [B3]: `heapq` is roughly 2x faster.
- Batch push [B1]: `heapq` is faster in absolute terms across all sizes.
- Isolated replace at small sizes [B4]: the pure-Python Fibonacci heap beats
  `heapx` (0.19 vs 0.68 microseconds at 1,000), though it was only measured up
  to 50,000 and lacks the broader feature set.

The decisive `heapx` advantage is concentrated in the decrease-key-driven
benchmarks (B4, B5, B7), which are exactly the operations a realistic
scheduler performs most.

## 6. Why heapx for Task Scheduling

A scheduler that only enqueues and dispatches could use `heapq`. A realistic
scheduler also cancels expired tasks and boosts waiting ones, and those are
the operations `heapq` handles in O(n). `heapx` provides both as O(log n)
C-level primitives:

- `heapx.replace(..., indices=idx)` makes priority boosting O(log n), turning
  the 52.8 s replace-heavy workload into 26 ms.
- `heapx.remove(..., predicate=...)` performs deadline-based cancellation in a
  single C pass with no list rebuild.
- Native tuple comparison avoids per-comparison Python callbacks.

The feature matrix (`fig09`) summarizes the gap: `heapx` supports min and max
heaps, key functions, bulk push and pop, removal by index and by predicate,
decrease-key, merge, d-ary arity, GIL release, and SIMD, all in a C
extension. `heapq` supports only the min-heap basics. For scheduling
workloads dominated by priority changes, that difference is the difference
between a scheduler that scales and one that does not.

## 7. Reproducing the Results

### 7.1 Requirements

```
python >= 3.9
heapx >= 1.0.0
numpy
matplotlib
sortedcontainers
heapdict
fibonacci-heap-mod
```

`heapx` installs from conda:

```bash
conda install mukherjee08::heapx
```

### 7.2 Run

```bash
python run_all.py          # benchmarks then figures
python benchmark.py        # produces results.json
python plot_results.py     # produces figures/*.png (600 DPI)
```

## References

1. A. Silberschatz, P. B. Galvin, and G. Gagne, Operating System Concepts,
   10th ed., Wiley, 2018, Chapter 5 (CPU Scheduling).
2. C. L. Liu and J. W. Layland, "Scheduling Algorithms for Multiprogramming
   in a Hard-Real-Time Environment," Journal of the ACM 20(1), 1973.
3. G. S. Brodal, "Priority Queues with Decreasing Keys," FUN 2022.
4. M. Rocklin, "Dask: Parallel Computation with Blocked Algorithms and Task
   Scheduling," Proc. SciPy 2015.
5. A. Staffolani et al., "RLQ: Workload Allocation with Reinforcement
   Learning in Distributed Queues," IEEE Transactions on Parallel and
   Distributed Systems 34(3), 2023.
6. R. K. Clark, "Scheduling Dependent Real-Time Activities," CMU-CS-90-155,
   1990.
