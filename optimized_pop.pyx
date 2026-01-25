# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: nonecheck=False
# cython: overflowcheck=False
# cython: infer_types=True
# cython: optimize.use_switch=True
# cython: optimize.unpack_method_calls=True
# cython: linetrace=False

"""
Ultra-Optimized Heap Operations for heapx

Optimizations:
- Type-specialized fast paths (int, float, bool use bottom-up Floyd's algorithm)
- Standard sift-down for str/custom (simpler, matches heapq performance)
- Native Python comparison for strings (faster than PyUnicode_Compare)
- Memory prefetching for cache optimization on numeric types
- Direct C-level value extraction bypassing Python API
"""

from cpython.object cimport PyObject
from cpython.ref cimport Py_INCREF, Py_DECREF

cdef extern from "Python.h":
    Py_ssize_t PyList_GET_SIZE(object)
    PyObject* PyList_GET_ITEM(object, Py_ssize_t)
    void PyList_SET_ITEM(object, Py_ssize_t, PyObject*)
    double PyFloat_AS_DOUBLE(object)
    int PyObject_RichCompareBool(object, object, int) except -1
    int Py_LT, Py_GT
    PyObject* Py_True

cdef extern from *:
    """
    #ifdef __GNUC__
    #define PREFETCH(addr) __builtin_prefetch(addr, 0, 3)
    #else
    #define PREFETCH(addr) ((void)0)
    #endif
    """
    void PREFETCH(void* addr) nogil

DEF TYPE_INT = 1
DEF TYPE_FLOAT = 2
DEF TYPE_STR = 3
DEF TYPE_BOOL = 4
DEF TYPE_OTHER = 5

cdef inline int detect_type(list heap, Py_ssize_t n) noexcept:
    """Fast type detection from first element."""
    if n == 0:
        return TYPE_OTHER
    cdef type t = type(heap[0])
    if t is int:
        return TYPE_INT
    if t is float:
        return TYPE_FLOAT
    if t is str:
        return TYPE_STR
    if t is bool:
        return TYPE_BOOL
    return TYPE_OTHER

# =============================================================================
# INTEGER SIFT-DOWN (Bottom-up Floyd's algorithm)
# =============================================================================

