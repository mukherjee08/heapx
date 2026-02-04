# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: nonecheck=False
# cython: overflowcheck=False
# cython: infer_types=True

"""
Ultra-optimized sift using native Python comparison.
Key insight: Cython compiles `a < b` to highly optimized C code.
"""

from cpython.object cimport PyObject
from cpython.ref cimport Py_INCREF, Py_DECREF

cdef extern from "Python.h":
    double PyFloat_AS_DOUBLE(object)
    long PyLong_AsLong(object)
    bint PyFloat_CheckExact(object)
    bint PyLong_CheckExact(object)
    bint PyUnicode_CheckExact(object)
    bint PyTuple_CheckExact(object)
    bint PyBool_Check(object)

# ============================================================================
# CORE SIFT - Uses native Python < which Cython optimizes extremely well
# ============================================================================

cdef inline void sift_native_min(list heap, Py_ssize_t n) noexcept:
    """Ultra-fast sift using native Python < operator."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
    
    # Sift down phase
    child = 1
    while child < n:
        right = child + 1
        if right < n and heap[right] < heap[child]:
            child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    # Sift up phase
    while pos > 0:
        parent = (pos - 1) >> 1
        if not (item < heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_native_max(list heap, Py_ssize_t n) noexcept:
    """Ultra-fast sift for max-heap using native Python > operator."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
    
    child = 1
    while child < n:
        right = child + 1
        if right < n and heap[right] > heap[child]:
            child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if not (item > heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# ============================================================================
# TYPE-SPECIALIZED SIFT FOR MAXIMUM PERFORMANCE
# ============================================================================

cdef inline void sift_int_min(list heap, Py_ssize_t n) noexcept:
    """Int-specialized sift using PyLong_AsLong for direct C comparison."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        long item_val = PyLong_AsLong(item)
        long child_val, right_val, parent_val
    
    child = 1
    while child < n:
        right = child + 1
        child_val = PyLong_AsLong(heap[child])
        if right < n:
            right_val = PyLong_AsLong(heap[right])
            if right_val < child_val:
                child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    while pos > 0:
        parent = (pos - 1) >> 1
        parent_val = PyLong_AsLong(heap[parent])
        if item_val >= parent_val:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_int_max(list heap, Py_ssize_t n) noexcept:
    """Int-specialized sift for max-heap."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        long item_val = PyLong_AsLong(item)
        long child_val, right_val, parent_val
    
    child = 1
    while child < n:
        right = child + 1
        child_val = PyLong_AsLong(heap[child])
        if right < n:
            right_val = PyLong_AsLong(heap[right])
            if right_val > child_val:
                child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    while pos > 0:
        parent = (pos - 1) >> 1
        parent_val = PyLong_AsLong(heap[parent])
        if item_val <= parent_val:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_float_min(list heap, Py_ssize_t n) noexcept:
    """Float-specialized sift using PyFloat_AS_DOUBLE for direct C comparison."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        double item_val = PyFloat_AS_DOUBLE(item)
        double child_val, right_val, parent_val
    
    child = 1
    while child < n:
        right = child + 1
        child_val = PyFloat_AS_DOUBLE(heap[child])
        if right < n:
            right_val = PyFloat_AS_DOUBLE(heap[right])
            if right_val < child_val:
                child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    while pos > 0:
        parent = (pos - 1) >> 1
        parent_val = PyFloat_AS_DOUBLE(heap[parent])
        if item_val >= parent_val:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_float_max(list heap, Py_ssize_t n) noexcept:
    """Float-specialized sift for max-heap."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        double item_val = PyFloat_AS_DOUBLE(item)
        double child_val, right_val, parent_val
    
    child = 1
    while child < n:
        right = child + 1
        child_val = PyFloat_AS_DOUBLE(heap[child])
        if right < n:
            right_val = PyFloat_AS_DOUBLE(heap[right])
            if right_val > child_val:
                child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    while pos > 0:
        parent = (pos - 1) >> 1
        parent_val = PyFloat_AS_DOUBLE(heap[parent])
        if item_val <= parent_val:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# ============================================================================
# POP FUNCTIONS
# ============================================================================

def pop_native(list heap, bint max_heap=False):
    """Pop using native Python comparison."""
    cdef:
        object result = heap[0]
        object last
        Py_ssize_t n = len(heap)
    
    if n == 1:
        heap.pop()
        return result
    
    last = heap.pop()
    heap[0] = last
    n -= 1
    
    if max_heap:
        sift_native_max(heap, n)
    else:
        sift_native_min(heap, n)
    return result

def pop_int(list heap, bint max_heap=False):
    """Pop for int heap."""
    cdef:
        object result = heap[0]
        object last
        Py_ssize_t n = len(heap)
    
    if n == 1:
        heap.pop()
        return result
    
    last = heap.pop()
    heap[0] = last
    n -= 1
    
    if max_heap:
        sift_int_max(heap, n)
    else:
        sift_int_min(heap, n)
    return result

def pop_float(list heap, bint max_heap=False):
    """Pop for float heap."""
    cdef:
        object result = heap[0]
        object last
        Py_ssize_t n = len(heap)
    
    if n == 1:
        heap.pop()
        return result
    
    last = heap.pop()
    heap[0] = last
    n -= 1
    
    if max_heap:
        sift_float_max(heap, n)
    else:
        sift_float_min(heap, n)
    return result

def pop_dispatch(list heap, bint max_heap=False):
    """Pop with automatic type dispatch."""
    cdef:
        object result = heap[0]
        object last
        Py_ssize_t n = len(heap)
        object first
    
    if n == 1:
        heap.pop()
        return result
    
    last = heap.pop()
    heap[0] = last
    n -= 1
    
    # Type dispatch based on first element
    first = heap[0]
    if PyLong_CheckExact(first) and not PyBool_Check(first):
        if max_heap:
            sift_int_max(heap, n)
        else:
            sift_int_min(heap, n)
    elif PyFloat_CheckExact(first):
        if max_heap:
            sift_float_max(heap, n)
        else:
            sift_float_min(heap, n)
    else:
        if max_heap:
            sift_native_max(heap, n)
        else:
            sift_native_min(heap, n)
    return result

def heapify_native(list heap, bint max_heap=False):
    """Heapify using native comparison."""
    cdef:
        Py_ssize_t n = len(heap), i, pos, child, right, parent, start
        object item
    
    if max_heap:
        for i in range((n >> 1) - 1, -1, -1):
            start = i
            pos = i
            item = heap[pos]
            
            while True:
                child = (pos << 1) + 1
                if child >= n:
                    break
                right = child + 1
                if right < n and heap[right] > heap[child]:
                    child = right
                heap[pos] = heap[child]
                pos = child
            
            while pos > start:
                parent = (pos - 1) >> 1
                if not (item > heap[parent]):
                    break
                heap[pos] = heap[parent]
                pos = parent
            heap[pos] = item
    else:
        for i in range((n >> 1) - 1, -1, -1):
            start = i
            pos = i
            item = heap[pos]
            
            while True:
                child = (pos << 1) + 1
                if child >= n:
                    break
                right = child + 1
                if right < n and heap[right] < heap[child]:
                    child = right
                heap[pos] = heap[child]
                pos = child
            
            while pos > start:
                parent = (pos - 1) >> 1
                if not (item < heap[parent]):
                    break
                heap[pos] = heap[parent]
                pos = parent
            heap[pos] = item
