# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: nonecheck=False

"""Minimal overhead sift using exact heapq approach."""

from cpython.object cimport PyObject, Py_LT
from cpython.ref cimport Py_INCREF, Py_DECREF

cdef extern from "Python.h":
    int PyObject_RichCompareBool(object, object, int) except -1
    Py_ssize_t PyList_GET_SIZE(object)
    PyObject* PyList_GET_ITEM(object, Py_ssize_t)
    int PyList_SetSlice(object, Py_ssize_t, Py_ssize_t, object) except -1

cdef extern from *:
    """
    #define LIST_ITEMS(op) (((PyListObject *)(op))->ob_item)
    """
    PyObject** LIST_ITEMS(object)

cdef int sift_min(object heap, Py_ssize_t pos) except -1:
    """Exact copy of heapq's siftup + siftdown."""
    cdef:
        Py_ssize_t startpos = pos, endpos, childpos, limit, parentpos
        PyObject** arr
        PyObject* tmp1
        PyObject* tmp2
        PyObject* newitem
        PyObject* parent
        int cmp
    
    endpos = PyList_GET_SIZE(heap)
    if pos >= endpos:
        return -1
    
    # Phase 1: siftup - bubble smaller child up until leaf
    arr = LIST_ITEMS(heap)
    limit = endpos >> 1
    
    while pos < limit:
        childpos = (pos << 1) + 1
        if childpos + 1 < endpos:
            Py_INCREF(<object>arr[childpos])
            Py_INCREF(<object>arr[childpos + 1])
            cmp = PyObject_RichCompareBool(<object>arr[childpos], <object>arr[childpos + 1], Py_LT)
            Py_DECREF(<object>arr[childpos])
            Py_DECREF(<object>arr[childpos + 1])
            if cmp < 0:
                return -1
            # childpos += (cmp ^ 1) - pick right child if left is not smaller
            if cmp == 0:
                childpos += 1
            arr = LIST_ITEMS(heap)  # May have changed
        
        # Swap arr[pos] and arr[childpos]
        tmp1 = arr[childpos]
        tmp2 = arr[pos]
        arr[childpos] = tmp2
        arr[pos] = tmp1
        pos = childpos
    
    # Phase 2: siftdown - bubble up to final position
    arr = LIST_ITEMS(heap)
    newitem = arr[pos]
    
    while pos > startpos:
        parentpos = (pos - 1) >> 1
        parent = arr[parentpos]
        Py_INCREF(<object>newitem)
        Py_INCREF(<object>parent)
        cmp = PyObject_RichCompareBool(<object>newitem, <object>parent, Py_LT)
        Py_DECREF(<object>parent)
        Py_DECREF(<object>newitem)
        if cmp < 0:
            return -1
        if cmp == 0:
            break
        arr = LIST_ITEMS(heap)
        parent = arr[parentpos]
        newitem = arr[pos]
        arr[parentpos] = newitem
        arr[pos] = parent
        pos = parentpos
    
    return 0

def pop_heapq_style(list heap):
    """Pop mimicking heapq exactly."""
    cdef:
        Py_ssize_t n
        PyObject* lastelt
        PyObject* returnitem
    
    n = PyList_GET_SIZE(heap)
    if n == 0:
        raise IndexError("index out of range")
    
    lastelt = PyList_GET_ITEM(heap, n - 1)
    Py_INCREF(<object>lastelt)
    
    if PyList_SetSlice(heap, n - 1, n, <object>NULL) < 0:
        Py_DECREF(<object>lastelt)
        raise
    
    n -= 1
    if n == 0:
        return <object>lastelt
    
    returnitem = PyList_GET_ITEM(heap, 0)
    Py_INCREF(<object>returnitem)  # Keep reference before overwriting
    
    # Put lastelt at position 0
    LIST_ITEMS(heap)[0] = lastelt
    
    if sift_min(heap, 0) < 0:
        Py_DECREF(<object>returnitem)
        raise
    
    return <object>returnitem