cdef inline void sift_down_int_min(list heap, Py_ssize_t pos, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t child, right, parent, gc
        object item = heap[pos]
        long item_val = <long>item
        Py_ssize_t start = pos
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        gc = (child << 1) + 1
        if gc < n:
            PREFETCH(<void*>heap[gc])
        right = child + 1
        if right < n and <long>heap[right] < <long>heap[child]:
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        if item_val >= <long>heap[parent]:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_int_max(list heap, Py_ssize_t pos, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t child, right, parent, gc
        object item = heap[pos]
        long item_val = <long>item
        Py_ssize_t start = pos
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        gc = (child << 1) + 1
        if gc < n:
            PREFETCH(<void*>heap[gc])
        right = child + 1
        if right < n and <long>heap[right] > <long>heap[child]:
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        if item_val <= <long>heap[parent]:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# FLOAT SIFT-DOWN (Bottom-up Floyd's algorithm)
# =============================================================================

cdef inline void sift_down_float_min(list heap, Py_ssize_t pos, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t child, right, parent, gc
        object item = heap[pos]
        double item_val = PyFloat_AS_DOUBLE(item)
        Py_ssize_t start = pos
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        gc = (child << 1) + 1
        if gc < n:
            PREFETCH(<void*>heap[gc])
        right = child + 1
        if right < n and PyFloat_AS_DOUBLE(heap[right]) < PyFloat_AS_DOUBLE(heap[child]):
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        if item_val >= PyFloat_AS_DOUBLE(heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_float_max(list heap, Py_ssize_t pos, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t child, right, parent, gc
        object item = heap[pos]
        double item_val = PyFloat_AS_DOUBLE(item)
        Py_ssize_t start = pos
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        gc = (child << 1) + 1
        if gc < n:
            PREFETCH(<void*>heap[gc])
        right = child + 1
        if right < n and PyFloat_AS_DOUBLE(heap[right]) > PyFloat_AS_DOUBLE(heap[child]):
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        if item_val <= PyFloat_AS_DOUBLE(heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# BOOL SIFT-DOWN (Bottom-up Floyd's algorithm - pointer comparison)
# =============================================================================

cdef inline void sift_down_bool_min(list heap, Py_ssize_t pos, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t child, right, parent, gc
        object item = heap[pos]
        bint item_val = item is True
        Py_ssize_t start = pos
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        gc = (child << 1) + 1
        if gc < n:
            PREFETCH(<void*>heap[gc])
        right = child + 1
        # False < True, so prefer False (not True)
        if right < n and (heap[right] is not True) and (heap[child] is True):
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        if item_val >= (heap[parent] is True):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_bool_max(list heap, Py_ssize_t pos, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t child, right, parent, gc
        object item = heap[pos]
        bint item_val = item is True
        Py_ssize_t start = pos
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        gc = (child << 1) + 1
        if gc < n:
            PREFETCH(<void*>heap[gc])
        right = child + 1
        if right < n and (heap[right] is True) and (heap[child] is not True):
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        if item_val <= (heap[parent] is True):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# STRING SIFT-DOWN (Standard top-down - matches heapq approach)
# Uses native Python < operator which is highly optimized
# =============================================================================

cdef inline void sift_down_str_min(list heap, Py_ssize_t pos, Py_ssize_t n):
    """Standard sift-down for strings using native Python comparison."""
    cdef:
        Py_ssize_t child, right, limit
        object item = heap[pos]
    
    limit = n >> 1
    while pos < limit:
        child = (pos << 1) + 1
        right = child + 1
        if right < n and heap[right] < heap[child]:
            child = right
        if item <= heap[child]:
            break
        heap[pos] = heap[child]
        pos = child
    heap[pos] = item

cdef inline void sift_down_str_max(list heap, Py_ssize_t pos, Py_ssize_t n):
    """Standard sift-down for strings (max-heap)."""
    cdef:
        Py_ssize_t child, right, limit
        object item = heap[pos]
    
    limit = n >> 1
    while pos < limit:
        child = (pos << 1) + 1
        right = child + 1
        if right < n and heap[right] > heap[child]:
            child = right
        if item >= heap[child]:
            break
        heap[pos] = heap[child]
        pos = child
    heap[pos] = item

# =============================================================================
# GENERIC SIFT-DOWN (Standard top-down - for custom objects)
# =============================================================================

cdef inline void sift_down_generic_min(list heap, Py_ssize_t pos, Py_ssize_t n):
    """Standard sift-down using native Python comparison."""
    cdef:
        Py_ssize_t child, right, limit
        object item = heap[pos]
    
    limit = n >> 1
    while pos < limit:
        child = (pos << 1) + 1
        right = child + 1
        if right < n and heap[right] < heap[child]:
            child = right
        if item <= heap[child]:
            break
        heap[pos] = heap[child]
        pos = child
    heap[pos] = item

cdef inline void sift_down_generic_max(list heap, Py_ssize_t pos, Py_ssize_t n):
    """Standard sift-down for max-heap."""
    cdef:
        Py_ssize_t child, right, limit
        object item = heap[pos]
    
    limit = n >> 1
    while pos < limit:
        child = (pos << 1) + 1
        right = child + 1
        if right < n and heap[right] > heap[child]:
            child = right
        if item >= heap[child]:
            break
        heap[pos] = heap[child]
        pos = child
    heap[pos] = item

# =============================================================================
# SIFT-DOWN WITH KEY FUNCTION
# =============================================================================

cdef inline void sift_down_with_key_min(list heap, Py_ssize_t pos, Py_ssize_t n, object key):
    cdef:
        Py_ssize_t child, right, limit
        object item = heap[pos]
        object item_key = key(item)
    
    limit = n >> 1
    while pos < limit:
        child = (pos << 1) + 1
        right = child + 1
        if right < n and key(heap[right]) < key(heap[child]):
            child = right
        if item_key <= key(heap[child]):
            break
        heap[pos] = heap[child]
        pos = child
    heap[pos] = item

cdef inline void sift_down_with_key_max(list heap, Py_ssize_t pos, Py_ssize_t n, object key):
    cdef:
        Py_ssize_t child, right, limit
        object item = heap[pos]
        object item_key = key(item)
    
    limit = n >> 1
    while pos < limit:
        child = (pos << 1) + 1
        right = child + 1
        if right < n and key(heap[right]) > key(heap[child]):
            child = right
        if item_key >= key(heap[child]):
            break
        heap[pos] = heap[child]
        pos = child
    heap[pos] = item

# =============================================================================
# N-ARY SIFT-DOWN
# =============================================================================

cdef inline void sift_down_nary_min(list heap, Py_ssize_t pos, Py_ssize_t n, Py_ssize_t arity):
    cdef:
        Py_ssize_t child, best, last, j
        object item = heap[pos]
    
    while True:
        child = arity * pos + 1
        if child >= n:
            break
        best = child
        last = child + arity
        if last > n:
            last = n
        for j in range(child + 1, last):
            if heap[j] < heap[best]:
                best = j
        if item <= heap[best]:
            break
        heap[pos] = heap[best]
        pos = best
    heap[pos] = item

cdef inline void sift_down_nary_max(list heap, Py_ssize_t pos, Py_ssize_t n, Py_ssize_t arity):
    cdef:
        Py_ssize_t child, best, last, j
        object item = heap[pos]
    
    while True:
        child = arity * pos + 1
        if child >= n:
            break
        best = child
        last = child + arity
        if last > n:
            last = n
        for j in range(child + 1, last):
            if heap[j] > heap[best]:
                best = j
        if item >= heap[best]:
            break
        heap[pos] = heap[best]
        pos = best
    heap[pos] = item

cdef inline void sift_down_nary_key_min(list heap, Py_ssize_t pos, Py_ssize_t n, Py_ssize_t arity, object key):
    cdef:
        Py_ssize_t child, best, last, j
        object item = heap[pos]
        object item_key = key(item)
    
    while True:
        child = arity * pos + 1
        if child >= n:
            break
        best = child
        last = child + arity
        if last > n:
            last = n
        for j in range(child + 1, last):
            if key(heap[j]) < key(heap[best]):
                best = j
        if item_key <= key(heap[best]):
            break
        heap[pos] = heap[best]
        pos = best
    heap[pos] = item

cdef inline void sift_down_nary_key_max(list heap, Py_ssize_t pos, Py_ssize_t n, Py_ssize_t arity, object key):
    cdef:
        Py_ssize_t child, best, last, j
        object item = heap[pos]
        object item_key = key(item)
    
    while True:
        child = arity * pos + 1
        if child >= n:
            break
        best = child
        last = child + arity
        if last > n:
            last = n
        for j in range(child + 1, last):
            if key(heap[j]) > key(heap[best]):
                best = j
        if item_key >= key(heap[best]):
            break
        heap[pos] = heap[best]
        pos = best
    heap[pos] = item

# =============================================================================
# SIFT-UP
# =============================================================================

cdef inline void sift_up_min(list heap, Py_ssize_t pos):
    cdef:
        Py_ssize_t parent
        object item = heap[pos]
    while pos > 0:
        parent = (pos - 1) >> 1
        if item >= heap[parent]:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_up_max(list heap, Py_ssize_t pos):
    cdef:
        Py_ssize_t parent
        object item = heap[pos]
    while pos > 0:
        parent = (pos - 1) >> 1
        if item <= heap[parent]:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# DISPATCH SIFT-DOWN
# =============================================================================

cdef inline void dispatch_sift_down(list heap, Py_ssize_t pos, Py_ssize_t n, bint is_max, int dtype):
    if dtype == TYPE_INT:
        if is_max:
            sift_down_int_max(heap, pos, n)
        else:
            sift_down_int_min(heap, pos, n)
    elif dtype == TYPE_FLOAT:
        if is_max:
            sift_down_float_max(heap, pos, n)
        else:
            sift_down_float_min(heap, pos, n)
    elif dtype == TYPE_BOOL:
        if is_max:
            sift_down_bool_max(heap, pos, n)
        else:
            sift_down_bool_min(heap, pos, n)
    elif dtype == TYPE_STR:
        if is_max:
            sift_down_str_max(heap, pos, n)
        else:
            sift_down_str_min(heap, pos, n)
    else:
        if is_max:
            sift_down_generic_max(heap, pos, n)
        else:
            sift_down_generic_min(heap, pos, n)

# =============================================================================
# HEAPIFY
# =============================================================================

cdef void do_heapify(list heap, bint is_max, int dtype):
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        dispatch_sift_down(heap, i, n, is_max, dtype)

def heapify(list heap, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Transform list into heap in-place."""
    cdef Py_ssize_t n = len(heap), i
    if n <= 1:
        return
    if cmp is not None:
        if arity == 2:
            for i in range((n >> 1) - 1, -1, -1):
                if max_heap:
                    sift_down_with_key_max(heap, i, n, cmp)
                else:
                    sift_down_with_key_min(heap, i, n, cmp)
        else:
            for i in range((n - 2) // arity, -1, -1):
                if max_heap:
                    sift_down_nary_key_max(heap, i, n, arity, cmp)
                else:
                    sift_down_nary_key_min(heap, i, n, arity, cmp)
    elif arity == 1:
        heap.sort(reverse=max_heap)
    elif arity == 2:
        do_heapify(heap, max_heap, detect_type(heap, n))
    else:
        for i in range((n - 2) // arity, -1, -1):
            if max_heap:
                sift_down_nary_max(heap, i, n, arity)
            else:
                sift_down_nary_min(heap, i, n, arity)

# =============================================================================
# POP
# =============================================================================

def pop(list heap, Py_ssize_t n=1, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """
    Pop and return the smallest (or largest if max_heap=True) item(s) from heap.
    
    Parameters:
        heap: list - the heap to pop from
        n: int - number of items to pop (default 1)
        max_heap: bool - True for max-heap, False for min-heap (default)
        cmp: callable - optional key function for comparison
        arity: int - heap arity (default 2 for binary heap)
        nogil: bool - API compatibility parameter
    
    Returns:
        Single item if n=1, list of items if n>1
    """
    cdef:
        Py_ssize_t heap_size = len(heap)
        Py_ssize_t new_size, i
        object result, last
        list results
        int dtype
    
    if heap_size == 0:
        raise IndexError("pop from empty heap")
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if arity < 1:
        raise ValueError(f"arity must be >= 1, got {arity}")
    if cmp is not None and not callable(cmp):
        raise TypeError("cmp must be callable or None")
    
    if n > heap_size:
        n = heap_size
    
    # SINGLE POP
    if n == 1:
        result = heap[0]
        if heap_size == 1:
            heap.pop()
            return result
        if arity == 1:
            del heap[0]
            return result
        
        last = heap.pop()
        heap[0] = last
        new_size = heap_size - 1
        
        if cmp is not None:
            if arity == 2:
                if max_heap:
                    sift_down_with_key_max(heap, 0, new_size, cmp)
                else:
                    sift_down_with_key_min(heap, 0, new_size, cmp)
            else:
                if max_heap:
                    sift_down_nary_key_max(heap, 0, new_size, arity, cmp)
                else:
                    sift_down_nary_key_min(heap, 0, new_size, arity, cmp)
        elif arity == 2:
            dtype = detect_type(heap, new_size)
            dispatch_sift_down(heap, 0, new_size, max_heap, dtype)
        else:
            if max_heap:
                sift_down_nary_max(heap, 0, new_size, arity)
            else:
                sift_down_nary_min(heap, 0, new_size, arity)
        return result
    
    # BULK POP
    if arity == 1:
        results = heap[:n]
        del heap[:n]
        return results
    
    results = []
    dtype = detect_type(heap, heap_size) if cmp is None else TYPE_OTHER
    
    for i in range(n):
        if len(heap) == 0:
            break
        result = heap[0]
        results.append(result)
        if len(heap) == 1:
            heap.pop()
            continue
        last = heap.pop()
        heap[0] = last
        new_size = len(heap)
        
        if cmp is not None:
            if arity == 2:
                if max_heap:
                    sift_down_with_key_max(heap, 0, new_size, cmp)
                else:
                    sift_down_with_key_min(heap, 0, new_size, cmp)
            else:
                if max_heap:
                    sift_down_nary_key_max(heap, 0, new_size, arity, cmp)
                else:
                    sift_down_nary_key_min(heap, 0, new_size, arity, cmp)
        elif arity == 2:
            dispatch_sift_down(heap, 0, new_size, max_heap, dtype)
        else:
            if max_heap:
                sift_down_nary_max(heap, 0, new_size, arity)
            else:
                sift_down_nary_min(heap, 0, new_size, arity)
    return results

# =============================================================================
# PUSH
# =============================================================================

def push(list heap, object items, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Push item(s) onto heap."""
    cdef object item
    if isinstance(items, (list, set, frozenset)):
        for item in items:
            heap.append(item)
            if max_heap:
                sift_up_max(heap, len(heap) - 1)
            else:
                sift_up_min(heap, len(heap) - 1)
    else:
        heap.append(items)
        if max_heap:
            sift_up_max(heap, len(heap) - 1)
        else:
            sift_up_min(heap, len(heap) - 1)

# =============================================================================
# VERIFY
# =============================================================================

def verify_heap(list heap, bint max_heap=False, Py_ssize_t arity=2):
    """Verify heap property."""
    cdef Py_ssize_t n = len(heap), i, j, child
    if arity == 1:
        for i in range(n - 1):
            if max_heap:
                if heap[i] < heap[i + 1]:
                    return False
            else:
                if heap[i] > heap[i + 1]:
                    return False
        return True
    for i in range(n):
        for j in range(1, arity + 1):
            child = arity * i + j
            if child >= n:
                break
            if max_heap:
                if heap[i] < heap[child]:
                    return False
            else:
                if heap[i] > heap[child]:
                    return False
    return True
