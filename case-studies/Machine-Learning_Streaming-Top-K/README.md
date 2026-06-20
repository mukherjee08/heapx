# Case Study 5 — Machine Learning: Streaming Top-K

## 1. Introduction

This case study benchmarks `heapx` on streaming top-K selection, the
operation of keeping the K largest (or smallest) values seen so far while a
stream of N values flows past one at a time. Top-K selection is a building
block that shows up across machine learning: beam search keeps the K
best-scoring decoding hypotheses, k-nearest-neighbour search keeps the K
closest points, feature selection keeps the K highest-importance features,
and streaming anomaly detection keeps the K most anomalous observations.

The baselines are `heapq` (the CPython standard heap) and NumPy's batch
selection routines (`numpy.argpartition`, `numpy.partition`, `numpy.argsort`).
The study is organized around one primitive, the bounded-heap replace, and
then applies it to five ML workloads (k-nearest neighbours, feature
selection, anomaly detection, beam search, and sliding-window monitoring)
plus a parallel-heapify experiment that exercises `heapx`'s ability to
release the global interpreter lock.

Every experiment is seeded (`seed=42`), and all timings are the median of
five measured runs after two warm-up runs unless a module states otherwise.

## 2. The Core Primitive: Bounded-Heap Replace

### 2.1 The streaming top-K problem

Given a stream of N scores and a fixed budget K, report the K largest. The
naive approach (store all N, sort, take the top K) costs O(N log N) time and
O(N) memory, which is impossible when N is large or unbounded. The streaming
approach keeps only K values in memory.

The data structure is a min-heap of size K holding the current K largest
scores. Its root is the smallest of those K, that is, the current K-th
largest overall, and so it is the admission threshold. For each new score
`s`:

```
if s > heap[0]:        # s beats the weakest of the current top-K
    replace the root with s and sift down   # O(log K)
else:
    discard s                                # O(1), no heap touch
```

```
   incoming score s = 7.4
            |
            v
   compare with root (threshold)
   heap (min-heap of size K=4):
                 3.1   <- root = smallest kept = threshold
                /   \
             5.0     4.2
             /
           9.8
   s = 7.4 > 3.1  ->  evict 3.1, insert 7.4, sift down
   new root becomes 4.2 (the threshold rises)
```

Each accepted score costs O(log K) and each rejected score costs O(1), so a
stream of N scores costs O(N log K) overall. This is optimal for the
streaming setting (Munro and Paterson 1980): the threshold rises over time,
so most late-arriving scores are rejected in O(1) and never touch the heap.

### 2.2 The fused replace

Evicting the root and inserting a new value is naturally two operations
(pop then push). A fused replace overwrites the root and sifts down once,
saving one of the two heap traversals. `heapx.replace(heap, s, indices=0)`
does exactly this, and `heapq.heapreplace(heap, s)` is the stdlib
equivalent. In `streaming_topk.py`:

```python
heap = scores[:k].tolist()
heapx.heapify(heap)
for s in rest:
    if s > heap[0]:
        heapx.replace(heap, s, indices=0)   # fused: overwrite root, sift down
```

### 2.3 Experimental setup

| Parameter | Value |
|---|---|
| Stream size N | 10,000,000 |
| Heap size K | 1,000 default; varied 10 to 100,000 |
| Score distribution | N(0, 1) standard normal |
| Random seed | 42 |
| Timing | `time.perf_counter`, median of 5 runs after 2 warm-ups |

## 3. The Seven Performance Dimensions

The study measures `heapx` along seven axes (`README` section 3 in the
source tree, realized by `run_benchmarks.py` and `visualize.py`):

1. Bulk heapify of homogeneous float arrays.
2. Type-specialized heapify (float, int, str, tuple).
3. N-ary (d-ary) heap tuning (arity 2, 3, 4, 8).
4. Bulk top-K extraction.
5. Push throughput (single and bulk).
6. Parallel heapify with GIL release.
7. End-to-end streaming top-K.

Five later dimensions apply the primitive to ML tasks: fused-replace
microbenchmark, beam-search decoding, sliding-window monitoring, per-replace
latency distribution, and a speedup summary.

### 3.1 Bulk heapify

Building a heap from an unordered array is O(n) by Floyd's bottom-up method.
`heapx.heapify` runs this in C over a homogeneous float array, avoiding the
per-element Python object handling that `heapq.heapify` pays.

