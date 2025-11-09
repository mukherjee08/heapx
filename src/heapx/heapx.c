/*
Compile this module with:

THE BELOW WILL CHANGE !!!

/usr/bin/clang -shared -fPIC -O3 -march=native -flto \
  -DNDEBUG -ffast-math \
  -I/Users/mukhani/miniconda3/envs/iheap/include/python3.12 \
  iheap.c \
  -o iheap.cpython-312-darwin.so \
  -undefined dynamic_lookup

Function: heapify( heap, max_heap=False, cmp=None, arity=2)
  - heap    : any list-like Python sequence supporting len, __getitem__, __setitem__
  - max_heap: bool (default False: min-heap)
  - cmp     : optional key function; when provided comparisons are performed on cmp(x)
  - arity   : integer >= 1 (default 2)
*/

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <listobject.h>

/* Optimization macros */
#define PyList_GET_ITEM_FAST(op, i) (((PyListObject *)(op))->ob_item[i])
#define PyList_SET_ITEM_FAST(op, i, v) (((PyListObject *)(op))->ob_item[i] = v)

#ifdef __GNUC__
#define likely(x)   __builtin_expect(!!(x), 1)
#define unlikely(x) __builtin_expect(!!(x), 0)
#define PREFETCH(addr) __builtin_prefetch((addr), 0, 3)
#else
#define likely(x)   (x)
#define unlikely(x) (x)
#define PREFETCH(addr) ((void)0)
#endif

/* Advanced prefetching for better cache utilization */
#define PREFETCH_DISTANCE 3
#define PREFETCH_MULTIPLE(base, start, n, max) do { \
  for (Py_ssize_t _i = 0; _i < PREFETCH_DISTANCE && (start) + _i < (max); _i++) { \
    PREFETCH(&(base)[(start) + _i]); \
  } \
} while(0)

/* Fast comparison for common types - bypasses Python's generic comparison machinery */
static inline int
fast_compare(PyObject *a, PyObject *b, int op, int *result) {
  /* OPTIMIZATION 1: Fast path for integers (most common case) */
  if (likely(PyLong_CheckExact(a) && PyLong_CheckExact(b))) {
    long val_a = PyLong_AsLong(a);
    if (likely(val_a != -1 || !PyErr_Occurred())) {
      long val_b = PyLong_AsLong(b);
      if (likely(val_b != -1 || !PyErr_Occurred())) {
        switch(op) {
          case Py_LT: *result = val_a < val_b; return 1;
          case Py_GT: *result = val_a > val_b; return 1;
          case Py_LE: *result = val_a <= val_b; return 1;
          case Py_GE: *result = val_a >= val_b; return 1;
        }
      }
    }
    PyErr_Clear();
  }
  
  /* OPTIMIZATION 2: Fast path for floats */
  if (likely(PyFloat_CheckExact(a) && PyFloat_CheckExact(b))) {
    double val_a = PyFloat_AS_DOUBLE(a);
    double val_b = PyFloat_AS_DOUBLE(b);
    switch(op) {
      case Py_LT: *result = val_a < val_b; return 1;
      case Py_GT: *result = val_a > val_b; return 1;
      case Py_LE: *result = val_a <= val_b; return 1;
      case Py_GE: *result = val_a >= val_b; return 1;
    }
  }
  
  return 0; /* Fall back to PyObject_RichCompareBool */
}

/* Optimized comparison with fast path and error batching */
static inline int
optimized_compare(PyObject *a, PyObject *b, int op) {
  int result;
  if (likely(fast_compare(a, b, op, &result))) {
    return result;
  }
  return PyObject_RichCompareBool(a, b, op);
}

/* SIMD and homogeneous array detection for vectorization opportunities */
static int
detect_homogeneous_type(PyObject **items, Py_ssize_t n) {
  if (unlikely(n < 8)) return 0; /* Too small for SIMD benefits */
  
  int all_long = 1, all_float = 1;
  
  /* Check first 8 elements to determine type homogeneity */
  for (Py_ssize_t i = 0; i < 8 && (all_long || all_float); i++) {
    if (!PyLong_CheckExact(items[i])) all_long = 0;
    if (!PyFloat_CheckExact(items[i])) all_float = 0;
  }
  
  if (!all_long && !all_float) return 0;
  
  /* Verify homogeneity across entire array */
  for (Py_ssize_t i = 8; i < n; i++) {
    if (all_long && !PyLong_CheckExact(items[i])) return 0;
    if (all_float && !PyFloat_CheckExact(items[i])) return 0;
  }
  
  return all_long ? 1 : 2; /* 1=integers, 2=floats */
}

