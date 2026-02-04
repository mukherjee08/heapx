# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: nonecheck=False

"""Test using direct pointer swaps like heapq."""

from cpython.object cimport PyObject, Py_LT
from cpython.list cimport PyList_GET_SIZE
from cpython.ref cimport Py_INCREF, Py_DECREF

cdef extern from "Python.h":
    int PyObject_RichCompareBool(object, object, int) except -1
    # Direct access to list internals
    PyObject** PySequence_Fast_ITEMS(object)

cdef extern from *:
    """
    #define GET_LIST_ITEMS(op) (((PyListObject *)(op))->ob_item)
    """
    PyObject** GET_LIST_ITEMS(object)

cdef inline void sift_direct_min(object heap, Py_ssize_t n):
    """Sift using direct pointer swaps - mimics heapq exactly."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent, startpos = 0
        PyObject** arr = GET_LIST_ITEMS(heap)
        PyObject* newitem = arr[0]
        PyObject* tmp
        int cmp
    
    # Phase 1: Bubble up smaller child until hitting a leaf
    # This is Floyd's bottom-up approach
    while pos < (n >> 1):  # While not a leaf
        child = (pos << 1) + 1
        right = child + 1
        
        if right < n:
            # Compare children, pick smaller
            Py_INCREF(<object>arr[child])
            Py_INCREF(<object>arr[right])
            cmp = PyObject_RichCompareBool(<object>arr[child], <object>arr[right], Py_LT)
            Py_DECREF(<object>arr[child])
            Py_DECREF(<object>arr[right])
            if cmp < 0:
                return  # Error
            if cmp == 0:  # right is smaller or equal
                child = right
        
        # Swap: move child up to pos
        tmp = arr[child]
        arr[child] = arr[pos]
        arr[pos] = tmp
        pos = child
    
    # Phase 2: Bubble newitem up from pos to its correct position
    # (siftdown in heapq terminology)
    while pos > startpos:
        parent = (pos - 1) >> 1
        Py_INCREF(<object>newitem)
        Py_INCREF(<object>arr[parent])
        cmp = PyObject_RichCompareBool(<object>newitem, <object>arr[parent], Py_LT)
        Py_DECREF(<object>arr[parent])
        Py_DECREF(<object>newitem)
        if cmp < 0:
            return  # Error
        if cmp == 0:
            break
        # Swap
        tmp = arr[parent]
        arr[parent] = arr[pos]
        arr[pos] = tmp
        pos = parent

def pop_direct(list heap):
    """Pop using direct pointer manipulation."""
    cdef:
        Py_ssize_t n = PyList_GET_SIZE(heap)
        PyObject** arr
        PyObject* lastelt
        PyObject* returnitem
    
    if n == 0:
        raise IndexError("index out of range")
    
    arr = GET_LIST_ITEMS(heap)
    lastelt = arr[n-1]
    Py_INCREF(<object>lastelt)
    
    # Remove last element
    del heap[n-1]
    n -= 1
    
    if n == 0:
        return <object>lastelt
    
    returnitem = arr[0]
    Py_INCREF(<object>returnitem)
    arr[0] = lastelt
    
    sift_direct_min(heap, n)
    
    return <object>returnitem
