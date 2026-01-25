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
Ultra-Optimized Pop - Step 1: Bottom-Up Sift-Down (Floyd's Algorithm)

Key optimization: Instead of comparing item with children at each level,
descend to leaf comparing only children, then bubble up. This reduces
comparisons by ~25% for large heaps.
"""

from cpython.object cimport PyObject
from cpython.ref cimport Py_INCREF, Py_DECREF
from libc.math cimport isnan

cdef extern from "Python.h":
    Py_ssize_t PyList_GET_SIZE(object)
    PyObject* PyList_GET_ITEM(object, Py_ssize_t)
    void PyList_SET_ITEM(object, Py_ssize_t, PyObject*)
    int PyLong_Check(object)
    int PyFloat_Check(object)
    int PyUnicode_Check(object)
    int PyBool_Check(object)
    int PyTuple_Check(object)
    long PyLong_AsLong(object) except? -1
    double PyFloat_AS_DOUBLE(object)
    int PyUnicode_Compare(object, object) except? -1
    int PyObject_RichCompareBool(object, object, int) except -1
    int Py_LT, Py_GT
    PyObject* Py_True

cdef extern from *:
    """
    #ifdef __GNUC__
    #define PREFETCH(addr) __builtin_prefetch(addr, 0, 3)
    #define LIKELY(x) __builtin_expect(!!(x), 1)
    #define UNLIKELY(x) __builtin_expect(!!(x), 0)
    #else
    #define PREFETCH(addr) ((void)0)
    #define LIKELY(x) (x)
    #define UNLIKELY(x) (x)
    #endif
    """
    void PREFETCH(void* addr) nogil
    bint LIKELY(bint x) nogil
    bint UNLIKELY(bint x) nogil

DEF TYPE_UNKNOWN = 0
DEF TYPE_INT = 1
DEF TYPE_FLOAT = 2
DEF TYPE_STR = 3
DEF TYPE_BOOL = 4
DEF TYPE_TUPLE = 5
DEF TYPE_MIXED = 6

cdef inline int detect_type(list heap, Py_ssize_t n) noexcept:
    """Fast type detection - only check first element (heap is homogeneous after heapify)."""
    cdef object first
    cdef type first_type
    
    if n == 0:
        return TYPE_UNKNOWN
    
    first = heap[0]
    first_type = type(first)
    
    if first_type is int:
        return TYPE_INT
    elif first_type is float:
        return TYPE_FLOAT
    elif first_type is str:
        return TYPE_STR
    elif first_type is bool:
        return TYPE_BOOL
    elif first_type is tuple:
        return TYPE_TUPLE
    return TYPE_MIXED

# =============================================================================
# BOTTOM-UP SIFT-DOWN: INTEGER (Floyd's Algorithm + Prefetching)
# =============================================================================

cdef inline void sift_down_int_min(list heap, Py_ssize_t start, Py_ssize_t n) noexcept:
    """Bottom-up sift-down for int min-heap with prefetching."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        object item = heap[start]
        long item_val = <long>item
        long child_val, right_val, parent_val
    
    # Phase 1: Descend to leaf with prefetching
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        # Prefetch grandchildren for next iteration
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        child_val = <long>heap[child]
        right = child + 1
        if right < n:
            right_val = <long>heap[right]
            if right_val < child_val:
                child = right
        
        heap[pos] = heap[child]
        pos = child
    
    # Phase 2: Bubble up from leaf position
    while pos > start:
        parent = (pos - 1) >> 1
        parent_val = <long>heap[parent]
        if item_val >= parent_val:
            break
        heap[pos] = heap[parent]
        pos = parent
    
    heap[pos] = item

cdef inline void sift_down_int_max(list heap, Py_ssize_t start, Py_ssize_t n) noexcept:
    """Bottom-up sift-down for int max-heap with prefetching."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        object item = heap[start]
        long item_val = <long>item
        long child_val, right_val, parent_val
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        # Prefetch grandchildren
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        child_val = <long>heap[child]
        right = child + 1
        if right < n:
            right_val = <long>heap[right]
            if right_val > child_val:
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
# BOTTOM-UP SIFT-DOWN: FLOAT (Optimized - no NaN check in hot path)
# =============================================================================

cdef inline void sift_down_float_min(list heap, Py_ssize_t start, Py_ssize_t n) noexcept:
    """Bottom-up sift-down for float min-heap - optimized for common case (no NaN)."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        object item = heap[start]
        double item_val = PyFloat_AS_DOUBLE(item)
        double child_val, right_val, parent_val
    
    # Phase 1: Descend to leaf with prefetching
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        # Prefetch grandchildren
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        child_val = PyFloat_AS_DOUBLE(heap[child])
        right = child + 1
        if right < n:
            right_val = PyFloat_AS_DOUBLE(heap[right])
            if right_val < child_val:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    # Phase 2: Bubble up
    while pos > start:
        parent = (pos - 1) >> 1
        parent_val = PyFloat_AS_DOUBLE(heap[parent])
        if item_val >= parent_val:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_float_max(list heap, Py_ssize_t start, Py_ssize_t n) noexcept:
    """Bottom-up sift-down for float max-heap."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        object item = heap[start]
        double item_val = PyFloat_AS_DOUBLE(item)
        double child_val, right_val, parent_val
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        child_val = PyFloat_AS_DOUBLE(heap[child])
        right = child + 1
        if right < n:
            right_val = PyFloat_AS_DOUBLE(heap[right])
            if right_val > child_val:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        parent_val = PyFloat_AS_DOUBLE(heap[parent])
        if item_val <= parent_val:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# BOTTOM-UP SIFT-DOWN: STRING (with prefetching)
# =============================================================================

cdef inline void sift_down_str_min(list heap, Py_ssize_t start, Py_ssize_t n) except *:
    """Bottom-up sift-down for string min-heap with prefetching."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        object item = heap[start]
        int cmp
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        # Prefetch grandchildren
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        right = child + 1
        if right < n:
            cmp = PyUnicode_Compare(heap[right], heap[child])
            if cmp < 0:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        cmp = PyUnicode_Compare(item, heap[parent])
        if cmp >= 0:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_str_max(list heap, Py_ssize_t start, Py_ssize_t n) except *:
    """Bottom-up sift-down for string max-heap with prefetching."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        object item = heap[start]
        int cmp
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        right = child + 1
        if right < n:
            cmp = PyUnicode_Compare(heap[right], heap[child])
            if cmp > 0:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        cmp = PyUnicode_Compare(item, heap[parent])
        if cmp <= 0:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# BOTTOM-UP SIFT-DOWN: BOOL (with prefetching)
# =============================================================================

cdef inline void sift_down_bool_min(list heap, Py_ssize_t start, Py_ssize_t n) noexcept:
    """Bottom-up sift-down for bool min-heap (False < True) with prefetching."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        object item = heap[start]
        bint item_val = (item is True)
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        right = child + 1
        if right < n:
            if (heap[right] is not True) and (heap[child] is True):
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

cdef inline void sift_down_bool_max(list heap, Py_ssize_t start, Py_ssize_t n) noexcept:
    """Bottom-up sift-down for bool max-heap with prefetching."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        object item = heap[start]
        bint item_val = (item is True)
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        right = child + 1
        if right < n:
            if (heap[right] is True) and (heap[child] is not True):
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
# FAST TUPLE COMPARISON
# =============================================================================

cdef inline int tuple_compare(tuple a, tuple b) except -2:
    """Fast tuple comparison: returns -1 if a<b, 0 if a==b, 1 if a>b."""
    cdef:
        Py_ssize_t len_a = len(a), len_b = len(b)
        Py_ssize_t min_len = len_a if len_a < len_b else len_b
        Py_ssize_t i
        object item_a, item_b
        int cmp
    
    for i in range(min_len):
        item_a = a[i]
        item_b = b[i]
        
        # Fast path for common element types
        if type(item_a) is int and type(item_b) is int:
            if <long>item_a < <long>item_b:
                return -1
            if <long>item_a > <long>item_b:
                return 1
        elif type(item_a) is float and type(item_b) is float:
            if PyFloat_AS_DOUBLE(item_a) < PyFloat_AS_DOUBLE(item_b):
                return -1
            if PyFloat_AS_DOUBLE(item_a) > PyFloat_AS_DOUBLE(item_b):
                return 1
        elif type(item_a) is str and type(item_b) is str:
            cmp = PyUnicode_Compare(item_a, item_b)
            if cmp != 0:
                return cmp
        else:
            # Generic comparison
            cmp = PyObject_RichCompareBool(item_a, item_b, Py_LT)
            if cmp < 0:
                return -2  # Error
            if cmp:
                return -1
            cmp = PyObject_RichCompareBool(item_b, item_a, Py_LT)
            if cmp < 0:
                return -2
            if cmp:
                return 1
    
    # All elements equal, compare lengths
    if len_a < len_b:
        return -1
    if len_a > len_b:
        return 1
    return 0

# =============================================================================
# BOTTOM-UP SIFT-DOWN: TUPLE (with fast comparison)
# =============================================================================

cdef inline void sift_down_tuple_min(list heap, Py_ssize_t start, Py_ssize_t n) except *:
    """Bottom-up sift-down for tuple min-heap with fast comparison."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        tuple item = <tuple>heap[start]
        int cmp
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        right = child + 1
        if right < n:
            cmp = tuple_compare(<tuple>heap[right], <tuple>heap[child])
            if cmp == -2:
                raise
            if cmp < 0:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        cmp = tuple_compare(item, <tuple>heap[parent])
        if cmp == -2:
            raise
        if cmp >= 0:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_tuple_max(list heap, Py_ssize_t start, Py_ssize_t n) except *:
    """Bottom-up sift-down for tuple max-heap."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        tuple item = <tuple>heap[start]
        int cmp
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        right = child + 1
        if right < n:
            cmp = tuple_compare(<tuple>heap[right], <tuple>heap[child])
            if cmp == -2:
                raise
            if cmp > 0:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        cmp = tuple_compare(item, <tuple>heap[parent])
        if cmp == -2:
            raise
        if cmp <= 0:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# BOTTOM-UP SIFT-DOWN: GENERIC (with prefetching)
# =============================================================================

cdef inline void sift_down_generic(list heap, Py_ssize_t start, Py_ssize_t n, bint is_max) except *:
    """Bottom-up sift-down for any comparable type with prefetching."""
    cdef:
        Py_ssize_t pos = start, child, right, parent, grandchild
        object item = heap[start]
        int op = Py_GT if is_max else Py_LT
        int cmp
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        
        grandchild = (child << 1) + 1
        if grandchild < n:
            PREFETCH(<void*>heap[grandchild])
            if grandchild + 1 < n:
                PREFETCH(<void*>heap[grandchild + 1])
        
        right = child + 1
        if right < n:
            cmp = PyObject_RichCompareBool(heap[right], heap[child], op)
            if cmp < 0:
                raise
            if cmp:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        cmp = PyObject_RichCompareBool(item, heap[parent], op)
        if cmp < 0:
            raise
        if not cmp:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_with_key(list heap, Py_ssize_t start, Py_ssize_t n, bint is_max, object key) except *:
    """Bottom-up sift-down with key function."""
    cdef:
        Py_ssize_t pos = start, child, right, parent
        object item = heap[start]
        object item_key = key(item)
        int op = Py_GT if is_max else Py_LT
        int cmp
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n:
            cmp = PyObject_RichCompareBool(key(heap[right]), key(heap[child]), op)
            if cmp < 0:
                raise
            if cmp:
                child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > start:
        parent = (pos - 1) >> 1
        cmp = PyObject_RichCompareBool(item_key, key(heap[parent]), op)
        if cmp < 0:
            raise
        if not cmp:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_nary(list heap, Py_ssize_t start, Py_ssize_t n, bint is_max, Py_ssize_t arity) except *:
    """Bottom-up sift-down for n-ary heap."""
    cdef:
        Py_ssize_t pos = start, child, best, last, j, parent
        object item = heap[start]
        int op = Py_GT if is_max else Py_LT
        int cmp
    
    while True:
        child = arity * pos + 1
        if child >= n:
            break
        best = child
        last = child + arity
        if last > n:
            last = n
        for j in range(child + 1, last):
            cmp = PyObject_RichCompareBool(heap[j], heap[best], op)
            if cmp < 0:
                raise
            if cmp:
                best = j
        heap[pos] = heap[best]
        pos = best
    
    while pos > start:
        parent = (pos - 1) // arity
        cmp = PyObject_RichCompareBool(item, heap[parent], op)
        if cmp < 0:
            raise
        if not cmp:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void sift_down_nary_key(list heap, Py_ssize_t start, Py_ssize_t n, bint is_max, Py_ssize_t arity, object key) except *:
    """Bottom-up sift-down for n-ary heap with key."""
    cdef:
        Py_ssize_t pos = start, child, best, last, j, parent
        object item = heap[start]
        object item_key = key(item)
        int op = Py_GT if is_max else Py_LT
        int cmp
    
    while True:
        child = arity * pos + 1
        if child >= n:
            break
        best = child
        last = child + arity
        if last > n:
            last = n
        for j in range(child + 1, last):
            cmp = PyObject_RichCompareBool(key(heap[j]), key(heap[best]), op)
            if cmp < 0:
                raise
            if cmp:
                best = j
        heap[pos] = heap[best]
        pos = best
    
    while pos > start:
        parent = (pos - 1) // arity
        cmp = PyObject_RichCompareBool(item_key, key(heap[parent]), op)
        if cmp < 0:
            raise
        if not cmp:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# SIFT-UP
# =============================================================================

cdef inline void sift_up_generic(list heap, Py_ssize_t pos, bint is_max) except *:
    """Generic sift-up."""
    cdef:
        Py_ssize_t parent
        object item = heap[pos]
        int op = Py_GT if is_max else Py_LT
        int cmp
    
    while pos > 0:
        parent = (pos - 1) >> 1
        cmp = PyObject_RichCompareBool(item, heap[parent], op)
        if cmp < 0:
            raise
        if not cmp:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# HEAPIFY
# =============================================================================

cdef void heapify_int_min(list heap) noexcept:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_int_min(heap, i, n)

cdef void heapify_int_max(list heap) noexcept:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_int_max(heap, i, n)

cdef void heapify_float_min(list heap) noexcept:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_float_min(heap, i, n)

cdef void heapify_float_max(list heap) noexcept:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_float_max(heap, i, n)

cdef void heapify_str_min(list heap) except *:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_str_min(heap, i, n)

cdef void heapify_str_max(list heap) except *:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_str_max(heap, i, n)

cdef void heapify_bool_min(list heap) noexcept:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_bool_min(heap, i, n)

cdef void heapify_bool_max(list heap) noexcept:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_bool_max(heap, i, n)

cdef void heapify_tuple_min(list heap) except *:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_tuple_min(heap, i, n)

cdef void heapify_tuple_max(list heap) except *:
    cdef Py_ssize_t n = len(heap), i
    for i in range((n >> 1) - 1, -1, -1):
        sift_down_tuple_max(heap, i, n)

cdef void heapify_generic(list heap, bint is_max, Py_ssize_t arity, object key) except *:
    cdef Py_ssize_t n = len(heap), i
    if arity == 1:
        heap.sort(key=key, reverse=is_max)
        return
    if key is not None:
        for i in range((n - 2) // arity, -1, -1):
            sift_down_nary_key(heap, i, n, is_max, arity, key)
    elif arity == 2:
        for i in range((n >> 1) - 1, -1, -1):
            sift_down_generic(heap, i, n, is_max)
    else:
        for i in range((n - 2) // arity, -1, -1):
            sift_down_nary(heap, i, n, is_max, arity)

# =============================================================================
# DISPATCH
# =============================================================================

cdef inline void dispatch_sift_down(list heap, Py_ssize_t pos, Py_ssize_t n, bint is_max, int dtype) except *:
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
    elif dtype == TYPE_STR:
        if is_max:
            sift_down_str_max(heap, pos, n)
        else:
            sift_down_str_min(heap, pos, n)
    elif dtype == TYPE_BOOL:
        if is_max:
            sift_down_bool_max(heap, pos, n)
        else:
            sift_down_bool_min(heap, pos, n)
    elif dtype == TYPE_TUPLE:
        if is_max:
            sift_down_tuple_max(heap, pos, n)
        else:
            sift_down_tuple_min(heap, pos, n)
    else:
        sift_down_generic(heap, pos, n, is_max)

# =============================================================================
# POP
# =============================================================================

def pop(list heap, Py_ssize_t n=1, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Ultra-optimized pop with bottom-up sift-down (Floyd's algorithm)."""
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
                sift_down_with_key(heap, 0, new_size, max_heap, cmp)
            else:
                sift_down_nary_key(heap, 0, new_size, max_heap, arity, cmp)
        elif arity == 2:
            dtype = detect_type(heap, new_size)
            dispatch_sift_down(heap, 0, new_size, max_heap, dtype)
        else:
            sift_down_nary(heap, 0, new_size, max_heap, arity)
        return result
    
    # BULK POP
    if arity == 1:
        results = heap[:n]
        del heap[:n]
        return results
    
    results = []
    dtype = detect_type(heap, heap_size) if cmp is None else TYPE_MIXED
    
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
                sift_down_with_key(heap, 0, new_size, max_heap, cmp)
            else:
                sift_down_nary_key(heap, 0, new_size, max_heap, arity, cmp)
        elif arity == 2:
            dispatch_sift_down(heap, 0, new_size, max_heap, dtype)
        else:
            sift_down_nary(heap, 0, new_size, max_heap, arity)
    return results

# =============================================================================
# HEAPIFY
# =============================================================================

def heapify(list heap, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Transform list into heap in-place."""
    cdef Py_ssize_t n = len(heap)
    cdef int dtype
    
    if n <= 1:
        return
    if cmp is not None:
        heapify_generic(heap, max_heap, arity, cmp)
    elif arity == 1:
        heap.sort(reverse=max_heap)
    elif arity == 2:
        dtype = detect_type(heap, n)
        if dtype == TYPE_INT:
            if max_heap:
                heapify_int_max(heap)
            else:
                heapify_int_min(heap)
        elif dtype == TYPE_FLOAT:
            if max_heap:
                heapify_float_max(heap)
            else:
                heapify_float_min(heap)
        elif dtype == TYPE_STR:
            if max_heap:
                heapify_str_max(heap)
            else:
                heapify_str_min(heap)
        elif dtype == TYPE_BOOL:
            if max_heap:
                heapify_bool_max(heap)
            else:
                heapify_bool_min(heap)
        elif dtype == TYPE_TUPLE:
            if max_heap:
                heapify_tuple_max(heap)
            else:
                heapify_tuple_min(heap)
        else:
            heapify_generic(heap, max_heap, arity, None)
    else:
        heapify_generic(heap, max_heap, arity, None)

# =============================================================================
# PUSH
# =============================================================================

def push(list heap, object items, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Push item(s) onto heap."""
    cdef object item
    if isinstance(items, (list, set, frozenset)):
        for item in items:
            heap.append(item)
            sift_up_generic(heap, len(heap) - 1, max_heap)
    else:
        heap.append(items)
        sift_up_generic(heap, len(heap) - 1, max_heap)

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