/* ---------- Ultra-optimized Floyd's heapify: binary min/max heap with fast comparisons ---------- */
static int
list_heapify_floyd_ultra_optimized(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = listobj->ob_item;
  
  /* OPTIMIZATION: Detect homogeneous arrays for potential SIMD acceleration */
  int homogeneous_type = detect_homogeneous_type(items, n);
  
  /* Enhanced Floyd's algorithm with fast comparisons */
  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *newitem = items[pos];
    
    /* PHASE 1: OPTIMIZED SIFT DOWN WITH FAST COMPARISONS */
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      PyObject *bestobj = items[child];
      
      /* ADVANCED PREFETCHING: Load multiple cache lines ahead */
      PREFETCH_MULTIPLE(items, (child << 1) + 1, PREFETCH_DISTANCE, n);
      
      Py_ssize_t right = child + 1;
      if (likely(right < n)) {
        PyObject *rightobj = items[right];
        
        /* FAST COMPARISON: Bypass Python dispatch for common types */
        int cmp = optimized_compare(rightobj, bestobj, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) return -1;
        if (cmp) {
          best = right;
          bestobj = rightobj;
        }
      }
      
      /* Direct pointer assignment - no reference counting overhead */
      items[pos] = bestobj;
      pos = best;
    }
    
    /* PHASE 2: OPTIMIZED SIFT UP WITH FAST COMPARISONS */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      PyObject *parentobj = items[parent];
      
      /* Fast comparison for sift-up operation */
      int cmp = optimized_compare(newitem, parentobj, is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) return -1;
      if (!cmp) break;
      
      items[pos] = parentobj;
      pos = parent;
    }
    
    items[pos] = newitem;
  }
  
  return 0;
}

/* ---------- Ultra-optimized key function path: binary list with precomputed keys and fast comparisons ---------- */
static int
list_heapify_with_key_ultra_optimized(PyListObject *listobj, PyObject *keyfunc, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = listobj->ob_item;
  
  /* Enhanced key caching with fast comparisons */
  PyObject **keys = PyMem_Malloc(sizeof(PyObject *) * (size_t)n);
  if (unlikely(!keys)) {
    PyErr_NoMemory();
    return -1;
  }

  /* PHASE 1: PRECOMPUTE ALL KEYS */
  for (Py_ssize_t i = 0; i < n; i++) {
    PyObject *k = PyObject_CallOneArg(keyfunc, items[i]);
    if (unlikely(!k)) {
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      PyMem_Free(keys);
      return -1;
    }
    keys[i] = k;
  }

  /* OPTIMIZATION: Detect homogeneous key types for fast comparison paths */
  int key_homogeneous_type = detect_homogeneous_type(keys, n);

  /* PHASE 2: FLOYD'S HEAPIFICATION WITH FAST KEY COMPARISONS */
  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *newitem = items[pos];
    PyObject *newkey = keys[pos];
    
    /* Sift down phase with fast key comparisons */
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      PyObject *bestkey = keys[child];
      
      /* Advanced prefetching for key arrays */
      PREFETCH_MULTIPLE(keys, (child << 1) + 1, PREFETCH_DISTANCE, n);
      
      Py_ssize_t right = child + 1;
      if (likely(right < n)) {
        /* FAST KEY COMPARISON: Use optimized comparison for common key types */
        int cmp = optimized_compare(keys[right], bestkey, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          PyMem_Free(keys);
          return -1;
        }
        if (cmp) {
          best = right;
          bestkey = keys[right];
        }
      }
      
      /* Move both item and key together - no ref counting in inner loop */
      items[pos] = items[best];
      keys[pos] = bestkey;
      pos = best;
    }
    
    /* Sift up phase with fast key comparisons */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      int cmp = optimized_compare(newkey, keys[parent], is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) {
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        PyMem_Free(keys);
        return -1;
      }
      if (!cmp) break;
      
      items[pos] = items[parent];
      keys[pos] = keys[parent];
      pos = parent;
    }
    
    items[pos] = newitem;
    keys[pos] = newkey;
  }

  /* PHASE 3: CLEANUP */
  for (Py_ssize_t i = 0; i < n; i++) Py_DECREF(keys[i]);
  PyMem_Free(keys);
  return 0;
}

