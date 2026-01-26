# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: nonecheck=False
# cython: overflowcheck=False
# cython: infer_types=True

"""
Ultra-Optimized Heap Pop for heapx - Production Ready

Key optimizations:
1. Fast comparison paths for all Python types (int, float, str, bool, bytes, tuple)
2. Direct list manipulation without Python API overhead
3. Bottom-up Floyd's algorithm for sift-down
4. Bulk pop entirely in Cython without Python function calls
"""

from cpython.object cimport PyObject, Py_LT, Py_GT
from cpython.ref cimport Py_INCREF, Py_DECREF
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM, PyList_SET_ITEM
from cpython.tuple cimport PyTuple_GET_SIZE, PyTuple_GET_ITEM
from cpython.bytes cimport PyBytes_GET_SIZE, PyBytes_AS_STRING
from cpython.unicode cimport PyUnicode_GET_LENGTH, PyUnicode_DATA, PyUnicode_KIND
from libc.string cimport memcmp

cdef extern from "Python.h":
    double PyFloat_AS_DOUBLE(object)
    bint PyLong_CheckExact(object)
    bint PyFloat_CheckExact(object)
    bint PyUnicode_CheckExact(object)
    bint PyBytes_CheckExact(object)
    bint PyTuple_CheckExact(object)
    bint PyBool_Check(object)
    long PyLong_AsLong(object)
    void PyErr_Clear()
    int PyErr_Occurred()
    PyObject* Py_True
    PyObject* Py_False
    int PyUnicode_1BYTE_KIND
    int PyUnicode_2BYTE_KIND
    int PyUnicode_4BYTE_KIND

# =============================================================================
# FAST COMPARISON - Matches heapx C implementation
# =============================================================================

cdef inline int fast_compare_lt(object a, object b) except -2:
    """Fast less-than comparison for all Python types. Returns 1 if a < b, 0 otherwise, -2 on error."""
    cdef:
        long la, lb
        double da, db
        Py_ssize_t len_a, len_b, min_len
        int cmp, kind_a, kind_b
        const char* str_a
        const char* str_b
        void* data_a
        void* data_b
    
    # Fast path: integers
    if PyLong_CheckExact(a) and PyLong_CheckExact(b):
        la = PyLong_AsLong(a)
        if la != -1 or not PyErr_Occurred():
            lb = PyLong_AsLong(b)
            if lb != -1 or not PyErr_Occurred():
                return 1 if la < lb else 0
        PyErr_Clear()
    
    # Fast path: floats
    if PyFloat_CheckExact(a) and PyFloat_CheckExact(b):
        da = PyFloat_AS_DOUBLE(a)
        db = PyFloat_AS_DOUBLE(b)
        return 1 if da < db else 0
    
    # Fast path: booleans
    if PyBool_Check(a) and PyBool_Check(b):
        return 1 if (a is False and b is True) else 0
    
    # Fast path: strings
    if PyUnicode_CheckExact(a) and PyUnicode_CheckExact(b):
        kind_a = PyUnicode_KIND(a)
        kind_b = PyUnicode_KIND(b)
        if kind_a == kind_b:
            len_a = PyUnicode_GET_LENGTH(a)
            len_b = PyUnicode_GET_LENGTH(b)
            if len_a > 0 and len_b > 0:
                data_a = PyUnicode_DATA(a)
                data_b = PyUnicode_DATA(b)
                min_len = len_a if len_a < len_b else len_b
                if kind_a == PyUnicode_1BYTE_KIND:
                    cmp = memcmp(data_a, data_b, min_len)
                elif kind_a == PyUnicode_2BYTE_KIND:
                    cmp = memcmp(data_a, data_b, min_len * 2)
                else:
                    cmp = memcmp(data_a, data_b, min_len * 4)
                if cmp == 0:
                    return 1 if len_a < len_b else 0
                return 1 if cmp < 0 else 0
    
    # Fast path: bytes
    if PyBytes_CheckExact(a) and PyBytes_CheckExact(b):
        len_a = PyBytes_GET_SIZE(a)
        len_b = PyBytes_GET_SIZE(b)
        if len_a > 0 and len_b > 0:
            str_a = PyBytes_AS_STRING(a)
            str_b = PyBytes_AS_STRING(b)
            min_len = len_a if len_a < len_b else len_b
            cmp = memcmp(str_a, str_b, min_len)
            if cmp == 0:
                return 1 if len_a < len_b else 0
            return 1 if cmp < 0 else 0
    
    # Fast path: tuples (lexicographic)
    if PyTuple_CheckExact(a) and PyTuple_CheckExact(b):
        return fast_compare_tuple_lt(a, b)
    
    # Fallback: Python comparison
    return 1 if a < b else 0