### 3.6 Parallel heapify and GIL release

`heapx.heapify(array, nogil=True)` extracts the raw C values from a
homogeneous array, releases the global interpreter lock, heapifies in pure C,
then reacquires the lock. Because the heavy work happens with the lock
released, multiple threads heapify different arrays at the same time. `heapq`
cannot do this: it holds the lock for every comparison. `parallel_topk.py`
distributes eight arrays of two million floats across a thread pool:

```python
# parallel_topk.py, _worker
barrier.wait()
for i in indices:
    heapx.heapify(arrays[i], nogil=use_nogil)
```

The barrier ensures all threads start together so the measured wall time
reflects genuine concurrency.

## 4. The ML Application Modules

### 4.1 k-Nearest Neighbours (`ml_knn.py`)

The selection phase of kNN finds the K smallest distances in a distance
array. The module heapifies the raw float distances as a min-heap and bulk-pops
the K smallest:

```python
heapx.heapify(d)
return heapx.pop(d, n=k)        # the K smallest, default min-heap
```

The baselines are `heapq.nsmallest(k, ...)`, `numpy.partition`, and
`numpy.sort`.

### 4.2 Feature Selection (`ml_feature_selection.py`)

Selecting the K highest feature-importance scores is a max-heap top-K. The
module heapifies as a max-heap and bulk-pops K, in both binary and arity-4
form:

```python
heapx.heapify(d, max_heap=True)
heapx.pop(d, n=K, max_heap=True)
# arity-4 variant:
heapx.heapify(d, max_heap=True, arity=4)
heapx.pop(d, n=K, max_heap=True, arity=4)
```

`heapx`'s native `max_heap=True` removes the manual key-negation trick
(`heapq.nlargest` or pushing `-score`) that `heapq` requires.

### 4.3 Streaming Anomaly Detection (`ml_anomaly_detection.py`)

Anomaly scores are computed as the L2 norm of each observation from the
origin. Normal points are drawn from N(0, 1) and injected anomalies from
N(5, 0.5), so anomalies have larger norms. A bounded min-heap of `(score,
index)` tuples keeps the top-K most anomalous, using the same fused-replace
pattern as the core primitive:

```python
heap = [(float(scores[i]), i) for i in range(k)]
heapx.heapify(heap)
for ...:
    if s > heap[0][0]:
        heapx.replace(heap, (s, i), indices=0)
```

The quality baseline is scikit-learn's `IsolationForest`. The module checks
precision@K and recall@K, which are identical for the heap and the forest,
so the only axis left to compare is speed.

### 4.4 Beam Search (`ml_beam_search.py`)

At each of T decoding steps, beam search scores K x V candidate
(hypothesis, token) pairs and keeps the K highest. The module builds a
max-heap over the candidate scores and bulk-pops K:

```python
scores = cand.tolist()
heapx.heapify(scores, max_heap=True)
top = heapx.pop(scores, n=k, max_heap=True)
```

Defaults: vocabulary V = 32,000, T = 50 steps, beam sizes 4 through 128. The
module also implements Gumbel-Top-K sampling (Kool et al. 2019) for sampling
sequences without replacement.

### 4.5 Sliding-Window Monitoring (`ml_sliding_window.py`)

Continuous top-K over a sliding window of the W most recent observations
requires expiring the element that leaves the window. The whole window is
kept as a max-heap of `(score, seq)` tuples, and the expiring element is
removed by object identity in O(log n):

```python
heapx.remove(heap, object=expired, max_heap=True)   # O(log n) inline removal
heapx.push(heap, entry, max_heap=True)
```

The `heapq` eager baseline must call `list.remove` followed by a full O(n)
`heapq.heapify` for each expiry; the `heapq` lazy baseline avoids that but
grows without bound.

## 5. Results

The numbers below are read from the committed JSON in `results/`. Where the
source README quotes slightly different figures, those came from a separate
re-run; the values here are the committed measured data. Speedups are
`heapq_time / heapx_time` unless stated.

### 5.1 Bulk heapify (homogeneous float, median ms)

| N | heapx | heapq | speedup |
|---|---|---|---|
| 10,000 | 0.039 | 0.141 | 3.65x |
| 100,000 | 0.714 | 1.639 | 2.29x |
| 1,000,000 | 9.693 | 17.920 | 1.85x |
| 5,000,000 | 59.811 | 94.470 | 1.58x |

