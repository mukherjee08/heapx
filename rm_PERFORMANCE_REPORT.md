# heapx Performance Report

**Python Version:** 3.12.11  
**Platform:** macOS ARM64 (Apple Silicon)  
**Test Configuration:** 10 repetitions per measurement (mean ± std dev)

---

## Executive Summary

| Metric | Result |
|--------|--------|
| **heapify speedup vs heapq** | 1.5x - 2.5x (size dependent) |
| **Best arity for heapify** | 16-64 (higher = faster for large n) |
| **Key function overhead** | ~4-5x slower than no key |
| **Data type impact** | int fastest, tuple slowest (~3.4x) |
| **sort vs Python sorted()** | ~1.0x (comparable) |
| **merge performance** | O(N) linear time confirmed |

---

## 1. HEAPIFY Performance

### 1.1 heapx vs heapq (min-heap, integers, arity=2)

| Size | heapx | heapq | Speedup |
|------|-------|-------|---------|
| 0 | 3.22µs | 0.38µs | 0.12x |
| 10 | 7.10µs | 0.71µs | 0.10x |
| 100 | 1.20µs | 1.70µs | **1.42x** |
| 1,000 | 5.67µs | 13.91µs | **2.46x** |
| 10,000 | 68.03µs | 145.1µs | **2.13x** |
| 100,000 | 0.77ms | 1.60ms | **2.07x** |
| 1,000,000 | 9.89ms | 17.32ms | **1.75x** |
| 10,000,000 | 106.7ms | 171.8ms | **1.61x** |
| 100,000,000 | 1.116s | 1.712s | **1.53x** |

**Key Insight:** heapx shows significant speedup (1.5x-2.5x) for n ≥ 100. Small heaps have overhead from type detection and dispatch.

### 1.2 Max-Heap Performance (heapx only)

| Size | Time |
|------|------|
| 0 | 1.00µs |
| 10 | 0.31µs |
| 100 | 0.85µs |
| 1,000 | 5.22µs |
| 10,000 | 59.96µs |
| 100,000 | 0.78ms |
| 1,000,000 | 9.45ms |
| 10,000,000 | 107.4ms |

**Note:** Max-heap performance is nearly identical to min-heap (no negation overhead).

### 1.3 Arity Impact (n=100,000)

| Arity | Time | vs arity=2 |
|-------|------|------------|
| 1 | 8.78ms | 11.4x slower |
| 2 | 0.77ms | baseline |
| 3 | 0.66ms | **1.16x faster** |
| 4 | 0.57ms | **1.34x faster** |
| 5 | 0.59ms | **1.31x faster** |
| 8 | 0.51ms | **1.51x faster** |
| 16 | 0.45ms | **1.69x faster** |
| 32 | 0.44ms | **1.75x faster** |
| 64 | 0.44ms | **1.75x faster** |

**Key Insight:** Higher arity reduces tree height and improves cache locality. Arity 16-64 provides best heapify performance.

### 1.4 Data Type Impact (n=100,000)

| Type | Time | vs int |
|------|------|--------|
| int | 0.77ms | baseline |
| float | 1.16ms | 1.51x slower |
| str | 1.88ms | 2.45x slower |
| tuple | 2.61ms | 3.40x slower |

**Key Insight:** Homogeneous integer arrays benefit from SIMD-friendly fast paths.

### 1.5 Key Function Overhead (n=100,000)

| Key | Time | vs None |
|-----|------|---------|
| None | 0.76ms | baseline |
| abs | 3.24ms | 4.27x slower |
| lambda x: -x | 4.14ms | 5.46x slower |

**Key Insight:** Key functions add significant overhead due to Python function call costs. Use native max_heap=True instead of cmp=lambda x: -x.

### 1.6 NoGIL Parameter (n=1,000,000, floats)

| nogil | Time |
|-------|------|
| False | 13.81ms |
| True | 18.65ms |

**Note:** nogil=True adds ~35% overhead for GIL release/acquire pattern.

---

## 2. PUSH Performance

### 2.1 Single Push: heapx vs heapq