cdef inline int fast_compare_gt(object a, object b) except -2:
    """Fast greater-than comparison. Returns 1 if a > b, 0 otherwise."""
    cdef:
        long la, lb
        double da, db
        Py_ssize_t len_a, len_b, min_len
        int cmp, kind_a, kind_b
        const char* str_a
        const char* str_b
        void* data_a
        void* data_b
    
    # Fast path: integers
    if PyLong_CheckExact(a) and PyLong_CheckExact(b):
        la = PyLong_AsLong(a)
        if la != -1 or not PyErr_Occurred():
            lb = PyLong_AsLong(b)
            if lb != -1 or not PyErr_Occurred():
                return 1 if la > lb else 0
        PyErr_Clear()
    
    # Fast path: floats
    if PyFloat_CheckExact(a) and PyFloat_CheckExact(b):
        da = PyFloat_AS_DOUBLE(a)
        db = PyFloat_AS_DOUBLE(b)
        return 1 if da > db else 0
    
    # Fast path: booleans
    if PyBool_Check(a) and PyBool_Check(b):
        return 1 if (a is True and b is False) else 0
    
    # Fast path: strings
    if PyUnicode_CheckExact(a) and PyUnicode_CheckExact(b):
        kind_a = PyUnicode_KIND(a)
        kind_b = PyUnicode_KIND(b)
        if kind_a == kind_b:
            len_a = PyUnicode_GET_LENGTH(a)
            len_b = PyUnicode_GET_LENGTH(b)
            if len_a > 0 and len_b > 0:
                data_a = PyUnicode_DATA(a)
                data_b = PyUnicode_DATA(b)
                min_len = len_a if len_a < len_b else len_b
                if kind_a == PyUnicode_1BYTE_KIND:
                    cmp = memcmp(data_a, data_b, min_len)
                elif kind_a == PyUnicode_2BYTE_KIND:
                    cmp = memcmp(data_a, data_b, min_len * 2)
                else:
                    cmp = memcmp(data_a, data_b, min_len * 4)
                if cmp == 0:
                    return 1 if len_a > len_b else 0
                return 1 if cmp > 0 else 0
    
    # Fast path: bytes
    if PyBytes_CheckExact(a) and PyBytes_CheckExact(b):
        len_a = PyBytes_GET_SIZE(a)
        len_b = PyBytes_GET_SIZE(b)
        if len_a > 0 and len_b > 0:
            str_a = PyBytes_AS_STRING(a)
            str_b = PyBytes_AS_STRING(b)
            min_len = len_a if len_a < len_b else len_b
            cmp = memcmp(str_a, str_b, min_len)
            if cmp == 0:
                return 1 if len_a > len_b else 0
            return 1 if cmp > 0 else 0
    
    # Fast path: tuples
    if PyTuple_CheckExact(a) and PyTuple_CheckExact(b):
        return fast_compare_tuple_gt(a, b)
    
    # Fallback: Python comparison
    return 1 if a > b else 0

cdef inline int fast_compare_tuple_lt(object a, object b) except -2:
    """Fast tuple less-than comparison."""
    cdef Py_ssize_t len_a = PyTuple_GET_SIZE(a)
    cdef Py_ssize_t len_b = PyTuple_GET_SIZE(b)
    cdef Py_ssize_t min_len = len_a if len_a < len_b else len_b
    cdef Py_ssize_t i
    cdef object item_a, item_b
    cdef int cmp_ab, cmp_ba
    
    for i in range(min_len):
        item_a = <object>PyTuple_GET_ITEM(a, i)
        item_b = <object>PyTuple_GET_ITEM(b, i)
        cmp_ab = fast_compare_lt(item_a, item_b)
        if cmp_ab == -2:
            return -2
        if cmp_ab:
            return 1
        cmp_ba = fast_compare_lt(item_b, item_a)
        if cmp_ba == -2:
            return -2
        if cmp_ba:
            return 0
    return 1 if len_a < len_b else 0

