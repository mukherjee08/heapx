# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: nonecheck=False

"""Test using PyObject_RichCompareBool directly."""

from cpython.object cimport PyObject, Py_LT, Py_GT
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM, PyList_SET_ITEM
from cpython.ref cimport Py_INCREF, Py_DECREF

cdef extern from "Python.h":
    int PyObject_RichCompareBool(object, object, int) except -1

cdef inline void sift_richcompare_min(list heap, Py_ssize_t n):
    """Sift using PyObject_RichCompareBool directly."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        PyObject** arr = <PyObject**>(<PyObject*>heap + 2)  # Skip ob_refcnt, ob_type
        object item, tmp
    
    # Get item at position 0
    item = <object>PyList_GET_ITEM(heap, 0)
    Py_INCREF(item)
    
    # Phase 1: Descend to leaf
    child = 1
    while child < n:
        right = child + 1
        if right < n:
            if PyObject_RichCompareBool(<object>PyList_GET_ITEM(heap, right), 
                                        <object>PyList_GET_ITEM(heap, child), Py_LT):
                child = right
        # Move child up
        tmp = <object>PyList_GET_ITEM(heap, child)
        Py_INCREF(tmp)
        Py_DECREF(<object>PyList_GET_ITEM(heap, pos))
        PyList_SET_ITEM(heap, pos, tmp)
        pos = child
        child = (pos << 1) + 1
    
    # Phase 2: Bubble up
    while pos > 0:
        parent = (pos - 1) >> 1
        if not PyObject_RichCompareBool(item, <object>PyList_GET_ITEM(heap, parent), Py_LT):
            break
        tmp = <object>PyList_GET_ITEM(heap, parent)
        Py_INCREF(tmp)
        Py_DECREF(<object>PyList_GET_ITEM(heap, pos))
        PyList_SET_ITEM(heap, pos, tmp)
        pos = parent
    
    Py_DECREF(<object>PyList_GET_ITEM(heap, pos))
    Py_INCREF(item)
    PyList_SET_ITEM(heap, pos, item)
    Py_DECREF(item)

def pop_test(list heap):
    """Test pop using RichCompareBool."""
    cdef Py_ssize_t n = len(heap)
    if n == 0:
        raise IndexError("empty")
    
    result = heap[0]
    if n == 1:
        heap.pop()
        return result
    
    last = heap.pop()
    heap[0] = last
    sift_richcompare_min(heap, n - 1)
    return result
