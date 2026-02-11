# heapx — Ultra-Optimized Heap Operations for Python

[![PyPI version](https://badge.fury.io/py/heapx.svg)](https://badge.fury.io/py/heapx)
[![Python Support](https://img.shields.io/pypi/pyversions/heapx.svg)](https://pypi.org/project/heapx/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`heapx` is a single-file C extension for Python that implements heap operations with explicit, performance-driven design choices at every level of the implementation. The module provides six public API functions — `heapify`, `push`, `pop`, `remove`, `replace`, and `merge` — each backed by a multi-tier dispatch system that selects the optimal algorithm at runtime based on data structure type, heap size, arity, key function presence, element type homogeneity, and GIL-release eligibility.

The implementation delivers its performance through five concrete mechanisms:

1. **Floyd's bottom-up heapify with arity specialization** (binary, ternary, quaternary, octonary) — reduces comparisons by ~25% versus standard top-down heapify and eliminates modulo/division overhead through bit-shift parent/child calculations for power-of-two arities.
2. **Precomputed key caching with vectorcall** — computes all keys in a single O(n) pass and caches them in a stack-allocated or heap-allocated array, reducing key function calls from O(n log n) to O(n) during heapify.
3. **Homogeneity detection and type-specialized paths** — SIMD-accelerated type pointer scanning (AVX2: 4 pointers/cycle, SSE2/NEON: 2 pointers/cycle) detects uniform int/float/string arrays and routes to C-native comparison loops that bypass `PyObject_RichCompareBool` entirely.
4. **GIL-releasing computation** — for homogeneous numeric arrays, the module extracts raw C values, releases the GIL, performs the entire heapify/pop in pure C, then reacquires the GIL and permutes the Python objects using cycle-following — enabling true multi-threaded parallelism.
5. **Stack-first memory allocation** — key arrays (≤128 elements) and value arrays (≤2,048 elements) use stack buffers (`KEY_STACK_SIZE=128`, `VALUE_STACK_SIZE=2048`) to avoid `malloc`/`free` overhead for the common case.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
  - [heapify](#1-heapify)
  - [push](#2-push)
  - [pop](#3-pop)
  - [remove](#4-remove)
  - [replace](#5-replace)
  - [merge](#6-merge)
- [Dispatch Architecture](#dispatch-architecture)
  - [Heapify Dispatch](#heapify-dispatch)
  - [Push Dispatch](#push-dispatch)
  - [Pop Dispatch](#pop-dispatch)
  - [Remove Dispatch](#remove-dispatch)
  - [Replace Dispatch](#replace-dispatch)
  - [Merge Dispatch](#merge-dispatch)
- [Optimization Layers](#optimization-layers)
  - [Fast Comparison Paths](#fast-comparison-paths)
  - [Homogeneous Type Detection](#homogeneous-type-detection)
  - [SIMD Acceleration](#simd-acceleration)
  - [GIL-Releasing Computation](#gil-releasing-computation)
  - [Prefetching and Cache Optimization](#prefetching-and-cache-optimization)
  - [Stack-First Memory Allocation](#stack-first-memory-allocation)
  - [Vectorcall Key Invocation](#vectorcall-key-invocation)
- [Algorithmic Foundations](#algorithmic-foundations)
- [Memory Safety](#memory-safety)
- [Platform Support](#platform-support)
- [Advanced Usage](#advanced-usage)

---

## Installation

```bash
pip install heapx
```

**Requirements:** Python ≥ 3.9, C compiler (GCC, Clang, or MSVC).

When installed via `pip`, the extension compiles with `-O3 -march=native -mtune=native -flto -fno-math-errno -fno-signed-zeros` (GCC/Clang) or `/O2 /Ot /GL /fp:precise` (MSVC), enabling full native CPU optimization. Conda builds use portable baselines (`-march=x86-64-v2` on x86-64, no arch flags on ARM64).

---

## Quick Start

```python
import heapx

# Min-heap (default)
data = [5, 2, 8, 1, 9, 3, 7]
heapx.heapify(data)
# data is now [1, 2, 3, 5, 9, 8, 7]

# Max-heap — native support, no negation needed
data = [5, 2, 8, 1, 9]
heapx.heapify(data, max_heap=True)
# data[0] is 9

# Push single item
heapx.push(data, 6, max_heap=True)

# Push bulk items (list detected automatically)
heapx.push(data, [10, 11, 12], max_heap=True)

# Pop root
largest = heapx.pop(data, max_heap=True)  # returns 12

# Pop top-k
top3 = heapx.pop(data, n=3, max_heap=True)  # returns [11, 10, 9]

# Custom key function — keys cached in O(n)
tasks = [{"name": "low", "pri": 10}, {"name": "high", "pri": 1}]
heapx.heapify(tasks, cmp=lambda x: x["pri"])
next_task = heapx.pop(tasks, cmp=lambda x: x["pri"])
# next_task is {"name": "high", "pri": 1}

# Ternary heap — 37% reduced tree height
data = list(range(100000, 0, -1))
heapx.heapify(data, arity=3)

# Remove by index with O(log n) maintenance
data = list(range(10))
heapx.heapify(data)
heapx.remove(data, indices=0)  # removes root (0)

# Remove by predicate
heapx.remove(data, predicate=lambda x: x > 7)

# Replace root
heapx.replace(data, 99, indices=0)

# Merge multiple heaps — O(N) concatenation + heapify
merged = heapx.merge([1, 3, 5], [2, 4, 6], [0, 7])
# merged is a valid min-heap containing all 8 elements

# GIL-releasing heapify for multi-threaded workloads
floats = [float(x) for x in range(1000000)]
heapx.heapify(floats, nogil=True)  # releases GIL during pure-C computation
```

---

## API Reference

All six functions share a common parameter structure. Parameters `max_heap`, `cmp`, `arity`, and `nogil` have consistent semantics across the entire API.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_heap` | `bool` | `False` | `False` = min-heap (smallest at root), `True` = max-heap (largest at root) |
| `cmp` | `callable` or `None` | `None` | Key function: elements compared via `cmp(x)` instead of `x` directly |
| `arity` | `int` ≥ 1 | `2` | Branching factor. 1=sorted list, 2=binary, 3=ternary, 4=quaternary, 8=octonary, up to 64 |
| `nogil` | `bool` | `False` | When `True` and data is homogeneous int/float, releases GIL during pure-C computation |


### 1. `heapify`

```python
heapx.heapify(heap, max_heap=False, cmp=None, arity=2, nogil=False)
```

Transforms a mutable sequence into a valid heap in-place. Uses Floyd's bottom-up algorithm (Wegener 1993 variant) which descends to a leaf comparing only children, then bubbles up — reducing comparisons by ~25% versus standard sift-down heapify.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `heap` | `list` or sequence | *(required)* | Mutable sequence to heapify. Lists use optimized direct-pointer paths; other sequences use `PySequence_GetItem`/`SetItem`. |
| `max_heap` | `bool` | `False` | Heap ordering direction. |
| `cmp` | `callable` or `None` | `None` | Key function. When provided, all keys are precomputed in a single O(n) pass and cached. |
| `arity` | `int` | `2` | Branching factor (1–64). Specialized implementations exist for 1, 2, 3, 4, and 8. |
| `nogil` | `bool` | `False` | Release GIL during computation for homogeneous int/float arrays. |

**Complexity:** O(n) comparisons via Floyd's bottom-up construction.

**Dispatch logic:** Heapify uses a two-phase dispatch. Phase 1 attempts homogeneous type-specialized paths (int, float, string) with optional GIL release. Phase 2 falls back to generic paths selected by arity and key function presence. See [Heapify Dispatch](#heapify-dispatch) for the complete decision tree.

**Examples:**

```python
# Binary min-heap (default) — Floyd's bottom-up, O(n)
data = [5, 3, 8, 1, 2]
heapx.heapify(data)
assert data[0] == 1  # smallest at root

# Max-heap — same algorithm, reversed comparisons
data = [5, 3, 8, 1, 2]
heapx.heapify(data, max_heap=True)
assert data[0] == 8  # largest at root

# Ternary heap — tree height is log₃(n) vs log₂(n), fewer sift levels
# For n=100000: binary=17 levels, ternary=11 levels (37% reduction)
data = list(range(100000))
heapx.heapify(data, arity=3)

# Key function — keys computed once in O(n), not O(n log n)
records = [{"id": i, "priority": 100 - i} for i in range(1000)]
heapx.heapify(records, cmp=lambda r: r["priority"])
assert records[0]["priority"] == 0  # lowest priority at root

# GIL-releasing path — enables parallel heapify in multi-threaded code
import threading
floats_a = [float(x) for x in range(500000)]
floats_b = [float(x) for x in range(500000)]
t1 = threading.Thread(target=heapx.heapify, args=(floats_a,), kwargs={"nogil": True})
t2 = threading.Thread(target=heapx.heapify, args=(floats_b,), kwargs={"nogil": True})
t1.start(); t2.start(); t1.join(); t2.join()
# Both heapified concurrently — GIL released during pure-C phase

# Arity=1 produces a sorted list (uses Python's Timsort internally)
data = [5, 3, 8, 1, 2]
heapx.heapify(data, arity=1)
assert data == [1, 2, 3, 5, 8]

# Arity=1 with max_heap produces reverse-sorted list
data = [5, 3, 8, 1, 2]
heapx.heapify(data, arity=1, max_heap=True)
assert data == [8, 5, 3, 2, 1]
```

---

### 2. `push`

```python
heapx.push(heap, items, max_heap=False, cmp=None, arity=2, nogil=False)
```

Inserts one or more items into a heap, maintaining the heap property. Detects single vs. bulk insertion automatically: if `items` is a `list`, it is treated as a batch of items to insert; all other types (including tuples, strings, and bytes) are treated as a single item.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `heap` | `list` or sequence | *(required)* | Existing heap to insert into. |
| `items` | any or `list` | *(required)* | Single item, or a `list` of items for bulk insertion. |
| `max_heap` | `bool` | `False` | Heap ordering direction. |
| `cmp` | `callable` or `None` | `None` | Key function for comparisons. |
| `arity` | `int` | `2` | Branching factor (1–64). |
| `nogil` | `bool` | `False` | Used in bulk push path when `k ≥ n` triggers full re-heapify. |

**Complexity:** O(log n) per single insert. Bulk insert: O(k log n) for k items via individual sift-ups, or O(n+k) when k ≥ n (triggers full re-heapify).

**Fast path:** When called as `push(heap, item)` with no keyword arguments, a zero-overhead inline path bypasses all argument parsing and performs a direct binary min-heap sift-up using `PyObject_RichCompareBool`. This is the common case and saves ~20ns per call.

**Bulk optimization:** When `k ≥ n` (number of new items exceeds current heap size) or `n = 0` (empty heap), push delegates to the full heapify dispatch (including homogeneous/SIMD/nogil paths) rather than performing k individual sift-ups, since O(n+k) heapify is asymptotically faster than O(k log(n+k)) individual insertions.

**Examples:**

```python
data = [1, 3, 5]
heapx.heapify(data)

# Single push — O(log n) sift-up
heapx.push(data, 2)
assert data[0] == 1  # heap property maintained

# Bulk push — list triggers batch mode
heapx.push(data, [0, -1, -2])
assert data[0] == -2  # new minimum at root

# Push with key function
tasks = []
heapx.push(tasks, {"name": "a", "pri": 5}, cmp=lambda x: x["pri"])
heapx.push(tasks, {"name": "b", "pri": 1}, cmp=lambda x: x["pri"])
assert tasks[0]["pri"] == 1

# Ternary heap push
data = [1, 2, 3, 4, 5]
heapx.heapify(data, arity=3)
heapx.push(data, 0, arity=3)
assert data[0] == 0

# Bulk push into empty heap — triggers O(n) heapify instead of n × O(log n)
data = []
heapx.push(data, list(range(10000, 0, -1)))
assert data[0] == 1
```

---

### 3. `pop`

```python
heapx.pop(heap, n=1, max_heap=False, cmp=None, arity=2, nogil=False)
```

Removes and returns the top element(s) from the heap. When `n=1`, returns a single item. When `n>1`, returns a list of the top n items in heap-priority order.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `heap` | `list` or sequence | *(required)* | Heap to pop from. |
| `n` | `int` | `1` | Number of items to pop. Must be ≥ 1. |
| `max_heap` | `bool` | `False` | Heap ordering direction. |
| `cmp` | `callable` or `None` | `None` | Key function for comparisons. |
| `arity` | `int` | `2` | Branching factor (1–64). |
| `nogil` | `bool` | `False` | Release GIL during bulk pop for homogeneous int/float arrays. |

**Complexity:** O(log n) per pop. Bulk pop of k items: O(k log n).

**Fast path:** When called as `pop(heap)` with no keyword arguments, a zero-overhead inline path bypasses all argument parsing, extracts the root, moves the last element to position 0, shrinks the list, and performs a binary min-heap sift-down using `sift_richcmp_min`. This saves ~20ns per call.

**Bulk pop type specialization:** For `n>1` with binary heaps and no key function, pop detects element type homogeneity and dispatches to type-specialized sift-down functions (`sift_float_min`, `sift_int_min`, `sift_str_min`, `sift_generic_min` and their max variants). This avoids per-element type checking during the sift loop.

**GIL-releasing bulk pop:** When `nogil=True`, `n>1`, and the array is homogeneous int/float, the entire bulk pop sequence executes with the GIL released, using `list_pop_bulk_homogeneous_float_nogil` or `list_pop_bulk_homogeneous_int_nogil`.

**Examples:**

```python
data = [5, 2, 8, 1, 9, 3]
heapx.heapify(data)

# Single pop — returns the minimum
smallest = heapx.pop(data)
assert smallest == 1

# Bulk pop — returns list of top-k in order
data = list(range(100))
heapx.heapify(data)
top5 = heapx.pop(data, n=5)
assert top5 == [0, 1, 2, 3, 4]

# Max-heap pop
data = [5, 2, 8, 1, 9]
heapx.heapify(data, max_heap=True)
largest = heapx.pop(data, max_heap=True)
assert largest == 9

# Pop with key function
tasks = [{"name": "a", "pri": 5}, {"name": "b", "pri": 1}, {"name": "c", "pri": 3}]
heapx.heapify(tasks, cmp=lambda x: x["pri"])
urgent = heapx.pop(tasks, cmp=lambda x: x["pri"])
assert urgent["pri"] == 1

# Pop from empty heap raises IndexError
import pytest
with pytest.raises(IndexError):
    heapx.pop([])
```

---

### 4. `remove`

```python
heapx.remove(heap, indices=None, object=None, predicate=None, n=None,
             return_items=False, max_heap=False, cmp=None, arity=2, nogil=False)
```

Removes items from a heap by index, object identity, or predicate. Exactly one of `indices`, `object`, or `predicate` should be specified.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `heap` | `list` or sequence | *(required)* | Heap to remove from. |
| `indices` | `int`, sequence of `int`, or `None` | `None` | Index or indices to remove. Negative indices supported. |
| `object` | any or `None` | `None` | Remove items matching this object by identity (`is`). |
| `predicate` | `callable` or `None` | `None` | Remove items where `predicate(item)` is truthy. |
| `n` | `int` or `None` | `None` | Maximum number of items to remove. `None` = no limit. |
| `return_items` | `bool` | `False` | If `True`, returns `(count, [removed_items])` instead of just `count`. |
| `max_heap` | `bool` | `False` | Heap ordering direction. |
| `cmp` | `callable` or `None` | `None` | Key function for heap maintenance after removal. |
| `arity` | `int` | `2` | Branching factor (1–64). |
| `nogil` | `bool` | `False` | Used when batch removal triggers re-heapify on homogeneous data. |

**Returns:** `int` (count of removed items) or `(int, list)` if `return_items=True`.

**Complexity:** Single index removal: O(log n) via inline sift-up/sift-down. Batch removal: O(k + n) where k items are removed and the heap is re-heapified.

**Hot path:** Single-index removal on a list uses `list_remove_at_index_optimized`, which moves the last element into the vacated position and performs either sift-up or sift-down depending on the replacement value's relationship to its parent — achieving O(log n) without a full re-heapify.

**Examples:**

```python
data = list(range(10))
heapx.heapify(data)

# Remove by index — O(log n) inline maintenance
heapx.remove(data, indices=0)  # removes root
assert 0 not in data

# Remove by predicate
data = list(range(20))
heapx.heapify(data)
count = heapx.remove(data, predicate=lambda x: x % 2 == 0)
assert all(x % 2 == 1 for x in data)

# Remove with return_items
data = list(range(10))
heapx.heapify(data)
count, items = heapx.remove(data, indices=0, return_items=True)
assert count == 1 and items == [0]

# Remove by object identity
sentinel = object()
data = [1, sentinel, 3, sentinel, 5]
heapx.heapify(data)
count = heapx.remove(data, object=sentinel)
assert count == 2

# Remove with n limit
data = list(range(100))
heapx.heapify(data)
count = heapx.remove(data, predicate=lambda x: x < 50, n=10)
assert count == 10
```


---

### 5. `replace`

```python
heapx.replace(heap, values, indices=None, object=None, predicate=None,
              max_heap=False, cmp=None, arity=2, nogil=False)
```

Replaces items in a heap by index, object identity, or predicate, maintaining the heap property. Exactly one of `indices`, `object`, or `predicate` should be specified.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `heap` | `list` or sequence | *(required)* | Heap to replace in. |
| `values` | any or sequence | *(required)* | Replacement value(s). Single value for single replacement; sequence for batch. |
| `indices` | `int`, sequence of `int`, or `None` | `None` | Index or indices to replace. |
| `object` | any or `None` | `None` | Replace items matching this object by identity (`is`). |
| `predicate` | `callable` or `None` | `None` | Replace items where `predicate(item)` is truthy. |
| `max_heap` | `bool` | `False` | Heap ordering direction. |
| `cmp` | `callable` or `None` | `None` | Key function for heap maintenance after replacement. |
| `arity` | `int` | `2` | Branching factor (1–64). |
| `nogil` | `bool` | `False` | Used when batch replacement triggers re-heapify on homogeneous data. |

**Returns:** `int` (count of replaced items).

**Complexity:** Single index replacement: O(log n) via inline sift-up or sift-down. Batch replacement: O(k + n) where k items are replaced and the heap is re-heapified.

**Hot path:** Single-index replacement on a list uses `list_replace_at_index_optimized`, which writes the new value and performs either sift-up or sift-down depending on the new value's relationship to its parent — achieving O(log n) without a full re-heapify.

**Examples:**

```python
data = list(range(10))
heapx.heapify(data)

# Replace root with a new value
count = heapx.replace(data, 99, indices=0)
assert count == 1

# Replace by predicate — all even numbers become 999
data = list(range(20))
heapx.heapify(data)
count = heapx.replace(data, 999, predicate=lambda x: x % 2 == 0)
assert count == 10

# Replace by object identity
sentinel = object()
data = [1, sentinel, 3]
heapx.heapify(data)
count = heapx.replace(data, 42, object=sentinel)
assert count == 1
```

---

### 6. `merge`

```python
heapx.merge(*heaps, max_heap=False, cmp=None, arity=2, nogil=False)
```

Merges two or more sequences into a single valid heap. Concatenates all inputs into a new list, then heapifies the result using the full dispatch system.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*heaps` | sequences | *(required, ≥ 2)* | Two or more sequences to merge. |
| `max_heap` | `bool` | `False` | Heap ordering direction. |
| `cmp` | `callable` or `None` | `None` | Key function for the merged heap. |
| `arity` | `int` | `2` | Branching factor (1–64). |
| `nogil` | `bool` | `False` | Release GIL during heapify phase for homogeneous int/float data. |

**Returns:** `list` — a new list containing all elements from all inputs, arranged as a valid heap.

**Complexity:** O(N) where N is the total number of elements across all inputs. The concatenation phase is O(N), and Floyd's heapify is O(N).

**Examples:**

```python
# Basic merge — result is a valid min-heap
merged = heapx.merge([1, 3, 5], [2, 4, 6])
assert merged[0] == 1  # minimum at root
assert len(merged) == 6

# Max-heap merge
merged = heapx.merge([1, 3], [2, 4], max_heap=True)
assert merged[0] == 4  # maximum at root

# Merge with key function
tasks_a = [{"pri": 1}, {"pri": 5}]
tasks_b = [{"pri": 2}, {"pri": 3}]
merged = heapx.merge(tasks_a, tasks_b, cmp=lambda x: x["pri"])
assert merged[0]["pri"] == 1

# Merge with ternary heap
merged = heapx.merge([10, 20], [5, 15], [1, 25], arity=3)
assert merged[0] == 1

# Merge empty heaps
merged = heapx.merge([], [], [1, 2])
assert merged == [1, 2]
```

---

## Dispatch Architecture

Each API function uses a multi-tier dispatch system to select the optimal algorithm at runtime. The dispatch decisions are based on: (1) whether the heap is a `list` (enables direct pointer access) or a generic sequence, (2) heap size relative to thresholds, (3) arity value, (4) presence of a key function, (5) element type homogeneity, and (6) the `nogil` flag.

The six functions do **not** all share an identical dispatch table. `heapify` and `merge` use the most comprehensive dispatch with 11 numbered priorities. `push` uses an 11-priority table with a different structure (fast path + bulk optimization + per-arity sift-up). `pop` uses a fast path plus arity-specialized sift-down with type-specialized bulk paths. `remove` and `replace` use a hot path for single-index operations plus batch re-heapify fallback.

### Heapify Dispatch

`py_heapify` uses a two-phase dispatch:

**Phase 1 — Homogeneous type-specialized paths** (attempted first when `cmp=None` and `n ≥ 8`):

The function calls `detect_homogeneous_type()` which uses SIMD-accelerated type pointer scanning to determine if all elements share the same type. Returns: 0=mixed, 1=all int, 2=all float, 3=all string.

| Arity | Homogeneous Type | nogil=False | nogil=True |
|-------|-----------------|-------------|------------|
| 2 | int | `list_heapify_homogeneous_int` | `list_heapify_homogeneous_int_nogil` |
| 2 | float | `list_heapify_homogeneous_float` | `list_heapify_homogeneous_float_nogil` |
| 2 | string | `list_heapify_homogeneous_string` | *(no nogil variant)* |
| 3 | int | `list_heapify_ternary_homogeneous_int` | `list_heapify_ternary_homogeneous_int_nogil` |
| 3 | float | `list_heapify_ternary_homogeneous_float` | `list_heapify_ternary_homogeneous_float_nogil` |
| 4 | int | `list_heapify_quaternary_homogeneous_int` | `list_heapify_quaternary_homogeneous_int_nogil` |
| 4 | float | `list_heapify_quaternary_homogeneous_float` | `list_heapify_quaternary_homogeneous_float_nogil` |
| ≥5 | int | `list_heapify_nary_simd_homogeneous_int` | `list_heapify_nary_simd_homogeneous_int_nogil` |
| ≥5 | float | `list_heapify_nary_simd_homogeneous_float` | `list_heapify_nary_simd_homogeneous_float_nogil` |

If the homogeneous path succeeds (returns 0), the function returns immediately. If it fails (integer overflow for bigints, or error), it clears the error and falls through to Phase 2.

**Phase 2 — Generic paths** (selected by arity and key function):

| Condition | No Key Function | With Key Function |
|-----------|----------------|-------------------|
| n ≤ 16 | `list_heapify_small_ultra_optimized` | *(falls through to arity switch)* |
| arity=1 | `heapify_arity_one_ultra_optimized` (Timsort) | `heapify_arity_one_ultra_optimized` (Timsort with key) |
| arity=2 | `list_heapify_floyd_ultra_optimized` | `list_heapify_with_key_ultra_optimized` |
| arity=3 | `list_heapify_ternary_ultra_optimized` | `list_heapify_ternary_with_key_ultra_optimized` |
| arity=4 | `list_heapify_quaternary_ultra_optimized` | `list_heapify_quaternary_with_key_ultra_optimized` |
| arity=8 | `list_heapify_octonary_ultra_optimized` | `list_heapify_octonary_with_key_ultra_optimized` |
| arity=5,6,7,9–64, n<1000 | `list_heapify_small_ultra_optimized` | `generic_heapify_ultra_optimized` |
| arity=5,6,7,9–64, n≥1000 | `generic_heapify_ultra_optimized` | `generic_heapify_ultra_optimized` |
| Non-list sequence | `generic_heapify_ultra_optimized` | `generic_heapify_ultra_optimized` |


### Push Dispatch

`py_push` uses a structurally different dispatch from heapify. It has a zero-overhead fast path, a bulk-push optimization gate, and then an 11-priority sift-up table:

**Fast path** (bypasses all argument parsing):
- Condition: exactly 2 positional args, no kwargs, heap is `list`, item is not `list`
- Action: `PyList_Append` + inline binary min-heap sift-up using `PyObject_RichCompareBool`

**Bulk push gate** (when `k ≥ n` or `n = 0`):
- Delegates to the full heapify dispatch (same as `py_heapify` Phase 1 + Phase 2) since O(n+k) heapify beats O(k log(n+k)) individual sift-ups

**11-priority sift-up table** (for `k < n`, items already appended):

| Priority | Condition | No Key Function | With Key Function |
|----------|-----------|----------------|-------------------|
| 1 | n ≤ 16, no key | `list_sift_up_ultra_optimized` per item | — |
| 2 | arity=1 | Binary search + shift (sorted insert) | — |
| 3 | arity=2 | `list_sift_up_binary_ultra_optimized` (bit-shift `>>1`) | — |
| 4 | arity=3 | Inline ternary sift-up (division by 3) | — |
| 5 | arity=4 | `list_sift_up_quaternary_ultra_optimized` (bit-shift `>>2`) | — |
| 6 | arity=8 | `list_sift_up_octonary_ultra_optimized` (bit-shift `>>3`) | — |
| 7 | arity≥5, ≠8 | Inline n-ary sift-up (division by arity) | — |
| 8 | arity=2, with key | Inline binary sift-up with `call_key_function` | ✓ |
| 9 | arity=3, with key | Inline ternary sift-up with `call_key_function` | ✓ |
| 10 | arity≥4, with key | Inline n-ary sift-up with `call_key_function` | ✓ |
| 11 | Non-list sequence | `sift_up` (generic `PySequence_GetItem`/`SetItem`) | ✓ |

For priorities 3–7 with bulk push (`n_items > 1`), homogeneous type detection is performed once and `list_sift_up_homogeneous_int` / `list_sift_up_homogeneous_float` are used when applicable, falling back to the generic sift-up on overflow or type mismatch.

### Pop Dispatch

`py_pop` has a fundamentally different dispatch structure from heapify/push because its core operation is sift-down (not sift-up or heapify). It splits into three paths:

**Fast path** (bypasses all argument parsing):
- Condition: exactly 1 positional arg, no kwargs, heap is `list`
- Action: extract root, move last to position 0, shrink list, `sift_richcmp_min`

**Single pop (n=1) sift-down dispatch:**

| Condition | Function |
|-----------|----------|
| arity=1, no key | `PyList_SetSlice` (remove first element of sorted list) |
| arity=2, no key, min-heap | `sift_richcmp_min` |
| arity=2, no key, max-heap | `sift_richcmp_max` |
| n ≤ 16, no key | `list_heapify_small_ultra_optimized` (re-heapify) |
| arity=2, no key | `list_sift_down_binary_ultra_optimized` |
| arity=4, no key | `list_sift_down_quaternary_ultra_optimized` |
| arity=8, no key | `list_sift_down_octonary_ultra_optimized` |
| other arity, no key | `list_sift_down_ultra_optimized` |
| with key | `list_sift_down_with_key_ultra_optimized` |
| non-list sequence | `sift_down` (generic) |

**Bulk pop (n>1) dispatch:**

1. **NoGIL path** (when `nogil=True`, `cmp=None`, `n ≥ 8`, `arity ≥ 2`): detects homogeneous float/int and uses `list_pop_bulk_homogeneous_float_nogil` or `list_pop_bulk_homogeneous_int_nogil`
2. **Type-specialized sift-down** (binary heap, no key): detects element type once via `detect_homogeneous_type`, then dispatches each pop's sift-down to `sift_float_min`/`sift_int_min`/`sift_str_min`/`sift_generic_min` (and max variants)
3. **Arity-specialized sift-down** (non-binary, no key): uses `list_sift_down_binary_ultra_optimized`, `list_sift_down_quaternary_ultra_optimized`, `list_sift_down_octonary_ultra_optimized`, or `list_sift_down_ultra_optimized`
4. **Key function path**: uses `list_sift_down_with_key_ultra_optimized` per pop
5. **Generic sequence**: uses `sift_down` (PySequence protocol)

### Remove Dispatch

`py_remove` uses a hot-path / general-case split:

**Hot path** (single integer `indices`, list heap, no `object`/`predicate`):

| Priority | Condition | Action |
|----------|-----------|--------|
| 1 | n ≤ 16, no key | Delete item + insertion sort re-heapify |
| 2 | arity=1 | `PySequence_DelItem` (sorted list, O(n) shift) |
| 3–10 | all other | `list_remove_at_index_optimized` — O(log n) inline sift-up or sift-down |

**General case** (batch indices, object identity, or predicate):
- Collects all indices to remove into a set
- Builds a new list excluding those indices
- Re-heapifies the result using the full heapify dispatch (with nogil/homogeneous support)

### Replace Dispatch

`py_replace` mirrors remove's structure:

**Hot path** (single integer `indices`, list heap, no `object`/`predicate`):

| Priority | Condition | Action |
|----------|-----------|--------|
| 1 | n ≤ 16, no key | Write new value + insertion sort re-heapify |
| 2 | arity=1 | Write new value + `PyList_Sort` (re-sort) |
| 3–10 | all other | `list_replace_at_index_optimized` — O(log n) inline sift-up or sift-down |

**General case** (batch indices, object identity, or predicate):
- Collects all indices to replace into a set
- Writes replacement values at those positions
- Re-heapifies the result using the full heapify dispatch (with nogil/homogeneous support)

### Merge Dispatch

`py_merge` concatenates all inputs into a new list, then applies an 11-priority heapify dispatch identical to `py_heapify`:

| Priority | Condition | Function |
|----------|-----------|----------|
| 1 | n ≤ 16, no key | Insertion sort |
| 2 | arity=1 | `PyList_Sort` / `list.sort(key=..., reverse=...)` |
| 3 | arity=2, no key | `list_heapify_floyd_ultra_optimized` (with homogeneous/nogil variants) |
| 4 | arity=3, no key | `list_heapify_ternary_ultra_optimized` (with homogeneous/nogil variants) |
| 5 | arity=4, no key | `list_heapify_quaternary_ultra_optimized` (with homogeneous/nogil variants) |
| 6 | arity≥5, no key, n<1000 | `list_heapify_nary_simd_homogeneous_*` or `list_heapify_small_ultra_optimized` |
| 7 | arity≥5, no key, n≥1000 | `list_heapify_nary_simd_homogeneous_*` or `generic_heapify_ultra_optimized` |
| 8 | arity=2, with key | `list_heapify_with_key_ultra_optimized` |
| 9 | arity=3, with key | `list_heapify_ternary_with_key_ultra_optimized` |
| 10 | arity≥4, with key | `generic_heapify_ultra_optimized` |
| 11 | fallback | `generic_heapify_ultra_optimized` |


---

## Optimization Layers

### Fast Comparison Paths

The `fast_compare` function (line 1191) provides type-specialized comparison for six Python types, bypassing `PyObject_RichCompareBool`:

| Type | Mechanism | Speedup Source |
|------|-----------|---------------|
| `int` | `PyLong_AsLong` → C `<`/`>` (Python 3.12+: `_PyLong_CompactValue` for small ints) | Avoids rich comparison protocol overhead |
| `float` | `PyFloat_AS_DOUBLE` → C `<`/`>` with NaN-aware ordering | Direct double extraction, no method lookup |
| `bytes` | `memcmp` on raw byte buffers | Single memcmp vs per-byte Python comparison |
| `str` | `memcmp` on `PyUnicode_DATA` (kind-aware: 1/2/4 byte) | Bypasses Python's unicode comparison machinery |
| `bool` | Direct `a == Py_True` pointer comparison | Zero-cost identity check |
| `tuple` | Recursive `fast_compare` on elements, then length comparison | Avoids creating intermediate comparison results |

NaN handling: NaN is treated as "largest" — it sinks to the bottom of min-heaps and rises to the top of max-heaps. This is enforced via explicit `isnan()` checks in the float path and the `HEAPX_FLOAT_LT`/`HEAPX_FLOAT_GT` macros used in all homogeneous float paths.

The `optimized_compare` wrapper (line 1391) calls `fast_compare` first; if the type is not handled (returns 0), it falls back to `PyObject_RichCompareBool`.

### Homogeneous Type Detection

`detect_homogeneous_type` (line 1421) scans all `n` elements' `ob_type` pointers to determine if the array is uniformly `int`, `float`, or `str`. The scan uses SIMD acceleration:

| Platform | Instruction Set | Pointers per Cycle | Mechanism |
|----------|----------------|-------------------|-----------|
| x86-64 (Haswell+) | AVX2 | 4 | `_mm256_cmpeq_epi64` on type pointer vectors |
| x86-64 (older) | SSE2 | 2 | `_mm_cmpeq_epi64` on type pointer pairs |
| ARM64 | NEON | 2 | `vceqq_s64` on type pointer pairs |
| Other | Scalar | 4 (unrolled) | 4-way unrolled pointer comparison loop |

Returns: `0` = mixed types, `1` = all `int`, `2` = all `float`, `3` = all `str`. Minimum array size for detection: `HEAPX_HOMOGENEOUS_SAMPLE_SIZE = 8`.

### SIMD Acceleration

SIMD is used in two contexts:

1. **Type detection** (above) — scanning type pointers.
2. **Child selection in quaternary/octonary/n-ary heaps** — finding the min/max among 4 or 8 children:

| Function | Width | Platform | Operation |
|----------|-------|----------|-----------|
| `simd_find_min_index_4_doubles` | 256-bit | AVX | `_mm256_cmp_pd` with `_CMP_LE_OQ` |
| `simd_find_min_index_4_doubles` | 128-bit | SSE2 | `_mm_cmple_pd` on pairs |
| `simd_find_min_index_4_doubles` | 128-bit | NEON | `vld1q_f64` + scalar compare |
| `simd_find_min_index_8_doubles` | 256-bit | AVX2 | `_mm256_min_pd` + horizontal reduction |
| `simd_find_min_index_4_longs` | 256-bit | AVX2 | `_mm256_cmpgt_epi64` + blend |
| `simd_find_min_index_8_longs` | 256-bit | AVX2 | Two `_mm256_loadu_si256` + reduction |
| `simd_find_best_child_float` | Mixed | All | Processes children in groups of 8→4→remainder |
| `simd_find_best_child_long` | Mixed | All | Same structure for integer children |

All SIMD functions have scalar fallbacks for platforms without hardware support. NaN values in float SIMD paths trigger a scalar fallback with explicit `HEAPX_FLOAT_LT`/`HEAPX_FLOAT_GT` NaN-aware comparisons.

### GIL-Releasing Computation

For homogeneous `int` or `float` arrays, the module implements a three-phase GIL-release pattern:

1. **Phase 1 (GIL held):** Extract raw C values (`PyFloat_AS_DOUBLE` / `PyLong_AsLongAndOverflow`) into a contiguous C array. Initialize an index permutation array `indices[i] = i`.
2. **Phase 2 (GIL released via `Py_BEGIN_ALLOW_THREADS`):** Perform the entire heapify/pop algorithm on the C arrays — pure C computation with no Python API calls.
3. **Phase 3 (GIL reacquired):** Validate the list wasn't modified by another thread (`PyList_GET_SIZE(listobj) != n` check). Rearrange Python objects using cycle-following permutation based on the `indices` array.

The cycle-following permutation (Phase 3) uses the standard algorithm: for each position `i`, follow the chain `indices[i] → indices[indices[i]] → ...` until returning to `i`, moving objects along the chain. Visited positions are marked with `indices[j] = -1 - indices[j]` to avoid revisiting.

This pattern exists for 10 function variants: binary/ternary/quaternary/n-ary × int/float, each with a `_nogil` suffix.

Integer overflow handling: `PyLong_AsLongAndOverflow` detects bigints that don't fit in C `long`. The function returns `2` (not `-1`) to signal "fall back to generic path" without setting a Python exception.

### Prefetching and Cache Optimization

Architecture-specific prefetch distances and strides are set at compile time:

| Architecture | Cache Line | `PREFETCH_DISTANCE` | `PREFETCH_STRIDE` |
|-------------|-----------|--------------------|--------------------|
| Apple Silicon (M1–M4) | 128 bytes | 4 | 16 pointers |
| x86-64 (any) | 64 bytes | 3–4 | 8 pointers |
| ARM64 (non-Apple) | 64 bytes | 4 | 8 pointers |
| IBM POWER | 128 bytes | 4 | 16 pointers |
| RISC-V | 64 bytes | 4 | 8 pointers |

Prefetching is applied in the quaternary heap sift-down loop, where grandchildren are prefetched before processing children. The `PREFETCH_MULTIPLE_STRIDE` macro issues up to `PREFETCH_DISTANCE` prefetch instructions spaced `PREFETCH_STRIDE` pointers apart.

### Stack-First Memory Allocation

Two stack buffer sizes avoid heap allocation for common cases:

| Buffer | Size | Used For | Threshold |
|--------|------|----------|-----------|
| `KEY_STACK_SIZE` | 128 `PyObject*` | Key function result cache | n ≤ 128 |
| `VALUE_STACK_SIZE` | 2,048 `double`/`long` | Homogeneous value extraction | n ≤ 2,048 |

When `n` exceeds the threshold, `PyMem_Malloc` is used with explicit `PyMem_Free` on all exit paths (including error paths). The `ASSUME_ALIGNED` macro hints to the compiler that stack buffers are 16-byte (or 32-byte for quaternary) aligned.

### Vectorcall Key Invocation

`call_key_function` (line 1401) uses Python 3.8+'s vectorcall protocol:

```c
vectorcallfunc vectorcall = PyVectorcall_Function(keyfunc);
if (vectorcall != NULL) {
    PyObject *args[1] = {item};
    return vectorcall(keyfunc, args, 1 | PY_VECTORCALL_ARGUMENTS_OFFSET, NULL);
}
return PyObject_CallOneArg(keyfunc, item);
```

Vectorcall avoids creating a temporary argument tuple, saving one allocation per key function call. For heapify with n=100,000 elements, this eliminates 100,000 tuple allocations during the key precomputation phase.

---

## Algorithmic Foundations

### Floyd's Bottom-Up Heapify (Wegener 1993 Variant)

Standard sift-down heapify compares the item against each child during descent, requiring ~2n comparisons. Floyd's bottom-up variant:

1. **Descend to leaf** comparing only children against each other (not against the item being placed).
2. **Bubble up** from the leaf position until the item finds its correct position.

Since most items in a heap are near the leaves, the bubble-up phase is typically O(1), reducing total comparisons to ~1.5n. The implementation in `list_heapify_floyd_ultra_optimized` (line 3015) follows this pattern exactly.

### Arity Trade-offs

| Arity | Tree Height | Comparisons per Sift Level | Parent Calculation | Child Calculation |
|-------|------------|---------------------------|-------------------|-------------------|
| 2 (binary) | ⌊log₂(n)⌋ | 1 (compare 2 children) | `(pos-1) >> 1` | `(pos << 1) + 1` |
| 3 (ternary) | ⌊log₃(n)⌋ | 2 (compare 3 children) | `(pos-1) / 3` | `3*pos + 1` |
| 4 (quaternary) | ⌊log₄(n)⌋ | 3 (compare 4 children) | `(pos-1) >> 2` | `(pos << 2) + 1` |
| 8 (octonary) | ⌊log₈(n)⌋ | 7 (compare 8 children) | `(pos-1) >> 3` | `(pos << 3) + 1` |

Binary heaps minimize comparisons per level. Higher arities reduce tree height (fewer levels to traverse) at the cost of more comparisons per level. For cache-friendly access patterns with large n, quaternary heaps can outperform binary heaps because children are stored contiguously and fit in fewer cache lines.

Power-of-two arities (2, 4, 8) use bit-shift operations for parent/child calculations, avoiding integer division. Arity=3 uses explicit division, which modern compilers optimize to multiplication by a magic constant.

### Small-Heap Insertion Sort

For n ≤ 16 (`HEAPX_SMALL_HEAP_THRESHOLD`), insertion sort outperforms heapify due to:
- No function call overhead (inline loop)
- Sequential memory access (cache-friendly)
- Branch prediction friendly (nearly-sorted data common after single insertions)
- Lower constant factor than Floyd's algorithm for small n

The threshold of 16 was chosen empirically: it corresponds to elements fitting in 1–2 cache lines (16 × 8 bytes = 128 bytes on x86-64).

---

## Memory Safety

Every comparison in the generic paths (non-homogeneous) follows this safety protocol:

1. **`Py_INCREF` before comparison:** Objects held across `optimized_compare` calls are protected against use-after-free if the comparison triggers Python code that modifies the list.
2. **List size validation after comparison:** `PyList_GET_SIZE(listobj) != n` is checked after every comparison that could invoke Python code. If the list was modified, the function raises `ValueError` and returns cleanly.
3. **`Py_DECREF` on all exit paths:** Every error path decrements all held references before returning.
4. **Reference transfer semantics:** When placing an item in its final position, the held reference is transferred to the list slot (no extra INCREF/DECREF pair).

The homogeneous paths (int/float) do not need this protocol because they operate on extracted C values, not Python objects, during the computation phase.

---

## Platform Support

| Platform | Architecture | SIMD | Prefetch | Tested |
|----------|-------------|------|----------|--------|
| macOS | ARM64 (Apple Silicon) | NEON | 128-byte lines | ✓ |
| macOS | x86-64 | AVX2/SSE2 | 64-byte lines | ✓ |
| Linux | x86-64 | AVX2/SSE2 | 64-byte lines | ✓ |
| Linux | ARM64 | NEON/SVE | 64-byte lines | ✓ |
| Windows | x86-64 | AVX2/SSE2 | 64-byte lines | ✓ |
| RISC-V | RV64 | Scalar | 64-byte lines | Compile-time support |
| IBM POWER | PPC64 | Scalar | 128-byte lines | Compile-time support |

Compiler support: GCC ≥ 4.9, Clang ≥ 3.6, MSVC ≥ 2015. All SIMD paths have scalar fallbacks.

---

## Advanced Usage

### Multi-Threaded Heapify with GIL Release

```python
import heapx
import threading

def heapify_worker(data):
    heapx.heapify(data, nogil=True)

# Create independent float arrays
arrays = [[float(x) for x in range(100000)] for _ in range(4)]

# Heapify all 4 arrays concurrently
threads = [threading.Thread(target=heapify_worker, args=(a,)) for a in arrays]
for t in threads: t.start()
for t in threads: t.join()
# All 4 arrays are now valid min-heaps, heapified in parallel
```

### Priority Queue with Custom Objects

```python
import heapx

class Task:
    def __init__(self, priority, name):
        self.priority = priority
        self.name = name

tasks = [Task(5, "low"), Task(1, "critical"), Task(3, "medium")]
key = lambda t: t.priority

heapx.heapify(tasks, cmp=key)
most_urgent = heapx.pop(tasks, cmp=key)
assert most_urgent.name == "critical"

# Add new task
heapx.push(tasks, Task(0, "emergency"), cmp=key)
assert heapx.pop(tasks, cmp=key).name == "emergency"
```

### Streaming Top-K with Bounded Heap

```python
import heapx

def streaming_top_k(stream, k):
    """Maintain top-k largest elements using a min-heap of size k."""
    heap = []
    for item in stream:
        if len(heap) < k:
            heapx.push(heap, item)
        elif item > heap[0]:
            heapx.replace(heap, item, indices=0)
    return sorted([heapx.pop(heap) for _ in range(len(heap))], reverse=True)

top10 = streaming_top_k(range(1000000), 10)
assert top10 == list(range(999999, 999989, -1))
```

### Quaternary Heap for Cache-Friendly Bulk Operations

```python
import heapx

# Quaternary heap: 4 children per node, stored contiguously
# For n=1M: binary=20 levels, quaternary=10 levels
data = list(range(1000000, 0, -1))
heapx.heapify(data, arity=4)

# Bulk pop top-100 with quaternary sift-down
top100 = heapx.pop(data, n=100, arity=4)
assert top100 == list(range(1, 101))
```

---