cdef inline int fast_compare_tuple_gt(object a, object b) except -2:
    """Fast tuple greater-than comparison."""
    cdef Py_ssize_t len_a = PyTuple_GET_SIZE(a)
    cdef Py_ssize_t len_b = PyTuple_GET_SIZE(b)
    cdef Py_ssize_t min_len = len_a if len_a < len_b else len_b
    cdef Py_ssize_t i
    cdef object item_a, item_b
    cdef int cmp_ab, cmp_ba
    
    for i in range(min_len):
        item_a = <object>PyTuple_GET_ITEM(a, i)
        item_b = <object>PyTuple_GET_ITEM(b, i)
        cmp_ab = fast_compare_gt(item_a, item_b)
        if cmp_ab == -2:
            return -2
        if cmp_ab:
            return 1
        cmp_ba = fast_compare_gt(item_b, item_a)
        if cmp_ba == -2:
            return -2
        if cmp_ba:
            return 0
    return 1 if len_a > len_b else 0


# =============================================================================
# SIFT-DOWN - Bottom-up Floyd's algorithm with fast comparison
# =============================================================================

cdef inline void sift_down_min(list heap, Py_ssize_t pos, Py_ssize_t n) except *:
    """Bottom-up sift-down for min-heap using fast comparison."""
    cdef:
        Py_ssize_t child, right, parent, start = pos
        object item = heap[pos]
        int cmp
    
    # Phase 1: Descend to leaf
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n:
            cmp = fast_compare_lt(heap[right], heap[child])
            if cmp == -2:
                raise RuntimeError("Comparison failed")
            if cmp:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    # Phase 2: Bubble up
    while pos > start:
        parent = (pos - 1) >> 1
        cmp = fast_compare_lt(item, heap[parent])
        if cmp == -2:
            raise RuntimeError("Comparison failed")
        if not cmp:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_max(list heap, Py_ssize_t pos, Py_ssize_t n) except *:
    """Bottom-up sift-down for max-heap using fast comparison."""
    cdef:
        Py_ssize_t child, right, parent, start = pos
        object item = heap[pos]
        int cmp
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n:
            cmp = fast_compare_gt(heap[right], heap[child])
            if cmp == -2:
                raise RuntimeError("Comparison failed")
            if cmp:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        cmp = fast_compare_gt(item, heap[parent])
        if cmp == -2:
            raise RuntimeError("Comparison failed")
        if not cmp:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_nary(list heap, Py_ssize_t pos, Py_ssize_t n, bint is_max, Py_ssize_t arity, object cmp_func) except *:
    """N-ary sift-down with optional key function."""
    cdef:
        Py_ssize_t child, best, last, j, parent, start = pos
        object item = heap[pos]
        object item_key = cmp_func(item) if cmp_func is not None else item
        object best_key, cur_key
        int cmp
    
    while True:
        child = arity * pos + 1
        if child >= n:
            break
        best = child
        best_key = cmp_func(heap[child]) if cmp_func is not None else heap[child]
        last = child + arity
        if last > n:
            last = n
        
        for j in range(child + 1, last):
            cur_key = cmp_func(heap[j]) if cmp_func is not None else heap[j]
            if is_max:
                cmp = fast_compare_gt(cur_key, best_key)
            else:
                cmp = fast_compare_lt(cur_key, best_key)
            if cmp == -2:
                raise RuntimeError("Comparison failed")
            if cmp:
                best = j
                best_key = cur_key
        
        if is_max:
            cmp = fast_compare_gt(best_key, item_key)
        else:
            cmp = fast_compare_lt(best_key, item_key)
        if cmp == -2:
            raise RuntimeError("Comparison failed")
        if not cmp:
            break
        
        heap[pos] = heap[best]
        pos = best
    heap[pos] = item

# =============================================================================
# HEAPIFY
# =============================================================================