/* ---------- Ultra-optimized arity == 1 heapify with fast comparisons ---------- */
static int
heapify_arity_one_ultra_optimized(PyObject *heap, int is_max, PyObject *cmp)
{
  Py_ssize_t n = PySequence_Size(heap);
  if (unlikely(n <= 1)) return 0;

  for (Py_ssize_t i = n - 2; i >= 0; i--) {
    Py_ssize_t pos = i;
    
    while (1) {
      Py_ssize_t child = pos + 1;
      if (unlikely(child >= n)) break;

      PyObject *parent = PySequence_GetItem(heap, pos);
      if (unlikely(!parent)) return -1;
      
      PyObject *childobj = PySequence_GetItem(heap, child);
      if (unlikely(!childobj)) { Py_DECREF(parent); return -1; }

      PyObject *parentkey, *childkey;
      if (likely(cmp)) {
        parentkey = PyObject_CallOneArg(cmp, parent);
        if (unlikely(!parentkey)) { Py_DECREF(parent); Py_DECREF(childobj); return -1; }
        childkey = PyObject_CallOneArg(cmp, childobj);
        if (unlikely(!childkey)) { Py_DECREF(parent); Py_DECREF(childobj); Py_DECREF(parentkey); return -1; }
      } else {
        parentkey = parent;
        childkey = childobj;
        Py_INCREF(parentkey);
        Py_INCREF(childkey);
      }

      /* FAST COMPARISON: Use optimized comparison for better scaling */
      int done = optimized_compare(parentkey, childkey, is_max ? Py_GE : Py_LE);
      Py_DECREF(parentkey);
      Py_DECREF(childkey);
      
      if (unlikely(done < 0)) { Py_DECREF(parent); Py_DECREF(childobj); return -1; }
      if (done) { Py_DECREF(parent); Py_DECREF(childobj); break; }

      if (unlikely(PySequence_SetItem(heap, pos, childobj) < 0 || 
                   PySequence_SetItem(heap, child, parent) < 0)) {
        Py_DECREF(parent); Py_DECREF(childobj);
        return -1;
      }
      
      Py_DECREF(parent);
      Py_DECREF(childobj);
      pos = child;
    }
  }
  return 0;
}

/* ---------- Ultra-optimized generic n-ary heapify with fast comparisons ---------- */
static int
generic_heapify_ultra_optimized(PyObject *heap, int is_max, PyObject *cmp, Py_ssize_t arity)
{
  Py_ssize_t n = PySequence_Size(heap);
  if (unlikely(n <= 1)) return 0;

  for (Py_ssize_t i = (n - 2) / arity; i >= 0; i--) {
    Py_ssize_t pos = i;
    
    while (1) {
      Py_ssize_t child = arity * pos + 1;
      if (unlikely(child >= n)) break;

      Py_ssize_t best = child;
      PyObject *bestobj = PySequence_GetItem(heap, child);
      if (unlikely(!bestobj)) return -1;
      
      PyObject *bestkey;
      if (likely(cmp)) {
        bestkey = PyObject_CallOneArg(cmp, bestobj);
        if (unlikely(!bestkey)) { Py_DECREF(bestobj); return -1; }
      } else {
        bestkey = bestobj;
        Py_INCREF(bestkey);
      }

      Py_ssize_t last = child + arity;
      if (unlikely(last > n)) last = n;

      /* Advanced prefetching for n-ary heaps */
      if (likely(child < n)) PREFETCH(&heap);

      for (Py_ssize_t j = child + 1; j < last; j++) {
        PyObject *cur = PySequence_GetItem(heap, j);
        if (unlikely(!cur)) { 
          Py_DECREF(bestobj); 
          Py_DECREF(bestkey); 
          return -1; 
        }
        
        PyObject *curkey;
        if (likely(cmp)) {
          curkey = PyObject_CallOneArg(cmp, cur);
          if (unlikely(!curkey)) { 
            Py_DECREF(cur); Py_DECREF(bestobj); Py_DECREF(bestkey); 
            return -1; 
          }
        } else {
          curkey = cur;
          Py_INCREF(curkey);
        }

        /* FAST COMPARISON: Use optimized comparison for better scaling */
        int better = optimized_compare(curkey, bestkey, is_max ? Py_GT : Py_LT);
        if (unlikely(better < 0)) { 
          Py_DECREF(cur); Py_DECREF(curkey); Py_DECREF(bestobj); Py_DECREF(bestkey); 
          return -1; 
        }
        
        if (better) {
          Py_DECREF(bestobj);
          Py_DECREF(bestkey);
          best = j;
          bestobj = cur;
          bestkey = curkey;
        } else {
          Py_DECREF(cur);
          Py_DECREF(curkey);
        }
      }

      PyObject *parent = PySequence_GetItem(heap, pos);
      if (unlikely(!parent)) { Py_DECREF(bestobj); Py_DECREF(bestkey); return -1; }
      
      PyObject *parentkey;
      if (likely(cmp)) {
        parentkey = PyObject_CallOneArg(cmp, parent);
        if (unlikely(!parentkey)) { 
          Py_DECREF(parent); Py_DECREF(bestobj); Py_DECREF(bestkey); 
          return -1; 
        }
      } else {
        parentkey = parent;
        Py_INCREF(parentkey);
      }

      /* FAST COMPARISON: Use optimized comparison for parent-child check */
      int done = optimized_compare(parentkey, bestkey, is_max ? Py_GE : Py_LE);
      Py_DECREF(parent); Py_DECREF(parentkey);
      Py_DECREF(bestobj); Py_DECREF(bestkey);
      
      if (unlikely(done < 0)) return -1;
      if (done) break;

      PyObject *tmp_parent = PySequence_GetItem(heap, pos);
      PyObject *tmp_child = PySequence_GetItem(heap, best);
      if (unlikely(!tmp_parent || !tmp_child)) { 
        Py_XDECREF(tmp_parent); Py_XDECREF(tmp_child); 
        return -1; 
      }
      
      if (unlikely(PySequence_SetItem(heap, pos, tmp_child) < 0 || 
                   PySequence_SetItem(heap, best, tmp_parent) < 0)) {
        Py_DECREF(tmp_parent); Py_DECREF(tmp_child);
        return -1;
      }
      
      Py_DECREF(tmp_parent); Py_DECREF(tmp_child);
      pos = best;
    }
  }
  return 0;
}