| Heap Size | heapx | heapq | Speedup |
|-----------|-------|-------|---------|
| 100 | 0.75µs | 0.42µs | 0.56x |
| 1,000 | 1.81µs | 1.45µs | 0.80x |
| 10,000 | 16.40µs | 19.08µs | **1.16x** |
| 100,000 | 0.20ms | 0.20ms | 1.01x |
| 1,000,000 | 2.93ms | 2.96ms | 1.01x |

**Key Insight:** Single push is comparable to heapq. heapx has slight overhead for small heaps due to dispatch logic.

### 2.2 Bulk Push (1000 items)

| Heap Size | Time |
|-----------|------|
| 0 | 11.05µs |
| 100 | 8.76µs |
| 1,000 | 12.80µs |
| 10,000 | 35.38µs |
| 100,000 | 0.23ms |

**Key Insight:** Bulk push is highly efficient - 1000 items in ~35µs for 10K heap.

### 2.3 Arity Impact (heap=10,000, push 100 items)

| Arity | Time |
|-------|------|
| 1 | 0.15ms |
| 2 | 21.06µs |
| 3 | 23.05µs |
| 4 | 21.45µs |
| 5 | 21.44µs |
| 8 | 25.16µs |

**Key Insight:** Arity=1 (sorted list) is ~7x slower due to O(n) insertion. Binary heap is optimal for push.

---

## 3. POP Performance

### 3.1 Single Pop: heapx vs heapq

| Heap Size | heapx | heapq | Speedup |
|-----------|-------|-------|---------|
| 100 | 2.12µs | 0.37µs | 0.18x |
| 1,000 | 1.33µs | 1.17µs | 0.88x |
| 10,000 | 16.66µs | 17.86µs | **1.07x** |
| 100,000 | 0.21ms | 0.20ms | 0.96x |
| 1,000,000 | 2.06ms | 1.97ms | 0.96x |

**Key Insight:** Pop performance is comparable to heapq. Small heap overhead from dispatch.

### 3.2 Bulk Pop (from heap of 100,000)

| n | Time |
|---|------|
| 1 | 0.19ms |
| 10 | 0.23ms |
| 100 | 0.25ms |
| 1,000 | 0.36ms |
| 10,000 | 1.04ms |

**Key Insight:** Bulk pop scales well - 10,000 pops in ~1ms.

### 3.3 Arity Impact (heap=100,000)

| Arity | Time |
|-------|------|
| 1 | 0.21ms |
| 2 | 0.20ms |
| 3 | 0.19ms |
| 4 | 0.20ms |
| 5 | 0.18ms |
| 8 | 0.20ms |

**Key Insight:** Pop performance is consistent across arities.

---

## 4. SORT Performance

### 4.1 heapx.sort vs Python sorted()

| Size | heapx.sort | sorted() | Speedup |
|------|------------|----------|---------|
| 0 | 0.25µs | 0.28µs | 1.11x |
| 10 | 0.40µs | 0.29µs | 0.74x |
| 100 | 3.02µs | 2.49µs | 0.82x |
| 1,000 | 37.60µs | 29.96µs | 0.80x |
| 10,000 | 0.64ms | 0.59ms | 0.92x |
| 100,000 | 9.05ms | 9.09ms | **1.00x** |
| 1,000,000 | 122.6ms | 124.7ms | **1.02x** |

**Key Insight:** heapx.sort is comparable to Python's Timsort. Timsort is faster for small/partially sorted data; heapsort is competitive for large random data.

### 4.2 Sort Parameters (n=100,000)

| Parameter | Value | Time |
|-----------|-------|------|
| reverse | False | 9.62ms |
| reverse | True | 9.49ms |
| inplace | False | 9.32ms |
| inplace | True | 8.77ms |

**Key Insight:** inplace=True saves ~6% by avoiding copy.

### 4.3 Sort with Key Function (n=100,000)

| Key | Time | vs None |
|-----|------|---------|
| None | 9.54ms | baseline |
| abs | 52.92ms | 5.5x slower |

**Key Insight:** Key functions have significant overhead in sort due to O(n log n) comparisons.

