# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: nonecheck=False
# cython: overflowcheck=False
# cython: infer_types=True

"""
Ultra-Optimized Heap Pop for heapx

Strategy:
- int/float/bool: Specialized C-level comparisons with Floyd's algorithm
- str/custom: Direct delegation to heapq (no wrapper overhead)
"""

import heapq as _heapq

cdef extern from "Python.h":
    double PyFloat_AS_DOUBLE(object)

# =============================================================================
# TYPE DETECTION
# =============================================================================

DEF TYPE_INT = 1
DEF TYPE_FLOAT = 2
DEF TYPE_BOOL = 3
DEF TYPE_OTHER = 4

cdef inline int _detect_type(list heap) noexcept:
    if len(heap) == 0:
        return TYPE_OTHER
    cdef type t = type(heap[0])
    if t is int:
        return TYPE_INT
    if t is float:
        return TYPE_FLOAT
    if t is bool:
        return TYPE_BOOL
    return TYPE_OTHER

# =============================================================================
# SPECIALIZED SIFT-DOWN FUNCTIONS (Floyd's bottom-up algorithm)
# =============================================================================

cdef inline void _sift_int_min(list heap, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        long item_val = <long>item
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n and <long>heap[right] < <long>heap[child]:
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if item_val >= <long>heap[parent]:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void _sift_int_max(list heap, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        long item_val = <long>item
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n and <long>heap[right] > <long>heap[child]:
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if item_val <= <long>heap[parent]:
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void _sift_float_min(list heap, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        double item_val = PyFloat_AS_DOUBLE(item)
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n and PyFloat_AS_DOUBLE(heap[right]) < PyFloat_AS_DOUBLE(heap[child]):
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if item_val >= PyFloat_AS_DOUBLE(heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void _sift_float_max(list heap, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        double item_val = PyFloat_AS_DOUBLE(item)
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n and PyFloat_AS_DOUBLE(heap[right]) > PyFloat_AS_DOUBLE(heap[child]):
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if item_val <= PyFloat_AS_DOUBLE(heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void _sift_bool_min(list heap, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        bint item_val = item is True
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n and (heap[right] is not True) and (heap[child] is True):
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if item_val >= (heap[parent] is True):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void _sift_bool_max(list heap, Py_ssize_t n) noexcept:
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
        bint item_val = item is True
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n and (heap[right] is True) and (heap[child] is not True):
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if item_val <= (heap[parent] is True):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

cdef inline void _sift_generic_max(list heap, Py_ssize_t n):
    """Generic max-heap sift-down for any type."""
    cdef:
        Py_ssize_t pos = 0, child, right, parent
        object item = heap[0]
    
    while True:
        child = (pos << 1) + 1
        if child >= n:
            break
        right = child + 1
        if right < n and heap[right] > heap[child]:
            child = right
        heap[pos] = heap[child]
        pos = child
    
    while pos > 0:
        parent = (pos - 1) >> 1
        if not (item > heap[parent]):
            break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# HEAPIFY HELPERS
# =============================================================================

cdef inline void _heapify_int(list heap, Py_ssize_t n, bint is_max) noexcept:
    cdef Py_ssize_t i, pos, child, right, parent, start
    cdef object item
    cdef long item_val
    
    for i in range((n >> 1) - 1, -1, -1):
        pos = i
        start = i
        item = heap[pos]
        item_val = <long>item
        
        while True:
            child = (pos << 1) + 1
            if child >= n:
                break
            right = child + 1
            if is_max:
                if right < n and <long>heap[right] > <long>heap[child]:
                    child = right
            else:
                if right < n and <long>heap[right] < <long>heap[child]:
                    child = right
            heap[pos] = heap[child]
            pos = child
        
        while pos > start:
            parent = (pos - 1) >> 1
            if is_max:
                if item_val <= <long>heap[parent]:
                    break
            else:
                if item_val >= <long>heap[parent]:
                    break
            heap[pos] = heap[parent]
            pos = parent
        heap[pos] = item

cdef inline void _heapify_float(list heap, Py_ssize_t n, bint is_max) noexcept:
    cdef Py_ssize_t i, pos, child, right, parent, start
    cdef object item
    cdef double item_val
    
    for i in range((n >> 1) - 1, -1, -1):
        pos = i
        start = i
        item = heap[pos]
        item_val = PyFloat_AS_DOUBLE(item)
        
        while True:
            child = (pos << 1) + 1
            if child >= n:
                break
            right = child + 1
            if is_max:
                if right < n and PyFloat_AS_DOUBLE(heap[right]) > PyFloat_AS_DOUBLE(heap[child]):
                    child = right
            else:
                if right < n and PyFloat_AS_DOUBLE(heap[right]) < PyFloat_AS_DOUBLE(heap[child]):
                    child = right
            heap[pos] = heap[child]
            pos = child
        
        while pos > start:
            parent = (pos - 1) >> 1
            if is_max:
                if item_val <= PyFloat_AS_DOUBLE(heap[parent]):
                    break
            else:
                if item_val >= PyFloat_AS_DOUBLE(heap[parent]):
                    break
            heap[pos] = heap[parent]
            pos = parent
        heap[pos] = item

cdef inline void _heapify_bool(list heap, Py_ssize_t n, bint is_max) noexcept:
    cdef Py_ssize_t i, pos, child, right, parent, start
    cdef object item
    cdef bint item_val
    
    for i in range((n >> 1) - 1, -1, -1):
        pos = i
        start = i
        item = heap[pos]
        item_val = item is True
        
        while True:
            child = (pos << 1) + 1
            if child >= n:
                break
            right = child + 1
            if is_max:
                if right < n and (heap[right] is True) and (heap[child] is not True):
                    child = right
            else:
                if right < n and (heap[right] is not True) and (heap[child] is True):
                    child = right
            heap[pos] = heap[child]
            pos = child
        
        while pos > start:
            parent = (pos - 1) >> 1
            if is_max:
                if item_val <= (heap[parent] is True):
                    break
            else:
                if item_val >= (heap[parent] is True):
                    break
            heap[pos] = heap[parent]
            pos = parent
        heap[pos] = item

cdef inline void _heapify_generic_max(list heap, Py_ssize_t n):
    cdef Py_ssize_t i, pos, child, right, parent, start
    cdef object item
    
    for i in range((n >> 1) - 1, -1, -1):
        pos = i
        start = i
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

# =============================================================================
# N-ARY HEAP HELPERS
# =============================================================================

cdef void _nary_sift_down(list heap, Py_ssize_t pos, Py_ssize_t n, bint is_max, Py_ssize_t arity, object key):
    cdef:
        Py_ssize_t child, best, last, j
        object item = heap[pos]
        object item_key = key(item) if key is not None else item
    
    while True:
        child = arity * pos + 1
        if child >= n:
            break
        best = child
        last = child + arity
        if last > n:
            last = n
        
        if key is not None:
            for j in range(child + 1, last):
                if is_max:
                    if key(heap[j]) > key(heap[best]):
                        best = j
                else:
                    if key(heap[j]) < key(heap[best]):
                        best = j
            if is_max:
                if item_key >= key(heap[best]):
                    break
            else:
                if item_key <= key(heap[best]):
                    break
        else:
            for j in range(child + 1, last):
                if is_max:
                    if heap[j] > heap[best]:
                        best = j
                else:
                    if heap[j] < heap[best]:
                        best = j
            if is_max:
                if item >= heap[best]:
                    break
            else:
                if item <= heap[best]:
                    break
        
        heap[pos] = heap[best]
        pos = best
    heap[pos] = item

cdef void _nary_sift_up(list heap, Py_ssize_t pos, bint is_max, Py_ssize_t arity, object key):
    cdef:
        Py_ssize_t parent
        object item = heap[pos]
        object item_key = key(item) if key is not None else item
    
    while pos > 0:
        parent = (pos - 1) // arity
        if key is not None:
            if is_max:
                if item_key <= key(heap[parent]):
                    break
            else:
                if item_key >= key(heap[parent]):
                    break
        else:
            if is_max:
                if item <= heap[parent]:
                    break
            else:
                if item >= heap[parent]:
                    break
        heap[pos] = heap[parent]
        pos = parent
    heap[pos] = item

# =============================================================================
# PUBLIC API: HEAPIFY
# =============================================================================

def heapify(list heap, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Transform list into heap in-place."""
    cdef Py_ssize_t n = len(heap), i
    cdef int dtype
    
    if n <= 1:
        return
    
    if arity == 1:
        heap.sort(key=cmp, reverse=max_heap)
        return
    
    if cmp is not None or arity != 2:
        for i in range((n - 2) // arity, -1, -1):
            _nary_sift_down(heap, i, n, max_heap, arity, cmp)
        return
    
    dtype = _detect_type(heap)
    
    if dtype == TYPE_INT:
        _heapify_int(heap, n, max_heap)
    elif dtype == TYPE_FLOAT:
        _heapify_float(heap, n, max_heap)
    elif dtype == TYPE_BOOL:
        _heapify_bool(heap, n, max_heap)
    elif max_heap:
        _heapify_generic_max(heap, n)
    else:
        _heapq.heapify(heap)

# =============================================================================
# PUBLIC API: POP
# =============================================================================

def pop(list heap, Py_ssize_t n=1, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Pop and return the smallest (or largest) item(s) from heap."""
    cdef:
        Py_ssize_t heap_size = len(heap)
        object result, last
        int dtype
        type t
    
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
    
    # FAST PATH: min-heap with binary arity and no key function
    if cmp is None and arity == 2 and not max_heap:
        # Quick type check - if not int/float/bool, delegate to heapq immediately
        t = type(heap[0])
        if t is not int and t is not float and t is not bool:
            if n == 1:
                return _heapq.heappop(heap)
            else:
                return [_heapq.heappop(heap) for _ in range(min(n, len(heap)))]
    
    # Single pop
    if n == 1:
        return _pop_single_opt(heap, max_heap, cmp, arity)
    
    # Bulk pop
    return _pop_bulk_opt(heap, n, max_heap, cmp, arity)

cdef inline object _pop_single_opt(list heap, bint max_heap, object cmp, Py_ssize_t arity):
    cdef:
        Py_ssize_t heap_size = len(heap)
        object result = heap[0]
        object last
        int dtype
    
    if heap_size == 1:
        heap.pop()
        return result
    
    if arity == 1:
        del heap[0]
        return result
    
    last = heap.pop()
    heap[0] = last
    heap_size -= 1
    
    if cmp is not None or arity != 2:
        _nary_sift_down(heap, 0, heap_size, max_heap, arity, cmp)
        return result
    
    dtype = _detect_type(heap)
    
    if dtype == TYPE_INT:
        if max_heap:
            _sift_int_max(heap, heap_size)
        else:
            _sift_int_min(heap, heap_size)
    elif dtype == TYPE_FLOAT:
        if max_heap:
            _sift_float_max(heap, heap_size)
        else:
            _sift_float_min(heap, heap_size)
    elif dtype == TYPE_BOOL:
        if max_heap:
            _sift_bool_max(heap, heap_size)
        else:
            _sift_bool_min(heap, heap_size)
    else:
        # max_heap with generic type
        _sift_generic_max(heap, heap_size)
    
    return result

cdef list _pop_bulk_opt(list heap, Py_ssize_t n, bint max_heap, object cmp, Py_ssize_t arity):
    cdef list results = []
    cdef Py_ssize_t i
    
    if arity == 1:
        results = heap[:n]
        del heap[:n]
        return results
    
    for i in range(n):
        if len(heap) == 0:
            break
        results.append(_pop_single_opt(heap, max_heap, cmp, arity))
    
    return results

# =============================================================================
# PUBLIC API: PUSH
# =============================================================================

def push(list heap, object items, bint max_heap=False, object cmp=None, Py_ssize_t arity=2, bint nogil=False):
    """Push item(s) onto heap."""
    cdef int dtype
    
    # Fast path for str/custom min-heap
    if cmp is None and arity == 2 and not max_heap:
        dtype = _detect_type(heap) if len(heap) > 0 else TYPE_OTHER
        if dtype == TYPE_OTHER:
            if isinstance(items, (list, set, frozenset)):
                for item in items:
                    _heapq.heappush(heap, item)
            else:
                _heapq.heappush(heap, items)
            return
    
    if isinstance(items, (list, set, frozenset)):
        for item in items:
            _push_single_opt(heap, item, max_heap, cmp, arity)
    else:
        _push_single_opt(heap, items, max_heap, cmp, arity)

cdef inline void _push_single_opt(list heap, object item, bint max_heap, object cmp, Py_ssize_t arity):
    heap.append(item)
    if max_heap or cmp is not None or arity != 2:
        _nary_sift_up(heap, len(heap) - 1, max_heap, arity, cmp)
    else:
        _heapq._siftdown(heap, 0, len(heap) - 1)

# =============================================================================
# PUBLIC API: VERIFY
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
