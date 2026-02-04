# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: nonecheck=False
# cython: overflowcheck=False
# cython: infer_types=True
# cython: optimize.unpack_method_calls=True

"""
Test different sift implementations to find the fastest.
"""

from cpython.object cimport PyObject
from cpython.ref cimport Py_INCREF, Py_DECREF

cdef extern from "Python.h":
    int PyObject_RichCompareBool(object, object, int) except -1
    int Py_LT
    int Py_GT
    double PyFloat_AS_DOUBLE(object)
    long PyLong_AsLong(object)
    bint PyFloat_CheckExact(object)
    bint PyLong_CheckExact(object)
    bint PyBool_Check(object)

# Version 1: Using PyObject_RichCompareBool directly (like heapq)
cdef inline void sift_v1_min(list heap, Py_ssize_t n) except *:
    """Sift using PyObject_RichCompareBool - matches heapq's approach."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
    
    child = 1
    while child < n:
        right = child + 1
        if right < n and PyObject_RichCompareBool(heap[right], heap[child], Py_LT):
            child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if not PyObject_RichCompareBool(item, heap[parent], Py_LT):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# Version 2: Using native Python < operator
cdef inline void sift_v2_min(list heap, Py_ssize_t n) noexcept:
    """Sift using native Python < operator."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
    
    child = 1
    while child < n:
        right = child + 1
        if right < n and heap[right] < heap[child]:
            child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if not (item < heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# Version 3: Type-specialized for int
cdef inline void sift_v3_int_min(list heap, Py_ssize_t n) noexcept:
    """Sift for int using PyLong_AsLong."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        long item_val = PyLong_AsLong(item)
    
    child = 1
    while child < n:
        right = child + 1
        if right < n and PyLong_AsLong(heap[right]) < PyLong_AsLong(heap[child]):
            child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if item_val >= PyLong_AsLong(heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# Version 4: Type-specialized for float
cdef inline void sift_v4_float_min(list heap, Py_ssize_t n) noexcept:
    """Sift for float using PyFloat_AS_DOUBLE."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        double item_val = PyFloat_AS_DOUBLE(item)
    
    child = 1
    while child < n:
        right = child + 1
        if right < n and PyFloat_AS_DOUBLE(heap[right]) < PyFloat_AS_DOUBLE(heap[child]):
            child = right
        heap[pos] = heap[child]
        pos = child
        child = (pos << 1) + 1
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if item_val >= PyFloat_AS_DOUBLE(heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# Test functions
def test_v1(list heap):
    """Test PyObject_RichCompareBool version."""
    cdef object result = heap[0]
    cdef object last
    cdef Py_ssize_t n = len(heap)
    if n == 1:
        heap.pop()
        return result
    last = heap.pop()
    heap[0] = last
    sift_v1_min(heap, n - 1)
    return result

def test_v2(list heap):
    """Test native Python < version."""
    cdef object result = heap[0]
    cdef object last
    cdef Py_ssize_t n = len(heap)
    if n == 1:
        heap.pop()
        return result
    last = heap.pop()
    heap[0] = last
    sift_v2_min(heap, n - 1)
    return result

def test_v3_int(list heap):
    """Test int-specialized version."""
    cdef object result = heap[0]
    cdef object last
    cdef Py_ssize_t n = len(heap)
    if n == 1:
        heap.pop()
        return result
    last = heap.pop()
    heap[0] = last
    sift_v3_int_min(heap, n - 1)
    return result

def test_v4_float(list heap):
    """Test float-specialized version."""
    cdef object result = heap[0]
    cdef object last
    cdef Py_ssize_t n = len(heap)
    if n == 1:
        heap.pop()
        return result
    last = heap.pop()
    heap[0] = last
    sift_v4_float_min(heap, n - 1)
    return result

def heapify_simple(list heap):
    """Simple heapify using native comparison."""
    cdef Py_ssize_t n = len(heap), i, pos, child, right, parent, start
    cdef object item
    
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