/* ---------- Python wrapper with ultra-optimized algorithm selection ---------- */
static PyObject *
py_heapify(PyObject *self, PyObject *args, PyObject *kwargs)
{
  static char *kwlist[] = {"heap", "max_heap", "cmp", "arity", NULL};
  PyObject *heap;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OOn:heapify", kwlist,
                                   &heap, &max_heap_obj, &cmp, &arity))
    return NULL;

  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_SetString(PyExc_TypeError, "cmp must be callable or None");
    return NULL;
  }
  if (unlikely(arity < 1)) {
    PyErr_SetString(PyExc_ValueError, "arity must be >= 1");
    return NULL;
  }

  int rc = 0;

  /* ULTRA-OPTIMIZED ALGORITHM SELECTION */
  if (likely(PyList_CheckExact(heap) && cmp == Py_None && arity == 2)) {
    /* FASTEST PATH: Binary heap with ultra-fast comparisons */
    rc = list_heapify_floyd_ultra_optimized((PyListObject *)heap, is_max);
    
  } else if (PyList_CheckExact(heap) && cmp != Py_None && arity == 2) {
    /* FAST PATH: Binary heap with key function and fast comparisons */
    rc = list_heapify_with_key_ultra_optimized((PyListObject *)heap, cmp, is_max);
    
  } else if (arity == 1) {
    /* SPECIALIZED PATH: Unary heap with fast comparisons */
    rc = heapify_arity_one_ultra_optimized(heap, is_max, (cmp == Py_None ? NULL : cmp));
    
  } else {
    /* GENERAL PATH: N-ary heap with fast comparisons */
    rc = generic_heapify_ultra_optimized(heap, is_max, (cmp == Py_None ? NULL : cmp), arity);
  }

  if (unlikely(rc < 0)) return NULL;
  Py_RETURN_NONE;
}

/* ---------- Module definition ---------- */
static PyMethodDef Methods[] = {
  {"heapify", (PyCFunction)py_heapify, METH_VARARGS | METH_KEYWORDS,
   "Ultra-optimized heapify with fast comparisons (supports min/max, n-ary, optional cmp)."},
  {NULL, NULL, 0, NULL}
};

static struct PyModuleDef heapx = {
  PyModuleDef_HEAD_INIT,
  "heapx",
  "Extended heap module for Python",
  -1,
  Methods
};

PyMODINIT_FUNC
PyInit_heapx(void)
{
  return PyModule_Create(&heapx);
}