cpdef heapify(list heap, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Transform list into heap in-place."""
    cdef Py_ssize_t n = len(heap), i
    
    if n <= 1:
        return
    
    if arity == 1:
        heap.sort(key=cmp, reverse=max_heap)
        return
    
    if cmp is not None or arity != 2:
        for i in range((n - 2) // arity, -1, -1):
            sift_down_nary(heap, i, n, max_heap, arity, cmp)
        return
    
    # Binary heap without key function - use fast comparison
    for i in range((n >> 1) - 1, -1, -1):
        if max_heap:
            sift_down_max(heap, i, n)
        else:
            sift_down_min(heap, i, n)


# =============================================================================
# POP - Main Entry Point
# =============================================================================

cpdef pop(list heap, Py_ssize_t n=1, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """
    Pop and return the smallest (or largest if max_heap=True) item(s) from heap.
    
    This implementation uses fast comparison paths for all Python types,
    matching the heapx C implementation for maximum performance.
    """
    cdef:
        Py_ssize_t heap_size = len(heap)
        Py_ssize_t new_size, i
        object result, last
        list results
    
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
    
    # SINGLE POP (n=1)
    if n == 1:
        return _pop_single(heap, max_heap, cmp, arity)
    
    # BULK POP (n>1) - Entirely in Cython with fast comparison
    return _pop_bulk(heap, n, max_heap, cmp, arity)

cdef inline object _pop_single(list heap, bint max_heap, object cmp, Py_ssize_t arity):
    """Single pop operation."""
    cdef:
        Py_ssize_t heap_size = len(heap)
        object result = heap[0]
        object last
    
    if heap_size == 1:
        heap.pop()
        return result
    
    # Arity=1 (sorted list)
    if arity == 1:
        del heap[0]
        return result
    
    # Standard heap pop
    last = heap.pop()
    heap[0] = last
    heap_size -= 1
    
    if cmp is not None or arity != 2:
        sift_down_nary(heap, 0, heap_size, max_heap, arity, cmp)
    elif max_heap:
        sift_down_max(heap, 0, heap_size)
    else:
        sift_down_min(heap, 0, heap_size)
    
    return result

cdef list _pop_bulk(list heap, Py_ssize_t n, bint max_heap, object cmp, Py_ssize_t arity):
    """
    Bulk pop operation - entirely in Cython with fast comparison.
    
    This is the key optimization: instead of calling heapq.heappop() in a loop,
    we do the entire operation in Cython with direct list manipulation and
    fast comparison paths.
    """
    cdef:
        Py_ssize_t heap_size, new_size, i
        object result, last
        list results
    
    # Arity=1 (sorted list) - just slice
    if arity == 1:
        results = heap[:n]
        del heap[:n]
        return results
    
    results = []
    
    for i in range(n):
        heap_size = len(heap)
        if heap_size == 0:
            break
        
        result = heap[0]
        results.append(result)
        
        if heap_size == 1:
            heap.pop()
            continue
        
        last = heap.pop()
        heap[0] = last
        new_size = heap_size - 1
        
        if cmp is not None or arity != 2:
            sift_down_nary(heap, 0, new_size, max_heap, arity, cmp)
        elif max_heap:
            sift_down_max(heap, 0, new_size)
        else:
            sift_down_min(heap, 0, new_size)
    
    return results

# =============================================================================
# PUSH
# =============================================================================

cpdef push(list heap, object items, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Push item(s) onto heap."""
    if isinstance(items, (list, set, frozenset)):
        for item in items:
            _push_single(heap, item, max_heap, cmp, arity)
    else:
        _push_single(heap, items, max_heap, cmp, arity)

cdef inline void _push_single(list heap, object item, bint max_heap, object cmp, Py_ssize_t arity) except *:
    """Single push with sift-up."""
    cdef:
        Py_ssize_t pos, parent
        object item_key, parent_key
        int cmp_result
    
    heap.append(item)
    pos = len(heap) - 1
    
    if pos == 0:
        return
    
    item_key = cmp(item) if cmp is not None else item
    
    while pos > 0:
        parent = (pos - 1) // arity
        parent_key = cmp(heap[parent]) if cmp is not None else heap[parent]
        
        if max_heap:
            cmp_result = fast_compare_gt(item_key, parent_key)
        else:
            cmp_result = fast_compare_lt(item_key, parent_key)
        
        if cmp_result == -2:
            raise RuntimeError("Comparison failed")
        if not cmp_result:
            break
        
        heap[pos] = heap[parent]
        pos = parent
    
    heap[pos] = item

# =============================================================================
# VERIFY
# =============================================================================

def verify_heap(list heap, bint max_heap=False, Py_ssize_t arity=2):
    """Verify heap property."""
    cdef Py_ssize_t n = len(heap), i, j, child
    cdef int cmp_result
    
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
                cmp_result = fast_compare_lt(heap[i], heap[child])
                if cmp_result == -2:
                    return False
                if cmp_result:
                    return False
            else:
                cmp_result = fast_compare_gt(heap[i], heap[child])
                if cmp_result == -2:
                    return False
                if cmp_result:
                    return False
    return True