`heapx` heapifies floats roughly 1.6x to 3.7x faster than `heapq`. The
advantage shrinks at large N as both become bound by memory bandwidth rather
than per-element overhead.

### 5.2 N-ary heap tuning (1,000,000 floats, heapify ms)

| Arity | heapify ms | speedup vs heapq binary (17.92 ms) |
|---|---|---|
| 2 | 10.823 | 1.66x |
| 3 | 9.518 | 1.88x |
| 4 | 7.755 | 2.31x |
| 8 | 6.368 | 2.81x |

Raising the arity flattens the tree, reducing levels and improving cache
locality because each node's children sit contiguously. Arity 8 heapifies a
million floats 2.81x faster than the stdlib binary heap.

### 5.3 Bulk top-K extraction (1,000,000 elements, max-heap)

| K | heapx ms | heapq ms | speedup |
|---|---|---|---|
| 1 | 11.64 | 4.39 | 0.38x |
| 1,000 | 14.02 | 7.79 | 0.56x |
| 10,000 | 16.62 | 23.28 | 1.40x |
| 50,000 | 28.00 | 113.93 | 4.13x |
| 100,000 | 40.60 | 183.58 | 4.52x |

For small K, `heapq.nlargest` wins because `heapx`'s bulk-pop path has fixed
setup cost that does not pay off. The crossover is near K = 5,000; beyond it
`heapx` pulls ahead, reaching 4.5x at K = 100,000. This is an honest,
workload-dependent result, and the figures show the crossover rather than
hiding it.

### 5.4 Parallel heapify (8 arrays x 2,000,000 floats, GIL release)

| Threads | nogil=True wall (s) | speedup | nogil=False wall (s) | speedup |
|---|---|---|---|---|
| 1 | 0.247 | 1.00x | 0.124 | 1.00x |
| 2 | 0.178 | 1.39x | 0.127 | 0.98x |
| 4 | 0.165 | 1.50x | 0.126 | 0.99x |
| 8 | 0.159 | 1.55x | 0.128 | 0.97x |

With `nogil=True`, adding threads cuts wall time because heapify runs in
parallel C. With `nogil=False` the lock is held throughout, so more threads
give no speedup (the curve is flat at 1.0x). This dimension demonstrates a
capability `heapq` does not have, rather than a raw per-call win.

### 5.5 End-to-end streaming top-K (N = 10,000,000, K = 1,000)

| Method | Wall (s) | Throughput (scores/s) |
|---|---|---|
| heapx | 0.5159 | 19,384,066 |
| heapq | 0.5164 | 19,363,746 |
| numpy (batch) | 0.0519 | 192,672,195 |

For the full stream, `heapx` and `heapq` reach near parity (1.001x), because
the rising threshold means almost all of the ten million scores are rejected
by the O(1) `s > heap[0]` guard and the heap is rarely touched. NumPy is
about 10x faster here, but it is a batch routine that needs the entire array
in memory at once, so it does not solve the streaming problem; it is included
as a ceiling, not a competitor.

### 5.6 Fused replace microbenchmark (N = 2,000,000, ns per accepted update)

| K | heapx replace | pop+push | heapq.heapreplace |
|---|---|---|---|
| 100 | 150.3 | 82.6 | 63.0 |
| 1,000 | 177.5 | 120.7 | 100.3 |
| 100,000 | 288.1 | 231.5 | 237.2 |

This is the study's most candid finding. On the isolated per-replace
operation, `heapq.heapreplace` and even a manual pop+push beat `heapx.replace`
at every tested K, with `heapx` approaching parity only at K = 100,000. The
`heapx` advantage in this case study lives in bulk heapify, large-K bulk
extraction, native max-heap and key support, d-ary tuning, and GIL release,
not in single-element replace latency.

### 5.7 Anomaly detection vs scikit-learn (end-to-end)

| Method | Time (ms) | Precision@K |
|---|---|---|
| heapx top-K | 6.4 | 1.0 |
| IsolationForest | 550.2 | 1.0 |

At equal detection quality (both reach precision 1.0 on this well-separated
data), the heap-based pipeline finishes 86.6x faster than the forest, because
selecting the top-K anomalies by score is far cheaper than fitting an
ensemble.

### 5.8 Feature selection (K = 100, top-K from F features)