---

## 5. REMOVE Performance

### 5.1 Single Index Removal

| Heap Size | Time |
|-----------|------|
| 100 | 0.90µs |
| 1,000 | 1.37µs |
| 10,000 | 16.50µs |
| 100,000 | 0.20ms |

**Key Insight:** O(log n) removal via inline sift operations.

### 5.2 Multiple Index Removal (heap=10,000)

| # Indices | Time |
|-----------|------|
| 1 | 58.54µs |
| 10 | 70.21µs |
| 100 | 0.15ms |
| 1,000 | 0.54ms |

**Key Insight:** Batch removal uses single heapify at end for efficiency.

### 5.3 Predicate Removal (heap=10,000)

| Predicate | Time |
|-----------|------|
| x % 2 == 0 (n=100) | 0.16ms |
| x > 9000 | 0.30ms |

---

## 6. REPLACE Performance

### 6.1 Single Index Replace

| Heap Size | Time |
|-----------|------|
| 100 | 0.53µs |
| 1,000 | 1.43µs |
| 10,000 | 17.93µs |
| 100,000 | 0.22ms |

**Key Insight:** O(log n) replace via inline sift operations.

### 6.2 Multiple Index Replace (heap=10,000)

| # Indices | Time |
|-----------|------|
| 1 | 19.07µs |
| 10 | 19.80µs |
| 100 | 23.84µs |
| 1,000 | 64.00µs |

**Key Insight:** Adaptive strategy - sequential O(log n) for small batches, heapify for large.

---

## 7. MERGE Performance

### 7.1 Two Heaps (equal size)

| Each Size | Time | Total Elements |
|-----------|------|----------------|
| 100 | 2.27µs | 200 |
| 1,000 | 9.35µs | 2,000 |
| 10,000 | 0.11ms | 20,000 |
| 100,000 | 1.10ms | 200,000 |
| 500,000 | 5.68ms | 1,000,000 |

**Key Insight:** O(N) merge confirmed - ~5.7ms for 1M elements.

### 7.2 Multiple Heaps (each 1,000 elements)

| # Heaps | Time | Total Elements |
|---------|------|----------------|
| 2 | 9.81µs | 2,000 |
| 5 | 26.65µs | 5,000 |
| 10 | 52.10µs | 10,000 |
| 20 | 0.11ms | 20,000 |
| 50 | 0.27ms | 50,000 |

**Key Insight:** Linear scaling with total elements.

### 7.3 Arity Impact (2 heaps of 10,000)

| Arity | Time |
|-------|------|
| 1 | 64.44µs |
| 2 | 0.11ms |
| 3 | 88.56µs |
| 4 | 88.30µs |
| 8 | 79.33µs |

---

## 8. Parameter Matrix Summary (n=10,000)

| max_heap | arity | cmp | nogil | Time |
|----------|-------|-----|-------|------|
| False | 2 | None | False | 64.95µs |
| False | 2 | abs | False | 0.20ms |
| False | 3 | None | False | 55.84µs |
| False | 4 | None | False | 57.35µs |
| True | 2 | None | False | 60.36µs |
| True | 4 | None | False | 53.24µs |

---

## Recommendations

### For Maximum Performance:
1. **Use arity=4 or higher** for heapify on large datasets (n > 10,000)
2. **Avoid key functions** when possible - use max_heap=True instead of cmp=lambda x: -x
3. **Use homogeneous integer arrays** for best SIMD optimization
4. **Use bulk operations** (push/pop multiple items) instead of sequential calls
5. **Use inplace=True** for sort when original order not needed

### When to Use heapx vs heapq:
- **Use heapx:** n ≥ 100, max-heap needed, bulk operations, remove/replace needed
- **Use heapq:** n < 100, simple min-heap only, minimal dependencies

### Arity Selection Guide:
| Use Case | Recommended Arity |
|----------|-------------------|
| General purpose | 2 (binary) |
| Large heapify (n > 100K) | 8-16 |
| Frequent push/pop | 2-4 |
| Sorted list semantics | 1 |

---

*Report generated with heapx v1.0.0*
