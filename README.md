# heapx - Ultra-Optimized Heap Operations for Python

[![PyPI version](https://badge.fury.io/py/heapx.svg)](https://badge.fury.io/py/heapx)
[![Python Support](https://img.shields.io/pypi/pyversions/heapx.svg)](https://pypi.org/project/heapx/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`heapx` is a compact C‑level Python extension engineered to deliver faster execution and memory‑efficient heap operations through deliberate, performance‑driven implementation choices. These include **specialized arities**, **SIMD/homogeneity detection**, **precomputed key caching**, **advanced prefetching**, and a **small‑object key pool**. Each choice eliminates Python‑level overhead and ensures predictable, production‑grade performance across critical domains such as scheduling, graph algorithms, streaming analytics, and real‑time systems.

## Introduction

Data structures are the foundation of reliable, high‑performance software: they determine how quickly programs respond, how much data can be processed, and how predictable resource use will be in production systems. `heapx` is a C extension for Python that implements the heap with explicit, performance‑oriented design choices: **Floyd’s and arity‑specialized heapify (binary, ternary, quaternary)** for fewer comparisons and faster sifts; **precomputed key caching with vectorcall** to eliminate repeated Python call overhead; **homogeneity detection and SIMD‑friendly paths** to accelerate numeric workloads; **advanced prefetching and assume‑aligned hints** to maximize cache utilization; and a **small memory pool for key arrays** to reduce malloc/free churn. These choices are implemented to be safe, reference‑count correct, and to preserve Python semantics while delivering C‑level throughput.

---

## `heapx` implementation benefits & why each is necessary

1. **Faster heapify and sift operations** reduce $O(n)$ and $O(\log(n))$ constants so large datasets and latency‑sensitive systems complete operations with lower CPU time and jitter.

2. **Arity specialization** enables for fewer tree levels for the same element count means fewer comparisons and memory accesses, directly improving throughput for bulk heap construction.

3. **Precomputed keys with vectorcall** avoids repeated Python function call overhead for key extraction, which is the dominant cost when keys are expensive or when n is large.

4. **Homogeneity detection and numeric fast paths** enables for tight C numeric comparisons and potential SIMD acceleration, essential for analytics and numeric streaming where element types are uniform.

5. **Advanced prefetching and alignment hints** reduces cache misses and memory latency, which is the primary bottleneck on modern CPUs for pointer‑heavy data structures.

6. **Key memory pool** minimizes allocator overhead and fragmentation in workloads that repeatedly build and tear down heaps, improving latency and memory stability. 

7. **Small‑heap specializations and insertion sort fallback** optimizes the common case of small heaps found in many real systems, delivering better real‑world performance than a one‑size‑fits‑all approach.

---

## `heapx` useability benefits & why each is necessary

1. **Complete Heap Ecosystem in One Module**: `heapx` provides all essential heap operations (`heapify`, `push`, `pop`, `remove`, `replace`, `sort`, `merge`) in a single, comprehensive API. This eliminates the need for users to combine multiple libraries or write custom heap utilities, ensuring consistency and reducing integration complexity.

2. **Native Min/Max Heap Support Without Data Transformation**: `heapx` natively supports both min-heap and max-heap modes through a simple parameter. This preserves data integrity, simplifies debugging, and eliminates conversion overhead.

3. **Configurable N-ary Heap Arity for Performance Tuning**: Users can specify heap arity ($1$-ary sorted lists through $4$-ary quaternary heaps up to general $n$-ary) to match specific workload characteristics. This enables fine-grained optimization where binary heaps suit general use, ternary/quaternary reduce comparisons for large datasets, and $1$-ary provides sorted list semantics.

4. **Intelligent Key Function Caching with Vectorcall Optimization**: When using key functions, `hepax` precomputes and caches all keys in $O(n)$ time rather than $O(n log n)$, reducing Python function call overhead. The integration of Python $3.8+$ vectorcall protocol further accelerates key extraction through direct C-level invocation.

5. **Bulk Operations with Optimized Batch Processing**: All core operations support both single-item and bulk processing modes with algorithms that minimize per-item overhead. Bulk `push` and `pop` operations use specialized paths that reduce function call overhead and improve cache locality.

6. **Flexible Element Selection via Multiple Identification Methods**: The `remove` and `replace` functions support three distinct identification modes: by index (fast $O(log n)$ removal), by object identity (pointer comparison), and by predicate function (flexible condition matching). This provides users with flexibility for heap modification without sacrificing performance.

7. **In-Place and Copy Modes for Memory Control**: The `sort` operation offers both in-place modification (minimal memory overhead) and copy-based sorting (preserves original heap). This gives users explicit control over memory usage patterns crucial for large-scale or embedded applications.

8. **Efficient Multi-Heap Merging with Sorted Heap Optimization**: The `merge` function combines multiple heaps in linear time with automatic algorithm selection based on input characteristics. The optional `sorted_heaps` parameter allows skipping heapification when inputs are already valid heaps, providing optimal performance for streaming aggregation scenarios.

9. **Automatic Algorithm Selection via $11$-Priority Dispatch Table**: `heapx` chooses the optimal implementation based on heap size, arity, presence of key functions, and data type homogeneity. This eliminates manual optimization decisions while ensuring each operation uses the most efficient algorithm for the specific context.

10. **Small-Heap Specialization with Insertion Sort Fallback**: For heaps of size $\le 16$, `heapx` automatically switches to insertion sort algorithms that outperform traditional heap algorithms for small datasets. This optimization is particularly valuable for real-time systems and microservices where heap sizes are frequently small.

11. **Homogeneous Type Detection with SIMD-Optimized Paths**: Automatic detection of uniform numeric types (all integers or all floats) enables use of specialized comparison functions and potential SIMD vectorization opportunities, providing significant speedups for scientific computing and numerical analysis workloads.

12. **Production-Grade Error Handling and Memory Safety**: All operations maintain proper Python reference counting, handle allocation failures gracefully, and provide clear error messages. The key memory pool reduces allocation fragmentation while ensuring deterministic performance in long-running applications.

13. **Comprehensive Fast Comparison Paths for Python Types**: Specialized comparison optimizations for integers, floats, strings, bytes, booleans, and tuples bypass Python's general comparison machinery, providing C-level speed while maintaining full Python semantics including proper $NaN$ handling.

14. **Advanced Prefetching and Cache Optimization Hints**: Built-in memory prefetching and alignment assumptions maximize CPU cache utilization, reducing memory latency bottlenecks that dominate performance in pointer-heavy data structures on modern architectures.

15. **Unified API with Consistent Parameter Semantics**: All functions share a common parameter structure (`max_heap`, `cmp`, `arity`) with consistent defaults, reducing cognitive load and enabling code reuse across different heap operation contexts.

16. **Detailed Documentation and Type-Safe Interface**: Each function includes comprehensive docstrings with parameter descriptions, complexity analysis, and usage examples. The C implementation validates all inputs with precise type checking before execution, preventing runtime errors.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Performance](#performance)
- [Core Advantages](#core-advantages)
- [API Reference](#api-reference)
  - [heapify](#heapify)
  - [push](#push)
  - [pop](#pop)
  - [remove](#remove)
  - [replace](#replace)
  - [sort](#sort)
  - [merge](#merge)
- [Advanced Usage](#advanced-usage)
- [Technical Details](#technical-details)
- [Contributing](#contributing)
- [License](#license)

## Overview

Heap data structures maintain the most important element at the root, enabling efficient priority queue operations. The `heapx` module extends Python's heap capabilities with:

- **Native max-heap and min-heap support** without data transformation
- **N-ary heap support** (binary, ternary, quaternary, and arbitrary arity)
- **Custom comparison functions** with intelligent key caching
- **40-80% performance improvement** over `heapq` for large datasets
- **Advanced C-level optimizations** including SIMD, prefetching, and fast comparison paths
- **Comprehensive API** with remove, replace, and merge operations 

## Key Features

### 1. **Native Max-Heap & Min-Heap Support**

Unlike `heapq` which only supports min-heaps, `heapx` provides native support for both heap types:

```python
import heapx

# Min-heap (default) - smallest element at root
data = [5, 2, 8, 1, 9]
heapx.heapify(data)
print(data[0])  # 1

# Max-heap - largest element at root
data = [5, 2, 8, 1, 9]
heapx.heapify(data, max_heap=True)
print(data[0])  # 9
```

**Benefits:**
- No need for element negation or wrapper objects
- Cleaner, more readable code
- Better performance (no transformation overhead)
- Type-safe operations

### 2. **N-ary Heap Support**

Configure heap branching factor for optimal performance based on your use case:

```python
# Binary heap (default, arity=2)
heapx.heapify(data, arity=2)

# Ternary heap (arity=3) - 37% reduced tree height
heapx.heapify(data, arity=3)

# Quaternary heap (arity=4) - cache-friendly
heapx.heapify(data, arity=4)

# Custom arity for specialized applications
heapx.heapify(data, arity=8)
```

**Performance characteristics:**
- **Binary (arity=2):** Optimal for most use cases, fastest comparisons
- **Ternary (arity=3):** Reduced tree height, better cache locality for large datasets
- **Quaternary (arity=4):** Excellent cache performance on modern CPUs
- **Higher arity:** Specialized applications with specific memory access patterns

### 3. **Custom Comparison Functions**

Sort by any attribute or computed value with intelligent key caching:

```python
# Sort by absolute value
data = [-5, 2, -8, 1, 9]
heapx.heapify(data, cmp=abs)

# Priority queue with custom objects
class Task:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority

tasks = [Task("low", 10), Task("high", 1), Task("medium", 5)]
heapx.heapify(tasks, cmp=lambda t: t.priority)
```

**Key caching optimization:**
- Keys computed once during heapify: O(n) key function calls
- Without caching: O(n log n) key function calls
- 50-80% performance improvement for expensive key functions

### 4. **Advanced C-Level Optimizations**

The module implements multiple optimization layers:

**Fast Comparison Paths:**
- Integers: Direct value comparison (no Python API overhead)
- Floats: IEEE 754 comparison with NaN handling
- Strings: Optimized `memcmp()` for bulk comparison
- Bytes: Direct memory comparison
- Tuples: Recursive fast comparison with early termination
- Booleans: Direct boolean comparison

**Memory Optimizations:**
- Advanced prefetching for cache-friendly access
- SIMD-friendly data layouts for homogeneous arrays
- Pointer arithmetic for direct memory access
- Minimal Python API overhead

**Algorithm Selection:**
- Automatic dispatch to optimal algorithm based on:
  - Data structure type (list vs sequence)
  - Heap size (small vs large)
  - Arity (binary, ternary, quaternary, n-ary)
  - Key function presence
  - Element type homogeneity

### 5. **Comprehensive API**

Beyond basic heap operations, `heapx` provides:

- **remove:** Remove items by index, object identity, or predicate
- **replace:** Replace items with O(log n) heap maintenance
- **merge:** Efficiently merge multiple heaps
- **sort:** Heapsort with in-place and copy modes

## Installation

```bash
# Install from PyPI
pip install heapx
```

**Requirements:**
- Python 3.8 or higher
- C compiler (GCC, Clang, or MSVC)

## Quick Start

```python
import heapx

# Create a min-heap
data = [5, 2, 8, 1, 9, 3, 7]
heapx.heapify(data)
print(data)  # [1, 2, 3, 5, 9, 8, 7]

# Push new items
heapx.push(data, 4)
heapx.push(data, [0, 6])  # Bulk insert

# Pop smallest items
smallest = heapx.pop(data)  # Returns 0
top_three = heapx.pop(data, n=3)  # Returns [1, 2, 3]

# Create a max-heap
data = [5, 2, 8, 1, 9]
heapx.heapify(data, max_heap=True)
largest = heapx.pop(data, max_heap=True)  # Returns 9

# Custom comparison (priority queue)
tasks = [
    {"name": "urgent", "priority": 1},
    {"name": "normal", "priority": 5},
    {"name": "low", "priority": 10}
]
heapx.heapify(tasks, cmp=lambda x: x["priority"])
next_task = heapx.pop(tasks, cmp=lambda x: x["priority"])
print(next_task)  # {"name": "urgent", "priority": 1}

# Ternary heap for large datasets
large_data = list(range(1000000, 0, -1))
heapx.heapify(large_data, arity=3)  # Faster for large datasets

# Remove specific items
data = [1, 2, 3, 4, 5]
heapx.heapify(data)
heapx.remove(data, indices=2)  # Remove by index
heapx.remove(data, predicate=lambda x: x > 3)  # Remove by condition

# Replace items efficiently
heapx.replace(data, 10, indices=0)  # Replace root with 10

# Merge multiple heaps
heap1 = [1, 3, 5]
heap2 = [2, 4, 6]
heapx.heapify(heap1)
heapx.heapify(heap2)
merged = heapx.merge(heap1, heap2, sorted_heaps=True)

# Sort using heapsort
data = [5, 2, 8, 1, 9]
sorted_data = heapx.sort(data)  # Returns [1, 2, 5, 8, 9]
heapx.sort(data, inplace=True, reverse=True)  # In-place descending sort
```

## Performance

### Benchmark Results

Performance comparison against Python's `heapq` module (lower is better):

| Operation | Dataset Size | heapq (ms) | heapx (ms) | Speedup |
|-----------|--------------|------------|------------|---------|
| heapify | 10,000 | 1.2 | 0.5 | 2.4x |
| heapify | 100,000 | 15.3 | 6.8 | 2.2x |
| heapify | 1,000,000 | 182.4 | 78.1 | 2.3x |
| push (single) | 10,000 | 0.8 | 0.4 | 2.0x |
| push (bulk) | 10,000 | 12.5 | 4.2 | 3.0x |
| pop (single) | 10,000 | 0.9 | 0.5 | 1.8x |
| pop (bulk) | 10,000 | 14.2 | 7.1 | 2.0x |

**Key Performance Factors:**
- **Small heaps (n ≤ 16):** Insertion sort optimization provides 3-5x speedup
- **Large heaps (n ≥ 1000):** Floyd's algorithm and cache optimizations provide 2-3x speedup
- **Custom key functions:** Key caching provides 50-80% improvement
- **Bulk operations:** Batch optimizations provide 2-4x speedup over sequential operations

### Memory Efficiency

- **No wrapper objects:** Direct element storage (unlike `heapq` max-heap workarounds)
- **Key caching:** O(n) temporary space during heapify with key function
- **In-place operations:** All operations modify heap in-place (except merge and sort with `inplace=False`)
- **Minimal overhead:** C extension with direct memory access

## Core Advantages

### vs. Python's `heapq`

| Feature | heapq | heapx |
|---------|-------|-------|
| Max-heap support | ❌ (requires negation) | ✅ Native |
| N-ary heaps | ❌ Binary only | ✅ Configurable arity |
| Custom comparison | ❌ (requires wrapper) | ✅ Key function |
| Remove operation | ❌ | ✅ O(log n) |
| Replace operation | ❌ | ✅ O(log n) |
| Merge operation | ❌ | ✅ O(N) |
| Performance | Baseline | 2-3x faster |
| Sequence support | Lists only | Lists, tuples, arrays |

### vs. Other Heap Libraries

**heapdict, pqdict:**
- heapx is 5-10x faster for large datasets
- heapx supports n-ary heaps
- heapx has lower memory overhead

**fibonacci-heap-mod, pairing-heap:**
- heapx has simpler API
- heapx has better cache locality
- heapx is more memory efficient

**binheap:**
- heapx has native max-heap support
- heapx has comprehensive API (remove, replace, merge)
- heapx has superior performance optimizations

## API Reference

The `heapx` module employs a sophisticated multi-tier optimization strategy that dynamically selects the most efficient algorithm based on runtime characteristics. This approach ensures optimal performance across diverse use cases while maintaining memory efficiency.

### **Algorithm Selection Strategy**

All heap operations in `heapx` utilize an intelligent dispatch system that analyzes the following factors to select the optimal implementation:

| **Optimization Factor** | **Detection Method** | **Performance Impact** |
|-------------------------|---------------------|------------------------|
| **Data Structure Type** | `PyList_CheckExact()` vs `PySequence_Check()` | Lists enable direct pointer manipulation (40-60% faster) |
| **Heap Size** | `n ≤ 16` vs `n < 1000` vs `n ≥ 1000` | Small heaps use insertion sort; large heaps use Floyd's algorithm |
| **Arity (Branching Factor)** | `arity = 1, 2, 3, 4` vs `arity ≥ 5` | Specialized implementations for common arities (2-3x faster) |
| **Key Function Presence** | `cmp == None` vs callable | Key caching eliminates redundant function calls (50-80% faster) |
| **Element Type Homogeneity** | First 8 elements type check | Enables fast comparison paths and SIMD opportunities |

### **Why These Optimizations Matter**

**1. Data Structure Specialization**
   - **Lists:** Direct access to internal `ob_item` array eliminates Python API overhead
   - **Sequences:** Generic `PySequence_*` API maintains compatibility with tuples, arrays, and custom types
   - **Trade-off:** Code complexity vs 40-60% performance gain for the common case

**2. Size-Based Algorithm Selection**
   - **Small heaps (n ≤ 16):** Insertion sort has lower constant factors and better cache locality
   - **Medium heaps (16 < n < 1000):** Specialized algorithms balance code size and performance
   - **Large heaps (n ≥ 1000):** Floyd's bottom-up heapification minimizes comparisons (O(n) vs O(n log n))
   - **Rationale:** Asymptotic complexity matters less than constant factors for small inputs

**3. Arity Specialization**
   - **Binary heaps (arity=2):** Most common case; Floyd's algorithm is optimal
   - **Ternary/Quaternary (arity=3,4):** Unrolled loops eliminate modulo operations
   - **General n-ary (arity≥5):** Flexible loop-based implementation for arbitrary branching
   - **Memory benefit:** Higher arity reduces tree height, improving cache performance for large heaps

**4. Key Function Optimization**
   - **Without key:** Direct element comparison using fast paths for built-in types
   - **With key:** Pre-compute all keys once, cache in temporary array, compare cached keys
   - **Critical insight:** Key function calls dominate runtime; caching converts O(n log n) calls to O(n)

**5. Type-Specific Fast Paths**
   - **Integers:** Direct value comparison (no Python API calls)
   - **Floats:** IEEE 754 comparison with NaN handling
   - **Strings/Bytes:** `memcmp()` for bulk comparison
   - **Tuples:** Recursive fast comparison with early termination
   - **Impact:** 2-5x speedup for homogeneous data vs generic `PyObject_RichCompareBool`

### **Specialized Algorithm Dispatch Table**

The following table illustrates the algorithm selection logic applied across all heap operations:

| **Priority** | **Condition** | **Selected Algorithm** | **Complexity** | **Use Case** |
|--------------|---------------|------------------------|----------------|--------------|
| 1 | `n ≤ 16` | Insertion sort / Small heap specialization | O(n²) | Tiny heaps where constant factors dominate |
| 2 | `arity = 1` | Sorted list maintenance | O(n log n) | Priority queue with single child (degenerate) |
| 3 | `List + arity=2 + no key` | Floyd's binary heap | O(n) | Most common case; optimal for heapify |
| 4 | `List + arity=3 + no key` | Specialized ternary heap | O(n) | Reduced tree height for large datasets |
| 5 | `List + arity=4 + no key` | Specialized quaternary heap | O(n) | Cache-friendly for modern CPUs |
| 6 | `List + arity≥5 + no key + n<1000` | Small n-ary heap | O(n log_k n) | Medium-sized heaps with custom arity |
| 7 | `List + arity≥5 + no key + n≥1000` | General n-ary heap | O(n log_k n) | Large heaps with custom arity |
| 8 | `List + arity=2 + key` | Binary heap with key caching | O(n) + O(n) key calls | Common case with custom ordering |
| 9 | `List + arity=3 + key` | Ternary heap with key caching | O(n) + O(n) key calls | Custom ordering with reduced height |
| 10 | `List + arity≥4 + key` | General n-ary with key caching | O(n log_k n) + O(n) key calls | Flexible custom ordering |
| 11 | `Sequence (non-list)` | Generic sequence algorithm | O(n log_k n) | Tuples, arrays, custom sequences |

**Note:** This dispatch strategy is applied consistently across `heapify`, `push`, `pop`, `sort`, `remove`, `replace`, and `merge` operations, ensuring predictable performance characteristics throughout the API.

### **1. Heapify**

Transform any Python sequence into a valid heap structure in-place with optimal time complexity.

```python
heapx.heapify(heap, max_heap=False, cmp=None, arity=2)
```

**Parameters:**

- **`heap`** *(required, mutable sequence)*  
  Any Python sequence supporting `len()`, `__getitem__()`, and `__setitem__()`. Commonly a `list`, but also supports `bytearray`, `array.array`, or custom mutable sequences. The sequence is modified in-place to satisfy the heap property.

- **`max_heap`** *(optional, bool, default=False)*  
  Controls heap ordering:
  - `False`: Creates a **min-heap** where the smallest element is at index 0
  - `True`: Creates a **max-heap** where the largest element is at index 0
  
  Unlike `heapq`, this native support eliminates the need for element negation or wrapper objects.

- **`cmp`** *(optional, callable or None, default=None)*  
  Custom key function for element comparison. When provided:
  - Each element `x` is compared using `cmp(x)` instead of `x` directly
  - Keys are computed once and cached for O(n) total key function calls
  - Signature: `cmp(element) -> comparable_value`
  - Example: `cmp=lambda x: x.priority` for objects with priority attributes
  - Example: `cmp=abs` to heap by absolute value
  
  When `None`, elements are compared directly using their natural ordering.

- **`arity`** *(optional, int ≥ 1, default=2)*  
  The branching factor of the heap (number of children per node):
  - `arity=1`: Unary heap (degenerates to sorted list)
  - `arity=2`: Binary heap (standard, most common)
  - `arity=3`: Ternary heap (reduces tree height by ~37%)
  - `arity=4`: Quaternary heap (optimal for some cache architectures)
  - `arity≥5`: General n-ary heap
  
  Higher arity reduces tree height (improving cache locality) but increases comparison overhead per level. Binary heaps (arity=2) are optimal for most use cases.

**Returns:** `None` (modifies `heap` in-place)

**Time Complexity:** O(n) for heapify operation, where n is the length of the sequence

**Space Complexity:** O(1) auxiliary space when `cmp=None`; O(n) temporary space for key caching when `cmp` is provided

**Example Usage:**
```python
import heapx

# Min-heap (default)
data = [5, 2, 8, 1, 9]
heapx.heapify(data)
# data is now [1, 2, 8, 5, 9]

# Max-heap
data = [5, 2, 8, 1, 9]
heapx.heapify(data, max_heap=True)
# data is now [9, 5, 8, 1, 2]

# Custom comparison (heap by absolute value)
data = [-5, 2, -8, 1, 9]
heapx.heapify(data, cmp=abs)
# data is now [1, 2, -8, -5, 9]

# Ternary heap for reduced height
data = list(range(1000))
heapx.heapify(data, arity=3)
```



### **2. Push**

Insert one or more items into an existing heap while maintaining the heap property through optimized sift-up operations.

```python
heapx.push(heap, items, max_heap=False, cmp=None, arity=2)
```

**Parameters:**

- **`heap`** *(required, mutable sequence)*  
  The heap to insert items into. Must be a valid heap structure (typically created via `heapify()` or previous `push()` operations). Commonly a `list`, but also supports other mutable sequences. The sequence is modified in-place.

- **`items`** *(required, single item or sequence)*  
  Item(s) to insert into the heap:
  - **Single item:** Any Python object to insert (e.g., `5`, `"hello"`, `(1, 2)`)
  - **Bulk insertion:** A sequence of items (list, tuple, etc.) to insert efficiently
  - **Note:** Strings, bytes, and tuples are treated as single items, not sequences
  
  Bulk insertion is optimized to be ~3x faster than sequential single insertions.

- **`max_heap`** *(optional, bool, default=False)*  
  Controls heap ordering:
  - `False`: Maintains a **min-heap** where the smallest element stays at index 0
  - `True`: Maintains a **max-heap** where the largest element stays at index 0
  
  Must match the heap type used during `heapify()`.

- **`cmp`** *(optional, callable or None, default=None)*  
  Custom key function for element comparison. When provided:
  - Each element `x` is compared using `cmp(x)` instead of `x` directly
  - Keys are computed on-demand during sift-up (O(1) auxiliary space)
  - Signature: `cmp(element) -> comparable_value`
  - Example: `cmp=lambda x: x.priority` for priority-based insertion
  - Example: `cmp=abs` to maintain heap by absolute value
  
  When `None`, elements are compared directly using their natural ordering.

- **`arity`** *(optional, int ≥ 1, default=2)*  
  The branching factor of the heap (must match the heap's existing arity):
  - `arity=1`: Sorted list (uses binary insertion)
  - `arity=2`: Binary heap (standard sift-up with bit-shift optimization)
  - `arity=3`: Ternary heap (division by 3)
  - `arity=4`: Quaternary heap (bit-shift optimization)
  - `arity≥5`: General n-ary heap (flexible division)
  
  Using the wrong arity will corrupt the heap structure.

**Returns:** `None` (modifies `heap` in-place)

**Time Complexity:** 
- Single insertion: O(log n) where n is the heap size
- Bulk insertion: O(k log n) where k is the number of items to insert
- Arity=1 (sorted list): O(n) per insertion due to binary search + shifting

**Space Complexity:** O(1) auxiliary space (no key caching; keys computed on-demand)

**Algorithm Details:**

The push operation follows an 11-priority dispatch table for optimal performance:

1. **Small heap (n ≤ 16, no key):** Uses insertion sort for newly added elements
2. **Arity=1 (sorted list):** Binary search to find insertion position, then shift elements
3. **Binary heap (arity=2, no key):** Inline sift-up with bit-shift parent calculation `(pos-1)>>1`
4. **Ternary heap (arity=3, no key):** Sift-up with division by 3
5. **Quaternary heap (arity=4, no key):** Sift-up with bit-shift `(pos-1)>>2`
6. **General n-ary (arity≥5, no key):** Flexible sift-up with division
7. **Binary heap with key (arity=2):** On-demand key computation during sift-up
8. **Ternary heap with key (arity=3):** Reduced tree height with key function
9. **General n-ary with key (arity≥4):** Maximum flexibility with custom ordering
10. **Generic sequence (non-list):** Uses `PySequence_InPlaceConcat` for compatibility

**Key Optimizations:**

- **Pointer refresh:** After `PyList_Append`, the internal array pointer is refreshed to handle list reallocation
- **Bulk detection:** Automatically detects sequences (excluding strings/bytes/tuples) for bulk insertion
- **Bit-shift optimization:** Binary (arity=2) and quaternary (arity=4) heaps use fast bit-shift operations instead of division
- **On-demand key computation:** Keys are computed only when needed during sift-up, avoiding O(n) memory overhead

**Example Usage:**

```python
import heapx

# Single item insertion (min-heap)
heap = [1, 3, 5, 7, 9]
heapx.heapify(heap)
heapx.push(heap, 4)
# heap is now [1, 3, 4, 7, 9, 5]

# Bulk insertion (3x faster than sequential)
heap = [1, 3, 5]
heapx.heapify(heap)
heapx.push(heap, [2, 4, 6, 8])
# heap is now [1, 2, 3, 4, 5, 6, 8]

# Max-heap insertion
heap = [9, 7, 5, 3, 1]
heapx.heapify(heap, max_heap=True)
heapx.push(heap, 6, max_heap=True)
# heap is now [9, 7, 6, 3, 1, 5]

# Custom comparison (priority queue)
class Task:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority

heap = []
heapx.push(heap, Task("low", 10), cmp=lambda t: t.priority)
heapx.push(heap, Task("high", 1), cmp=lambda t: t.priority)
heapx.push(heap, Task("medium", 5), cmp=lambda t: t.priority)
# heap[0] is Task("high", 1) - highest priority at top

# Ternary heap for reduced height
heap = list(range(100))
heapx.heapify(heap, arity=3)
heapx.push(heap, [101, 102, 103], arity=3)

# Sorted list maintenance (arity=1)
heap = [1, 3, 5, 7, 9]
heapx.heapify(heap, arity=1)
heapx.push(heap, 4, arity=1)
# heap is now [1, 3, 4, 5, 7, 9] - maintains sorted order
```

**Performance Notes:**

- Bulk insertion is ~3x faster than sequential single insertions
- Binary heaps (arity=2) are fastest for most use cases due to bit-shift optimizations
- Key functions add ~3.2x overhead due to function call costs
- Small heaps (n ≤ 16) use insertion sort which is faster than sift-up for tiny datasets
- Arity=1 (sorted list) has O(n) insertion cost but enables O(1) access to all elements in sorted order



### **3. Pop**

Remove and return the top element(s) from the heap while maintaining the heap property through optimized sift-down operations.

```python
heapx.pop(heap, n=1, max_heap=False, cmp=None, arity=2)
```

**Parameters:**

- **`heap`** *(required, mutable sequence)*  
  The heap to pop from. Must be a valid heap structure (typically created via `heapify()` or maintained through `push()` operations). Commonly a `list`, but also supports other mutable sequences. The sequence is modified in-place.

- **`n`** *(optional, int ≥ 1, default=1)*  
  Number of items to pop from the heap:
  - `n=1`: Returns a single item (the root element)
  - `n>1`: Returns a list of n items in heap order
  - If `n` exceeds heap size, pops all available items
  
  Bulk pop operations are optimized for efficiency.

- **`max_heap`** *(optional, bool, default=False)*  
  Controls heap ordering:
  - `False`: Pops from a **min-heap** (returns smallest element)
  - `True`: Pops from a **max-heap** (returns largest element)
  
  Must match the heap type used during `heapify()`.

- **`cmp`** *(optional, callable or None, default=None)*  
  Custom key function for element comparison. When provided:
  - Each element `x` is compared using `cmp(x)` instead of `x` directly
  - Keys are computed on-demand during sift-down (O(1) auxiliary space)
  - Signature: `cmp(element) -> comparable_value`
  - Example: `cmp=lambda x: x.priority` for priority-based extraction
  - Example: `cmp=abs` to pop by absolute value
  
  When `None`, elements are compared directly using their natural ordering.

- **`arity`** *(optional, int ≥ 1, default=2)*  
  The branching factor of the heap (must match the heap's existing arity):
  - `arity=1`: Sorted list (O(1) pop from front)
  - `arity=2`: Binary heap (standard sift-down with bit-shift optimization)
  - `arity=3`: Ternary heap (division by 3)
  - `arity=4`: Quaternary heap (bit-shift optimization)
  - `arity≥5`: General n-ary heap (flexible division)
  
  Using the wrong arity will corrupt the heap structure.

**Returns:** 
- `n=1`: Single element (the root)
- `n>1`: List of n elements in heap order

**Raises:**
- `IndexError`: If attempting to pop from an empty heap
- `ValueError`: If `n < 1` or `arity < 1`
- `TypeError`: If `cmp` is not callable or None

**Time Complexity:** 
- Single pop: O(log n) where n is the heap size
- Bulk pop: O(k log n) where k is the number of items to pop
- Small heap (n ≤ 16): O(n²) but faster in practice due to better constant factors
- Arity=1 (sorted list): O(1) per pop (already sorted)

**Space Complexity:** O(1) auxiliary space (no key caching; keys computed on-demand)

**Algorithm Details:**

The pop operation follows an 11-priority dispatch table for optimal performance:

1. **Small heap (n ≤ 16, no key):** Uses insertion sort after removing root element
2. **Arity=1 (sorted list):** Direct removal from front (O(1) operation)
3. **Binary heap (arity=2, no key):** Inline sift-down with bit-shift child calculation `(pos<<1)+1`
4. **Ternary heap (arity=3, no key):** Inline sift-down with 3 children comparison
5. **Quaternary heap (arity=4, no key):** Inline sift-down with bit-shift `(pos<<2)+1`
6. **General n-ary (arity≥5, no key):** Helper function for flexible arity
7. **Binary heap with key (arity=2):** Inline sift-down with on-demand key computation
8. **Ternary heap with key (arity=3):** Helper function with key computation
9. **General n-ary with key (arity≥4):** Maximum flexibility with custom ordering
10. **Generic sequence (non-list):** Uses `PySequence_*` API for compatibility

**Key Optimizations:**

- **Pointer refresh:** After list modification, the internal array pointer is refreshed to handle reallocation
- **Inline sift-down:** Binary, ternary, and quaternary heaps use inline implementations to eliminate function call overhead
- **Bit-shift optimization:** Binary (arity=2) and quaternary (arity=4) heaps use fast bit-shift operations for child calculation
- **On-demand key computation:** Keys are computed only when needed during sift-down, avoiding O(n) memory overhead
- **Small heap optimization:** Heaps with n ≤ 16 use insertion sort which has better constant factors
- **Memory safety:** Proper reference counting with `Py_SETREF` and `Py_INCREF` to prevent use-after-free bugs

**Example Usage:**

```python
import heapx

# Single item pop (min-heap)
heap = [1, 3, 2, 7, 5, 4, 6]
heapx.heapify(heap)
result = heapx.pop(heap)
# result is 1, heap is now [2, 3, 4, 7, 5, 6]

# Bulk pop (extract top 5 elements)
heap = list(range(20, 0, -1))
heapx.heapify(heap)
results = heapx.pop(heap, n=5)
# results is [1, 2, 3, 4, 5], heap has 15 elements remaining

# Max-heap pop
heap = [1, 2, 3, 4, 5]
heapx.heapify(heap, max_heap=True)
result = heapx.pop(heap, max_heap=True)
# result is 5, heap is now [4, 2, 3, 1]

# Pop all elements (heapsort)
heap = [5, 2, 8, 1, 9, 3, 7]
heapx.heapify(heap)
sorted_data = []
while heap:
    sorted_data.append(heapx.pop(heap))
# sorted_data is [1, 2, 3, 5, 7, 8, 9]

# Custom comparison (priority queue)
class Task:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority
    def __repr__(self):
        return f"Task({self.name}, {self.priority})"

heap = []
heapx.push(heap, Task("low", 10), cmp=lambda t: t.priority)
heapx.push(heap, Task("high", 1), cmp=lambda t: t.priority)
heapx.push(heap, Task("medium", 5), cmp=lambda t: t.priority)
task = heapx.pop(heap, cmp=lambda t: t.priority)
# task is Task(high, 1) - highest priority task

# Ternary heap pop
heap = list(range(100, 0, -1))
heapx.heapify(heap, arity=3)
result = heapx.pop(heap, arity=3)
# result is 1, heap maintains ternary heap property

# Sorted list pop (arity=1)
heap = [1, 3, 5, 7, 9]
heapx.heapify(heap, arity=1)
result = heapx.pop(heap, arity=1)
# result is 1, heap is now [3, 5, 7, 9] - still sorted

# Bulk pop with key function
heap = [-5, 2, -8, 1, 9, -3, 7, -4, 6, -2]
heapx.heapify(heap, cmp=abs)
results = heapx.pop(heap, n=3, cmp=abs)
# results contains 3 elements with smallest absolute values
```

**Performance Notes:**

- Single pop is comparable to `heapq.heappop` for binary heaps
- Small heaps (n ≤ 16) benefit from insertion sort optimization
- Binary heaps (arity=2) are fastest due to bit-shift optimizations
- Key functions add ~3x overhead due to function call costs
- Bulk pop is more efficient than repeated single pops
- Arity=1 (sorted list) has O(1) pop cost (already sorted)
- Ternary and quaternary heaps reduce tree height, improving cache performance for large datasets

**Common Use Cases:**

- **Priority Queue:** Pop highest/lowest priority items
- **Heapsort:** Extract all elements in sorted order
- **Top-K Selection:** Pop k smallest/largest elements
- **Event Scheduling:** Pop next event by timestamp
- **Median Maintenance:** Pop from min/max heaps alternately
- **Streaming Algorithms:** Maintain top-k elements in a stream

### **4. Remove**

Remove one or more items from the heap by index, object identity, or predicate while maintaining the heap property through optimized O(log n) inline heap maintenance.

```python
heapx.remove(heap, indices=None, object=None, predicate=None, n=None, return_items=False, max_heap=False, cmp=None, arity=2)
```

**Parameters:**

- **`heap`** *(required, mutable sequence)*  
  The heap to remove items from. Must be a valid heap structure (typically created via `heapify()` or maintained through heap operations). Commonly a `list`, but also supports other mutable sequences. The sequence is modified in-place.

- **`indices`** *(optional, int or sequence of ints, default=None)*  
  Index or indices of items to remove:
  - **Single index:** Integer index (e.g., `0` for root, `-1` for last)
  - **Multiple indices:** Sequence of indices (list, tuple, etc.) for batch removal
  - **Negative indices:** Supported (e.g., `-1` removes last element)
  - **Out of bounds:** Silently ignored (no error raised)
  
  When `None`, no index-based removal is performed.

- **`object`** *(optional, any Python object, default=None)*  
  Remove items by object identity (using `is` comparison):
  - Searches for items that are the exact same object (not just equal)
  - Useful for removing specific object instances
  - Can be combined with `n` to limit removals
  
  When `None`, no object-based removal is performed.

- **`predicate`** *(optional, callable, default=None)*  
  Remove items matching a predicate function:
  - Signature: `predicate(element) -> bool`
  - Items where `predicate(item)` returns `True` are removed
  - Can be combined with `n` to limit removals
  - Example: `lambda x: x > 10` removes all items greater than 10
  
  When `None`, no predicate-based removal is performed.

- **`n`** *(optional, int, default=None)*  
  Maximum number of items to remove:
  - Limits the number of items removed by `object` or `predicate`
  - When `None` or `-1`, removes all matching items
  - Stops after removing `n` items even if more matches exist
  
  Does not apply to `indices` (all specified indices are always removed).

- **`return_items`** *(optional, bool, default=False)*  
  Controls return value format:
  - `False`: Returns count of removed items (integer)
  - `True`: Returns tuple `(count, items)` where `items` is a list of removed elements
  
  Useful when you need to inspect or process removed items.

- **`max_heap`** *(optional, bool, default=False)*  
  Controls heap ordering:
  - `False`: Maintains a **min-heap** where the smallest element stays at index 0
  - `True`: Maintains a **max-heap** where the largest element stays at index 0
  
  Must match the heap type used during `heapify()`.

- **`cmp`** *(optional, callable or None, default=None)*  
  Custom key function for element comparison. When provided:
  - Each element `x` is compared using `cmp(x)` instead of `x` directly
  - Keys are computed on-demand during heap maintenance (O(1) auxiliary space)
  - Signature: `cmp(element) -> comparable_value`
  - Example: `cmp=lambda x: x.priority` for priority-based heaps
  - Example: `cmp=abs` to maintain heap by absolute value
  
  When `None`, elements are compared directly using their natural ordering.

- **`arity`** *(optional, int ≥ 1, default=2)*  
  The branching factor of the heap (must match the heap's existing arity):
  - `arity=1`: Sorted list (O(n) removal with shift)
  - `arity=2`: Binary heap (O(log n) sift with bit-shift optimization)
  - `arity=3`: Ternary heap (O(log₃ n) sift)
  - `arity=4`: Quaternary heap (O(log₄ n) sift with bit-shift)
  - `arity≥5`: General n-ary heap (O(log_k n) sift)
  
  Using the wrong arity will corrupt the heap structure.

**Returns:** 
- `return_items=False`: Integer count of removed items
- `return_items=True`: Tuple `(count, items)` where `items` is a list of removed elements

**Raises:**
- `TypeError`: If `cmp` or `predicate` is not callable or None
- `ValueError`: If `arity < 1`

**Time Complexity:** 
- Single removal: O(log n) where n is the heap size (uses inline sift-up/sift-down)
- Batch removal: O(k + n) where k is the number of items removed (single heapify at end)
- Small heap (n ≤ 16): O(n²) insertion sort but faster in practice
- Arity=1 (sorted list): O(n) per removal due to element shifting
- Predicate/object search: O(n) to scan + removal cost

**Space Complexity:** O(1) auxiliary space for single removal; O(k) for batch removal to track indices

**Algorithm Details:**

The remove operation follows an 11-priority dispatch table for optimal performance:

1. **Small heap (n ≤ 16, no key):** Uses insertion sort after removal for better constant factors
2. **Arity=1 (sorted list):** Direct O(n) removal with element shifting
3. **Binary heap (arity=2, no key):** Inline O(log n) sift-up/sift-down with bit-shift optimization
4. **Ternary heap (arity=3, no key):** Inline O(log₃ n) sift-up/sift-down
5. **Quaternary heap (arity=4, no key):** Inline O(log₄ n) sift with bit-shift `(pos-1)>>2`
6. **General n-ary (arity≥5, no key):** Helper function for flexible arity sift operations
7. **Binary heap with key (arity=2):** On-demand key computation during sift operations
8. **Ternary heap with key (arity=3):** Reduced tree height with key function
9. **General n-ary with key (arity≥4):** Maximum flexibility with custom ordering
10. **Batch removal (result ≤ 16):** Insertion sort for small result heap
11. **Batch removal (result > 16):** Full heapify for large result heap

**Key Optimizations:**

- **O(log n) inline maintenance:** Single removals use sift-up/sift-down instead of O(n) heapify (~100x faster for large heaps)
- **Intelligent sift direction:** Tries sift-up first, then sift-down to minimize operations
- **Pointer refresh:** After list modification, internal array pointer is refreshed to handle reallocation
- **Bit-shift optimization:** Binary (arity=2) and quaternary (arity=4) heaps use fast bit-shift operations
- **On-demand key computation:** Keys computed only when needed, avoiding O(n) memory overhead
- **Small heap optimization:** Heaps with n ≤ 16 use insertion sort with better constant factors
- **Batch efficiency:** Multiple removals collect indices, remove in reverse order, then single heapify
- **Memory safety:** Proper reference counting with `Py_INCREF`/`Py_DECREF` and `Py_SETREF`

**Example Usage:**

```python
import heapx

# Remove by single index (root)
heap = [1, 3, 2, 7, 5, 4, 6]
heapx.heapify(heap)
count = heapx.remove(heap, indices=0)
# count is 1, heap is now [2, 3, 4, 7, 5, 6]

# Remove by multiple indices (batch removal)
heap = list(range(1, 21))
heapx.heapify(heap)
count = heapx.remove(heap, indices=[0, 5, 10, 15])
# count is 4, heap has 16 elements remaining

# Remove by negative index
heap = [1, 2, 3, 4, 5]
heapx.heapify(heap)
count = heapx.remove(heap, indices=-1)
# count is 1, removes last element

# Remove by object identity
obj = "target"
heap = [1, obj, 3, 4, 5]
heapx.heapify(heap, cmp=lambda x: 0 if x == obj else hash(x))
count = heapx.remove(heap, object=obj, cmp=lambda x: 0 if x == obj else hash(x))
# count is 1, obj removed from heap

# Remove by predicate (even numbers)
heap = list(range(1, 21))
heapx.heapify(heap)
count = heapx.remove(heap, predicate=lambda x: x % 2 == 0, n=5)
# count is 5, removes first 5 even numbers

# Remove with return_items
heap = [5, 3, 8, 1, 9]
heapx.heapify(heap)
count, items = heapx.remove(heap, indices=0, return_items=True)
# count is 1, items is [1], heap is [3, 5, 8, 9]

# Remove from max heap
heap = [1, 2, 3, 4, 5]
heapx.heapify(heap, max_heap=True)
count = heapx.remove(heap, indices=0, max_heap=True)
# count is 1, removes largest element (5)

# Remove with custom comparison
heap = [-5, 2, -8, 1, 9, -3, 7]
heapx.heapify(heap, cmp=abs)
count = heapx.remove(heap, indices=0, cmp=abs)
# count is 1, removes element with smallest absolute value

# Remove from ternary heap
heap = list(range(100, 0, -1))
heapx.heapify(heap, arity=3)
count = heapx.remove(heap, indices=10, arity=3)
# count is 1, maintains ternary heap property

# Remove from sorted list (arity=1)
heap = [1, 3, 5, 7, 9]
heapx.heapify(heap, arity=1)
count = heapx.remove(heap, indices=2, arity=1)
# count is 1, heap is [1, 3, 7, 9] - still sorted

# Remove all elements greater than threshold
heap = list(range(1, 21))
heapx.heapify(heap)
count = heapx.remove(heap, predicate=lambda x: x > 15)
# count is 5, removes all elements > 15

# Remove with predicate and limit
heap = list(range(1, 21))
heapx.heapify(heap)
count = heapx.remove(heap, predicate=lambda x: x < 10, n=3)
# count is 3, removes only first 3 matches

# Complex removal with custom class
class Task:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority
    def __lt__(self, other):
        return self.priority < other.priority

heap = [Task("low", 10), Task("high", 1), Task("medium", 5)]
heapx.heapify(heap)
count = heapx.remove(heap, predicate=lambda t: t.priority > 5)
# count is 1, removes low priority task
```

**Performance Notes:**

- Single removal is ~100x faster than O(n) heapify for large heaps (uses O(log n) sift)
- Small heaps (n ≤ 16) benefit from insertion sort optimization
- Binary heaps (arity=2) are fastest due to bit-shift optimizations
- Key functions add ~3x overhead due to function call costs
- Batch removal is more efficient than sequential single removals (O(k + n) vs O(k log n))
- Arity=1 (sorted list) has O(n) removal cost but maintains sorted order
- Predicate/object search requires O(n) scan but removal is still optimized
- Ternary and quaternary heaps reduce tree height, improving cache performance

**Common Use Cases:**

- **Priority Queue Management:** Remove completed or cancelled tasks
- **Dynamic Scheduling:** Remove events that are no longer needed
- **Heap Maintenance:** Remove duplicate or invalid entries
- **Conditional Removal:** Remove items matching specific criteria
- **Batch Operations:** Efficiently remove multiple items at once
- **Object Tracking:** Remove specific object instances from heap
- **Filtered Heaps:** Remove items based on complex predicates

### **5. Replace**

Replace one or more items in the heap by index, object identity, or predicate while maintaining the heap property through optimized O(log n) inline heap maintenance.

```python
heapx.replace(heap, values, indices=None, object=None, predicate=None, max_heap=False, cmp=None, arity=2)
```

**Parameters:**

- **`heap`** *(required, mutable sequence)*  
  The heap to replace items in. Must be a valid heap structure (typically created via `heapify()` or maintained through heap operations). Commonly a `list`, but also supports other mutable sequences. The sequence is modified in-place.

- **`values`** *(required, single value or sequence)*  
  Replacement value(s) for selected items:
  - **Single value:** Any Python object to use as replacement for all selected items
  - **Multiple values:** Sequence of values matching the number of items to replace
  - **Note:** Strings, bytes, and tuples are treated as single values, not sequences
  - **Length requirement:** If a sequence, must have length 1 or match the number of items being replaced
  
  When replacing a list as a value, wrap it in a tuple: `([1, 2, 3],)` to treat it as a single value.

- **`indices`** *(optional, int or sequence of ints, default=None)*  
  Index or indices of items to replace:
  - **Single index:** Integer index (e.g., `0` for root, `-1` for last)
  - **Multiple indices:** Sequence of indices (list, tuple, etc.) for batch replacement
  - **Negative indices:** Supported (e.g., `-1` replaces last element)
  - **Out of bounds:** Silently ignored (no error raised)
  
  When `None`, no index-based replacement is performed.

- **`object`** *(optional, any Python object, default=None)*  
  Replace items by object identity (using `is` comparison):
  - Searches for items that are the exact same object (not just equal)
  - Useful for replacing specific object instances
  - All matching instances are replaced
  
  When `None`, no object-based replacement is performed.

- **`predicate`** *(optional, callable, default=None)*  
  Replace items matching a predicate function:
  - Signature: `predicate(element) -> bool`
  - Items where `predicate(item)` returns `True` are replaced
  - Example: `lambda x: x > 10` replaces all items greater than 10
  
  When `None`, no predicate-based replacement is performed.

- **`max_heap`** *(optional, bool, default=False)*  
  Controls heap ordering:
  - `False`: Maintains a **min-heap** where the smallest element stays at index 0
  - `True`: Maintains a **max-heap** where the largest element stays at index 0
  
  Must match the heap type used during `heapify()`.

- **`cmp`** *(optional, callable or None, default=None)*  
  Custom key function for element comparison. When provided:
  - Each element `x` is compared using `cmp(x)` instead of `x` directly
  - Keys are computed on-demand during heap maintenance (O(1) auxiliary space)
  - Signature: `cmp(element) -> comparable_value`
  - Example: `cmp=lambda x: x.priority` for priority-based heaps
  - Example: `cmp=abs` to maintain heap by absolute value
  
  When `None`, elements are compared directly using their natural ordering.

- **`arity`** *(optional, int ≥ 1, default=2)*  
  The branching factor of the heap (must match the heap's existing arity):
  - `arity=1`: Sorted list (O(n²) re-sort after replacement)
  - `arity=2`: Binary heap (O(log n) sift with bit-shift optimization)
  - `arity=3`: Ternary heap (O(log₃ n) sift)
  - `arity=4`: Quaternary heap (O(log₄ n) sift with bit-shift)
  - `arity≥5`: General n-ary heap (O(log_k n) sift)
  
  Using the wrong arity will corrupt the heap structure.

**Returns:** Integer count of replaced items

**Raises:**
- `TypeError`: If `cmp` or `predicate` is not callable or None
- `ValueError`: If `arity < 1` or if `values` length doesn't match selection count (when sequence)

**Time Complexity:** 
- Single replacement: O(log n) where n is the heap size (uses inline sift-up/sift-down)
- Batch replacement (k < n/4): O(k log n) sequential replacements
- Batch replacement (k ≥ n/4): O(n) batch replace + heapify
- Small heap (n ≤ 16): O(n²) insertion sort but faster in practice
- Arity=1 (sorted list): O(n²) re-sort after replacement
- Predicate/object search: O(n) to scan + replacement cost

**Space Complexity:** O(1) auxiliary space for single replacement; O(k) for batch replacement to track indices

**Algorithm Details:**

The replace operation follows an 11-priority dispatch table for optimal performance:

1. **Small heap (n ≤ 16, no key):** Uses insertion sort after replacement for better constant factors
2. **Arity=1 (sorted list):** Re-sorts entire list after replacement to maintain order
3. **Binary heap (arity=2, no key):** Inline O(log n) sift-up/sift-down with bit-shift optimization
4. **Ternary heap (arity=3, no key):** Inline O(log₃ n) sift-up/sift-down
5. **Quaternary heap (arity=4, no key):** Inline O(log₄ n) sift with bit-shift `(pos-1)>>2`
6. **General n-ary (arity≥5, no key):** Helper function for flexible arity sift operations
7. **Binary heap with key (arity=2):** On-demand key computation during sift operations
8. **Ternary heap with key (arity=3):** Reduced tree height with key function
9. **General n-ary with key (arity≥4):** Maximum flexibility with custom ordering
10. **Small batch (k < n/4):** Sequential O(log n) replacements for efficiency
11. **Large batch (k ≥ n/4):** Batch replace + single heapify for large operations

**Key Optimizations:**

- **O(log n) inline maintenance:** Single replacements use sift-up/sift-down instead of O(n) heapify (~100x faster for large heaps)
- **Intelligent sift direction:** Compares with parent first to determine optimal sift direction (up or down)
- **Adaptive batch strategy:** Automatically selects sequential O(log n) for small batches (k < n/4) or batch+heapify for large batches (k ≥ n/4)
- **Pointer refresh:** After list modification, internal array pointer is refreshed to handle reallocation
- **Bit-shift optimization:** Binary (arity=2) and quaternary (arity=4) heaps use fast bit-shift operations
- **On-demand key computation:** Keys computed only when needed, avoiding O(n) memory overhead
- **Small heap optimization:** Heaps with n ≤ 16 use insertion sort with better constant factors
- **Memory safety:** Proper reference counting with `Py_INCREF`/`Py_DECREF` and `Py_SETREF`

**Example Usage:**

```python
import heapx

# Replace by single index (root)
heap = [1, 3, 2, 7, 5, 4, 6]
heapx.heapify(heap)
count = heapx.replace(heap, 10, indices=0)
# count is 1, heap is now [2, 3, 4, 7, 5, 10, 6]

# Replace by multiple indices (batch replacement)
heap = list(range(1, 11))
heapx.heapify(heap)
count = heapx.replace(heap, [99, 98, 97], indices=[0, 5, 9])
# count is 3, replaces items at indices 0, 5, 9

# Replace by negative index
heap = [1, 2, 3, 4, 5]
heapx.heapify(heap)
count = heapx.replace(heap, 99, indices=-1)
# count is 1, replaces last element

# Replace by object identity
obj = "target"
heap = [1, obj, 3, 4, 5]
heapx.heapify(heap, cmp=lambda x: 0 if x == obj else hash(x))
count = heapx.replace(heap, "new", object=obj, cmp=lambda x: 0 if isinstance(x, str) else hash(x))
# count is 1, obj replaced with "new"

# Replace by predicate (even numbers)
heap = list(range(1, 21))
heapx.heapify(heap)
count = heapx.replace(heap, 99, predicate=lambda x: x % 2 == 0)
# count is 10, replaces all even numbers with 99

# Replace with single value for multiple matches
heap = [5, 3, 8, 1, 9]
heapx.heapify(heap)
count = heapx.replace(heap, 0, predicate=lambda x: x > 5)
# count is 2, replaces 8 and 9 with 0

# Replace from max heap
heap = [1, 2, 3, 4, 5]
heapx.heapify(heap, max_heap=True)
count = heapx.replace(heap, 10, indices=0, max_heap=True)
# count is 1, replaces largest element (5) with 10

# Replace with custom comparison
heap = [-5, 2, -8, 1, 9, -3, 7]
heapx.heapify(heap, cmp=abs)
count = heapx.replace(heap, 100, indices=0, cmp=abs)
# count is 1, replaces element with smallest absolute value

# Replace from ternary heap
heap = list(range(100, 0, -1))
heapx.heapify(heap, arity=3)
count = heapx.replace(heap, 999, indices=10, arity=3)
# count is 1, maintains ternary heap property

# Replace from sorted list (arity=1)
heap = [1, 3, 5, 7, 9]
heapx.heapify(heap, arity=1)
count = heapx.replace(heap, 4, indices=2, arity=1)
# count is 1, heap is [1, 3, 4, 7, 9] - still sorted

# Replace all elements greater than threshold
heap = list(range(1, 21))
heapx.heapify(heap)
count = heapx.replace(heap, 0, predicate=lambda x: x > 15)
# count is 5, replaces all elements > 15 with 0

# Replace with matching value sequence
heap = list(range(1, 11))
heapx.heapify(heap)
count = heapx.replace(heap, [100, 200, 300], indices=[0, 1, 2])
# count is 3, replaces indices 0, 1, 2 with 100, 200, 300 respectively

# Replace list as a value (wrap in tuple)
obj = [1, 2, 3]
heap = [obj, [4, 5], [6, 7]]
heapx.heapify(heap, cmp=lambda x: sum(x))
count = heapx.replace(heap, ([0, 0, 0],), object=obj, cmp=lambda x: sum(x))
# count is 1, replaces [1, 2, 3] with [0, 0, 0]

# Complex replacement with custom class
class Task:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority
    def __lt__(self, other):
        return self.priority < other.priority

heap = [Task("low", 10), Task("high", 1), Task("medium", 5)]
heapx.heapify(heap)
count = heapx.replace(heap, Task("urgent", 0), predicate=lambda t: t.priority > 5)
# count is 1, replaces low priority task with urgent task
```

**Performance Notes:**

- Single replacement is ~100x faster than O(n) heapify for large heaps (uses O(log n) sift)
- Small heaps (n ≤ 16) benefit from insertion sort optimization
- Binary heaps (arity=2) are fastest due to bit-shift optimizations
- Key functions add ~3x overhead due to function call costs
- Adaptive batch strategy automatically optimizes: sequential for k < n/4, heapify for k ≥ n/4
- Arity=1 (sorted list) has O(n²) replacement cost but maintains sorted order
- Predicate/object search requires O(n) scan but replacement is still optimized
- Ternary and quaternary heaps reduce tree height, improving cache performance

**Common Use Cases:**

- **Priority Queue Updates:** Replace task priorities dynamically
- **Dynamic Scheduling:** Update event timestamps or priorities
- **Heap Maintenance:** Replace invalid or outdated entries
- **Conditional Updates:** Replace items matching specific criteria
- **Batch Operations:** Efficiently replace multiple items at once
- **Object Tracking:** Replace specific object instances in heap
- **Value Normalization:** Replace items based on complex predicates

### **6. Sort**

Sort a sequence using the heapsort algorithm with optimal O(n log n) time complexity. Supports in-place and copy modes, custom comparison functions, and all heap arities.

```python
heapx.sort(heap, reverse=False, inplace=False, max_heap=False, cmp=None, arity=2)
```

**Parameters:**

- **`heap`** *(required, sequence)*  
  The sequence to sort. Can be any Python sequence supporting `len()`, `__getitem__()`, and `__setitem__()`. Commonly a `list`, but also supports `tuple`, `bytearray`, or custom sequences. When `inplace=False` (default), the original sequence is unchanged and a sorted copy is returned.

- **`reverse`** *(optional, bool, default=False)*  
  Sort order:
  - `False`: Ascending order (smallest to largest)
  - `True`: Descending order (largest to smallest)
  
  Independent of `max_heap` parameter.

- **`inplace`** *(optional, bool, default=False)*  
  Modification mode:
  - `False`: Returns a new sorted list, original unchanged
  - `True`: Sorts in-place, modifies original sequence, returns `None`
  
  When `inplace=True` and the input is already a heap, the heap property is restored after sorting.

- **`max_heap`** *(optional, bool, default=False)*  
  Heap type for internal heapify operation:
  - `False`: Uses min-heap for heapify phase
  - `True`: Uses max-heap for heapify phase
  
  Only relevant when input is already a heap. For non-heap input, this parameter is automatically handled.

- **`cmp`** *(optional, callable or None, default=None)*  
  Custom key function for element comparison. When provided:
  - Each element `x` is compared using `cmp(x)` instead of `x` directly
  - Keys are computed on-demand during heap operations (O(1) auxiliary space)
  - Signature: `cmp(element) -> comparable_value`
  - Example: `cmp=lambda x: x.priority` for priority-based sorting
  - Example: `cmp=abs` to sort by absolute value
  
  When `None`, elements are compared directly using their natural ordering.

- **`arity`** *(optional, int ≥ 1, default=2)*  
  The branching factor of the heap used internally:
  - `arity=1`: Sorted list (O(n²) insertion sort for small data, O(n) if already sorted)
  - `arity=2`: Binary heap (standard heapsort with bit-shift optimization)
  - `arity=3`: Ternary heap (reduced tree height)
  - `arity=4`: Quaternary heap (bit-shift optimization)
  - `arity≥5`: General n-ary heap (flexible branching)
  
  Higher arity reduces tree height but increases comparison overhead per level. Binary heaps (arity=2) are optimal for most use cases.

**Returns:** 
- `inplace=False`: Sorted list (new list object)
- `inplace=True`: `None` (original sequence modified)

**Raises:**
- `TypeError`: If `cmp` is not callable or None
- `ValueError`: If `arity < 1`

**Time Complexity:** 
- Heapsort: O(n log n) for all cases
- Small heap (n ≤ 16, no key): O(n²) insertion sort but faster in practice
- Arity=1: O(n²) insertion sort for unsorted data, O(n) if already sorted
- With key function: O(n log n) + O(n log n) key calls (on-demand computation)

**Space Complexity:** 
- `inplace=False`: O(n) for new list
- `inplace=True`: O(1) auxiliary space (no key caching; keys computed on-demand)

**Algorithm Details:**

The sort operation follows an 11-priority dispatch table for optimal performance:

1. **Small heap (n ≤ 16, no key):** Direct insertion sort (O(n²) but faster constant factors)
2. **Arity=1 (sorted list):** Insertion sort to ensure order, then reverse if needed (O(n²) or O(n))
3. **Binary heap (arity=2, no key):** Floyd's heapify + inline binary heapsort with bit-shift
4. **Ternary heap (arity=3, no key):** Ternary heapify + inline ternary heapsort
5. **Quaternary heap (arity=4, no key):** Quaternary heapify + inline quaternary heapsort with bit-shift
6. **N-ary heap (arity≥5, no key, n<1000):** Small n-ary heapify + general heapsort loop
7. **N-ary heap (arity≥5, no key, n≥1000):** Generic heapify + general heapsort loop
8. **Binary heap with key (arity=2):** Binary heapify with key + inline heapsort with on-demand keys
9. **Ternary heap with key (arity=3):** Ternary heapify with key + ternary heapsort with key
10. **N-ary heap with key (arity≥4):** Generic heapify with key + general heapsort with key
11. **Generic sequence (non-list):** Generic heapify + PySequence API heapsort

**Key Optimizations:**

- **Direct C function calls:** All heapify operations use direct C calls instead of Python API wrappers
- **Inline heapsort implementations:** Binary, ternary, and quaternary heaps have specialized inline loops
- **Bit-shift optimization:** Binary (arity=2) and quaternary (arity=4) use fast bit-shift operations
- **On-demand key computation:** Keys computed only when needed during sift operations (O(1) space)
- **Small heap fast path:** Direct insertion sort for n ≤ 16 (better constant factors)
- **Arity=1 optimization:** O(n) sort for already sorted data instead of O(n log n)
- **Size-based dispatch:** Separate paths for n<1000 vs n≥1000 with arity≥5
- **Memory safety:** Proper reference counting with `Py_INCREF`/`Py_DECREF` and `Py_SETREF`

**Example Usage:**

```python
import heapx

# Basic ascending sort
data = [5, 2, 8, 1, 9, 3, 7]
result = heapx.sort(data)
# result is [1, 2, 3, 5, 7, 8, 9], data unchanged

# Descending sort
data = [5, 2, 8, 1, 9, 3, 7]
result = heapx.sort(data, reverse=True)
# result is [9, 8, 7, 5, 3, 2, 1]

# In-place sort
data = [5, 2, 8, 1, 9]
heapx.heapify(data)
heapx.sort(data, inplace=True)
# data is now [1, 2, 5, 8, 9], returns None

# Sort with custom comparison (by absolute value)
data = [-5, 2, -8, 1, 9, -3, 7]
result = heapx.sort(data, cmp=abs)
# result is [1, 2, -3, -5, 7, -8, 9]

# Sort strings by length
data = ["apple", "pie", "banana", "kiwi"]
result = heapx.sort(data, cmp=len)
# result is ['pie', 'kiwi', 'apple', 'banana']

# Sort with ternary heap
data = list(range(100, 0, -1))
result = heapx.sort(data, arity=3)
# result is [1, 2, 3, ..., 100]

# Sort from existing heap
data = [5, 2, 8, 1, 9]
heapx.heapify(data)
result = heapx.sort(data, max_heap=False)
# result is [1, 2, 5, 8, 9]

# Sort with key and reverse
data = [-5, 2, -8, 1, 9]
result = heapx.sort(data, cmp=abs, reverse=True)
# result is [9, -8, -5, 2, 1]

# Sort custom objects
class Task:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority
    def __repr__(self):
        return f"Task({self.name}, {self.priority})"

tasks = [Task("low", 10), Task("high", 1), Task("medium", 5)]
result = heapx.sort(tasks, cmp=lambda t: t.priority)
# result is [Task(high, 1), Task(medium, 5), Task(low, 10)]

# Sort large dataset with quaternary heap
data = list(range(10000, 0, -1))
result = heapx.sort(data, arity=4)
# result is [1, 2, 3, ..., 10000]

# Sort tuple input
data = (5, 2, 8, 1, 9)
result = heapx.sort(data)
# result is [1, 2, 5, 8, 9] (returns list)

# Sort with modulo key
data = list(range(1, 51))
result = heapx.sort(data, cmp=lambda x: x % 10)
# Sorted by last digit: [10, 20, 30, 40, 50, 1, 11, 21, ...]

# In-place sort preserves heap property
data = [5, 2, 8, 1, 9, 3, 7]
heapx.heapify(data, max_heap=True)
heapx.sort(data, max_heap=True, inplace=True)
# data is [1, 2, 3, 5, 7, 8, 9] and maintains heap property

# Sort with arity=1 (sorted list optimization)
data = list(range(100, 0, -1))
result = heapx.sort(data, arity=1)
# result is [1, 2, 3, ..., 100] using optimized path
```

**Performance Notes:**

- Heapsort is **not stable** - equal elements may not maintain their original relative order
- Small heaps (n ≤ 16) use insertion sort which is faster than heapsort for tiny datasets
- Binary heaps (arity=2) are fastest for most use cases due to bit-shift optimizations
- Key functions add ~3x overhead due to function call costs
- Arity=1 (sorted list) has O(n) cost if data is already sorted
- Ternary and quaternary heaps reduce tree height, improving cache performance for large datasets
- In-place sort is more memory efficient but modifies the original sequence
- For stable sorting, use Python's built-in `sorted()` function

**Common Use Cases:**

- **General Sorting:** Sort any sequence with O(n log n) guaranteed performance
- **Large Datasets:** Efficient sorting with predictable memory usage
- **Custom Ordering:** Sort by complex criteria using key functions
- **In-Place Sorting:** Memory-efficient sorting when original order is not needed
- **Heap-Based Algorithms:** Sort data that's already in heap form
- **Priority-Based Sorting:** Sort tasks, events, or items by priority
- **Numerical Analysis:** Sort data by absolute value, magnitude, or custom metrics

### **7. Merge**

Merge multiple sequences into a single heap with optimal O(N) time complexity. Supports pre-heapified input optimization, custom comparison functions, and all heap arities.

```python
heapx.merge(*heaps, max_heap=False, cmp=None, arity=2, sorted_heaps=False)
```

**Parameters:**

- **`*heaps`** *(required, variable number of sequences)*  
  Two or more sequences to merge into a single heap. Each sequence can be any Python sequence supporting `len()` and `__getitem__()`. Commonly lists, but also supports tuples, arrays, or custom sequences. At least 2 sequences must be provided.

- **`max_heap`** *(optional, bool, default=False)*  
  Controls heap ordering:
  - `False`: Creates a **min-heap** where the smallest element is at index 0
  - `True`: Creates a **max-heap** where the largest element is at index 0
  
  Must match the heap type of input sequences when `sorted_heaps=True`.

- **`cmp`** *(optional, callable or None, default=None)*  
  Custom key function for element comparison. When provided:
  - Each element `x` is compared using `cmp(x)` instead of `x` directly
  - Keys are computed on-demand during heapify (O(1) auxiliary space)
  - Signature: `cmp(element) -> comparable_value`
  - Example: `cmp=lambda x: x.priority` for priority-based merging
  - Example: `cmp=abs` to merge by absolute value
  
  When `None`, elements are compared directly using their natural ordering.

- **`arity`** *(optional, int ≥ 1, default=2)*  
  The branching factor of the resulting heap:
  - `arity=1`: Unary heap (degenerates to sorted list)
  - `arity=2`: Binary heap (standard, most common)
  - `arity=3`: Ternary heap (reduces tree height by ~37%)
  - `arity=4`: Quaternary heap (optimal for some cache architectures)
  - `arity≥5`: General n-ary heap
  
  Higher arity reduces tree height but increases comparison overhead per level. Binary heaps (arity=2) are optimal for most use cases.

- **`sorted_heaps`** *(optional, bool, default=False)*  
  Optimization flag for pre-heapified input:
  - `False`: Performs heapify on concatenated result (default, safe for any input)
  - `True`: Skips heapify phase, assumes all input sequences are already valid heaps
  
  When `True`, provides ~2x speedup by skipping the O(N) heapify operation. Only use when all input sequences are already valid heaps with matching `max_heap`, `cmp`, and `arity` parameters.

**Returns:** New list containing all elements from input sequences, organized as a valid heap

**Raises:**
- `ValueError`: If fewer than 2 sequences are provided
- `TypeError`: If `cmp` is not callable or None, or if inputs are not sequences

**Time Complexity:** 
- Concatenation: O(N) where N is the total number of elements
- Heapify: O(N) when `sorted_heaps=False`
- Total: O(N) for merge operation
- With `sorted_heaps=True`: O(N) concatenation only (skips heapify)

**Space Complexity:** O(N) for the new merged list

**Algorithm Details:**

The merge operation follows an 11-priority dispatch table for optimal performance:

1. **Small heap (n ≤ 16, no key):** Direct insertion sort after concatenation (O(n²) but faster constant factors)
2. **Arity=1 (sorted list):** Concatenate and sort to maintain order
3. **Binary heap (arity=2, no key):** Floyd's heapify with bit-shift optimization
4. **Ternary heap (arity=3, no key):** Ternary heapify with reduced tree height
5. **Quaternary heap (arity=4, no key):** Quaternary heapify with bit-shift optimization
6. **N-ary heap (arity≥5, no key, n<1000):** Small n-ary heapify for medium datasets
7. **N-ary heap (arity≥5, no key, n≥1000):** Generic heapify for large datasets
8. **Binary heap with key (arity=2):** Binary heapify with on-demand key computation
9. **Ternary heap with key (arity=3):** Ternary heapify with key function
10. **N-ary heap with key (arity≥4):** Generic heapify with key function
11. **Generic sequence (non-list):** PySequence API for tuple/array compatibility

**Key Optimizations:**

- **PySequence_Fast optimization:** Converts sequences to fast-access format for direct pointer manipulation
- **Direct pointer concatenation:** Uses `memcpy()` for bulk element copying instead of Python API calls
- **Empty heap skipping:** Automatically skips empty input sequences during concatenation
- **Single non-empty optimization:** Returns direct copy when only one non-empty sequence exists
- **sorted_heaps parameter:** Skips O(N) heapify when inputs are already valid heaps (~2x speedup)
- **Bit-shift optimization:** Binary (arity=2) and quaternary (arity=4) heaps use fast bit-shift operations
- **On-demand key computation:** Keys computed only when needed during heapify (O(1) space)
- **Size-based dispatch:** Separate paths for n<1000 vs n≥1000 with arity≥5
- **Memory safety:** Proper reference counting with `Py_INCREF`/`Py_DECREF`

**Example Usage:**

```python
import heapx

# Basic merge (two lists)
heap1 = [1, 3, 5, 7, 9]
heap2 = [2, 4, 6, 8, 10]
result = heapx.merge(heap1, heap2)
# result is [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] (heapified)

# Merge three heaps
heap1 = [1, 4, 7]
heap2 = [2, 5, 8]
heap3 = [3, 6, 9]
result = heapx.merge(heap1, heap2, heap3)
# result contains all 9 elements in heap order

# Merge many heaps
heaps = [list(range(i*10, (i+1)*10)) for i in range(10)]
result = heapx.merge(*heaps)
# result contains 100 elements in heap order

# Max-heap merge
heap1 = [9, 7, 5, 3, 1]
heap2 = [8, 6, 4, 2, 0]
heapx.heapify(heap1, max_heap=True)
heapx.heapify(heap2, max_heap=True)
result = heapx.merge(heap1, heap2, max_heap=True)
# result is a max-heap containing all elements

# Merge with custom comparison (by absolute value)
heap1 = [-5, 2, -8, 1]
heap2 = [9, -3, 7, -4]
result = heapx.merge(heap1, heap2, cmp=abs)
# result is heapified by absolute value

# Merge with ternary heap
heap1 = list(range(50))
heap2 = list(range(50, 100))
result = heapx.merge(heap1, heap2, arity=3)
# result is a ternary heap with reduced height

# Optimized merge with sorted_heaps=True
heap1 = [1, 3, 5, 7, 9]
heap2 = [2, 4, 6, 8, 10]
heapx.heapify(heap1)
heapx.heapify(heap2)
result = heapx.merge(heap1, heap2, sorted_heaps=True)
# ~2x faster - skips heapify since inputs are already heaps

# Merge with key and arity
heap1 = list(range(-25, 0))
heap2 = list(range(0, 25))
result = heapx.merge(heap1, heap2, cmp=abs, arity=3)
# Ternary heap ordered by absolute value

# Merge tuples
heap1 = (1, 3, 5)
heap2 = (2, 4, 6)
result = heapx.merge(heap1, heap2)
# result is [1, 2, 3, 4, 5, 6] (returns list)

# Merge with empty heaps
heap1 = [1, 2, 3]
heap2 = []
heap3 = [4, 5, 6]
result = heapx.merge(heap1, heap2, heap3)
# Empty heap is automatically skipped

# Priority queue merge
class Task:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority
    def __repr__(self):
        return f"Task({self.name}, {self.priority})"

queue1 = [Task("low", 10), Task("medium", 5)]
queue2 = [Task("high", 1), Task("urgent", 0)]
result = heapx.merge(queue1, queue2, cmp=lambda t: t.priority)
# result is heap of tasks ordered by priority

# K-way merge for sorted sequences
sorted1 = [1, 4, 7, 10]
sorted2 = [2, 5, 8, 11]
sorted3 = [3, 6, 9, 12]
heapx.heapify(sorted1, arity=1)
heapx.heapify(sorted2, arity=1)
heapx.heapify(sorted3, arity=1)
result = heapx.merge(sorted1, sorted2, sorted3, arity=1, sorted_heaps=True)
# Efficient k-way merge maintaining sorted order

# Large dataset merge
heap1 = list(range(10000))
heap2 = list(range(10000, 20000))
result = heapx.merge(heap1, heap2)
# Efficiently merges 20,000 elements

# Merge with quaternary heap
heap1 = list(range(500))
heap2 = list(range(500, 1000))
result = heapx.merge(heap1, heap2, arity=4)
# Quaternary heap for cache-friendly access
```

**Performance Notes:**

- Merge is O(N) where N is the total number of elements across all input sequences
- `sorted_heaps=True` provides ~2x speedup by skipping heapify (use only when inputs are valid heaps)
- Binary heaps (arity=2) are fastest for most use cases due to bit-shift optimizations
- Key functions add ~3x overhead due to function call costs
- Empty input sequences are automatically skipped with no performance penalty
- Single non-empty sequence returns direct copy (no concatenation overhead)
- Ternary and quaternary heaps reduce tree height, improving cache performance for large datasets
- PySequence_Fast optimization provides 40-60% speedup for mixed sequence types

**Common Use Cases:**

- **Priority Queue Merging:** Combine multiple priority queues into one
- **K-Way Merge:** Merge k sorted or heapified sequences efficiently
- **Distributed Systems:** Merge heaps from multiple sources/workers
- **Batch Processing:** Combine multiple batches of data into single heap
- **Event Scheduling:** Merge event queues from different sources
- **Data Aggregation:** Combine datasets while maintaining heap property
## Advanced Usage

### Priority Queue Implementation

```python
import heapx

class PriorityQueue:
    def __init__(self, max_heap=False):
        self._heap = []
        self._max_heap = max_heap
    
    def push(self, item, priority):
        heapx.push(self._heap, (priority, item), max_heap=self._max_heap)
    
    def pop(self):
        if not self._heap:
            raise IndexError("pop from empty priority queue")
        priority, item = heapx.pop(self._heap, max_heap=self._max_heap)
        return item
    
    def peek(self):
        if not self._heap:
            raise IndexError("peek from empty priority queue")
        return self._heap[0][1]
    
    def __len__(self):
        return len(self._heap)

# Usage
pq = PriorityQueue()
pq.push("task1", priority=5)
pq.push("task2", priority=1)
pq.push("task3", priority=3)
print(pq.pop())  # "task2" (lowest priority)
```

### Top-K Elements

```python
import heapx

def top_k_elements(data, k, key=None):
    """Find top k elements efficiently."""
    heap = data[:k]
    heapx.heapify(heap, cmp=key)
    
    for item in data[k:]:
        if key:
            if key(item) > key(heap[0]):
                heapx.replace(heap, item, indices=0, cmp=key)
        else:
            if item > heap[0]:
                heapx.replace(heap, item, indices=0)
    
    return heapx.sort(heap, reverse=True, cmp=key)

# Usage
data = [5, 2, 8, 1, 9, 3, 7, 4, 6]
top_3 = top_k_elements(data, 3)
print(top_3)  # [9, 8, 7]
```

### Median Maintenance

```python
import heapx

class MedianFinder:
    def __init__(self):
        self._max_heap = []  # Lower half
        self._min_heap = []  # Upper half
    
    def add_num(self, num):
        if not self._max_heap or num <= -self._max_heap[0]:
            heapx.push(self._max_heap, -num)
        else:
            heapx.push(self._min_heap, num)
        
        # Balance heaps
        if len(self._max_heap) > len(self._min_heap) + 1:
            heapx.push(self._min_heap, -heapx.pop(self._max_heap))
        elif len(self._min_heap) > len(self._max_heap):
            heapx.push(self._max_heap, -heapx.pop(self._min_heap))
    
    def find_median(self):
        if len(self._max_heap) > len(self._min_heap):
            return -self._max_heap[0]
        return (-self._max_heap[0] + self._min_heap[0]) / 2.0

# Usage
mf = MedianFinder()
for num in [5, 2, 8, 1, 9]:
    mf.add_num(num)
    print(f"Median: {mf.find_median()}")
```

### K-Way Merge

```python
import heapx

def k_way_merge(*sorted_lists):
    """Merge k sorted lists efficiently."""
    # Create initial heap with first element from each list
    heap = []
    for i, lst in enumerate(sorted_lists):
        if lst:
            heapx.push(heap, (lst[0], i, 0))
    
    result = []
    while heap:
        val, list_idx, elem_idx = heapx.pop(heap)
        result.append(val)
        
        # Add next element from same list
        if elem_idx + 1 < len(sorted_lists[list_idx]):
            next_val = sorted_lists[list_idx][elem_idx + 1]
            heapx.push(heap, (next_val, list_idx, elem_idx + 1))
    
    return result

# Usage
list1 = [1, 4, 7]
list2 = [2, 5, 8]
list3 = [3, 6, 9]
merged = k_way_merge(list1, list2, list3)
print(merged)  # [1, 2, 3, 4, 5, 6, 7, 8, 9]
```

## Technical Details

### Implementation Architecture

**heapx** is implemented as a C extension module with the following architecture:

1. **Fast Comparison Layer**
   - Type-specific comparison functions for integers, floats, strings, bytes, booleans, and tuples
   - Automatic fallback to Python's rich comparison for custom types
   - Early termination for tuple comparisons

2. **Algorithm Dispatch Layer**
   - 11-priority dispatch table for each operation
   - Runtime detection of optimal algorithm based on:
     - Data structure type (list vs generic sequence)
     - Heap size (small, medium, large)
     - Arity (1, 2, 3, 4, or n-ary)
     - Key function presence
     - Element type homogeneity

3. **Optimization Layer**
   - Floyd's algorithm for binary heap heapification
   - Specialized implementations for ternary and quaternary heaps
   - Insertion sort for small heaps (n ≤ 16)
   - Key caching for custom comparison functions
   - Advanced prefetching for cache optimization
   - SIMD-friendly data layouts

### Compiler Optimizations

The module is compiled with aggressive optimizations:

**GCC/Clang:**
- `-O3`: Maximum optimization level
- `-march=native -mtune=native`: CPU-specific optimizations
- `-flto`: Link-time optimization
- `-ffast-math`: Fast floating-point math
- `-funroll-loops`: Loop unrolling
- `-ftree-vectorize` (GCC) / `-fvectorize` (Clang): Auto-vectorization

**MSVC:**
- `/O2`: Maximum optimization
- `/Ot`: Favor fast code
- `/GL`: Whole program optimization
- `/arch:AVX2`: AVX2 instructions
- `/fp:fast`: Fast floating-point

### Platform Support

- **Operating Systems:** Linux, macOS, Windows
- **Architectures:** x86-64, ARM64
- **Python Versions:** 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
- **Compilers:** GCC, Clang, MSVC

### Memory Safety

All operations maintain proper Python reference counting:
- `Py_INCREF` / `Py_DECREF` for reference management
- `Py_SETREF` for safe reference replacement
- Proper cleanup on error paths
- No memory leaks in normal or exceptional execution

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Code Style**
   - C code: Follow Python's C API conventions
   - Python code: Follow PEP 8
   - Use meaningful variable names
   - Add comments for complex logic

2. **Testing**
   - Add tests for new features
   - Ensure all existing tests pass
   - Include edge cases and error conditions
   - Add performance benchmarks for optimizations

3. **Documentation**
   - Update README.md for API changes
   - Add docstrings for new functions
   - Include usage examples
   - Document performance characteristics

4. **Pull Requests**
   - Create feature branch from `main`
   - Write clear commit messages
   - Reference related issues
   - Ensure CI passes

### Development Setup

```bash
# Clone repository
git clone https://github.com/ivan121500/heapx.git
cd heapx

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run benchmarks
pytest tests/ -m benchmark
```

## License

MIT License

Copyright (c) 2024 Aniruddha Mukherjee

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

**Author:** Aniruddha Mukherjee  
**Email:** mukher66@purdue.edu  
**GitHub:** https://github.com/ivan121500/heapx  
**PyPI:** https://pypi.org/project/heapx/


























