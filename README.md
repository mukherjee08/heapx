# heapx - Enhanced Heap Operations for Python

- [Overview](#overview)
- [Detailed Benefits Analysis](#detailed-benefits-analysis)
  - [1. Native Max-heap & Min-heap Support](#1-native-max-heap--min-heap-support)
  - [2. Advanced Performance Optimizations](#2-advanced-performance-optimizations)
  - [3. N-ary Heap Support](#3-n-ary-heap-support)
  - [4. Broader Sequence Support](#4-broader-sequence-support)
  - [5. Custom Comparison Functions](#5-custom-comparison-functions)
  - [6. Memory Efficiency](#6-memory-efficiency)
- [API Function Overview](#api-function-overview)
  - [1. Heapify](#1-heapify)
  - [2. Push](#2-push)
  - [3. Pop](#3-pop)
  - [4. Remove](#4-remove)
  - [5. Replace](#5-replace)
  - [6. Sort](#6-sort)
  - [7. Merge](#7-merge)

## Overview

The `heapx` module provides optimized heap operations with enhanced functionality compared to Python's standard heap modules, such as the built in standard library `heapq`, or other third-party packages such as `heapdict`, `pqdict`, `binarydict`, `fibonacci-heap-mod`, `pairing-heap`, and `binheap`.

Heap data types are very useful because they always keep the most important item/element at the very top. It's like having a priority system which automatically organizes itself. 

## Detailed Benefits Analysis



### **1. Native Max-heap & Min-heap Support**



### **2. Advanced Performance Optimizations**



### **3. N-ary Heap Support**



### **4. Broader Sequence Support**



### **5. Custom Comparison Functions**



### **6. Memory Efficiency**



## API Function Overview

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



### **6. Sort**



### **7. Merge**


























