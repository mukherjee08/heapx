# Case Study 4 — Real-Time Systems: Discrete-Event Simulation

## 1. Introduction

This case study benchmarks the pending-event-set (PES) of a discrete-event
simulation (DES) across seven Python priority-queue implementations, with
`heapx` as the module under evaluation. A DES advances a model not by a
fixed clock tick but by jumping from one scheduled event to the next. The
data structure that holds those scheduled future events, ordered by their
timestamps, is the single hottest component of the simulator. Every event
the simulation processes touches it at least twice (one removal of the
imminent event, one insertion of the events that event spawns), so the
asymptotic cost of its operations sets the asymptotic cost of the whole run.

The seven engines are `heapx`, `heapq` (the CPython standard binary heap),
`heapq_lazy` (the lazy-deletion pattern from the Python documentation),
`sortedcontainers.SortedList`, `heapdict`, `pqdict`, and the thread-safe
`queue.PriorityQueue`. The study isolates the two operations that separate
a plain heap from an event-set heap: cancelling a scheduled event (removing
an arbitrary interior element) and rescheduling one (changing an interior
element's key). On these two operations the implementations diverge by more
than three orders of magnitude.

All randomness is seeded (`seed=42`) so every figure and number reproduces
exactly.

## 2. Background: Discrete-Event Simulation

### 2.1 What a discrete-event simulation is

A simulation models a system whose state changes only at discrete instants
called events. Between events nothing of interest happens, so the simulator
skips the idle gaps entirely. Examples of events: a packet arrives at a
router, a customer joins a queue, a machine finishes a job, a sensor fires.

A DES keeps three things:

- A simulation clock `t` holding the current virtual time.
- A pending event set (PES): all events scheduled for some future time,
  ordered by timestamp.
- An event routine for each event type that updates state and may schedule
  new future events.

The main loop is short and never changes:

```
while PES is not empty:
    e  <- remove the event with the smallest timestamp   (EXTRACT-MIN)
    t  <- e.timestamp                                     (advance the clock)
    run e's event routine, which may:
        schedule new events    (INSERT)
        cancel pending events  (DELETE arbitrary element)
        reschedule events      (DECREASE/INCREASE-KEY)
```

```
   virtual time ->
   t0      t1        t2   t3              t4
   |       |         |    |               |
   v       v         v    v               v
 [arrive][service][arrive][depart] ..... [arrive]
   \____________ pending event set, kept sorted by time ___________/
        ^ the simulator always pulls the leftmost (earliest) event
```

The PES therefore needs exactly three operations: insert an event,
extract the minimum-timestamp event, and (for realistic models) remove or
re-key an arbitrary interior event. This is the priority-queue interface,
and choosing its implementation is the central engineering decision in a
simulator. Jones (1986) made this the subject of the foundational empirical
comparison that this case study follows.

### 2.2 The hold model

To benchmark a PES without committing to one application, the literature
uses the hold model (Jones 1986). After filling the queue to a target
size, each iteration performs one extract-min immediately followed by one
insert. The queue size stays roughly constant, so the measurement reflects
steady-state behavior rather than transient fill-up or drain. This is the
"classic hold" experiment.

This case study uses the extended hold model: the classic pop-then-push,
plus two extensions drawn from real simulators.

- Cancel: with probability `cancel_rate`, an already-scheduled event is
  removed before it ever fires. Example: a timeout is cancelled because the
  awaited reply arrived first.
- Reschedule: with probability `reschedule_rate`, a pending event's
  timestamp is shifted. Example: a job's estimated completion time is
  revised.

### 2.3 The arrival process

Event timestamps are generated as a Poisson process, the standard arrival
model in DES (Jones 1986; Brown 1988; Ronngren and Ayani 1997). A Poisson
process with rate lambda has inter-arrival times drawn independently from
an exponential distribution with mean `1/lambda`. The code uses `lambda=1`:

```python
# simulation.py, _make_workload
rng = np.random.default_rng(seed)
ts = np.cumsum(rng.exponential(1.0, size=n_events + steady_state_size))
```

`rng.exponential(1.0, ...)` draws the gaps; `np.cumsum` turns gaps into
absolute, strictly increasing timestamps. The exponential distribution is
memoryless, which is what makes the resulting timestamps a true Poisson
process. Section 5 shows the empirical inter-arrival histogram matching the
exponential probability density (figure `fig09_inter_arrival.png`).

The reschedule shifts are themselves exponential with mean 0.5
(`rng.exponential(0.5, ...)`), and the cancel/reschedule decisions are
uniform draws compared against the configured rates.

### 2.4 The three phases of a simulation run

The traced run (`run_heapx_traced` in `simulation.py`) records the queue
size at every operation and labels three phases that every finite DES
exhibits:

```
  queue
  size
   ^
   |                ________________________
   |               /  steady state           \
   |              /  (pop = push, qsize ~ S)   \
   |   buildup   /                              \   drain
   |   (push     /                                \ (pop only,
   |    only) ->/                                  \<- qsize -> 0)
   |          _/                                    \_
   +---------------------------------------------------------> virtual time
       phase 1            phase 2                     phase 3
```

1. Buildup (transient warm-up): starting from an empty PES, events are
   pushed one at a time until the queue reaches `steady_state_size`. No pops
   occur, so the queue grows linearly. This is the transient phase of the
   Up/Down model (Ronngren and Ayani 1993; Tang, Perumalla, and Fujimoto
   2005). These pushes are tagged `init_push` so they do not distort the
   steady-state operation-mix figure.
2. Steady state: the classic hold loop (pop, push, and probabilistic
   cancel/reschedule). Queue size fluctuates around `steady_state_size`.
3. Drain: the arrival stream is exhausted, so only pops remain and the
   queue decays linearly to empty. The boundary into this phase is locked
   the first iteration that completes with no refill push.

In the shipped trace (`steady_state_size = 250,000`), the buildup ends at
sample index 250,000 and the steady/drain boundary falls at index 430,801,
matching the recorded `phase_boundaries`.

## 3. The Priority-Queue Operations and Their Costs

### 3.1 The interface

| Operation | Meaning in DES terms |
|---|---|
| INSERT(x) | Schedule a new future event |
| EXTRACT-MIN() | Remove and return the imminent (earliest) event |
| REMOVE(i) | Cancel the event currently at position `i` |
| REPLACE(i, k) | Reschedule the event at position `i` to new time `k` |

A binary heap stores the events in an array with the heap property: every
parent's key is no larger than its children's. INSERT and EXTRACT-MIN are
O(log n) because they walk one root-to-leaf path, sifting an element up or
down. The difficulty is REMOVE and REPLACE of an interior element.

### 3.2 Why the stdlib `heapq` cancel is O(n)

`heapq` exposes no interior remove. The only correct way to delete an
arbitrary element with the stdlib primitives is to overwrite it, drop the
tail, and rebuild the entire heap:

```python
# simulation.py, run_heapq_simulation  (cancel)
heap[idx] = heap[-1]; heap.pop(); heapq.heapify(heap); cancel_c += 1
```

`heapq.heapify` is O(n): it re-establishes the heap property over all n
elements. So every cancel costs O(n). Reschedule has the same problem; the
key changes in place and the whole array must be re-heapified:

```python
# simulation.py, run_heapq_simulation  (reschedule)
heap[idx] = heap[idx] + float(w["resched_deltas"][i])
heapq.heapify(heap); resched_c += 1
```

`queue.PriorityQueue` wraps `heapq` and inherits the identical O(n) cancel
by reaching into its backing list. The lazy-deletion engine (`heapq_lazy`)
avoids the re-heapify by marking entries as removed and skipping them at
pop time, which trades O(n) cancel for unbounded heap growth and a
bookkeeping dictionary.

### 3.3 How `heapx` does it in O(log n)

`heapx` supports interior remove and replace as first-class operations.
Removing the element at a known index repairs the heap by sifting only the
element that backfills the hole, touching one root-to-leaf path:

```python
# simulation.py, run_heapx_simulation
heapx.heapify(heap)                                    # build PES, O(n) once
...
heapx.pop(heap); pop_c += 1                            # EXTRACT-MIN, O(log n)
heapx.push(heap, float(w["timestamps"][nxt])); ...     # INSERT, O(log n)
...
idx = int(w["cancel_indices"][i]) % len(heap)
heapx.remove(heap, indices=idx); cancel_c += 1         # CANCEL, O(log n)
...
heapx.replace(heap, heap[idx] + float(w["resched_deltas"][i]), indices=idx)
                                                       # RESCHEDULE, O(log n)
```

The `indices=` argument names the slot to act on. `heapx.remove` moves the
last element into that slot and sifts it (up or down as needed);
`heapx.replace` writes the new key and sifts. Both are O(log n) because a
single path is repaired rather than the whole array. The complete cost
table:

| Module | Type | Cancel (remove) | Reschedule (replace) | C extension |
|---|---|---|---|---|
| heapx | C-extension heap | O(log n) | O(log n) | Yes |
| heapq | stdlib binary heap | O(n) re-heapify | O(n) re-heapify | Yes |
| heapq_lazy | heapq + lazy deletion | O(1) mark | O(1) mark + O(log n) push | Yes |
| sortedcontainers | pure-Python sorted list | O(log n) | O(log n) | No |
| heapdict | pure-Python indexed heap | O(log n) | O(log n) | No |
| pqdict | pure-Python indexed heap | O(log n) | O(log n) | No |
| PriorityQueue | thread-safe heapq wrapper | O(n) | O(n) | No |

The pure-Python O(log n) structures share `heapx`'s asymptotics but pay a
large constant factor per operation because each comparison and pointer
chase runs in interpreted Python rather than compiled C.

## 4. Code Architecture

### 4.1 File overview

| File | Role |
|---|---|
| `simulation.py` | The seven DES engines, the workload generator, and the traced run |
| `benchmark.py` | The four benchmarks, parallelized across worker processes |
| `plot_results.py` | Figure generation (600 DPI PNGs) |
| `run_all.py` | Orchestrator: benchmark then plot |
| `results.json` | A standalone heapx-vs-heapq run |
| `bench_results.json` | The full benchmark output |

### 4.2 The workload generator (`_make_workload`)

One generator produces a shared, seeded array bundle so every engine sees
byte-identical input. It returns the Poisson `timestamps`, the uniform
`cancel_rolls` and `resched_rolls` that drive the probabilistic branches,
the exponential `resched_deltas`, and `cancel_indices` (the interior slot
targeted by each cancel and reschedule). Reusing one index array for both
cancel and reschedule keeps every engine comparing the same decisions.

### 4.3 The engines

Each `run_<module>_simulation` function shares one skeleton: build the PES
to `steady_state_size`, then loop `n_events` times doing pop, refill push,
probabilistic cancel (with a refill push to hold the size steady), and
probabilistic reschedule. The functions differ only in which library calls
implement those four operations, which is exactly the variable under study.
`ALL_ENGINES` maps the seven names to these functions.

### 4.4 The four benchmarks (`benchmark.py`)

1. Cancellation-rate sweep: all seven engines at a fixed queue of 250,000,
   sweeping the cancel rate over `[0.0, 0.05, ..., 0.50]` (reschedule fixed
   at 0.05). Shows how throughput responds as cancels become more frequent.
2. Queue-size scaling: all engines at 30% cancel, sweeping queue size over
   `[1,000 ... 1,000,000]`. Shows how the O(n)-versus-O(log n) gap widens
   with n.
3. Per-operation latency micro-benchmark: isolates push, pop, remove, and
   replace and times each in nanoseconds for all seven modules at queue
   250,000.
4. DES trace (heapx only): records queue size and operation type over a
   full run to produce the phase and operation-mix figures.

The sweeps run engines in parallel worker processes (`multiprocessing.Pool`).

### 4.5 Figures

| File | Title |
|---|---|
| `fig01_cancel_sweep.png` | Simulation Throughput Under Varying Cancellation Rates |
| `fig02_scaling.png` | Throughput Scaling with Pending Event Set Size |
| `fig03_speedup_cancel.png` | Relative Speedup as a Function of Cancellation Rate |
| `fig04_speedup_scaling.png` | Relative Speedup as a Function of Queue Size |
| `fig05_latency_bars.png` | Per-Operation Latency Across Priority Queue Implementations |
| `fig06_complexity.png` | Asymptotic Cost of Event Cancellation and Rescheduling |
| `fig07_queue_evolution.png` | Pending Event Set Size Over Simulation Time |
| `fig08_operation_mix.png` | Heap Operation Mix |
| `fig09_inter_arrival.png` | Inter-Event Time Distribution (PDF + CDF with Exponential Fit) |
| `fig11_e2e_timing.png` | End-to-End DES Execution Time by Priority Queue Module |

(`fig06` draws the theory curves `O(log n)` for heapx remove/replace and
`O(n)` for the heapq scan-and-re-heapify cancel, with a vertical reference
at the benchmark queue size of 250,000.)

## 5. Results

The numbers below are read directly from the committed `results.json` and
`bench_results.json`. The benchmark file was produced in quick mode
(`repeats=1`), so its scaling sweep carries five queue sizes rather than the
full eight, and its confidence intervals collapse to the median. The
standalone `results.json` run uses `n_events=200,000`, `queue_size=50,000`,
`cancel_rate=0.30`, `reschedule_rate=0.05`.

### 5.1 Headline end-to-end run (`results.json`)

| Engine | Elapsed (s) | Throughput (events/s) |
|---|---|---|
| heapx | 0.1235 | 1,556,513 |
| heapq | 50.8885 | 3,778 |

Recorded speedup: 411.99x. Both engines processed identical work (192,256
pops, 200,000 pushes, 57,744 cancels, 9,561 reschedules). The only
difference is that `heapq` pays O(n) per cancel and per reschedule while
`heapx` pays O(log n).

### 5.2 Per-operation latency (nanoseconds, queue 250,000)

| Engine | push | pop | remove | replace |
|---|---|---|---|---|
| heapx | 46.5 | 229.4 | 285.4 | 1,031.6 |
| heapq | 30.3 | 212.8 | 2,689,257 | 2,685,584 |
| heapq_lazy | 129.1 | 788.1 | 1,175,935 | 1,536,108 |
| sortedcontainers | 609.2 | 270.9 | 1,557.1 | 3,589.9 |
| heapdict | 395.2 | 4,126.3 | 4,308,634 | 4,713.2 |
| pqdict | 503.9 | 3,299.0 | 7,645,561 | 3,356.0 |
| PriorityQueue | 304.7 | 504.6 | 2,670,635 | 2,726,675 |

The story is in the `remove` column. `heapx` removes an interior element in
285 ns. `heapq` takes 2.69 ms, roughly 9,400x longer, because it rebuilds a
250,000-element heap on every call. The pure-Python O(log n) structures
(`sortedcontainers` at 1,557 ns) avoid the asymptotic blowup but run about
5x slower than `heapx` from interpreter overhead. On the simple push and
pop, `heapq` is marginally faster than `heapx` (30 ns vs 47 ns push); the
advantage of `heapx` is entirely in the interior operations that a real
event set demands.

### 5.3 Cancellation-rate sweep (median events/s, queue 250,000)

| cancel rate | heapx | heapq | sortedcontainers |
|---|---|---|---|
| 0.00 | 978,420 | 1,810 | 334,630 |
| 0.10 | 527,144 | 538 | 289,070 |
| 0.30 | 521,055 | 194 | 185,735 |
| 0.50 | 435,944 | 128 | 276,237 |

At zero cancels `heapx` already leads `heapq` by about 540x (the gap comes
from the reschedules, which stay at 5%). As the cancel rate climbs, `heapq`
throughput collapses toward 130 events/s while `heapx` stays in the hundreds
of thousands, widening the gap past 3,400x at 50% cancels.

### 5.4 Queue-size scaling (median events/s, 30% cancel)

| queue size | heapx | heapq | heapx/heapq |
|---|---|---|---|
| 1,000 | 1,920,240 | 126,367 | 15x |
| 10,000 | 1,306,307 | 11,794 | 111x |
| 50,000 | 960,250 | 1,527 | 629x |
| 250,000 | 632,620 | 302 | 2,095x |

This is the asymptotic prediction made visible. The O(n) cancel makes
`heapq` throughput fall roughly in proportion to the queue size, so each
10x increase in n multiplies the `heapx` advantage by about the same factor.
The `heapx` curve declines only with `log n`.

### 5.5 End-to-end timing across all engines (`e2e_timing`)

For a run of 50,000 events at queue 250,000:

| Engine | Elapsed (s) | Slowdown vs heapx |
|---|---|---|
| heapx | 0.031 | 1.0x |
| sortedcontainers | 0.102 | 3.3x |
| PriorityQueue | 47.62 | 1,550x |
| heapdict | 77.68 | 2,530x |
| heapq | 97.50 | 3,175x |
| pqdict | 168.47 | 5,486x |

`sortedcontainers` is the only competitor within one order of magnitude,
again confirming that the right asymptotics (O(log n) interior remove)
matter more than the implementation language, and that `heapx` wins by
having both.

## 6. Why heapx for Discrete-Event Simulation

A simulator's PES must support cancel and reschedule, not just insert and
extract-min, because real models cancel timeouts and revise schedules
constantly. The stdlib `heapq` forces a choice between two bad options: pay
O(n) per cancel (the re-heapify pattern, which the scaling results show
becomes ruinous past a few thousand pending events) or adopt lazy deletion
(which grows the heap without bound and needs a side dictionary). `heapx`
removes the dilemma by providing O(log n) interior remove and replace
directly in C.

The practical consequences:

- Throughput stays high as the model scales. The 2,095x advantage at a
  250,000-event queue means a simulation that finishes in seconds with
  `heapx` would take over half an hour with `heapq`.
- The heap stays bounded. Unlike lazy deletion, `heapx.remove` shrinks the
  array, so memory tracks the live event count rather than the cumulative
  cancel count.
- One data structure covers the whole interface. There is no need to bolt a
  position-tracking dictionary onto a plain heap to get interior operations.

For models with few or no cancels, `heapq` remains a reasonable choice and is
marginally faster on bare push/pop. The case for `heapx` is precisely the
case of a realistic event set, where interior mutation is frequent.

## 7. Reproducing the Results

### 7.1 Requirements

```
heapx >= 1.0.0
numpy
matplotlib
sortedcontainers
heapdict
pqdict
```

`heapx` installs from conda:

```bash
conda install mukherjee08::heapx
```

### 7.2 Run

```bash
python run_all.py                # full pipeline (10M events, 250K queue)
python run_all.py -q             # quick debug run (reduced events)
python benchmark.py --repeats 3  # benchmarks only
python plot_results.py           # figures only, from cached data
```

`run_all.py` writes `bench_results.json` and the figures into `figures/`.
The standalone two-engine comparison is reproduced with
`python simulation.py` (defaults to 10M events; pass `--events` and
`--queue-size` to match `results.json`).

## References

1. D. W. Jones, "An Empirical Comparison of Priority-Queue and Event-Set
   Implementations," Communications of the ACM 29(4), pp. 300-311, 1986.
2. R. Brown, "Calendar Queues: A Fast O(1) Priority Queue Implementation for
   the Simulation Event Set Problem," Communications of the ACM 31(10),
   pp. 1220-1227, 1988.
3. R. Ronngren and R. Ayani, "A Comparative Study of Parallel and Sequential
   Priority Queue Algorithms," ACM Transactions on Modeling and Computer
   Simulation 7(2), 1997.
4. R. Ronngren and R. Ayani, the Up/Down access model for transient-phase
   priority-queue benchmarking, 1993.
5. J. Tang, K. Perumalla, and R. Fujimoto, analysis of the transient phase
   in discrete-event simulation event-set benchmarks, 2005.