| F | heapx ms | heapx arity-4 ms | heapq ms | speedup (arity-4) |
|---|---|---|---|---|
| 1,000 | 0.005 | 0.009 | 0.054 | 6.00x |
| 10,000 | 0.066 | 0.065 | 0.135 | 2.08x |
| 100,000 | 0.887 | 0.616 | 0.684 | 1.11x |
| 1,000,000 | 17.102 | 10.477 | 6.809 | 0.65x |

For small to moderate feature counts `heapx` leads, and the arity-4 variant
extends the lead. For very large F at small K, `heapq.nlargest` wins, again
the crossover behavior of section 5.3.

## 6. Figures

Core figures (`fig1` through `fig7`) cover heapify, type specialization,
arity tuning, bulk top-K, push throughput, parallel scaling, and the score
distribution. ML figures cover each application: `knn_*`, `fs_*`, `ad_*`
(anomaly detection, including precision/recall panels), `fig_beam_search_*`,
`fig_gumbel_topk.png`, `fig_sliding_window_scaling.png`,
`fig_replace_vs_popush.png`, `fig_latency_cdf.png` (per-replace latency CDF
with p50/p99 markers, following Dean and Barroso 2013), and
`fig_speedup_summary.png`. All are 600 DPI with a colour-blind-safe palette
(heapx blue, heapq orange, numpy green).

## 7. Why heapx for Machine-Learning Top-K

`heapx` is the strongest choice when the workload is one of:

- Bulk heapify of large homogeneous numeric arrays (1.6x to 3.7x over
  `heapq`), as in the kNN and feature-selection selection phases.
- Large-K bulk extraction, where `heapx` overtakes `heapq` past the
  K ~ 5,000 crossover and reaches 4.5x at K = 100,000.
- Native max-heap and key support, removing the negation and tuple-wrapping
  tricks `heapq` forces on max-oriented ML scoring.
- d-ary tuning, where arity 8 gives a further 1.5x on heapify by improving
  cache locality.
- Parallel heapify, where GIL release lets multiple threads build heaps at
  once, which `heapq` cannot do.

`heapq` remains preferable for single-element replace latency and for
small-K extraction, and NumPy is faster when the entire dataset fits in
memory and streaming is not required. The benchmarks report these cases
plainly so the choice can be made on the actual workload.

## 8. Reproducing the Results

### 8.1 Requirements

```
heapx >= 1.0.0
numpy
matplotlib
scikit-learn
```

`heapx` installs from conda:

```bash
conda install mukherjee08::heapx
```

### 8.2 Run

```bash
python run_all.py                  # full pipeline: all benchmarks then figures
python run_all.py --only ml_knn    # run a single stage
python run_all.py --skip parallel_topk   # skip a stage
python run_benchmarks.py           # the seven core dimensions
python visualize.py                # figures from cached results
```

Results land in `results/` and figures in `figures/`.

## References

1. J. I. Munro and M. S. Paterson, "Selection and Sorting with Limited
   Storage," Theoretical Computer Science 12, pp. 315-323, 1980.
2. M. Freitag and Y. Al-Onaizan, "Beam Search Strategies for Neural Machine
   Translation," Proc. First Workshop on Neural Machine Translation, 2017.
3. S. Wiseman and A. M. Rush, "Sequence-to-Sequence Learning as Beam-Search
   Optimization," EMNLP 2016.
4. W. Kool, H. Van Hoof, and M. Welling, "Stochastic Beams and Where to Find
   Them: The Gumbel-Top-k Trick for Sampling Sequences Without Replacement,"
   ICML 2019.
5. K. Mouratidis, S. Bakiras, and D. Papadias, "Continuous Monitoring of
   Top-k Queries over Sliding Windows," SIGMOD 2006.
6. J. S. Vitter, "External Memory Algorithms and Data Structures: Dealing
   with Massive Data," ACM Computing Surveys 33(2), pp. 209-271, 2001.
7. J. Dean and L. A. Barroso, "The Tail at Scale," Communications of the ACM
   56(2), pp. 74-80, 2013.
8. C. R. Harris et al., "Array Programming with NumPy," Nature 585,
   pp. 357-362, 2020.
9. T. H. Cormen, C. E. Leiserson, R. L. Rivest, and C. Stein, Introduction
   to Algorithms, 3rd ed., Chapter 6 (Heapsort), MIT Press, 2009.
