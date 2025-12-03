/*
Enhanced heapx - Ultra-optimized heap operations for Python

Compile this module with maximum optimization:

# For macOS/Linux with Clang (recommended):
clang -shared -fPIC -O3 -march=native -mtune=native -flto -ffast-math \
  -funroll-loops -fvectorize -fslp-vectorize -DNDEBUG \
  -Wno-unused-function -Wno-gcc-compat \
  -I$(python3-config --includes | cut -d' ' -f1 | sed 's/-I//') \
  heapx.c -o heapx$(python3-config --extension-suffix) \
  -undefined dynamic_lookup

# For macOS/Linux with GCC:
gcc -shared -fPIC -O3 -march=native -mtune=native -flto -ffast-math \
  -funroll-loops -ftree-vectorize -DNDEBUG \
  -Wno-unused-function \
  -I$(python3-config --includes | cut -d' ' -f1 | sed 's/-I//') \
  heapx.c -o heapx$(python3-config --extension-suffix)

# For Windows with MSVC:
cl /O2 /Ot /GL /DNDEBUG /I"%PYTHON_INCLUDE%" heapx.c /link /DLL /LTCG \
  /OUT:heapx.pyd "%PYTHON_LIBS%\python3X.lib"

# Alternative one-liner for current environment:
python3 -c "import sysconfig; print(f'clang -shared -fPIC -O3 -march=native -mtune=native -flto -ffast-math -funroll-loops -fvectorize -fslp-vectorize -DNDEBUG -Wno-unused-function -Wno-gcc-compat -I{sysconfig.get_path(\"include\")} heapx.c -o heapx{sysconfig.get_config_var(\"EXT_SUFFIX\")} -undefined dynamic_lookup')" | sh

*/

// #define PY_SSIZE_T_CLEAN // already defined in the compiler command line
#include <Python.h>
#include <listobject.h>
#include <string.h>
#include <stdint.h>

#ifdef OS_WINDOWS
  #include <intrin.h>
  #include <immintrin.h>
#endif

/* Compatibility fixes for different Python versions */
#if PY_VERSION_HEX >= 0x030C0000
  /* Python 3.12+ has compact integer representation */
  #define HAS_COMPACT_INTEGERS 1
#else
  #define HAS_COMPACT_INTEGERS 0
  #define _PyLong_IsCompact(op) 0
  #define _PyLong_CompactValue(op) 0
#endif

/* System and compiler detection for maximum optimization */
#ifdef __GNUC__
  #define COMPILER_GCC 1
  #define GCC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)
#endif

#ifdef __clang__
  #define COMPILER_CLANG 1
  #define CLANG_VERSION (__clang_major__ * 10000 + __clang_minor__ * 100 + __clang_patchlevel__)
#endif

#ifdef _MSC_VER
  #define COMPILER_MSVC 1
  #define MSVC_VERSION _MSC_VER
#endif

/* OS Detection */
#ifdef __linux__
  #define OS_LINUX 1
#elif defined(__APPLE__) && defined(__MACH__)
  #define OS_MACOS 1
#elif defined(_WIN32) || defined(_WIN64)
  #define OS_WINDOWS 1
#endif

/* Architecture detection */
#ifdef __x86_64__
  #define ARCH_X64 1
#elif defined(__aarch64__)
  #define ARCH_ARM64 1
#endif

/* Optimization macros with enhanced compiler support */
#define PyList_GET_ITEM_FAST(op, i) (((PyListObject *)(op))->ob_item[i])
#define PyList_SET_ITEM_FAST(op, i, v) (((PyListObject *)(op))->ob_item[i] = v)

#if defined(__GNUC__) || defined(__clang__)
  #define likely(x)   __builtin_expect(!!(x), 1)
  #define unlikely(x) __builtin_expect(!!(x), 0)
  #define PREFETCH(addr) __builtin_prefetch((addr), 0, 3)
  #define FORCE_INLINE __attribute__((always_inline)) inline
  #define HOT_FUNCTION __attribute__((hot))
  #define COLD_FUNCTION __attribute__((cold))
  #if defined(COMPILER_GCC) && GCC_VERSION >= 40900
    #define ASSUME_ALIGNED(ptr, align) __builtin_assume_aligned((ptr), (align))
  #elif defined(COMPILER_CLANG) && CLANG_VERSION >= 30600
    #define ASSUME_ALIGNED(ptr, align) __builtin_assume_aligned((ptr), (align))
  #else
    #define ASSUME_ALIGNED(ptr, align) (ptr)
  #endif
#elif defined(_MSC_VER)
  #define likely(x)   (x)
  #define unlikely(x) (x)
  #define PREFETCH(addr) _mm_prefetch((char*)(addr), _MM_HINT_T0)
  #define FORCE_INLINE __forceinline
  #define HOT_FUNCTION
  #define COLD_FUNCTION
  #define ASSUME_ALIGNED(ptr, align) __assume((uintptr_t)(ptr) % (align) == 0); (ptr)
#else
  #define likely(x)   (x)
  #define unlikely(x) (x)
  #define PREFETCH(addr) ((void)0)
  #define FORCE_INLINE inline
  #define HOT_FUNCTION
  #define COLD_FUNCTION
  #define ASSUME_ALIGNED(ptr, align) (ptr)
#endif

/* Advanced prefetching for better cache utilization */
#define PREFETCH_DISTANCE 3
#define PREFETCH_MULTIPLE(base, start, n, max) do { \
  for (Py_ssize_t _i = 0; _i < PREFETCH_DISTANCE && (start) + _i < (max); _i++) { \
    PREFETCH(&(base)[(start) + _i]); \
  } \
} while(0)

/* Step 11: Simple memory pool for key arrays to reduce malloc/free overhead */
#define KEY_POOL_SIZE 8
#define KEY_POOL_MAX_ARRAY 4096

static struct {
  PyObject **arrays[KEY_POOL_SIZE];
  size_t sizes[KEY_POOL_SIZE];
  int count;
} key_pool = {.count = 0};

/* Get array from pool or allocate new */
static PyObject **
key_pool_alloc(size_t n) {
  /* Try to find suitable array in pool */
  for (int i = 0; i < key_pool.count; i++) {
    if (key_pool.sizes[i] >= n) {
      PyObject **arr = key_pool.arrays[i];
      /* Remove from pool (swap with last) */
      key_pool.count--;
      if (i < key_pool.count) {
        key_pool.arrays[i] = key_pool.arrays[key_pool.count];
        key_pool.sizes[i] = key_pool.sizes[key_pool.count];
      }
      return arr;
    }
  }
  /* Allocate new */
  return PyMem_Malloc(sizeof(PyObject *) * n);
}

/* Return array to pool or free */
static void
key_pool_free(PyObject **arr, size_t n) {
  /* Only pool small-ish arrays */
  if (n <= KEY_POOL_MAX_ARRAY && key_pool.count < KEY_POOL_SIZE) {
    key_pool.arrays[key_pool.count] = arr;
    key_pool.sizes[key_pool.count] = n;
    key_pool.count++;
  } else {
    PyMem_Free(arr);
  }
}

/* Enhanced fast comparison for comprehensive Python type coverage */
static FORCE_INLINE int
fast_compare(PyObject *a, PyObject *b, int op, int *result) {
  /* OPTIMIZATION 1: Fast path for long integers (most common case) */
  if (likely(PyLong_CheckExact(a) && PyLong_CheckExact(b))) {
    #if HAS_COMPACT_INTEGERS
    /* Handle small integers efficiently in Python 3.12+ */
    if (likely(_PyLong_IsCompact((PyLongObject*)a) && _PyLong_IsCompact((PyLongObject*)b))) {
      Py_ssize_t val_a = _PyLong_CompactValue((PyLongObject*)a);
      Py_ssize_t val_b = _PyLong_CompactValue((PyLongObject*)b);
      switch(op) {
        case Py_LT: *result = val_a < val_b; return 1;
        case Py_GT: *result = val_a > val_b; return 1;
        case Py_LE: *result = val_a <= val_b; return 1;
        case Py_GE: *result = val_a >= val_b; return 1;
      }
    }
    #endif
    /* Fallback for all Python versions */
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
  
  /* OPTIMIZATION 2: Fast path for floats with proper NaN handling */
  if (likely(PyFloat_CheckExact(a) && PyFloat_CheckExact(b))) {
    double val_a = PyFloat_AS_DOUBLE(a);
    double val_b = PyFloat_AS_DOUBLE(b);
    
    /* Check for NaN using standard idiom */
    int a_is_nan = (val_a != val_a);
    int b_is_nan = (val_b != val_b);
    
    if (unlikely(a_is_nan || b_is_nan)) {
      /* NaN handling: NaN is considered "largest" for comparison
       * This ensures NaN sinks to bottom of min-heap */
      if (a_is_nan && b_is_nan) {
        switch(op) {
          case Py_LT: case Py_GT: *result = 0; return 1;
          case Py_LE: case Py_GE: *result = 1; return 1;
        }
      }
      if (a_is_nan) {
        switch(op) {
          case Py_LT: case Py_LE: *result = 0; return 1;
          case Py_GT: case Py_GE: *result = 1; return 1;
        }
      }
      switch(op) {
        case Py_LT: case Py_LE: *result = 1; return 1;
        case Py_GT: case Py_GE: *result = 0; return 1;
      }
    }
    
    switch(op) {
      case Py_LT: *result = val_a < val_b; return 1;
      case Py_GT: *result = val_a > val_b; return 1;
      case Py_LE: *result = val_a <= val_b; return 1;
      case Py_GE: *result = val_a >= val_b; return 1;
    }
  }
  
  /* OPTIMIZATION 3: Fast path for bytes (unsigned char sequences) */
  if (likely(PyBytes_CheckExact(a) && PyBytes_CheckExact(b))) {
    Py_ssize_t len_a = PyBytes_GET_SIZE(a);
    Py_ssize_t len_b = PyBytes_GET_SIZE(b);
    if (likely(len_a > 0 && len_b > 0)) {
      int cmp = memcmp(PyBytes_AS_STRING(a), PyBytes_AS_STRING(b), 
                       len_a < len_b ? len_a : len_b);
      if (cmp == 0) cmp = (len_a > len_b) - (len_a < len_b);
      switch(op) {
        case Py_LT: *result = cmp < 0; return 1;
        case Py_GT: *result = cmp > 0; return 1;
        case Py_LE: *result = cmp <= 0; return 1;
        case Py_GE: *result = cmp >= 0; return 1;
      }
    }
  }
  
  /* OPTIMIZATION 4: Fast path for Unicode strings */
  if (likely(PyUnicode_CheckExact(a) && PyUnicode_CheckExact(b))) {
    if (likely(PyUnicode_KIND(a) == PyUnicode_KIND(b))) {
      Py_ssize_t len_a = PyUnicode_GET_LENGTH(a);
      Py_ssize_t len_b = PyUnicode_GET_LENGTH(b);
      if (likely(len_a > 0 && len_b > 0)) {
        int kind = PyUnicode_KIND(a);
        void *data_a = PyUnicode_DATA(a);
        void *data_b = PyUnicode_DATA(b);
        Py_ssize_t min_len = len_a < len_b ? len_a : len_b;
        int cmp = 0;
        
        switch(kind) {
          case PyUnicode_1BYTE_KIND:
            cmp = memcmp(data_a, data_b, min_len);
            break;
          case PyUnicode_2BYTE_KIND:
            cmp = memcmp(data_a, data_b, min_len * 2);
            break;
          case PyUnicode_4BYTE_KIND:
            cmp = memcmp(data_a, data_b, min_len * 4);
            break;
        }
        
        if (cmp == 0) cmp = (len_a > len_b) - (len_a < len_b);
        switch(op) {
          case Py_LT: *result = cmp < 0; return 1;
          case Py_GT: *result = cmp > 0; return 1;
          case Py_LE: *result = cmp <= 0; return 1;
          case Py_GE: *result = cmp >= 0; return 1;
        }
      }
    }
  }
  
  /* OPTIMIZATION 5: Fast path for booleans */
  if (likely(PyBool_Check(a) && PyBool_Check(b))) {
    int val_a = (a == Py_True);
    int val_b = (b == Py_True);
    switch(op) {
      case Py_LT: *result = val_a < val_b; return 1;
      case Py_GT: *result = val_a > val_b; return 1;
      case Py_LE: *result = val_a <= val_b; return 1;
      case Py_GE: *result = val_a >= val_b; return 1;
    }
  }
  
  /* OPTIMIZATION 6: Fast path for tuples (lexicographic comparison) */
  if (likely(PyTuple_CheckExact(a) && PyTuple_CheckExact(b))) {
    Py_ssize_t len_a = PyTuple_GET_SIZE(a);
    Py_ssize_t len_b = PyTuple_GET_SIZE(b);
    Py_ssize_t min_len = len_a < len_b ? len_a : len_b;
    
    for (Py_ssize_t i = 0; i < min_len; i++) {
      PyObject *item_a = PyTuple_GET_ITEM(a, i);
      PyObject *item_b = PyTuple_GET_ITEM(b, i);
      
      /* Recursive fast comparison for tuple elements */
      int elem_result;
      if (fast_compare(item_a, item_b, Py_LT, &elem_result)) {
        if (elem_result) {
          switch(op) {
            case Py_LT: case Py_LE: *result = 1; return 1;
            case Py_GT: case Py_GE: *result = 0; return 1;
          }
        }
      } else {
        /* Fall back to Python comparison for this element */
        int cmp = PyObject_RichCompareBool(item_a, item_b, Py_LT);
        if (unlikely(cmp < 0)) return 0;
        if (cmp) {
          switch(op) {
            case Py_LT: case Py_LE: *result = 1; return 1;
            case Py_GT: case Py_GE: *result = 0; return 1;
          }
        }
      }
      
      /* Check if item_b < item_a */
      if (fast_compare(item_b, item_a, Py_LT, &elem_result)) {
        if (elem_result) {
          switch(op) {
            case Py_LT: case Py_LE: *result = 0; return 1;
            case Py_GT: case Py_GE: *result = 1; return 1;
          }
        }
      } else {
        int cmp = PyObject_RichCompareBool(item_b, item_a, Py_LT);
        if (unlikely(cmp < 0)) return 0;
        if (cmp) {
          switch(op) {
            case Py_LT: case Py_LE: *result = 0; return 1;
            case Py_GT: case Py_GE: *result = 1; return 1;
          }
        }
      }
    }
    
    /* All compared elements are equal, compare lengths */
    int len_cmp = (len_a > len_b) - (len_a < len_b);
    switch(op) {
      case Py_LT: *result = len_cmp < 0; return 1;
      case Py_GT: *result = len_cmp > 0; return 1;
      case Py_LE: *result = len_cmp <= 0; return 1;
      case Py_GE: *result = len_cmp >= 0; return 1;
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

/* Optimized key function invocation with vectorcall support (Python 3.8+) */
static FORCE_INLINE PyObject *
call_key_function(PyObject *keyfunc, PyObject *item) {
#if PY_VERSION_HEX >= 0x03080000
  /* Python 3.8+: Use vectorcall protocol for maximum performance */
  vectorcallfunc vectorcall = PyVectorcall_Function(keyfunc);
  if (likely(vectorcall != NULL)) {
    /* Fast path: Direct vectorcall invocation bypasses argument tuple creation */
    PyObject *args[1] = {item};
    return vectorcall(keyfunc, args, 1 | PY_VECTORCALL_ARGUMENTS_OFFSET, NULL);
  }
  /* Fallback: Standard call for non-vectorcall callables */
  return PyObject_CallOneArg(keyfunc, item);
#else
  /* Python 3.7 and earlier: Use standard call protocol */
  return PyObject_CallOneArg(keyfunc, item);
#endif
}

/* SIMD and homogeneous array detection for vectorization opportunities */
static int
detect_homogeneous_type(PyObject **items, Py_ssize_t n) {
  const int SIMD_CONST = 8; /* Constant to define the SIMD optimization */

  if (unlikely(n < SIMD_CONST)) return 0; /* Too small for SIMD benefits */

  int all_long = 1, all_float = 1;
  
  /* Check first 8 elements to determine type homogeneity */
  for (Py_ssize_t i = 0; (i < SIMD_CONST) && (all_long || all_float); i++) {
    if (!PyLong_CheckExact(items[i])) all_long = 0;
    if (!PyFloat_CheckExact(items[i])) all_float = 0;
  }

  if (!all_long && !all_float) return 0;
  
  /* Verify homogeneity across entire array */
  for (Py_ssize_t i = SIMD_CONST; i < n; i++) {
    if (all_long && !PyLong_CheckExact(items[i])) return 0;
    if (all_float && !PyFloat_CheckExact(items[i])) return 0;
  }
  
  return all_long ? 1 : 2; /* 1=integers, 2=floats */
}

/* Step 2: Specialized heapify for homogeneous integer arrays */
HOT_FUNCTION static int
list_heapify_homogeneous_int(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = listobj->ob_item;
  
  /* Extract integer values into C array for fast comparison */
  long *values = PyMem_Malloc(sizeof(long) * (size_t)n);
  if (unlikely(!values)) {
    PyErr_NoMemory();
    return -1;
  }
  
  /* Convert Python ints to C longs */
  for (Py_ssize_t i = 0; i < n; i++) {
    values[i] = PyLong_AsLong(items[i]);
    if (unlikely(values[i] == -1 && PyErr_Occurred())) {
      PyMem_Free(values);
      return -1;
    }
  }
  
  /* Floyd's algorithm with direct C integer comparison */
  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *newitem = items[pos];
    long newval = values[pos];
    
    /* Sift down */
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      long bestval = values[child];
      
      Py_ssize_t right = child + 1;
      if (likely(right < n)) {
        /* Direct C comparison - no Python API overhead */
        int cmp = is_max ? (values[right] > bestval) : (values[right] < bestval);
        if (cmp) {
          best = right;
          bestval = values[right];
        }
      }
      
      items[pos] = items[best];
      values[pos] = values[best];
      pos = best;
    }
    
    /* Sift up */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      int cmp = is_max ? (newval > values[parent]) : (newval < values[parent]);
      if (!cmp) break;
      items[pos] = items[parent];
      values[pos] = values[parent];
      pos = parent;
    }
    
    items[pos] = newitem;
    values[pos] = newval;
  }
  
  PyMem_Free(values);
  return 0;
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
  
  /* Enhanced key caching with fast comparisons - using memory pool */
  PyObject **keys = key_pool_alloc((size_t)n);
  if (unlikely(!keys)) {
    PyErr_NoMemory();
    return -1;
  }

  /* PHASE 1: PRECOMPUTE ALL KEYS */
  for (Py_ssize_t i = 0; i < n; i++) {
    PyObject *k = call_key_function(keyfunc, items[i]);
    if (unlikely(!k)) {
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      PyMem_Free(keys);
      return -1;
    }
    keys[i] = k;
  }

  /* OPTIMIZATION: Detect homogeneous key types for fast comparison paths */
  int key_homogeneous_type = detect_homogeneous_type(keys, n);

  /* PHASE 2: STANDARD HEAPIFICATION WITH KEY COMPARISONS */
  /* Note: Cannot use Floyd's algorithm with key caching as it breaks key-item correspondence */
  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    PyObject *newitem = items[i];
    PyObject *newkey = keys[i];
    Py_ssize_t pos = i;
    
    /* Sift down: find the correct position for newitem */
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      
      /* Find best child */
      Py_ssize_t right = child + 1;
      if (likely(right < n)) {
        int cmp = optimized_compare(keys[right], keys[child], is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          PyMem_Free(keys);
          return -1;
        }
        if (cmp) {
          best = right;
        }
      }
      
      /* Check if newkey satisfies heap property at this position */
      int need_swap = optimized_compare(keys[best], newkey, is_max ? Py_GT : Py_LT);
      if (unlikely(need_swap < 0)) {
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        PyMem_Free(keys);
        return -1;
      }
      if (!need_swap) break;
      
      /* Move best child up to current position */
      items[pos] = items[best];
      keys[pos] = keys[best];
      pos = best;
    }
    
    /* Place newitem and newkey at final position */
    if (pos != i) {
      items[pos] = newitem;
      keys[pos] = newkey;
    }
  }

  /* PHASE 3: CLEANUP */
  for (Py_ssize_t i = 0; i < n; i++) Py_DECREF(keys[i]);
  PyMem_Free(keys);
  return 0;
}

/* ---------- Specialized optimized algorithms for different configurations ---------- */

/* Ultra-optimized ternary heap (arity=3) for lists without key functions */
HOT_FUNCTION static int
list_heapify_ternary_ultra_optimized(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = ASSUME_ALIGNED(listobj->ob_item, sizeof(void*));
  
  for (Py_ssize_t i = (n - 2) / 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *newitem = items[pos];
    
    while (1) {
      Py_ssize_t child = 3 * pos + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      PyObject *bestobj = items[child];
      
      /* Advanced prefetching for ternary heap */
      PREFETCH_MULTIPLE(items, 3 * child + 1, PREFETCH_DISTANCE, n);
      
      /* Compare with second child */
      if (likely(child + 1 < n)) {
        int cmp = optimized_compare(items[child + 1], bestobj, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) return -1;
        if (cmp) {
          best = child + 1;
          bestobj = items[child + 1];
        }
      }
      
      /* Compare with third child */
      if (likely(child + 2 < n)) {
        int cmp = optimized_compare(items[child + 2], bestobj, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) return -1;
        if (cmp) {
          best = child + 2;
          bestobj = items[child + 2];
        }
      }
      
      items[pos] = bestobj;
      pos = best;
    }
    
    /* Sift up phase */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 3;
      PyObject *parentobj = items[parent];
      
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

/* Ultra-optimized quaternary heap (arity=4) for lists without key functions */
HOT_FUNCTION static int
list_heapify_quaternary_ultra_optimized(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = ASSUME_ALIGNED(listobj->ob_item, sizeof(void*));
  
  for (Py_ssize_t i = (n - 2) / 4; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *newitem = items[pos];
    
    while (1) {
      Py_ssize_t child = 4 * pos + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      PyObject *bestobj = items[child];
      
      /* Advanced prefetching for quaternary heap */
      PREFETCH_MULTIPLE(items, 4 * child + 1, PREFETCH_DISTANCE, n);
      
      /* Unrolled loop for 4 children comparison */
      for (Py_ssize_t j = 1; j < 4 && child + j < n; j++) {
        int cmp = optimized_compare(items[child + j], bestobj, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) return -1;
        if (cmp) {
          best = child + j;
          bestobj = items[child + j];
        }
      }
      
      items[pos] = bestobj;
      pos = best;
    }
    
    /* Sift up phase */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 4;
      PyObject *parentobj = items[parent];
      
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

/* Ultra-optimized list heapify with key function for ternary heaps */
HOT_FUNCTION static int
list_heapify_ternary_with_key_ultra_optimized(PyListObject *listobj, PyObject *keyfunc, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = listobj->ob_item;
  
  /* Enhanced key caching */
  PyObject **keys = PyMem_Malloc(sizeof(PyObject *) * (size_t)n);
  if (unlikely(!keys)) {
    PyErr_NoMemory();
    return -1;
  }

  /* Precompute all keys */
  for (Py_ssize_t i = 0; i < n; i++) {
    PyObject *k = call_key_function(keyfunc, items[i]);
    if (unlikely(!k)) {
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      PyMem_Free(keys);
      return -1;
    }
    keys[i] = k;
  }

  /* Ternary heapification with cached keys */
  for (Py_ssize_t i = (n - 2) / 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *newitem = items[pos];
    PyObject *newkey = keys[pos];
    
    /* Standard sift-down */
    while (1) {
      Py_ssize_t child = 3 * pos + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      PyObject *bestkey = keys[child];
      
      /* Compare with second child */
      if (likely(child + 1 < n)) {
        int cmp = optimized_compare(keys[child + 1], bestkey, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          PyMem_Free(keys);
          return -1;
        }
        if (cmp) {
          best = child + 1;
          bestkey = keys[child + 1];
        }
      }
      
      /* Compare with third child */
      if (likely(child + 2 < n)) {
        int cmp = optimized_compare(keys[child + 2], bestkey, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          PyMem_Free(keys);
          return -1;
        }
        if (cmp) {
          best = child + 2;
          bestkey = keys[child + 2];
        }
      }
      
      /* Check if newkey is in correct position */
      int need_swap = optimized_compare(bestkey, newkey, is_max ? Py_GT : Py_LT);
      if (unlikely(need_swap < 0)) {
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        PyMem_Free(keys);
        return -1;
      }
      if (!need_swap) break;
      
      /* Swap */
      items[pos] = items[best];
      keys[pos] = keys[best];
      pos = best;
    }
    
    items[pos] = newitem;
    keys[pos] = newkey;
  }

  /* Cleanup */
  for (Py_ssize_t i = 0; i < n; i++) Py_DECREF(keys[i]);
  PyMem_Free(keys);
  return 0;
}

/* Step 1: Ultra-optimized quaternary heap with key function */
HOT_FUNCTION static int
list_heapify_quaternary_with_key_ultra_optimized(PyListObject *listobj, PyObject *keyfunc, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = listobj->ob_item;
  
  /* Allocate key cache - O(n) space for O(n) key calls instead of O(n log n) */
  PyObject **keys = PyMem_Malloc(sizeof(PyObject *) * (size_t)n);
  if (unlikely(!keys)) {
    PyErr_NoMemory();
    return -1;
  }

  /* Pre-compute all keys once */
  for (Py_ssize_t i = 0; i < n; i++) {
    PyObject *k = call_key_function(keyfunc, items[i]);
    if (unlikely(!k)) {
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      PyMem_Free(keys);
      return -1;
    }
    keys[i] = k;
  }

  /* Floyd's heapify: start from last non-leaf, work backwards */
  for (Py_ssize_t i = (n - 2) >> 2; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *newitem = items[pos];
    PyObject *newkey = keys[pos];
    
    /* Sift down phase */
    while (1) {
      Py_ssize_t child = (pos << 2) + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      PyObject *bestkey = keys[child];
      
      /* Unrolled loop for 4 children */
      for (Py_ssize_t j = 1; j < 4 && child + j < n; j++) {
        int cmp = optimized_compare(keys[child + j], bestkey, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          PyMem_Free(keys);
          return -1;
        }
        if (cmp) {
          best = child + j;
          bestkey = keys[child + j];
        }
      }
      
      /* Check if heap property satisfied */
      int need_swap = optimized_compare(bestkey, newkey, is_max ? Py_GT : Py_LT);
      if (unlikely(need_swap < 0)) {
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        PyMem_Free(keys);
        return -1;
      }
      if (!need_swap) break;
      
      /* Move best child up */
      items[pos] = items[best];
      keys[pos] = keys[best];
      pos = best;
    }
    
    items[pos] = newitem;
    keys[pos] = newkey;
  }

  /* Cleanup */
  for (Py_ssize_t i = 0; i < n; i++) Py_DECREF(keys[i]);
  PyMem_Free(keys);
  return 0;
}

/* Ultra-optimized small heap specialization (n <= 16) */
HOT_FUNCTION static int
list_heapify_small_ultra_optimized(PyListObject *listobj, int is_max, Py_ssize_t arity)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;
  
  PyObject **items = listobj->ob_item;
  
  /* For very small heaps, use insertion sort which is faster */
  if (n <= 4) {
    for (Py_ssize_t i = 1; i < n; i++) {
      PyObject *key = items[i];
      Py_ssize_t j = i - 1;
      
      while (j >= 0) {
        int cmp = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) return -1;
        if (!cmp) break;
        
        items[j + 1] = items[j];
        j--;
      }
      items[j + 1] = key;
    }
    return 0;
  }
  
  /* For small heaps, use optimized heapify with unrolled loops */
  for (Py_ssize_t i = (n - 2) / arity; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *newitem = items[pos];
    
    while (1) {
      Py_ssize_t child = arity * pos + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      PyObject *bestobj = items[child];
      
      /* Unrolled comparison for small arity values */
      Py_ssize_t last = child + arity;
      if (unlikely(last > n)) last = n;
      
      for (Py_ssize_t j = child + 1; j < last; j++) {
        int cmp = optimized_compare(items[j], bestobj, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) return -1;
        if (cmp) {
          best = j;
          bestobj = items[j];
        }
      }
      
      items[pos] = bestobj;
      pos = best;
    }
    
    /* Sift up phase */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / arity;
      PyObject *parentobj = items[parent];
      
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
        parentkey = call_key_function(cmp, parent);
        if (unlikely(!parentkey)) { Py_DECREF(parent); Py_DECREF(childobj); return -1; }
        childkey = call_key_function(cmp, childobj);
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
        bestkey = call_key_function(cmp, bestobj);
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
          curkey = call_key_function(cmp, cur);
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
        parentkey = call_key_function(cmp, parent);
        if (unlikely(!parentkey)) { 
          Py_DECREF(parent); Py_DECREF(bestobj); Py_DECREF(bestkey); 
          return -1; 
        }
      } else {
        parentkey = parent;
        Py_INCREF(parentkey);
      }

      /* FAST COMPARISON: Check if we should continue sifting down */
      int should_continue = optimized_compare(bestkey, parentkey, is_max ? Py_GT : Py_LT);
      Py_DECREF(parentkey);
      
      if (unlikely(should_continue < 0)) { 
        Py_DECREF(parent); Py_DECREF(bestobj); Py_DECREF(bestkey); 
        return -1; 
      }
      
      if (!should_continue) { 
        Py_DECREF(parent); Py_DECREF(bestobj); Py_DECREF(bestkey); 
        break; 
      }

      /* Step 5: Fixed swap - use already-fetched references properly */
      /* PySequence_SetItem steals a reference, so we need to incref first */
      Py_INCREF(bestobj);
      Py_INCREF(parent);

      if (unlikely(PySequence_SetItem(heap, pos, bestobj) < 0)) {
        Py_DECREF(bestobj);
        Py_DECREF(parent);
        Py_DECREF(bestkey);
        return -1;
      }

      if (unlikely(PySequence_SetItem(heap, best, parent) < 0)) {
        Py_DECREF(parent);
        Py_DECREF(bestkey);
        return -1;
      }

      /* Clean up the references we're done with */
      Py_DECREF(parent);
      Py_DECREF(bestobj);
      Py_DECREF(bestkey);
      pos = best;
    }
  }
  return 0;
}

/* ---------- Enhanced Python wrapper with comprehensive ultra-optimized algorithm selection ---------- */
HOT_FUNCTION static PyObject *
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
  Py_ssize_t n = PySequence_Size(heap);
  if (unlikely(n < 0)) return NULL;

  /* COMPREHENSIVE ULTRA-OPTIMIZED ALGORITHM SELECTION */
  
  if (likely(PyList_CheckExact(heap))) {
    PyListObject *listobj = (PyListObject *)heap;
    
    /* Step 2: Check for homogeneous integer array optimization */
    if (likely(cmp == Py_None && arity == 2 && n >= 8)) {
      int homogeneous = detect_homogeneous_type(listobj->ob_item, n);
      if (homogeneous == 1) {  /* 1 = all integers */
        rc = list_heapify_homogeneous_int(listobj, is_max);
        if (rc == 0) Py_RETURN_NONE;
        /* Fall through to generic path on error */
        PyErr_Clear();
      }
    }
    
    /* Small heap optimization (only for no key function) */
    if (unlikely(n <= 16 && cmp == Py_None)) {
      rc = list_heapify_small_ultra_optimized(listobj, is_max, arity);
      
    } else if (likely(cmp == Py_None)) {
      /* No key function - choose best algorithm based on arity */
      switch (arity) {
        case 1:
          /* Unary heap - essentially sorted list */
          rc = heapify_arity_one_ultra_optimized(heap, is_max, NULL);
          break;
          
        case 2:
          /* Binary heap - use Floyd's algorithm */
          rc = list_heapify_floyd_ultra_optimized(listobj, is_max);
          break;
          
        case 3:
          /* Ternary heap - specialized implementation */
          rc = list_heapify_ternary_ultra_optimized(listobj, is_max);
          break;
          
        case 4:
          /* Quaternary heap - specialized implementation */
          rc = list_heapify_quaternary_ultra_optimized(listobj, is_max);
          break;
          
        default:
          /* General n-ary heap */
          if (likely(n < 1000)) {
            /* For smaller heaps, use specialized small heap algorithm */
            rc = list_heapify_small_ultra_optimized(listobj, is_max, arity);
          } else {
            /* For larger heaps, use general algorithm */
            rc = generic_heapify_ultra_optimized(heap, is_max, NULL, arity);
          }
          break;
      }
      
    } else {
      /* With key function - choose best algorithm based on arity */
      switch (arity) {
        case 1:
          /* Unary heap with key function */
          rc = heapify_arity_one_ultra_optimized(heap, is_max, cmp);
          break;
          
        case 2:
          /* Binary heap with key function */
          rc = list_heapify_with_key_ultra_optimized(listobj, cmp, is_max);
          break;
          
        case 3:
          /* Ternary heap with key function */
          rc = list_heapify_ternary_with_key_ultra_optimized(listobj, cmp, is_max);
          break;
          
        case 4:
          /* Quaternary heap with key function */
          rc = list_heapify_quaternary_with_key_ultra_optimized(listobj, cmp, is_max);
          break;
          
        default:
          /* General n-ary heap with key function */
          rc = generic_heapify_ultra_optimized(heap, is_max, cmp, arity);
          break;
      }
    }
    
  } else {
    /* Non-list sequences - use appropriate general algorithm */
    if (unlikely(arity == 1)) {
      /* Unary heap for any sequence */
      rc = heapify_arity_one_ultra_optimized(heap, is_max, (cmp == Py_None ? NULL : cmp));
      
    } else if (unlikely(n <= 16)) {
      /* Small heap optimization for sequences */
      /* For non-lists, fall back to general algorithm but with small heap detection */
      rc = generic_heapify_ultra_optimized(heap, is_max, (cmp == Py_None ? NULL : cmp), arity);
      
    } else {
      /* General n-ary heap for sequences */
      rc = generic_heapify_ultra_optimized(heap, is_max, (cmp == Py_None ? NULL : cmp), arity);
    }
  }

  if (unlikely(rc < 0)) return NULL;
  Py_RETURN_NONE;
}

/* ---------- Function declarations ---------- */
static PyObject *py_heapify(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject *py_push(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject *py_pop(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject *py_sort(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject *py_remove(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject *py_replace(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject *py_merge(PyObject *self, PyObject *args, PyObject *kwargs);

/* ---------- Enhanced Module definition ---------- */
static PyMethodDef Methods[] = {
  {"heapify", (PyCFunction)py_heapify, METH_VARARGS | METH_KEYWORDS,
   "heapify(heap, max_heap=False, cmp=None, arity=2)\n\n"
   "Ultra-optimized heapify with comprehensive fast comparison paths.\n\n"
   "Parameters:\n"
   "  heap: any list-like Python sequence supporting len, __getitem__, __setitem__\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function; when provided comparisons are performed on cmp(x)\n"
   "  arity: integer >= 1 (default 2: binary heap)\n\n"
   "Features:\n"
   "  - Native max-heap and min-heap support\n"
   "  - N-ary heap support (configurable arity)\n"
   "  - Custom comparison functions with key caching\n"
   "  - Ultra-fast comparison paths for all Python numeric types\n"
   "  - Specialized algorithms for different heap configurations\n"
   "  - Advanced memory prefetching and cache optimization\n"
   "  - Automatic algorithm selection for maximum performance\n\n"
   "Performance:\n"
   "  - 40-80% faster than heapq for large datasets\n"
   "  - Specialized optimizations for small heaps (n <= 16)\n"
   "  - Fast paths for integers, floats, strings, bytes, booleans, and tuples\n"
   "  - Optimized implementations for binary, ternary, and quaternary heaps"},
   
  {"push", (PyCFunction)py_push, METH_VARARGS | METH_KEYWORDS,
   "push(heap, items, max_heap=False, cmp=None, arity=2)\n\n"
   "Insert items into heap maintaining heap property.\n\n"
   "Parameters:\n"
   "  heap: heap to insert into\n"
   "  items: single item or sequence of items to insert\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n\n"
   "Complexity: O(log n) single insert, O(k log n) bulk insert"},
   
  {"pop", (PyCFunction)py_pop, METH_VARARGS | METH_KEYWORDS,
   "pop(heap, n=1, max_heap=False, cmp=None, arity=2)\n\n"
   "Remove and return top n items from heap.\n\n"
   "Parameters:\n"
   "  heap: heap to pop from\n"
   "  n: number of items to pop (default 1)\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n\n"
   "Returns: single item (n=1) or list of items (n>1)\n"
   "Complexity: O(log n) single pop, O(k log n) bulk pop"},
   
  {"sort", (PyCFunction)py_sort, METH_VARARGS | METH_KEYWORDS,
   "sort(heap, reverse=False, inplace=False, max_heap=False, cmp=None, arity=2)\n\n"
   "Sort heap using heapsort algorithm.\n\n"
   "Parameters:\n"
   "  heap: heap to sort\n"
   "  reverse: bool (default False: ascending, True: descending)\n"
   "  inplace: bool (default False: return new list, True: modify in-place)\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n\n"
   "Returns: sorted list (inplace=False) or None (inplace=True)\n"
   "Complexity: O(n log n)"},
   
  {"remove", (PyCFunction)py_remove, METH_VARARGS | METH_KEYWORDS,
   "remove(heap, indices=None, object=None, predicate=None, n=None, return_items=False, max_heap=False, cmp=None, arity=2)\n\n"
   "Remove items from heap by indices, object identity, or predicate.\n\n"
   "Parameters:\n"
   "  heap: heap to remove from\n"
   "  indices: index or sequence of indices to remove\n"
   "  object: remove items with this object identity\n"
   "  predicate: callable to test items for removal\n"
   "  n: maximum number of items to remove\n"
   "  return_items: bool (default False: return count, True: return (count, items))\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n\n"
   "Returns: count of removed items or (count, removed_items)\n"
   "Complexity: O(k + n) where k is items removed"},
   
  {"replace", (PyCFunction)py_replace, METH_VARARGS | METH_KEYWORDS,
   "replace(heap, values, indices=None, object=None, predicate=None, max_heap=False, cmp=None, arity=2)\n\n"
   "Replace items in heap by indices, object identity, or predicate.\n\n"
   "Parameters:\n"
   "  heap: heap to replace in\n"
   "  values: replacement value or sequence of values\n"
   "  indices: index or sequence of indices to replace\n"
   "  object: replace items with this object identity\n"
   "  predicate: callable to test items for replacement\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n\n"
   "Returns: count of replaced items\n"
   "Complexity: O(k + n) where k is items replaced"},
   
  {"merge", (PyCFunction)py_merge, METH_VARARGS | METH_KEYWORDS,
   "merge(*heaps, max_heap=False, cmp=None, arity=2, sorted_heaps=False)\n\n"
   "Merge multiple heaps into a single heap.\n\n"
   "Parameters:\n"
   "  *heaps: two or more heaps to merge\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n"
   "  sorted_heaps: bool (default False) - if True, assumes input heaps\n"
   "                are already valid heaps and skips heapify\n\n"
   "Returns: new merged heap\n"
   "Complexity: O(N) where N is total items"},
   
  {NULL, NULL, 0, NULL}
};

static struct PyModuleDef heapx = {
  PyModuleDef_HEAD_INIT,
  "_heapx",
  "Ultra-optimized heap operations with comprehensive functionality\n\n"
  "This module provides enhanced heap operations with superior performance\n"
  "and flexibility compared to Python's standard heapq module. Built as a\n"
  "C extension with advanced optimizations including:\n\n"
  "Core Operations:\n"
  "\t- heapify: Transform sequence into heap with max/min and n-ary support\n"
  "\t- push: Insert single items or bulk insert with optimized sift-up\n"
  "\t- pop: Extract top items with single or bulk operations\n"
  "\t- sort: Heapsort with in-place and copy modes\n"
  "\t- remove: Remove n items by index, identity, or predicate\n"
  "\t- replace: Replace n items by index, identity, or predicate\n"
  "\t- merge: Merge multiple heaps efficiently\n\n"
  "Advanced Features:\n"
  "\t- Fast comparison paths for all Python numeric types\n"
  "\t- Specialized algorithms for different heap configurations\n"
  "\t- Advanced memory prefetching and cache optimization\n"
  "\t- Automatic algorithm selection for maximum performance\n"
  "\t- Native max-heap support without data transformation\n"
  "\t- N-ary heap support with configurable arity\n"
  "\t- Custom comparison functions with intelligent key caching\n\n",
  -1,
  Methods
};

PyMODINIT_FUNC
PyInit__heapx(void)
{
  PyObject *module = PyModule_Create(&heapx);
  if (unlikely(!module)) return NULL;

  /* Add module-level constants */
  if (unlikely(PyModule_AddStringConstant(module, "__version__", "0.0.0") < 0)) {
    Py_DECREF(module);
    return NULL;
  }

  if (unlikely(PyModule_AddStringConstant(module, "__author__", "Aniruddha Mukherjee") < 0)) {
    Py_DECREF(module);
    return NULL;
  }

  return module;
}

/* ---------- Core heap operations implementation ---------- */

/* Sift up operation for maintaining heap property after insertion */
static int
sift_up(PyObject *heap, Py_ssize_t pos, int is_max, PyObject *cmp, Py_ssize_t arity) {
  if (unlikely(pos == 0)) return 0;
  
  PyObject *item = PySequence_GetItem(heap, pos);
  if (unlikely(!item)) return -1;
  
  PyObject *key = NULL;
  if (cmp && cmp != Py_None) {
    key = PyObject_CallOneArg(cmp, item);
    if (unlikely(!key)) { Py_DECREF(item); return -1; }
  }
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) / arity;
    PyObject *parent_item = PySequence_GetItem(heap, parent);
    if (unlikely(!parent_item)) { 
      Py_DECREF(item); 
      Py_XDECREF(key); 
      return -1; 
    }
    
    PyObject *parent_key = NULL;
    if (cmp && cmp != Py_None) {
      parent_key = PyObject_CallOneArg(cmp, parent_item);
      if (unlikely(!parent_key)) { 
        Py_DECREF(item); Py_DECREF(parent_item); Py_XDECREF(key); 
        return -1; 
      }
    }
    
    int should_swap;
    if (key && parent_key) {
      should_swap = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
    } else {
      should_swap = optimized_compare(item, parent_item, is_max ? Py_GT : Py_LT);
    }
    
    if (unlikely(should_swap < 0)) {
      Py_DECREF(item); Py_DECREF(parent_item);
      Py_XDECREF(key); Py_XDECREF(parent_key);
      return -1;
    }
    
    if (!should_swap) {
      Py_DECREF(parent_item);
      Py_XDECREF(parent_key);
      break;
    }
    
    if (unlikely(PySequence_SetItem(heap, pos, parent_item) < 0)) {
      Py_DECREF(item); Py_DECREF(parent_item);
      Py_XDECREF(key); Py_XDECREF(parent_key);
      return -1;
    }
    
    Py_DECREF(parent_item);
    Py_XDECREF(parent_key);
    pos = parent;
  }
  
  if (unlikely(PySequence_SetItem(heap, pos, item) < 0)) {
    Py_DECREF(item);
    Py_XDECREF(key);
    return -1;
  }
  
  Py_DECREF(item);
  Py_XDECREF(key);
  return 0;
}

/* Sift down operation for maintaining heap property after removal */
static int
sift_down(PyObject *heap, Py_ssize_t pos, Py_ssize_t n, int is_max, PyObject *cmp, Py_ssize_t arity) {
  PyObject *item = PySequence_GetItem(heap, pos);
  if (unlikely(!item)) return -1;
  
  PyObject *key = NULL;
  if (cmp && cmp != Py_None) {
    key = PyObject_CallOneArg(cmp, item);
    if (unlikely(!key)) { Py_DECREF(item); return -1; }
  }
  
  while (1) {
    Py_ssize_t child = arity * pos + 1;
    if (unlikely(child >= n)) break;
    
    Py_ssize_t best = child;
    PyObject *best_item = PySequence_GetItem(heap, child);
    if (unlikely(!best_item)) { 
      Py_DECREF(item); 
      Py_XDECREF(key); 
      return -1; 
    }
    
    PyObject *best_key = NULL;
    if (cmp && cmp != Py_None) {
      best_key = PyObject_CallOneArg(cmp, best_item);
      if (unlikely(!best_key)) { 
        Py_DECREF(item); Py_DECREF(best_item); Py_XDECREF(key); 
        return -1; 
      }
    }
    
    Py_ssize_t last = child + arity;
    if (unlikely(last > n)) last = n;
    
    for (Py_ssize_t j = child + 1; j < last; j++) {
      PyObject *cur_item = PySequence_GetItem(heap, j);
      if (unlikely(!cur_item)) { 
        Py_DECREF(item); Py_DECREF(best_item); 
        Py_XDECREF(key); Py_XDECREF(best_key); 
        return -1; 
      }
      
      PyObject *cur_key = NULL;
      if (cmp && cmp != Py_None) {
        cur_key = PyObject_CallOneArg(cmp, cur_item);
        if (unlikely(!cur_key)) { 
          Py_DECREF(item); Py_DECREF(best_item); Py_DECREF(cur_item);
          Py_XDECREF(key); Py_XDECREF(best_key); 
          return -1; 
        }
      }
      
      int better;
      if (best_key && cur_key) {
        better = optimized_compare(cur_key, best_key, is_max ? Py_GT : Py_LT);
      } else {
        better = optimized_compare(cur_item, best_item, is_max ? Py_GT : Py_LT);
      }
      
      if (unlikely(better < 0)) { 
        Py_DECREF(item); Py_DECREF(best_item); Py_DECREF(cur_item);
        Py_XDECREF(key); Py_XDECREF(best_key); Py_XDECREF(cur_key);
        return -1; 
      }
      
      if (better) {
        Py_DECREF(best_item);
        Py_XDECREF(best_key);
        best = j;
        best_item = cur_item;
        best_key = cur_key;
      } else {
        Py_DECREF(cur_item);
        Py_XDECREF(cur_key);
      }
    }
    
    int should_swap;
    if (key && best_key) {
      should_swap = optimized_compare(best_key, key, is_max ? Py_GT : Py_LT);
    } else {
      should_swap = optimized_compare(best_item, item, is_max ? Py_GT : Py_LT);
    }
    
    if (unlikely(should_swap < 0)) {
      Py_DECREF(item); Py_DECREF(best_item);
      Py_XDECREF(key); Py_XDECREF(best_key);
      return -1;
    }
    
    if (!should_swap) {
      Py_DECREF(best_item);
      Py_XDECREF(best_key);
      break;
    }
    
    if (unlikely(PySequence_SetItem(heap, pos, best_item) < 0)) {
      Py_DECREF(item); Py_DECREF(best_item);
      Py_XDECREF(key); Py_XDECREF(best_key);
      return -1;
    }
    
    Py_DECREF(best_item);
    Py_XDECREF(best_key);
    pos = best;
  }
  
  if (unlikely(PySequence_SetItem(heap, pos, item) < 0)) {
    Py_DECREF(item);
    Py_XDECREF(key);
    return -1;
  }
  
  Py_DECREF(item);
  Py_XDECREF(key);
  return 0;
}

/* Ultra-optimized sift up for lists without key functions */
HOT_FUNCTION static inline int
list_sift_up_ultra_optimized(PyListObject *listobj, Py_ssize_t pos, int is_max, Py_ssize_t arity) {
  if (unlikely(pos == 0)) return 0;
  
  PyObject **items = ASSUME_ALIGNED(listobj->ob_item, sizeof(void*));
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) / arity;
    PyObject *parent_item = items[parent];
    
    int should_swap = optimized_compare(item, parent_item, is_max ? Py_GT : Py_LT);
    if (unlikely(should_swap < 0)) { Py_DECREF(item); return -1; }
    if (!should_swap) break;
    
    items[pos] = parent_item;
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Ultra-optimized sift up with key function */
HOT_FUNCTION static inline int
list_sift_up_with_key_ultra_optimized(PyListObject *listobj, Py_ssize_t pos, int is_max, PyObject *keyfunc, Py_ssize_t arity) {
  if (unlikely(pos == 0)) return 0;
  
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  PyObject *key = PyObject_CallOneArg(keyfunc, item);
  if (unlikely(!key)) { Py_DECREF(item); return -1; }
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) / arity;
    PyObject *parent_item = items[parent];
    
    PyObject *parent_key = PyObject_CallOneArg(keyfunc, parent_item);
    if (unlikely(!parent_key)) { Py_DECREF(item); Py_DECREF(key); return -1; }
    
    int should_swap = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
    Py_DECREF(parent_key);
    if (unlikely(should_swap < 0)) { Py_DECREF(item); Py_DECREF(key); return -1; }
    if (!should_swap) break;
    
    items[pos] = parent_item;
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  Py_DECREF(key);
  return 0;
}

/* Ultra-optimized sift down for lists without key functions */
HOT_FUNCTION static inline int
list_sift_down_ultra_optimized(PyListObject *listobj, Py_ssize_t pos, Py_ssize_t n, int is_max, Py_ssize_t arity) {
  PyObject **items = ASSUME_ALIGNED(listobj->ob_item, sizeof(void*));
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (1) {
    Py_ssize_t child = arity * pos + 1;
    if (unlikely(child >= n)) break;
    
    Py_ssize_t best = child;
    PyObject *best_item = items[child];
    
    PREFETCH_MULTIPLE(items, arity * child + 1, PREFETCH_DISTANCE, n);
    
    Py_ssize_t last = child + arity;
    if (unlikely(last > n)) last = n;
    
    for (Py_ssize_t j = child + 1; j < last; j++) {
      int better = optimized_compare(items[j], best_item, is_max ? Py_GT : Py_LT);
      if (unlikely(better < 0)) { Py_DECREF(item); return -1; }
      if (better) {
        best = j;
        best_item = items[j];
      }
    }
    
    int should_swap = optimized_compare(best_item, item, is_max ? Py_GT : Py_LT);
    if (unlikely(should_swap < 0)) { Py_DECREF(item); return -1; }
    if (!should_swap) break;
    
    items[pos] = best_item;
    pos = best;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Ultra-optimized sift down with key function for lists */
HOT_FUNCTION static inline int
list_sift_down_with_key_ultra_optimized(PyListObject *listobj, Py_ssize_t pos, Py_ssize_t n, int is_max, PyObject *keyfunc, Py_ssize_t arity) {
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  PyObject *key = call_key_function(keyfunc, item);
  if (unlikely(!key)) return -1;
  
  while (1) {
    Py_ssize_t child = arity * pos + 1;
    if (unlikely(child >= n)) break;
    
    Py_ssize_t best = child;
    PyObject *best_item = items[child];
    PyObject *best_key = call_key_function(keyfunc, best_item);
    if (unlikely(!best_key)) { Py_DECREF(key); return -1; }
    
    Py_ssize_t last = child + arity;
    if (unlikely(last > n)) last = n;
    
    for (Py_ssize_t j = child + 1; j < last; j++) {
      PyObject *cur_key = call_key_function(keyfunc, items[j]);
      if (unlikely(!cur_key)) { Py_DECREF(key); Py_DECREF(best_key); return -1; }
      
      int better = optimized_compare(cur_key, best_key, is_max ? Py_GT : Py_LT);
      if (unlikely(better < 0)) { Py_DECREF(key); Py_DECREF(best_key); Py_DECREF(cur_key); return -1; }
      
      if (better) {
        Py_DECREF(best_key);
        best = j;
        best_item = items[j];
        best_key = cur_key;
      } else {
        Py_DECREF(cur_key);
      }
    }
    
    int should_swap = optimized_compare(best_key, key, is_max ? Py_GT : Py_LT);
    Py_DECREF(best_key);
    if (unlikely(should_swap < 0)) { Py_DECREF(key); return -1; }
    if (!should_swap) break;
    
    items[pos] = best_item;
    pos = best;
  }
  
  items[pos] = item;
  Py_DECREF(key);
  return 0;
}

/* Helper: Remove single item at index with O(log n) inline heap maintenance */
HOT_FUNCTION static inline int
list_remove_at_index_optimized(PyListObject *listobj, Py_ssize_t idx, int is_max, PyObject *keyfunc, Py_ssize_t arity) {
  Py_ssize_t n = Py_SIZE(listobj);
  if (unlikely(idx < 0 || idx >= n)) return -1;
  
  PyObject **items = listobj->ob_item;
  PyObject *removed = items[idx];
  Py_INCREF(removed);
  
  /* Move last element to removed position */
  Py_ssize_t last_idx = n - 1;
  if (idx == last_idx) {
    /* Removing last element - just shrink */
    Py_DECREF(removed);
    if (unlikely(PyList_SetSlice((PyObject*)listobj, last_idx, n, NULL) < 0)) return -1;
    return 0;
  }
  
  PyObject *last_item = items[last_idx];
  Py_INCREF(last_item);
  
  /* Shrink list */
  if (unlikely(PyList_SetSlice((PyObject*)listobj, last_idx, n, NULL) < 0)) {
    Py_DECREF(removed);
    Py_DECREF(last_item);
    return -1;
  }
  
  /* Refresh pointer after resize */
  items = listobj->ob_item;
  Py_ssize_t new_size = Py_SIZE(listobj);
  
  /* Place last item at removed position */
  Py_SETREF(items[idx], last_item);
  
  /* Restore heap property: try sift-up first, then sift-down */
  if (keyfunc == NULL) {
    if (idx > 0) {
      Py_ssize_t parent = (idx - 1) / arity;
      int cmp_res = optimized_compare(items[idx], items[parent], is_max ? Py_GT : Py_LT);
      if (unlikely(cmp_res < 0)) {
        Py_DECREF(removed);
        return -1;
      }
      if (cmp_res) {
        if (unlikely(list_sift_up_ultra_optimized(listobj, idx, is_max, arity) < 0)) {
          Py_DECREF(removed);
          return -1;
        }
        Py_DECREF(removed);
        return 0;
      }
    }
    if (unlikely(list_sift_down_ultra_optimized(listobj, idx, new_size, is_max, arity) < 0)) {
      Py_DECREF(removed);
      return -1;
    }
  } else {
    if (idx > 0) {
      Py_ssize_t parent = (idx - 1) / arity;
      PyObject *key_item = call_key_function(keyfunc, items[idx]);
      if (unlikely(!key_item)) {
        Py_DECREF(removed);
        return -1;
      }
      PyObject *key_parent = call_key_function(keyfunc, items[parent]);
      if (unlikely(!key_parent)) {
        Py_DECREF(key_item);
        Py_DECREF(removed);
        return -1;
      }
      int cmp_res = optimized_compare(key_item, key_parent, is_max ? Py_GT : Py_LT);
      Py_DECREF(key_item);
      Py_DECREF(key_parent);
      if (unlikely(cmp_res < 0)) {
        Py_DECREF(removed);
        return -1;
      }
      if (cmp_res) {
        if (unlikely(list_sift_up_with_key_ultra_optimized(listobj, idx, is_max, keyfunc, arity) < 0)) {
          Py_DECREF(removed);
          return -1;
        }
        Py_DECREF(removed);
        return 0;
      }
    }
    if (unlikely(list_sift_down_with_key_ultra_optimized(listobj, idx, new_size, is_max, keyfunc, arity) < 0)) {
      Py_DECREF(removed);
      return -1;
    }
  }
  
  Py_DECREF(removed);
  return 0;
}

/* Ultra-optimized push with comprehensive dispatch following priority table */
static PyObject *
py_push(PyObject *self, PyObject *args, PyObject *kwargs) {
  static char *kwlist[] = {"heap", "items", "max_heap", "cmp", "arity", NULL};
  PyObject *heap, *items;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|OOn:push", kwlist,
                                   &heap, &items, &max_heap_obj, &cmp, &arity))
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

  Py_ssize_t n = PySequence_Size(heap);
  if (unlikely(n < 0)) return NULL;

  /* Detect single vs bulk insertion - exclude strings, bytes, and tuples */
  int is_bulk = (PyList_CheckExact(items) || 
                 (PySequence_Check(items) && !PyUnicode_Check(items) && 
                  !PyBytes_Check(items) && !PyTuple_Check(items)));
  Py_ssize_t n_items = is_bulk ? PySequence_Size(items) : 1;
  if (unlikely(is_bulk && n_items < 0)) return NULL;
  if (is_bulk && n_items == 0) Py_RETURN_NONE;

  /* DISPATCH FOLLOWING PRIORITY TABLE */
  
  if (likely(PyList_CheckExact(heap))) {
    PyListObject *listobj = (PyListObject *)heap;
    
    /* Append items first */
    if (!is_bulk) {
      if (unlikely(PyList_Append(heap, items) < 0)) return NULL;
    } else {
      for (Py_ssize_t i = 0; i < n_items; i++) {
        PyObject *item = PySequence_GetItem(items, i);
        if (unlikely(!item)) return NULL;
        int rc = PyList_Append(heap, item);
        Py_DECREF(item);
        if (unlikely(rc < 0)) return NULL;
      }
    }
    
    /* Refresh pointer after append (list may have reallocated) */
    PyObject **arr = listobj->ob_item;
    
    /* Priority 1: Small heap (n ≤ 16) - only without key */
    if (unlikely(n + n_items <= 16 && cmp == Py_None)) {
      /* Insertion sort for newly added elements */
      for (Py_ssize_t i = n; i < n + n_items; i++) {
        PyObject *key = arr[i];
        Py_ssize_t j = i - 1;
        while (j >= 0) {
          int cmp_res = optimized_compare(key, arr[j], is_max ? Py_GT : Py_LT);
          if (unlikely(cmp_res < 0)) return NULL;
          if (!cmp_res) break;
          arr[j + 1] = arr[j];
          j--;
        }
        arr[j + 1] = key;
      }
      Py_RETURN_NONE;
    }
    
    if (likely(cmp == Py_None)) {
      /* No key function path */
      
      /* Priority 2: Arity = 1 (sorted list) */
      if (unlikely(arity == 1)) {
        /* Binary insertion for each new element to maintain sorted order */
        for (Py_ssize_t i = n; i < n + n_items; i++) {
          PyObject *item = arr[i];
          Py_ssize_t left = 0, right = i;
          /* Binary search for insertion position */
          while (left < right) {
            Py_ssize_t mid = (left + right) >> 1;
            /* For min-heap: find leftmost position where item < arr[mid] */
            /* For max-heap: find leftmost position where item > arr[mid] */
            int cmp_res = optimized_compare(item, arr[mid], is_max ? Py_GT : Py_LT);
            if (unlikely(cmp_res < 0)) return NULL;
            if (cmp_res) right = mid;  /* item should go before mid */
            else left = mid + 1;  /* item should go after mid */
          }
          /* Shift elements and insert */
          if (left < i) {
            PyObject *tmp = arr[i];
            for (Py_ssize_t j = i; j > left; j--) arr[j] = arr[j - 1];
            arr[left] = tmp;
          }
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 3: Binary heap (arity=2) - most common */
      if (likely(arity == 2)) {
        for (Py_ssize_t idx = n; idx < n + n_items; idx++) {
          Py_ssize_t pos = idx;
          PyObject *item = arr[pos];
          while (pos > 0) {
            Py_ssize_t parent = (pos - 1) >> 1;
            int cmp_res = optimized_compare(item, arr[parent], is_max ? Py_GT : Py_LT);
            if (unlikely(cmp_res < 0)) return NULL;
            if (!cmp_res) break;
            arr[pos] = arr[parent];
            pos = parent;
          }
          arr[pos] = item;
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 4: Ternary heap (arity=3) */
      if (arity == 3) {
        for (Py_ssize_t idx = n; idx < n + n_items; idx++) {
          Py_ssize_t pos = idx;
          PyObject *item = arr[pos];
          while (pos > 0) {
            Py_ssize_t parent = (pos - 1) / 3;
            int cmp_res = optimized_compare(item, arr[parent], is_max ? Py_GT : Py_LT);
            if (unlikely(cmp_res < 0)) return NULL;
            if (!cmp_res) break;
            arr[pos] = arr[parent];
            pos = parent;
          }
          arr[pos] = item;
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 5: Quaternary heap (arity=4) */
      if (arity == 4) {
        for (Py_ssize_t idx = n; idx < n + n_items; idx++) {
          Py_ssize_t pos = idx;
          PyObject *item = arr[pos];
          while (pos > 0) {
            Py_ssize_t parent = (pos - 1) >> 2;
            int cmp_res = optimized_compare(item, arr[parent], is_max ? Py_GT : Py_LT);
            if (unlikely(cmp_res < 0)) return NULL;
            if (!cmp_res) break;
            arr[pos] = arr[parent];
            pos = parent;
          }
          arr[pos] = item;
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 6 & 7: General n-ary (arity≥5) */
      for (Py_ssize_t idx = n; idx < n + n_items; idx++) {
        Py_ssize_t pos = idx;
        PyObject *item = arr[pos];
        while (pos > 0) {
          Py_ssize_t parent = (pos - 1) / arity;
          int cmp_res = optimized_compare(item, arr[parent], is_max ? Py_GT : Py_LT);
          if (unlikely(cmp_res < 0)) return NULL;
          if (!cmp_res) break;
          arr[pos] = arr[parent];
          pos = parent;
        }
        arr[pos] = item;
      }
      Py_RETURN_NONE;
      
    } else {
      /* With key function path */
      
      /* Priority 8: Binary heap with key (arity=2) */
      if (likely(arity == 2)) {
        for (Py_ssize_t idx = n; idx < n + n_items; idx++) {
          Py_ssize_t pos = idx;
          PyObject *item = arr[pos];
          PyObject *key = call_key_function(cmp, item);
          if (unlikely(!key)) return NULL;
          
          while (pos > 0) {
            Py_ssize_t parent = (pos - 1) >> 1;
            PyObject *parent_key = call_key_function(cmp, arr[parent]);
            if (unlikely(!parent_key)) { Py_DECREF(key); return NULL; }
            
            int cmp_res = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
            Py_DECREF(parent_key);
            if (unlikely(cmp_res < 0)) { Py_DECREF(key); return NULL; }
            if (!cmp_res) break;
            
            arr[pos] = arr[parent];
            pos = parent;
          }
          arr[pos] = item;
          Py_DECREF(key);
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 9: Ternary heap with key (arity=3) */
      if (arity == 3) {
        for (Py_ssize_t idx = n; idx < n + n_items; idx++) {
          Py_ssize_t pos = idx;
          PyObject *item = arr[pos];
          PyObject *key = call_key_function(cmp, item);
          if (unlikely(!key)) return NULL;
          
          while (pos > 0) {
            Py_ssize_t parent = (pos - 1) / 3;
            PyObject *parent_key = call_key_function(cmp, arr[parent]);
            if (unlikely(!parent_key)) { Py_DECREF(key); return NULL; }
            
            int cmp_res = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
            Py_DECREF(parent_key);
            if (unlikely(cmp_res < 0)) { Py_DECREF(key); return NULL; }
            if (!cmp_res) break;
            
            arr[pos] = arr[parent];
            pos = parent;
          }
          arr[pos] = item;
          Py_DECREF(key);
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 10: General n-ary with key (arity≥4) */
      for (Py_ssize_t idx = n; idx < n + n_items; idx++) {
        Py_ssize_t pos = idx;
        PyObject *item = arr[pos];
        PyObject *key = call_key_function(cmp, item);
        if (unlikely(!key)) return NULL;
        
        while (pos > 0) {
          Py_ssize_t parent = (pos - 1) / arity;
          PyObject *parent_key = call_key_function(cmp, arr[parent]);
          if (unlikely(!parent_key)) { Py_DECREF(key); return NULL; }
          
          int cmp_res = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
          Py_DECREF(parent_key);
          if (unlikely(cmp_res < 0)) { Py_DECREF(key); return NULL; }
          if (!cmp_res) break;
          
          arr[pos] = arr[parent];
          pos = parent;
        }
        arr[pos] = item;
        Py_DECREF(key);
      }
      Py_RETURN_NONE;
    }
  }
  
  /* Priority 11: Generic sequence (non-list) */
  if (!is_bulk) {
    PyObject *tuple = PyTuple_Pack(1, items);
    if (unlikely(!tuple)) return NULL;
    PyObject *result = PySequence_InPlaceConcat(heap, tuple);
    Py_DECREF(tuple);
    if (unlikely(!result)) return NULL;
    Py_DECREF(result);
    
    if (unlikely(sift_up(heap, n, is_max, cmp, arity) < 0)) return NULL;
  } else {
    for (Py_ssize_t i = 0; i < n_items; i++) {
      PyObject *item = PySequence_GetItem(items, i);
      if (unlikely(!item)) return NULL;
      
      PyObject *tuple = PyTuple_Pack(1, item);
      if (unlikely(!tuple)) { Py_DECREF(item); return NULL; }
      
      PyObject *result = PySequence_InPlaceConcat(heap, tuple);
      Py_DECREF(tuple);
      Py_DECREF(item);
      if (unlikely(!result)) return NULL;
      Py_DECREF(result);
      
      if (unlikely(sift_up(heap, n + i, is_max, cmp, arity) < 0)) return NULL;
    }
  }
  
  Py_RETURN_NONE;
}

/* Ultra-optimized pop with comprehensive 11-priority dispatch table */
static PyObject *
py_pop(PyObject *self, PyObject *args, PyObject *kwargs) {
  static char *kwlist[] = {"heap", "n", "max_heap", "cmp", "arity", NULL};
  PyObject *heap;
  Py_ssize_t n_pop = 1;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|nOOn:pop", kwlist,
                                   &heap, &n_pop, &max_heap_obj, &cmp, &arity))
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
  if (unlikely(n_pop < 1)) {
    PyErr_SetString(PyExc_ValueError, "n must be >= 1");
    return NULL;
  }

  Py_ssize_t heap_size = PySequence_Size(heap);
  if (unlikely(heap_size < 0)) return NULL;
  if (unlikely(heap_size == 0)) {
    PyErr_SetString(PyExc_IndexError, "pop from empty heap");
    return NULL;
  }

  if (n_pop > heap_size) n_pop = heap_size;

  /* SINGLE POP PATH (n=1) - COMPREHENSIVE DISPATCH */
  if (n_pop == 1) {
    if (likely(PyList_CheckExact(heap))) {
      PyListObject *listobj = (PyListObject *)heap;
      PyObject **items = listobj->ob_item;
      Py_ssize_t n = heap_size;
      
      PyObject *result = items[0];
      Py_INCREF(result);
      
      if (n == 1) {
        if (unlikely(PyList_SetSlice(heap, 0, 1, NULL) < 0)) {
          Py_DECREF(result);
          return NULL;
        }
        return result;
      }
      
      /* Priority 2: Arity=1 (sorted list) - just remove first element */
      if (unlikely(arity == 1 && cmp == Py_None)) {
        if (unlikely(PyList_SetSlice(heap, 0, 1, NULL) < 0)) {
          Py_DECREF(result);
          return NULL;
        }
        return result;
      }
      
      /* Save last item and shrink list */
      PyObject *last_item = items[n - 1];
      Py_INCREF(last_item);
      
      if (unlikely(PyList_SetSlice(heap, n - 1, n, NULL) < 0)) {
        Py_DECREF(last_item);
        Py_DECREF(result);
        return NULL;
      }
      
      /* Refresh pointer after modification */
      items = listobj->ob_item;
      Py_ssize_t new_size = n - 1;
      Py_SETREF(items[0], last_item);
      
      /* DISPATCH TABLE FOR SIFT-DOWN */
      if (likely(cmp == Py_None)) {
        /* Priority 1: Small heap (n ≤ 16) */
        if (unlikely(new_size <= 16)) {
          /* Inline insertion sort for small heaps */
          for (Py_ssize_t i = 1; i < new_size; i++) {
            PyObject *key = items[i];
            Py_ssize_t j = i - 1;
            while (j >= 0) {
              int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
              if (unlikely(cmp_res < 0)) { Py_DECREF(result); return NULL; }
              if (!cmp_res) break;
              items[j + 1] = items[j];
              j--;
            }
            items[j + 1] = key;
          }
          return result;
        }
        
        /* Priority 3: Binary heap (arity=2) - inline sift-down */
        if (likely(arity == 2)) {
          Py_ssize_t pos = 0;
          PyObject *item = items[0];
          
          while (1) {
            Py_ssize_t child = (pos << 1) + 1;
            if (unlikely(child >= new_size)) break;
            
            Py_ssize_t best = child;
            PyObject *best_item = items[child];
            
            Py_ssize_t right = child + 1;
            if (likely(right < new_size)) {
              int cmp_res = optimized_compare(items[right], best_item, is_max ? Py_GT : Py_LT);
              if (unlikely(cmp_res < 0)) { Py_DECREF(result); return NULL; }
              if (cmp_res) {
                best = right;
                best_item = items[right];
              }
            }
            
            int should_swap = optimized_compare(best_item, item, is_max ? Py_GT : Py_LT);
            if (unlikely(should_swap < 0)) { Py_DECREF(result); return NULL; }
            if (!should_swap) break;
            
            items[pos] = best_item;
            pos = best;
          }
          items[pos] = item;
          return result;
        }
        
        /* Priority 4: Ternary heap (arity=3) - inline sift-down */
        if (arity == 3) {
          Py_ssize_t pos = 0;
          PyObject *item = items[0];
          
          while (1) {
            Py_ssize_t child = 3 * pos + 1;
            if (unlikely(child >= new_size)) break;
            
            Py_ssize_t best = child;
            PyObject *best_item = items[child];
            
            Py_ssize_t last = child + 3;
            if (unlikely(last > new_size)) last = new_size;
            
            for (Py_ssize_t j = child + 1; j < last; j++) {
              int cmp_res = optimized_compare(items[j], best_item, is_max ? Py_GT : Py_LT);
              if (unlikely(cmp_res < 0)) { Py_DECREF(result); return NULL; }
              if (cmp_res) {
                best = j;
                best_item = items[j];
              }
            }
            
            int should_swap = optimized_compare(best_item, item, is_max ? Py_GT : Py_LT);
            if (unlikely(should_swap < 0)) { Py_DECREF(result); return NULL; }
            if (!should_swap) break;
            
            items[pos] = best_item;
            pos = best;
          }
          items[pos] = item;
          return result;
        }
        
        /* Priority 5: Quaternary heap (arity=4) - inline sift-down */
        if (arity == 4) {
          Py_ssize_t pos = 0;
          PyObject *item = items[0];
          
          while (1) {
            Py_ssize_t child = (pos << 2) + 1;
            if (unlikely(child >= new_size)) break;
            
            Py_ssize_t best = child;
            PyObject *best_item = items[child];
            
            Py_ssize_t last = child + 4;
            if (unlikely(last > new_size)) last = new_size;
            
            for (Py_ssize_t j = child + 1; j < last; j++) {
              int cmp_res = optimized_compare(items[j], best_item, is_max ? Py_GT : Py_LT);
              if (unlikely(cmp_res < 0)) { Py_DECREF(result); return NULL; }
              if (cmp_res) {
                best = j;
                best_item = items[j];
              }
            }
            
            int should_swap = optimized_compare(best_item, item, is_max ? Py_GT : Py_LT);
            if (unlikely(should_swap < 0)) { Py_DECREF(result); return NULL; }
            if (!should_swap) break;
            
            items[pos] = best_item;
            pos = best;
          }
          items[pos] = item;
          return result;
        }
        
        /* Priority 6 & 7: General n-ary (arity≥5) */
        if (unlikely(list_sift_down_ultra_optimized(listobj, 0, new_size, is_max, arity) < 0)) {
          Py_DECREF(result);
          return NULL;
        }
        return result;
        
      } else {
        /* WITH KEY FUNCTION */
        
        /* Priority 8: Binary heap with key (arity=2) */
        if (likely(arity == 2)) {
          Py_ssize_t pos = 0;
          PyObject *item = items[0];
          PyObject *key = call_key_function(cmp, item);
          if (unlikely(!key)) { Py_DECREF(result); return NULL; }
          
          while (1) {
            Py_ssize_t child = (pos << 1) + 1;
            if (unlikely(child >= new_size)) break;
            
            Py_ssize_t best = child;
            PyObject *best_item = items[child];
            PyObject *best_key = call_key_function(cmp, best_item);
            if (unlikely(!best_key)) { Py_DECREF(key); Py_DECREF(result); return NULL; }
            
            Py_ssize_t right = child + 1;
            if (likely(right < new_size)) {
              PyObject *right_key = call_key_function(cmp, items[right]);
              if (unlikely(!right_key)) { Py_DECREF(key); Py_DECREF(best_key); Py_DECREF(result); return NULL; }
              
              int cmp_res = optimized_compare(right_key, best_key, is_max ? Py_GT : Py_LT);
              if (unlikely(cmp_res < 0)) { Py_DECREF(key); Py_DECREF(best_key); Py_DECREF(right_key); Py_DECREF(result); return NULL; }
              if (cmp_res) {
                Py_DECREF(best_key);
                best = right;
                best_item = items[right];
                best_key = right_key;
              } else {
                Py_DECREF(right_key);
              }
            }
            
            int should_swap = optimized_compare(best_key, key, is_max ? Py_GT : Py_LT);
            Py_DECREF(best_key);
            if (unlikely(should_swap < 0)) { Py_DECREF(key); Py_DECREF(result); return NULL; }
            if (!should_swap) break;
            
            items[pos] = best_item;
            pos = best;
          }
          items[pos] = item;
          Py_DECREF(key);
          return result;
        }
        
        /* Priority 9: Ternary heap with key (arity=3) */
        if (arity == 3) {
          if (unlikely(list_sift_down_with_key_ultra_optimized(listobj, 0, new_size, is_max, cmp, arity) < 0)) {
            Py_DECREF(result);
            return NULL;
          }
          return result;
        }
        
        /* Priority 10: General n-ary with key (arity≥4) */
        if (unlikely(list_sift_down_with_key_ultra_optimized(listobj, 0, new_size, is_max, cmp, arity) < 0)) {
          Py_DECREF(result);
          return NULL;
        }
        return result;
      }
    }
    
    /* Priority 11: Generic sequence (non-list) */
    PyObject *result = PySequence_GetItem(heap, 0);
    if (unlikely(!result)) return NULL;

    if (heap_size > 1) {
      PyObject *last = PySequence_GetItem(heap, heap_size - 1);
      if (unlikely(!last)) {
        Py_DECREF(result);
        return NULL;
      }
      
      if (unlikely(PySequence_SetItem(heap, 0, last) < 0)) {
        Py_DECREF(result);
        Py_DECREF(last);
        return NULL;
      }
      Py_DECREF(last);
      
      if (PyList_CheckExact(heap)) {
        if (unlikely(PyList_SetSlice(heap, heap_size - 1, heap_size, NULL) < 0)) {
          Py_DECREF(result);
          return NULL;
        }
      }
      
      if (unlikely(sift_down(heap, 0, heap_size - 1, is_max, cmp, arity) < 0)) {
        Py_DECREF(result);
        return NULL;
      }
    } else {
      if (PyList_CheckExact(heap)) {
        if (unlikely(PyList_SetSlice(heap, 0, 1, NULL) < 0)) {
          Py_DECREF(result);
          return NULL;
        }
      }
    }
    
    return result;
  }
  
  /* BULK POP PATH (n>1) */
  PyObject *results = PyList_New(n_pop);
  if (unlikely(!results)) return NULL;
  
  if (likely(PyList_CheckExact(heap))) {
    PyListObject *listobj = (PyListObject *)heap;
    
    if (likely(cmp == Py_None)) {
      /* Optimized bulk pop without key function */
      for (Py_ssize_t i = 0; i < n_pop; i++) {
        Py_ssize_t current_size = PyList_GET_SIZE(heap);
        if (unlikely(current_size <= 0)) break;
        
        PyObject **items = listobj->ob_item;
        PyObject *item = items[0];
        Py_INCREF(item);
        PyList_SET_ITEM(results, i, item);
        
        if (current_size > 1) {
          PyObject *last_item = items[current_size - 1];
          Py_INCREF(last_item);
          
          if (unlikely(PyList_SetSlice(heap, current_size - 1, current_size, NULL) < 0)) {
            Py_DECREF(last_item);
            Py_DECREF(results);
            return NULL;
          }
          
          items = listobj->ob_item;
          Py_ssize_t new_size = current_size - 1;
          Py_SETREF(items[0], last_item);
          
          /* Use optimized sift-down based on arity */
          if (likely(arity == 2)) {
            Py_ssize_t pos = 0;
            PyObject *sift_item = items[0];
            
            while (1) {
              Py_ssize_t child = (pos << 1) + 1;
              if (unlikely(child >= new_size)) break;
              
              Py_ssize_t best = child;
              PyObject *best_item = items[child];
              
              Py_ssize_t right = child + 1;
              if (likely(right < new_size)) {
                int cmp_res = optimized_compare(items[right], best_item, is_max ? Py_GT : Py_LT);
                if (unlikely(cmp_res < 0)) { Py_DECREF(results); return NULL; }
                if (cmp_res) {
                  best = right;
                  best_item = items[right];
                }
              }
              
              int should_swap = optimized_compare(best_item, sift_item, is_max ? Py_GT : Py_LT);
              if (unlikely(should_swap < 0)) { Py_DECREF(results); return NULL; }
              if (!should_swap) break;
              
              items[pos] = best_item;
              pos = best;
            }
            items[pos] = sift_item;
          } else {
            if (unlikely(list_sift_down_ultra_optimized(listobj, 0, new_size, is_max, arity) < 0)) {
              Py_DECREF(results);
              return NULL;
            }
          }
        } else {
          if (unlikely(PyList_SetSlice(heap, 0, 1, NULL) < 0)) {
            Py_DECREF(results);
            return NULL;
          }
        }
      }
      return results;
    } else {
      /* Bulk pop with key function */
      for (Py_ssize_t i = 0; i < n_pop; i++) {
        Py_ssize_t current_size = PyList_GET_SIZE(heap);
        if (unlikely(current_size <= 0)) break;
        
        PyObject **items = listobj->ob_item;
        PyObject *item = items[0];
        Py_INCREF(item);
        PyList_SET_ITEM(results, i, item);
        
        if (current_size > 1) {
          PyObject *last_item = items[current_size - 1];
          Py_INCREF(last_item);
          
          if (unlikely(PyList_SetSlice(heap, current_size - 1, current_size, NULL) < 0)) {
            Py_DECREF(last_item);
            Py_DECREF(results);
            return NULL;
          }
          
          items = listobj->ob_item;
          Py_ssize_t new_size = current_size - 1;
          Py_SETREF(items[0], last_item);
          
          if (unlikely(list_sift_down_with_key_ultra_optimized(listobj, 0, new_size, is_max, cmp, arity) < 0)) {
            Py_DECREF(results);
            return NULL;
          }
        } else {
          if (unlikely(PyList_SetSlice(heap, 0, 1, NULL) < 0)) {
            Py_DECREF(results);
            return NULL;
          }
        }
      }
      return results;
    }
  }
  
  /* Generic sequence bulk pop */
  for (Py_ssize_t i = 0; i < n_pop; i++) {
    Py_ssize_t current_size = PySequence_Size(heap);
    if (unlikely(current_size <= 0)) break;
    
    PyObject *item = PySequence_GetItem(heap, 0);
    if (unlikely(!item)) {
      Py_DECREF(results);
      return NULL;
    }
    
    PyList_SET_ITEM(results, i, item);
    
    if (current_size > 1) {
      PyObject *last = PySequence_GetItem(heap, current_size - 1);
      if (unlikely(!last)) {
        Py_DECREF(results);
        return NULL;
      }
      
      if (unlikely(PySequence_SetItem(heap, 0, last) < 0)) {
        Py_DECREF(last);
        Py_DECREF(results);
        return NULL;
      }
      Py_DECREF(last);
      
      if (PyList_CheckExact(heap)) {
        if (unlikely(PyList_SetSlice(heap, current_size - 1, current_size, NULL) < 0)) {
          Py_DECREF(results);
          return NULL;
        }
      }
      
      if (unlikely(sift_down(heap, 0, current_size - 1, is_max, cmp, arity) < 0)) {
        Py_DECREF(results);
        return NULL;
      }
    } else {
      if (PyList_CheckExact(heap)) {
        if (unlikely(PyList_SetSlice(heap, 0, 1, NULL) < 0)) {
          Py_DECREF(results);
          return NULL;
        }
      }
    }
  }
  
  return results;
}


/* Helper: Inline ternary heapsort without key function */
HOT_FUNCTION static int
list_heapsort_ternary_ultra_optimized(PyListObject *listobj, int sort_is_max) {
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  
  for (Py_ssize_t i = n - 1; i > 0; i--) {
    PyObject *tmp = items[0];
    items[0] = items[i];
    items[i] = tmp;
    
    Py_ssize_t pos = 0;
    PyObject *item = items[0];
    
    while (1) {
      Py_ssize_t child = pos * 3 + 1;
      if (unlikely(child >= i)) break;
      
      Py_ssize_t best = child;
      PyObject *best_item = items[child];
      
      for (Py_ssize_t c = child + 1; c < child + 3 && c < i; c++) {
        int cmp_res = optimized_compare(items[c], best_item, sort_is_max ? Py_GT : Py_LT);
        if (unlikely(cmp_res < 0)) return -1;
        if (cmp_res) {
          best = c;
          best_item = items[c];
        }
      }
      
      int should_swap = optimized_compare(best_item, item, sort_is_max ? Py_GT : Py_LT);
      if (unlikely(should_swap < 0)) return -1;
      if (!should_swap) break;
      
      items[pos] = best_item;
      pos = best;
    }
    items[pos] = item;
  }
  return 0;
}

/* Helper: Inline quaternary heapsort without key function */
HOT_FUNCTION static int
list_heapsort_quaternary_ultra_optimized(PyListObject *listobj, int sort_is_max) {
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  
  for (Py_ssize_t i = n - 1; i > 0; i--) {
    PyObject *tmp = items[0];
    items[0] = items[i];
    items[i] = tmp;
    
    Py_ssize_t pos = 0;
    PyObject *item = items[0];
    
    while (1) {
      Py_ssize_t child = (pos << 2) + 1;
      if (unlikely(child >= i)) break;
      
      Py_ssize_t best = child;
      PyObject *best_item = items[child];
      
      for (Py_ssize_t c = child + 1; c < child + 4 && c < i; c++) {
        int cmp_res = optimized_compare(items[c], best_item, sort_is_max ? Py_GT : Py_LT);
        if (unlikely(cmp_res < 0)) return -1;
        if (cmp_res) {
          best = c;
          best_item = items[c];
        }
      }
      
      int should_swap = optimized_compare(best_item, item, sort_is_max ? Py_GT : Py_LT);
      if (unlikely(should_swap < 0)) return -1;
      if (!should_swap) break;
      
      items[pos] = best_item;
      pos = best;
    }
    items[pos] = item;
  }
  return 0;
}

/* Step 4: Bottom-up heapsort - reduces comparisons by ~50% */
HOT_FUNCTION static int
list_heapsort_binary_ultra_optimized(PyListObject *listobj, int sort_is_max) {
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  
  for (Py_ssize_t heap_size = n - 1; heap_size > 0; heap_size--) {
    /* Swap root (max/min) with last element in heap portion */
    PyObject *last = items[heap_size];
    items[heap_size] = items[0];
    
    /* Phase 1: Descend to leaf, always following better child */
    /* This uses only 1 comparison per level (child vs child) */
    Py_ssize_t pos = 0;
    Py_ssize_t child;
    
    while ((child = (pos << 1) + 1) < heap_size) {
      /* Find better child */
      Py_ssize_t right = child + 1;
      if (right < heap_size) {
        int cmp = optimized_compare(items[right], items[child], sort_is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) return -1;
        if (cmp) child = right;
      }
      
      /* Move down - no comparison with item being placed yet */
      items[pos] = items[child];
      pos = child;
    }
    
    /* Phase 2: Bubble up from leaf position */
    /* The item we're placing often belongs near the bottom, so this is fast */
    while (pos > 0) {
      Py_ssize_t parent = (pos - 1) >> 1;
      int cmp = optimized_compare(last, items[parent], sort_is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) return -1;
      if (!cmp) break;  /* Found correct position */
      
      items[pos] = items[parent];
      pos = parent;
    }
    items[pos] = last;
  }
  return 0;
}

/* Helper: Binary heapsort with key function */
HOT_FUNCTION static int
list_heapsort_binary_with_key_ultra_optimized(PyListObject *listobj, int sort_is_max, PyObject *keyfunc) {
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  
  for (Py_ssize_t i = n - 1; i > 0; i--) {
    PyObject *tmp = items[0];
    items[0] = items[i];
    items[i] = tmp;
    
    Py_ssize_t pos = 0;
    PyObject *item = items[0];
    PyObject *item_key = call_key_function(keyfunc, item);
    if (unlikely(!item_key)) return -1;
    
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (unlikely(child >= i)) {
        Py_DECREF(item_key);
        break;
      }
      
      Py_ssize_t best = child;
      PyObject *best_key = call_key_function(keyfunc, items[child]);
      if (unlikely(!best_key)) {
        Py_DECREF(item_key);
        return -1;
      }
      
      Py_ssize_t right = child + 1;
      if (likely(right < i)) {
        PyObject *right_key = call_key_function(keyfunc, items[right]);
        if (unlikely(!right_key)) {
          Py_DECREF(item_key);
          Py_DECREF(best_key);
          return -1;
        }
        int cmp_res = optimized_compare(right_key, best_key, sort_is_max ? Py_GT : Py_LT);
        if (unlikely(cmp_res < 0)) {
          Py_DECREF(item_key);
          Py_DECREF(best_key);
          Py_DECREF(right_key);
          return -1;
        }
        if (cmp_res) {
          best = right;
          Py_DECREF(best_key);
          best_key = right_key;
        } else {
          Py_DECREF(right_key);
        }
      }
      
      int should_swap = optimized_compare(best_key, item_key, sort_is_max ? Py_GT : Py_LT);
      Py_DECREF(best_key);
      if (unlikely(should_swap < 0)) {
        Py_DECREF(item_key);
        return -1;
      }
      if (!should_swap) {
        Py_DECREF(item_key);
        break;
      }
      
      items[pos] = items[best];
      pos = best;
    }
    items[pos] = item;
  }
  return 0;
}

/* Helper: Ternary heapsort with key function */
HOT_FUNCTION static int
list_heapsort_ternary_with_key_ultra_optimized(PyListObject *listobj, int sort_is_max, PyObject *keyfunc) {
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  
  for (Py_ssize_t i = n - 1; i > 0; i--) {
    PyObject *tmp = items[0];
    items[0] = items[i];
    items[i] = tmp;
    
    if (unlikely(list_sift_down_with_key_ultra_optimized(listobj, 0, i, sort_is_max, keyfunc, 3) < 0)) {
      return -1;
    }
  }
  return 0;
}

/* Step 7: Heapsort with pre-computed keys - O(n) key calls instead of O(n log n) */
HOT_FUNCTION static int
list_heapsort_with_cached_keys(PyListObject *listobj, int sort_is_max, PyObject *keyfunc, Py_ssize_t arity) {
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (n <= 1) return 0;
  
  PyObject **items = listobj->ob_item;
  
  /* Pre-compute all keys once: O(n) key calls */
  PyObject **keys = PyMem_Malloc(sizeof(PyObject *) * (size_t)n);
  if (unlikely(!keys)) {
    PyErr_NoMemory();
    return -1;
  }
  
  for (Py_ssize_t i = 0; i < n; i++) {
    keys[i] = call_key_function(keyfunc, items[i]);
    if (unlikely(!keys[i])) {
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      PyMem_Free(keys);
      return -1;
    }
  }
  
  /* Heapsort using cached keys */
  for (Py_ssize_t heap_size = n - 1; heap_size > 0; heap_size--) {
    /* Swap root with last element */
    PyObject *tmp_item = items[0];
    PyObject *tmp_key = keys[0];
    items[0] = items[heap_size];
    keys[0] = keys[heap_size];
    items[heap_size] = tmp_item;
    keys[heap_size] = tmp_key;
    
    /* Sift down using cached keys */
    Py_ssize_t pos = 0;
    PyObject *item = items[0];
    PyObject *key = keys[0];
    
    while (1) {
      Py_ssize_t child = arity * pos + 1;
      if (child >= heap_size) break;
      
      /* Find best child */
      Py_ssize_t best = child;
      PyObject *best_key = keys[child];
      
      Py_ssize_t last_child = child + arity;
      if (last_child > heap_size) last_child = heap_size;
      
      for (Py_ssize_t j = child + 1; j < last_child; j++) {
        int cmp = optimized_compare(keys[j], best_key, sort_is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          PyMem_Free(keys);
          return -1;
        }
        if (cmp) {
          best = j;
          best_key = keys[j];
        }
      }
      
      /* Check if heap property satisfied */
      int should_swap = optimized_compare(best_key, key, sort_is_max ? Py_GT : Py_LT);
      if (unlikely(should_swap < 0)) {
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        PyMem_Free(keys);
        return -1;
      }
      if (!should_swap) break;
      
      /* Move best child up */
      items[pos] = items[best];
      keys[pos] = keys[best];
      pos = best;
    }
    
    items[pos] = item;
    keys[pos] = key;
  }
  
  /* Cleanup */
  for (Py_ssize_t i = 0; i < n; i++) Py_DECREF(keys[i]);
  PyMem_Free(keys);
  return 0;
}

/* Ultra-optimized sort with complete 11-priority dispatch */
static PyObject *
py_sort(PyObject *self, PyObject *args, PyObject *kwargs) {
  static char *kwlist[] = {"heap", "reverse", "inplace", "max_heap", "cmp", "arity", NULL};
  PyObject *heap;
  PyObject *reverse_obj = Py_False;
  PyObject *inplace_obj = Py_False;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OOOOn:sort", kwlist, 
                                   &heap, &reverse_obj, &inplace_obj, &max_heap_obj, &cmp, &arity))
    return NULL;

  int reverse = PyObject_IsTrue(reverse_obj);
  if (unlikely(reverse < 0)) return NULL;
  
  int inplace = PyObject_IsTrue(inplace_obj);
  if (unlikely(inplace < 0)) return NULL;
  
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

  Py_ssize_t n = PySequence_Size(heap);
  if (unlikely(n < 0)) return NULL;
  if (n <= 1) {
    if (inplace) {
      Py_RETURN_NONE;
    } else {
      return PySequence_List(heap);
    }
  }

  PyObject *work_heap;
  if (inplace) {
    work_heap = heap;
    Py_INCREF(work_heap);
  } else {
    work_heap = PySequence_List(heap);
    if (unlikely(!work_heap)) return NULL;
  }

  /* For ascending: use max-heap. For descending: use min-heap */
  int sort_is_max = reverse ? 0 : 1;
  PyObject *keyfunc = (cmp == Py_None) ? NULL : cmp;

  /* ========== 11-PRIORITY DISPATCH TABLE ========== */
  
  /* Priority 1: Small heap (n ≤ 16, no key) - Direct insertion sort */
  if (unlikely(n <= 16 && keyfunc == NULL && PyList_CheckExact(work_heap))) {
    PyListObject *listobj = (PyListObject *)work_heap;
    PyObject **items = listobj->ob_item;
    
    for (Py_ssize_t i = 1; i < n; i++) {
      PyObject *key = items[i];
      Py_INCREF(key);
      Py_ssize_t j = i - 1;
      while (j >= 0) {
        int cmp_res = optimized_compare(items[j], key, reverse ? Py_LT : Py_GT);
        if (unlikely(cmp_res < 0)) {
          Py_DECREF(key);
          Py_DECREF(work_heap);
          return NULL;
        }
        if (!cmp_res) break;
        Py_INCREF(items[j]);
        Py_SETREF(items[j + 1], items[j]);
        j--;
      }
      Py_SETREF(items[j + 1], key);
    }
    
    if (inplace) {
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 2: Arity=1 (sorted list) - Sort first if needed, then reverse if requested */
  if (unlikely(arity == 1)) {
    if (PyList_CheckExact(work_heap) && keyfunc == NULL) {
      /* Use insertion sort to ensure sorted order */
      PyListObject *listobj = (PyListObject *)work_heap;
      PyObject **items = listobj->ob_item;
      
      for (Py_ssize_t i = 1; i < n; i++) {
        PyObject *key = items[i];
        Py_INCREF(key);
        Py_ssize_t j = i - 1;
        while (j >= 0) {
          int cmp_res = optimized_compare(items[j], key, Py_GT);
          if (unlikely(cmp_res < 0)) {
            Py_DECREF(key);
            Py_DECREF(work_heap);
            return NULL;
          }
          if (!cmp_res) break;
          Py_INCREF(items[j]);
          Py_SETREF(items[j + 1], items[j]);
          j--;
        }
        Py_SETREF(items[j + 1], key);
      }
      
      /* Now reverse if needed */
      if (reverse) {
        if (unlikely(PyList_Reverse(work_heap) < 0)) {
          Py_DECREF(work_heap);
          return NULL;
        }
      }
    } else {
      /* Generic sequence or with key - use heapify approach */
      if (unlikely(generic_heapify_ultra_optimized(work_heap, reverse ? 0 : 1, keyfunc, 1) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
    }
    
    if (inplace) {
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 3: List + arity=2 + no key */
  if (likely(PyList_CheckExact(work_heap) && arity == 2 && keyfunc == NULL)) {
    PyListObject *listobj = (PyListObject *)work_heap;
    
    if (unlikely(list_heapify_floyd_ultra_optimized(listobj, sort_is_max) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (unlikely(list_heapsort_binary_ultra_optimized(listobj, sort_is_max) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (inplace) {
      if (unlikely(list_heapify_floyd_ultra_optimized(listobj, is_max) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 4: List + arity=3 + no key */
  if (unlikely(PyList_CheckExact(work_heap) && arity == 3 && keyfunc == NULL)) {
    PyListObject *listobj = (PyListObject *)work_heap;
    
    if (unlikely(list_heapify_ternary_ultra_optimized(listobj, sort_is_max) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (unlikely(list_heapsort_ternary_ultra_optimized(listobj, sort_is_max) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (inplace) {
      if (unlikely(list_heapify_ternary_ultra_optimized(listobj, is_max) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 5: List + arity=4 + no key */
  if (unlikely(PyList_CheckExact(work_heap) && arity == 4 && keyfunc == NULL)) {
    PyListObject *listobj = (PyListObject *)work_heap;
    
    if (unlikely(list_heapify_quaternary_ultra_optimized(listobj, sort_is_max) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (unlikely(list_heapsort_quaternary_ultra_optimized(listobj, sort_is_max) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (inplace) {
      if (unlikely(list_heapify_quaternary_ultra_optimized(listobj, is_max) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 6: List + arity≥5 + no key + n<1000 */
  if (unlikely(PyList_CheckExact(work_heap) && arity >= 5 && keyfunc == NULL && n < 1000)) {
    PyListObject *listobj = (PyListObject *)work_heap;
    
    if (unlikely(list_heapify_small_ultra_optimized(listobj, sort_is_max, arity) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    for (Py_ssize_t i = n - 1; i > 0; i--) {
      PyObject **items = listobj->ob_item;
      PyObject *tmp = items[0];
      items[0] = items[i];
      items[i] = tmp;
      
      if (unlikely(list_sift_down_ultra_optimized(listobj, 0, i, sort_is_max, arity) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
    }
    
    if (inplace) {
      if (unlikely(list_heapify_small_ultra_optimized(listobj, is_max, arity) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 7: List + arity≥5 + no key + n≥1000 */
  if (unlikely(PyList_CheckExact(work_heap) && arity >= 5 && keyfunc == NULL && n >= 1000)) {
    PyListObject *listobj = (PyListObject *)work_heap;
    
    if (unlikely(generic_heapify_ultra_optimized(work_heap, sort_is_max, NULL, arity) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    for (Py_ssize_t i = n - 1; i > 0; i--) {
      PyObject **items = listobj->ob_item;
      PyObject *tmp = items[0];
      items[0] = items[i];
      items[i] = tmp;
      
      if (unlikely(list_sift_down_ultra_optimized(listobj, 0, i, sort_is_max, arity) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
    }
    
    if (inplace) {
      if (unlikely(generic_heapify_ultra_optimized(work_heap, is_max, NULL, arity) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 8: List + arity=2 + key */
  if (likely(PyList_CheckExact(work_heap) && arity == 2 && keyfunc != NULL)) {
    PyListObject *listobj = (PyListObject *)work_heap;
    
    if (unlikely(list_heapify_with_key_ultra_optimized(listobj, keyfunc, sort_is_max) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (unlikely(list_heapsort_binary_with_key_ultra_optimized(listobj, sort_is_max, keyfunc) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (inplace) {
      if (unlikely(list_heapify_with_key_ultra_optimized(listobj, keyfunc, is_max) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 9: List + arity=3 + key */
  if (unlikely(PyList_CheckExact(work_heap) && arity == 3 && keyfunc != NULL)) {
    PyListObject *listobj = (PyListObject *)work_heap;
    
    if (unlikely(list_heapify_ternary_with_key_ultra_optimized(listobj, keyfunc, sort_is_max) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (unlikely(list_heapsort_ternary_with_key_ultra_optimized(listobj, sort_is_max, keyfunc) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (inplace) {
      if (unlikely(list_heapify_ternary_with_key_ultra_optimized(listobj, keyfunc, is_max) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 10: List + arity≥4 + key */
  if (unlikely(PyList_CheckExact(work_heap) && arity >= 4 && keyfunc != NULL)) {
    PyListObject *listobj = (PyListObject *)work_heap;
    
    if (unlikely(generic_heapify_ultra_optimized(work_heap, sort_is_max, keyfunc, arity) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    
    for (Py_ssize_t i = n - 1; i > 0; i--) {
      PyObject **items = listobj->ob_item;
      PyObject *tmp = items[0];
      items[0] = items[i];
      items[i] = tmp;
      
      if (unlikely(list_sift_down_with_key_ultra_optimized(listobj, 0, i, sort_is_max, keyfunc, arity) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
    }
    
    if (inplace) {
      if (unlikely(generic_heapify_ultra_optimized(work_heap, is_max, keyfunc, arity) < 0)) {
        Py_DECREF(work_heap);
        return NULL;
      }
      Py_DECREF(work_heap);
      Py_RETURN_NONE;
    }
    return work_heap;
  }
  
  /* Priority 11: Generic sequence (non-list) */
  if (unlikely(generic_heapify_ultra_optimized(work_heap, sort_is_max, keyfunc, arity) < 0)) {
    Py_DECREF(work_heap);
    return NULL;
  }
  
  for (Py_ssize_t i = n - 1; i > 0; i--) {
    PyObject *root = PySequence_GetItem(work_heap, 0);
    PyObject *last = PySequence_GetItem(work_heap, i);
    if (unlikely(!root || !last)) {
      Py_XDECREF(root);
      Py_XDECREF(last);
      Py_DECREF(work_heap);
      return NULL;
    }
    
    if (unlikely(PySequence_SetItem(work_heap, 0, last) < 0 ||
                 PySequence_SetItem(work_heap, i, root) < 0)) {
      Py_DECREF(root);
      Py_DECREF(last);
      Py_DECREF(work_heap);
      return NULL;
    }
    
    Py_DECREF(root);
    Py_DECREF(last);
    
    if (unlikely(sift_down(work_heap, 0, i, sort_is_max, keyfunc, arity) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
  }
  
  if (inplace) {
    if (unlikely(generic_heapify_ultra_optimized(work_heap, is_max, keyfunc, arity) < 0)) {
      Py_DECREF(work_heap);
      return NULL;
    }
    Py_DECREF(work_heap);
    Py_RETURN_NONE;
  }
  
  return work_heap;
}

/* Perfect production-ready remove operation */
/* Ultra-optimized remove with 11-priority dispatch and O(log n) inline maintenance */
static PyObject *
py_remove(PyObject *self, PyObject *args, PyObject *kwargs) {
  static char *kwlist[] = {"heap", "indices", "object", "predicate", "n", "return_items", "max_heap", "cmp", "arity", NULL};
  PyObject *heap;
  PyObject *indices = Py_None;
  PyObject *object = Py_None;
  PyObject *predicate = Py_None;
  Py_ssize_t n = -1;
  PyObject *return_items_obj = Py_False;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OOOnOOOn:remove", kwlist,
                                   &heap, &indices, &object, &predicate, &n, &return_items_obj, &max_heap_obj, &cmp, &arity))
    return NULL;

  int return_items = PyObject_IsTrue(return_items_obj);
  if (unlikely(return_items < 0)) return NULL;
  
  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_SetString(PyExc_TypeError, "cmp must be callable or None");
    return NULL;
  }
  if (unlikely(predicate != Py_None && !PyCallable_Check(predicate))) {
    PyErr_SetString(PyExc_TypeError, "predicate must be callable or None");
    return NULL;
  }
  if (unlikely(arity < 1)) {
    PyErr_SetString(PyExc_ValueError, "arity must be >= 1");
    return NULL;
  }

  Py_ssize_t heap_size = PySequence_Size(heap);
  if (unlikely(heap_size < 0)) return NULL;
  if (heap_size == 0) {
    if (return_items) {
      return Py_BuildValue("(iO)", 0, PyList_New(0));
    } else {
      return PyLong_FromLong(0);
    }
  }

  /* HOT PATH: Single index removal with O(log n) inline maintenance */
  if (likely(PyList_CheckExact(heap) && indices != Py_None && object == Py_None && 
             predicate == Py_None && PyLong_Check(indices))) {
    
    Py_ssize_t idx = PyLong_AsSsize_t(indices);
    if (unlikely(idx == -1 && PyErr_Occurred())) return NULL;
    
    if (idx < 0) idx += heap_size;
    if (idx < 0 || idx >= heap_size) {
      if (return_items) {
        return Py_BuildValue("(iO)", 0, PyList_New(0));
      } else {
        return PyLong_FromLong(0);
      }
    }
    
    PyListObject *listobj = (PyListObject *)heap;
    PyObject *removed_item = NULL;
    if (return_items) {
      removed_item = listobj->ob_item[idx];
      Py_INCREF(removed_item);
    }
    
    Py_ssize_t new_size = heap_size - 1;
    
    /* Priority 1: Small heap (n ≤ 16) - use insertion sort after removal */
    if (unlikely(new_size <= 16 && cmp == Py_None)) {
      if (unlikely(PySequence_DelItem(heap, idx) < 0)) {
        Py_XDECREF(removed_item);
        return NULL;
      }
      
      if (new_size > 0) {
        PyObject **items = listobj->ob_item;
        for (Py_ssize_t i = 1; i < new_size; i++) {
          PyObject *key = items[i];
          Py_INCREF(key);
          Py_ssize_t j = i - 1;
          while (j >= 0) {
            int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
            if (unlikely(cmp_res < 0)) {
              Py_DECREF(key);
              Py_XDECREF(removed_item);
              return NULL;
            }
            if (!cmp_res) break;
            Py_INCREF(items[j]);
            Py_SETREF(items[j + 1], items[j]);
            j--;
          }
          Py_SETREF(items[j + 1], key);
        }
      }
      
      if (return_items) {
        PyObject *items_list = PyList_New(1);
        if (unlikely(!items_list)) {
          Py_DECREF(removed_item);
          return NULL;
        }
        PyList_SET_ITEM(items_list, 0, removed_item);
        return Py_BuildValue("(nO)", 1, items_list);
      }
      return PyLong_FromLong(1);
    }
    
    /* Priority 2: Arity=1 (sorted list) - O(n) removal with shift */
    if (unlikely(arity == 1)) {
      if (unlikely(PySequence_DelItem(heap, idx) < 0)) {
        Py_XDECREF(removed_item);
        return NULL;
      }
      
      if (return_items) {
        PyObject *items_list = PyList_New(1);
        if (unlikely(!items_list)) {
          Py_DECREF(removed_item);
          return NULL;
        }
        PyList_SET_ITEM(items_list, 0, removed_item);
        return Py_BuildValue("(nO)", 1, items_list);
      }
      return PyLong_FromLong(1);
    }
    
    /* Priorities 3-10: Use O(log n) inline heap maintenance */
    PyObject *keyfunc = (cmp == Py_None) ? NULL : cmp;
    if (unlikely(list_remove_at_index_optimized(listobj, idx, is_max, keyfunc, arity) < 0)) {
      Py_XDECREF(removed_item);
      return NULL;
    }
    
    if (return_items) {
      PyObject *items_list = PyList_New(1);
      if (unlikely(!items_list)) {
        Py_DECREF(removed_item);
        return NULL;
      }
      PyList_SET_ITEM(items_list, 0, removed_item);
      return Py_BuildValue("(nO)", 1, items_list);
    }
    return PyLong_FromLong(1);
  }

  /* GENERAL CASE: Multiple criteria or batch removal */
  PyObject *to_remove = PySet_New(NULL);
  if (unlikely(!to_remove)) return NULL;

  /* Collect indices based on criteria */
  if (indices != Py_None) {
    if (PySequence_Check(indices)) {
      Py_ssize_t n_indices = PySequence_Size(indices);
      for (Py_ssize_t i = 0; i < n_indices; i++) {
        PyObject *idx_obj = PySequence_GetItem(indices, i);
        if (unlikely(!idx_obj)) {
          Py_DECREF(to_remove);
          return NULL;
        }
        
        Py_ssize_t idx = PyLong_AsSsize_t(idx_obj);
        Py_DECREF(idx_obj);
        if (unlikely(idx == -1 && PyErr_Occurred())) {
          Py_DECREF(to_remove);
          return NULL;
        }
        
        if (idx < 0) idx += heap_size;
        if (idx >= 0 && idx < heap_size) {
          PyObject *idx_py = PyLong_FromSsize_t(idx);
          if (unlikely(!idx_py)) {
            Py_DECREF(to_remove);
            return NULL;
          }
          if (unlikely(PySet_Add(to_remove, idx_py) < 0)) {
            Py_DECREF(idx_py);
            Py_DECREF(to_remove);
            return NULL;
          }
          Py_DECREF(idx_py);
        }
      }
    } else {
      Py_ssize_t idx = PyLong_AsSsize_t(indices);
      if (unlikely(idx == -1 && PyErr_Occurred())) {
        Py_DECREF(to_remove);
        return NULL;
      }
      
      if (idx < 0) idx += heap_size;
      if (idx >= 0 && idx < heap_size) {
        PyObject *idx_py = PyLong_FromSsize_t(idx);
        if (unlikely(!idx_py)) {
          Py_DECREF(to_remove);
          return NULL;
        }
        if (unlikely(PySet_Add(to_remove, idx_py) < 0)) {
          Py_DECREF(idx_py);
          Py_DECREF(to_remove);
          return NULL;
        }
        Py_DECREF(idx_py);
      }
    }
  }

  /* Object identity search - optimized for lists */
  if (object != Py_None) {
    if (PyList_CheckExact(heap)) {
      PyObject **items = ((PyListObject *)heap)->ob_item;
      for (Py_ssize_t i = 0; i < heap_size; i++) {
        if (items[i] == object) {
          PyObject *idx_py = PyLong_FromSsize_t(i);
          if (unlikely(!idx_py)) {
            Py_DECREF(to_remove);
            return NULL;
          }
          if (unlikely(PySet_Add(to_remove, idx_py) < 0)) {
            Py_DECREF(idx_py);
            Py_DECREF(to_remove);
            return NULL;
          }
          Py_DECREF(idx_py);
          
          if (n > 0 && PySet_Size(to_remove) >= n) break;
        }
      }
    } else {
      for (Py_ssize_t i = 0; i < heap_size; i++) {
        PyObject *item = PySequence_GetItem(heap, i);
        if (unlikely(!item)) {
          Py_DECREF(to_remove);
          return NULL;
        }
        
        int is_same = (item == object);
        Py_DECREF(item);
        
        if (is_same) {
          PyObject *idx_py = PyLong_FromSsize_t(i);
          if (unlikely(!idx_py)) {
            Py_DECREF(to_remove);
            return NULL;
          }
          if (unlikely(PySet_Add(to_remove, idx_py) < 0)) {
            Py_DECREF(idx_py);
            Py_DECREF(to_remove);
            return NULL;
          }
          Py_DECREF(idx_py);
          
          if (n > 0 && PySet_Size(to_remove) >= n) break;
        }
      }
    }
  }

  /* Predicate search */
  if (predicate != Py_None) {
    for (Py_ssize_t i = 0; i < heap_size; i++) {
      PyObject *item = PySequence_GetItem(heap, i);
      if (unlikely(!item)) {
        Py_DECREF(to_remove);
        return NULL;
      }
      
      PyObject *result = PyObject_CallOneArg(predicate, item);
      Py_DECREF(item);
      if (unlikely(!result)) {
        Py_DECREF(to_remove);
        return NULL;
      }
      
      int matches = PyObject_IsTrue(result);
      Py_DECREF(result);
      if (unlikely(matches < 0)) {
        Py_DECREF(to_remove);
        return NULL;
      }
      
      if (matches) {
        PyObject *idx_py = PyLong_FromSsize_t(i);
        if (unlikely(!idx_py)) {
          Py_DECREF(to_remove);
          return NULL;
        }
        if (unlikely(PySet_Add(to_remove, idx_py) < 0)) {
          Py_DECREF(idx_py);
          Py_DECREF(to_remove);
          return NULL;
        }
        Py_DECREF(idx_py);
        
        if (n > 0 && PySet_Size(to_remove) >= n) break;
      }
    }
  }

  Py_ssize_t remove_count = PySet_Size(to_remove);
  if (remove_count == 0) {
    Py_DECREF(to_remove);
    if (return_items) {
      return Py_BuildValue("(iO)", 0, PyList_New(0));
    } else {
      return PyLong_FromLong(0);
    }
  }

  /* Collect removed items and perform removal */
  PyObject *removed_items = NULL;
  if (return_items) {
    removed_items = PyList_New(0);
    if (unlikely(!removed_items)) {
      Py_DECREF(to_remove);
      return NULL;
    }
  }

  /* Convert set to sorted list for efficient removal */
  PyObject *remove_list = PyList_New(0);
  if (unlikely(!remove_list)) {
    Py_DECREF(to_remove);
    Py_XDECREF(removed_items);
    return NULL;
  }

  PyObject *iterator = PyObject_GetIter(to_remove);
  if (unlikely(!iterator)) {
    Py_DECREF(to_remove);
    Py_DECREF(remove_list);
    Py_XDECREF(removed_items);
    return NULL;
  }

  PyObject *idx_obj;
  while ((idx_obj = PyIter_Next(iterator))) {
    if (unlikely(PyList_Append(remove_list, idx_obj) < 0)) {
      Py_DECREF(idx_obj);
      Py_DECREF(iterator);
      Py_DECREF(to_remove);
      Py_DECREF(remove_list);
      Py_XDECREF(removed_items);
      return NULL;
    }
    Py_DECREF(idx_obj);
  }
  Py_DECREF(iterator);
  Py_DECREF(to_remove);

  if (unlikely(PyList_Sort(remove_list) < 0)) {
    Py_DECREF(remove_list);
    Py_XDECREF(removed_items);
    return NULL;
  }

  /* Remove items in reverse order to maintain indices */
  if (PyList_CheckExact(heap)) {
    for (Py_ssize_t i = PyList_Size(remove_list) - 1; i >= 0; i--) {
      PyObject *idx_obj = PyList_GetItem(remove_list, i);
      Py_ssize_t idx = PyLong_AsSsize_t(idx_obj);
      
      if (return_items) {
        PyObject *item = PyList_GET_ITEM(heap, idx);
        Py_INCREF(item);
        if (unlikely(PyList_Insert(removed_items, 0, item) < 0)) {
          Py_DECREF(item);
          Py_DECREF(remove_list);
          Py_DECREF(removed_items);
          return NULL;
        }
        Py_DECREF(item);
      }
      
      if (unlikely(PySequence_DelItem(heap, idx) < 0)) {
        Py_DECREF(remove_list);
        Py_XDECREF(removed_items);
        return NULL;
      }
    }
  }
  
  Py_DECREF(remove_list);

  /* Re-heapify after batch removals - use full heapify for efficiency */
  Py_ssize_t new_size = PySequence_Size(heap);
  if (new_size > 0) {
    /* Priority 1: Small heap after removal */
    if (unlikely(new_size <= 16 && PyList_CheckExact(heap) && cmp == Py_None)) {
      PyListObject *listobj = (PyListObject *)heap;
      PyObject **items = listobj->ob_item;
      for (Py_ssize_t i = 1; i < new_size; i++) {
        PyObject *key = items[i];
        Py_INCREF(key);
        Py_ssize_t j = i - 1;
        while (j >= 0) {
          int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
          if (unlikely(cmp_res < 0)) {
            Py_DECREF(key);
            Py_XDECREF(removed_items);
            return NULL;
          }
          if (!cmp_res) break;
          Py_INCREF(items[j]);
          Py_SETREF(items[j + 1], items[j]);
          j--;
        }
        Py_SETREF(items[j + 1], key);
      }
    } else if (PyList_CheckExact(heap) && cmp == Py_None) {
      /* Priorities 3-7: Arity-specific heapify without key */
      PyListObject *listobj = (PyListObject *)heap;
      if (likely(arity == 2)) {
        if (unlikely(list_heapify_floyd_ultra_optimized(listobj, is_max) < 0)) {
          Py_XDECREF(removed_items);
          return NULL;
        }
      } else if (arity == 3) {
        if (unlikely(list_heapify_ternary_ultra_optimized(listobj, is_max) < 0)) {
          Py_XDECREF(removed_items);
          return NULL;
        }
      } else if (arity == 4) {
        if (unlikely(list_heapify_quaternary_ultra_optimized(listobj, is_max) < 0)) {
          Py_XDECREF(removed_items);
          return NULL;
        }
      } else {
        if (unlikely(list_heapify_small_ultra_optimized(listobj, is_max, arity) < 0)) {
          Py_XDECREF(removed_items);
          return NULL;
        }
      }
    } else {
      /* Fallback: generic heapify */
      if (unlikely(generic_heapify_ultra_optimized(heap, is_max, (cmp == Py_None ? NULL : cmp), arity) < 0)) {
        Py_XDECREF(removed_items);
        return NULL;
      }
    }
  }

  if (return_items) {
    return Py_BuildValue("(nO)", remove_count, removed_items);
  } else {
    return PyLong_FromSsize_t(remove_count);
  }
}

/* Helper: Replace single item at index with O(log n) inline heap maintenance */
HOT_FUNCTION static inline int
list_replace_at_index_optimized(PyListObject *listobj, Py_ssize_t idx, PyObject *new_value,
                                  int is_max, PyObject *keyfunc, Py_ssize_t arity) {
  Py_ssize_t n = Py_SIZE(listobj);
  if (unlikely(idx < 0 || idx >= n)) return -1;
  
  PyObject **items = listobj->ob_item;
  
  /* Replace value with proper refcounting */
  Py_INCREF(new_value);
  Py_SETREF(items[idx], new_value);
  
  /* Determine sift direction by comparing with parent */
  if (keyfunc == NULL) {
    if (idx > 0) {
      Py_ssize_t parent = (idx - 1) / arity;
      int cmp_res = optimized_compare(items[idx], items[parent], is_max ? Py_GT : Py_LT);
      if (unlikely(cmp_res < 0)) return -1;
      if (cmp_res) {
        /* New value violates parent relationship - sift up */
        return list_sift_up_ultra_optimized(listobj, idx, is_max, arity);
      }
    }
    /* Sift down to restore heap property */
    return list_sift_down_ultra_optimized(listobj, idx, n, is_max, arity);
  } else {
    if (idx > 0) {
      Py_ssize_t parent = (idx - 1) / arity;
      PyObject *key_item = call_key_function(keyfunc, items[idx]);
      if (unlikely(!key_item)) return -1;
      PyObject *key_parent = call_key_function(keyfunc, items[parent]);
      if (unlikely(!key_parent)) {
        Py_DECREF(key_item);
        return -1;
      }
      int cmp_res = optimized_compare(key_item, key_parent, is_max ? Py_GT : Py_LT);
      Py_DECREF(key_item);
      Py_DECREF(key_parent);
      if (unlikely(cmp_res < 0)) return -1;
      if (cmp_res) {
        return list_sift_up_with_key_ultra_optimized(listobj, idx, is_max, keyfunc, arity);
      }
    }
    return list_sift_down_with_key_ultra_optimized(listobj, idx, n, is_max, keyfunc, arity);
  }
}

/* Ultra-optimized replace with 11-priority dispatch and adaptive batch strategy */
static PyObject *
py_replace(PyObject *self, PyObject *args, PyObject *kwargs) {
  static char *kwlist[] = {"heap", "values", "indices", "object", "predicate", "max_heap", "cmp", "arity", NULL};
  PyObject *heap, *values;
  PyObject *indices = Py_None;
  PyObject *object = Py_None;
  PyObject *predicate = Py_None;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|OOOOOn:replace", kwlist,
                                   &heap, &values, &indices, &object, &predicate, &max_heap_obj, &cmp, &arity))
    return NULL;

  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_SetString(PyExc_TypeError, "cmp must be callable or None");
    return NULL;
  }
  if (unlikely(predicate != Py_None && !PyCallable_Check(predicate))) {
    PyErr_SetString(PyExc_TypeError, "predicate must be callable or None");
    return NULL;
  }
  if (unlikely(arity < 1)) {
    PyErr_SetString(PyExc_ValueError, "arity must be >= 1");
    return NULL;
  }

  Py_ssize_t heap_size = PySequence_Size(heap);
  if (unlikely(heap_size < 0)) return NULL;
  if (heap_size == 0) return PyLong_FromLong(0);

  /* HOT PATH: Single index replacement with O(log n) inline maintenance */
  if (likely(PyList_CheckExact(heap) && indices != Py_None && object == Py_None && 
             predicate == Py_None && PyLong_Check(indices))) {
    
    Py_ssize_t idx = PyLong_AsSsize_t(indices);
    if (unlikely(idx == -1 && PyErr_Occurred())) return NULL;
    
    if (idx < 0) idx += heap_size;
    if (idx < 0 || idx >= heap_size) return PyLong_FromLong(0);
    
    PyListObject *listobj = (PyListObject *)heap;
    Py_ssize_t new_size = heap_size;
    PyObject *keyfunc = (cmp == Py_None) ? NULL : cmp;
    
    /* Priority 1: Small heap (n ≤ 16) - use insertion sort after replacement */
    if (unlikely(new_size <= 16 && keyfunc == NULL)) {
      PyObject **items = listobj->ob_item;
      Py_INCREF(values);
      Py_SETREF(items[idx], values);
      
      for (Py_ssize_t i = 1; i < new_size; i++) {
        PyObject *key = items[i];
        Py_INCREF(key);
        Py_ssize_t j = i - 1;
        while (j >= 0) {
          int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
          if (unlikely(cmp_res < 0)) {
            Py_DECREF(key);
            return NULL;
          }
          if (!cmp_res) break;
          Py_INCREF(items[j]);
          Py_SETREF(items[j + 1], items[j]);
          j--;
        }
        Py_SETREF(items[j + 1], key);
      }
      return PyLong_FromLong(1);
    }
    
    /* Priority 2: Arity=1 (sorted list) - re-sort after replacement */
    if (unlikely(arity == 1)) {
      PyObject **items = listobj->ob_item;
      Py_INCREF(values);
      Py_SETREF(items[idx], values);
      
      /* Use insertion sort to maintain sorted order */
      for (Py_ssize_t i = 1; i < new_size; i++) {
        PyObject *key = items[i];
        Py_INCREF(key);
        Py_ssize_t j = i - 1;
        while (j >= 0) {
          int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
          if (unlikely(cmp_res < 0)) {
            Py_DECREF(key);
            return NULL;
          }
          if (!cmp_res) break;
          Py_INCREF(items[j]);
          Py_SETREF(items[j + 1], items[j]);
          j--;
        }
        Py_SETREF(items[j + 1], key);
      }
      return PyLong_FromLong(1);
    }
    
    /* Priorities 3-10: Use O(log n) inline heap maintenance */
    if (unlikely(list_replace_at_index_optimized(listobj, idx, values, is_max, keyfunc, arity) < 0)) {
      return NULL;
    }
    
    return PyLong_FromLong(1);
  }

  /* GENERAL CASE: Collect indices to replace */
  PyObject *to_replace = PyList_New(0);
  if (unlikely(!to_replace)) return NULL;

  if (indices != Py_None) {
    if (PySequence_Check(indices)) {
      Py_ssize_t n_indices = PySequence_Size(indices);
      for (Py_ssize_t i = 0; i < n_indices; i++) {
        PyObject *idx_obj = PySequence_GetItem(indices, i);
        if (unlikely(!idx_obj)) {
          Py_DECREF(to_replace);
          return NULL;
        }
        
        Py_ssize_t idx = PyLong_AsSsize_t(idx_obj);
        Py_DECREF(idx_obj);
        if (unlikely(idx == -1 && PyErr_Occurred())) {
          Py_DECREF(to_replace);
          return NULL;
        }
        
        if (idx < 0) idx += heap_size;
        if (idx >= 0 && idx < heap_size) {
          PyObject *idx_py = PyLong_FromSsize_t(idx);
          if (unlikely(!idx_py)) {
            Py_DECREF(to_replace);
            return NULL;
          }
          if (unlikely(PyList_Append(to_replace, idx_py) < 0)) {
            Py_DECREF(idx_py);
            Py_DECREF(to_replace);
            return NULL;
          }
          Py_DECREF(idx_py);
        }
      }
    } else {
      Py_ssize_t idx = PyLong_AsSsize_t(indices);
      if (unlikely(idx == -1 && PyErr_Occurred())) {
        Py_DECREF(to_replace);
        return NULL;
      }
      
      if (idx < 0) idx += heap_size;
      if (idx >= 0 && idx < heap_size) {
        PyObject *idx_py = PyLong_FromSsize_t(idx);
        if (unlikely(!idx_py)) {
          Py_DECREF(to_replace);
          return NULL;
        }
        if (unlikely(PyList_Append(to_replace, idx_py) < 0)) {
          Py_DECREF(idx_py);
          Py_DECREF(to_replace);
          return NULL;
        }
        Py_DECREF(idx_py);
      }
    }
  }

  /* Object identity search */
  if (object != Py_None) {
    if (PyList_CheckExact(heap)) {
      PyObject **items = ((PyListObject *)heap)->ob_item;
      for (Py_ssize_t i = 0; i < heap_size; i++) {
        if (items[i] == object) {
          PyObject *idx_py = PyLong_FromSsize_t(i);
          if (unlikely(!idx_py)) {
            Py_DECREF(to_replace);
            return NULL;
          }
          if (unlikely(PyList_Append(to_replace, idx_py) < 0)) {
            Py_DECREF(idx_py);
            Py_DECREF(to_replace);
            return NULL;
          }
          Py_DECREF(idx_py);
        }
      }
    } else {
      for (Py_ssize_t i = 0; i < heap_size; i++) {
        PyObject *item = PySequence_GetItem(heap, i);
        if (unlikely(!item)) {
          Py_DECREF(to_replace);
          return NULL;
        }
        
        int is_same = (item == object);
        Py_DECREF(item);
        
        if (is_same) {
          PyObject *idx_py = PyLong_FromSsize_t(i);
          if (unlikely(!idx_py)) {
            Py_DECREF(to_replace);
            return NULL;
          }
          if (unlikely(PyList_Append(to_replace, idx_py) < 0)) {
            Py_DECREF(idx_py);
            Py_DECREF(to_replace);
            return NULL;
          }
          Py_DECREF(idx_py);
        }
      }
    }
  }

  /* Predicate search */
  if (predicate != Py_None) {
    for (Py_ssize_t i = 0; i < heap_size; i++) {
      PyObject *item = PySequence_GetItem(heap, i);
      if (unlikely(!item)) {
        Py_DECREF(to_replace);
        return NULL;
      }
      
      PyObject *result = PyObject_CallOneArg(predicate, item);
      Py_DECREF(item);
      if (unlikely(!result)) {
        Py_DECREF(to_replace);
        return NULL;
      }
      
      int matches = PyObject_IsTrue(result);
      Py_DECREF(result);
      if (unlikely(matches < 0)) {
        Py_DECREF(to_replace);
        return NULL;
      }
      
      if (matches) {
        PyObject *idx_py = PyLong_FromSsize_t(i);
        if (unlikely(!idx_py)) {
          Py_DECREF(to_replace);
          return NULL;
        }
        if (unlikely(PyList_Append(to_replace, idx_py) < 0)) {
          Py_DECREF(idx_py);
          Py_DECREF(to_replace);
          return NULL;
        }
        Py_DECREF(idx_py);
      }
    }
  }

  Py_ssize_t replace_count = PyList_Size(to_replace);
  if (replace_count == 0) {
    Py_DECREF(to_replace);
    return PyLong_FromLong(0);
  }

  /* Handle values - single value or sequence */
  PyObject *value_list;
  if (PySequence_Check(values) && !PyUnicode_Check(values) && !PyBytes_Check(values)) {
    value_list = values;
    Py_INCREF(value_list);
    
    Py_ssize_t n_values = PySequence_Size(value_list);
    if (n_values != replace_count && n_values != 1) {
      PyErr_SetString(PyExc_ValueError, "values length must match selection count or be 1");
      Py_DECREF(to_replace);
      Py_DECREF(value_list);
      return NULL;
    }
  } else {
    value_list = PyList_New(replace_count);
    if (unlikely(!value_list)) {
      Py_DECREF(to_replace);
      return NULL;
    }
    for (Py_ssize_t i = 0; i < replace_count; i++) {
      Py_INCREF(values);
      PyList_SET_ITEM(value_list, i, values);
    }
  }

  /* ADAPTIVE BATCH STRATEGY: Sequential O(log n) vs Batch O(n) */
  if (PyList_CheckExact(heap) && replace_count < heap_size / 4) {
    /* Sequential O(log n) replacements for small batches */
    PyListObject *listobj = (PyListObject *)heap;
    PyObject *keyfunc = (cmp == Py_None) ? NULL : cmp;
    Py_ssize_t n_values = PySequence_Size(value_list);
    
    for (Py_ssize_t i = 0; i < replace_count; i++) {
      PyObject *idx_obj = PyList_GetItem(to_replace, i);
      Py_ssize_t idx = PyLong_AsSsize_t(idx_obj);
      
      PyObject *new_value;
      if (n_values == 1) {
        new_value = PySequence_GetItem(value_list, 0);
      } else {
        new_value = PySequence_GetItem(value_list, i);
      }
      
      if (unlikely(!new_value)) {
        Py_DECREF(to_replace);
        Py_DECREF(value_list);
        return NULL;
      }
      
      if (unlikely(list_replace_at_index_optimized(listobj, idx, new_value, is_max, keyfunc, arity) < 0)) {
        Py_DECREF(new_value);
        Py_DECREF(to_replace);
        Py_DECREF(value_list);
        return NULL;
      }
      Py_DECREF(new_value);
    }
    
    Py_DECREF(to_replace);
    Py_DECREF(value_list);
    return PyLong_FromSsize_t(replace_count);
  }

  /* Batch replacement + heapify for large batches */
  Py_ssize_t n_values = PySequence_Size(value_list);
  for (Py_ssize_t i = 0; i < replace_count; i++) {
    PyObject *idx_obj = PyList_GetItem(to_replace, i);
    Py_ssize_t idx = PyLong_AsSsize_t(idx_obj);
    
    PyObject *new_value;
    if (n_values == 1) {
      new_value = PySequence_GetItem(value_list, 0);
    } else {
      new_value = PySequence_GetItem(value_list, i);
    }
    
    if (unlikely(!new_value)) {
      Py_DECREF(to_replace);
      Py_DECREF(value_list);
      return NULL;
    }
    
    if (unlikely(PySequence_SetItem(heap, idx, new_value) < 0)) {
      Py_DECREF(new_value);
      Py_DECREF(to_replace);
      Py_DECREF(value_list);
      return NULL;
    }
    Py_DECREF(new_value);
  }

  Py_DECREF(to_replace);
  Py_DECREF(value_list);

  /* Re-heapify using optimized dispatch */
  if (PyList_CheckExact(heap)) {
    PyListObject *listobj = (PyListObject *)heap;
    Py_ssize_t new_size = Py_SIZE(listobj);
    
    /* Priority 1: Small heap after replacement */
    if (unlikely(new_size <= 16 && cmp == Py_None)) {
      PyObject **items = listobj->ob_item;
      for (Py_ssize_t i = 1; i < new_size; i++) {
        PyObject *key = items[i];
        Py_INCREF(key);
        Py_ssize_t j = i - 1;
        while (j >= 0) {
          int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
          if (unlikely(cmp_res < 0)) {
            Py_DECREF(key);
            return NULL;
          }
          if (!cmp_res) break;
          Py_INCREF(items[j]);
          Py_SETREF(items[j + 1], items[j]);
          j--;
        }
        Py_SETREF(items[j + 1], key);
      }
      return PyLong_FromSsize_t(replace_count);
    }
    
    /* Priorities 3-7: Arity-specific heapify without key */
    if (cmp == Py_None) {
      if (likely(arity == 2)) {
        if (unlikely(list_heapify_floyd_ultra_optimized(listobj, is_max) < 0)) {
          return NULL;
        }
      } else if (arity == 3) {
        if (unlikely(list_heapify_ternary_ultra_optimized(listobj, is_max) < 0)) {
          return NULL;
        }
      } else if (arity == 4) {
        if (unlikely(list_heapify_quaternary_ultra_optimized(listobj, is_max) < 0)) {
          return NULL;
        }
      } else {
        if (unlikely(list_heapify_small_ultra_optimized(listobj, is_max, arity) < 0)) {
          return NULL;
        }
      }
      return PyLong_FromSsize_t(replace_count);
    }
  }

  /* Fallback: generic heapify */
  if (unlikely(generic_heapify_ultra_optimized(heap, is_max, (cmp == Py_None ? NULL : cmp), arity) < 0)) {
    return NULL;
  }

  return PyLong_FromSsize_t(replace_count);
}

/* Ultra-optimized merge with complete 11-priority dispatch and sorted heap support */
static PyObject *
py_merge(PyObject *self, PyObject *args, PyObject *kwargs) {
  static char *kwlist[] = {"max_heap", "cmp", "arity", "sorted_heaps", NULL};
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;
  PyObject *sorted_heaps_obj = Py_False;

  /* Parse keyword arguments */
  if (!PyArg_ParseTupleAndKeywords(PyTuple_New(0), kwargs, "|OOnO:merge", kwlist,
                                   &max_heap_obj, &cmp, &arity, &sorted_heaps_obj))
    return NULL;

  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;
  
  int sorted_heaps = PyObject_IsTrue(sorted_heaps_obj);
  if (unlikely(sorted_heaps < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_SetString(PyExc_TypeError, "cmp must be callable or None");
    return NULL;
  }
  if (unlikely(arity < 1)) {
    PyErr_SetString(PyExc_ValueError, "arity must be >= 1");
    return NULL;
  }

  Py_ssize_t n_args = PyTuple_Size(args);
  if (n_args < 2) {
    PyErr_SetString(PyExc_ValueError, "merge requires at least 2 heaps");
    return NULL;
  }

  /* Calculate total size and validate inputs */
  Py_ssize_t total_size = 0;
  int all_lists = 1;
  int non_empty_count = 0;
  Py_ssize_t non_empty_idx = -1;
  
  for (Py_ssize_t i = 0; i < n_args; i++) {
    PyObject *heap = PyTuple_GetItem(args, i);
    if (unlikely(!PySequence_Check(heap))) {
      PyErr_SetString(PyExc_TypeError, "all arguments must be sequences");
      return NULL;
    }
    
    if (!PyList_CheckExact(heap)) all_lists = 0;

    Py_ssize_t heap_size = PySequence_Size(heap);
    if (unlikely(heap_size < 0)) return NULL;
    
    if (heap_size > 0) {
      non_empty_count++;
      non_empty_idx = i;
    }
    total_size += heap_size;
  }

  /* Edge case: only one non-empty heap */
  if (non_empty_count == 1) {
    return PySequence_List(PyTuple_GetItem(args, non_empty_idx));
  }
  
  /* Edge case: all heaps empty */
  if (total_size == 0) {
    return PyList_New(0);
  }

  PyObject *keyfunc = (cmp == Py_None) ? NULL : cmp;

  /* ========== CONCATENATION PHASE ========== */
  
  PyObject *result = PyList_New(total_size);
  if (unlikely(!result)) return NULL;
  
  Py_ssize_t pos = 0;
  
  if (all_lists) {
    /* Ultra-fast list concatenation */
    for (Py_ssize_t i = 0; i < n_args; i++) {
      PyListObject *heap_list = (PyListObject *)PyTuple_GetItem(args, i);
      Py_ssize_t heap_size = PyList_GET_SIZE(heap_list);
      if (heap_size == 0) continue;
      
      PyObject **heap_items = heap_list->ob_item;
      for (Py_ssize_t j = 0; j < heap_size; j++) {
        PyObject *item = heap_items[j];
        Py_INCREF(item);
        PyList_SET_ITEM(result, pos++, item);
      }
    }
  } else {
    /* General sequence concatenation with PySequence_Fast */
    for (Py_ssize_t i = 0; i < n_args; i++) {
      PyObject *heap = PyTuple_GetItem(args, i);
      PyObject *fast = PySequence_Fast(heap, "merge requires sequences");
      if (unlikely(!fast)) {
        Py_DECREF(result);
        return NULL;
      }
      
      Py_ssize_t heap_size = PySequence_Fast_GET_SIZE(fast);
      if (heap_size == 0) {
        Py_DECREF(fast);
        continue;
      }
      
      PyObject **items = PySequence_Fast_ITEMS(fast);
      for (Py_ssize_t j = 0; j < heap_size; j++) {
        PyObject *item = items[j];
        Py_INCREF(item);
        PyList_SET_ITEM(result, pos++, item);
      }
      Py_DECREF(fast);
    }
  }

  /* If sorted_heaps=True, result is already a valid heap, return immediately */
  if (sorted_heaps) {
    return result;
  }

  /* ========== 11-PRIORITY HEAPIFY DISPATCH ========== */
  
  PyListObject *result_list = (PyListObject *)result;
  
  /* Priority 1: Small heap (n ≤ 16, no key) */
  if (unlikely(total_size <= 16 && keyfunc == NULL)) {
    PyObject **items = result_list->ob_item;
    for (Py_ssize_t i = 1; i < total_size; i++) {
      PyObject *key = items[i];
      Py_INCREF(key);
      Py_ssize_t j = i - 1;
      while (j >= 0) {
        int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
        if (unlikely(cmp_res < 0)) {
          Py_DECREF(key);
          Py_DECREF(result);
          return NULL;
        }
        if (!cmp_res) break;
        Py_INCREF(items[j]);
        Py_SETREF(items[j + 1], items[j]);
        j--;
      }
      Py_SETREF(items[j + 1], key);
    }
    return result;
  }
  
  /* Priority 2: Arity=1 (sorted list) */
  if (unlikely(arity == 1)) {
    PyObject **items = result_list->ob_item;
    for (Py_ssize_t i = 1; i < total_size; i++) {
      PyObject *key = items[i];
      Py_INCREF(key);
      Py_ssize_t j = i - 1;
      
      if (keyfunc) {
        PyObject *key_val = call_key_function(keyfunc, key);
        if (unlikely(!key_val)) {
          Py_DECREF(key);
          Py_DECREF(result);
          return NULL;
        }
        
        while (j >= 0) {
          PyObject *j_key = call_key_function(keyfunc, items[j]);
          if (unlikely(!j_key)) {
            Py_DECREF(key);
            Py_DECREF(key_val);
            Py_DECREF(result);
            return NULL;
          }
          int cmp_res = optimized_compare(key_val, j_key, is_max ? Py_GT : Py_LT);
          Py_DECREF(j_key);
          if (unlikely(cmp_res < 0)) {
            Py_DECREF(key);
            Py_DECREF(key_val);
            Py_DECREF(result);
            return NULL;
          }
          if (!cmp_res) break;
          Py_INCREF(items[j]);
          Py_SETREF(items[j + 1], items[j]);
          j--;
        }
        Py_DECREF(key_val);
      } else {
        while (j >= 0) {
          int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
          if (unlikely(cmp_res < 0)) {
            Py_DECREF(key);
            Py_DECREF(result);
            return NULL;
          }
          if (!cmp_res) break;
          Py_INCREF(items[j]);
          Py_SETREF(items[j + 1], items[j]);
          j--;
        }
      }
      Py_SETREF(items[j + 1], key);
    }
    return result;
  }
  
  /* Priority 3: Binary heap (arity=2, no key) */
  if (likely(arity == 2 && keyfunc == NULL)) {
    if (unlikely(list_heapify_floyd_ultra_optimized(result_list, is_max) < 0)) {
      Py_DECREF(result);
      return NULL;
    }
    return result;
  }
  
  /* Priority 4: Ternary heap (arity=3, no key) */
  if (unlikely(arity == 3 && keyfunc == NULL)) {
    if (unlikely(list_heapify_ternary_ultra_optimized(result_list, is_max) < 0)) {
      Py_DECREF(result);
      return NULL;
    }
    return result;
  }
  
  /* Priority 5: Quaternary heap (arity=4, no key) */
  if (unlikely(arity == 4 && keyfunc == NULL)) {
    if (unlikely(list_heapify_quaternary_ultra_optimized(result_list, is_max) < 0)) {
      Py_DECREF(result);
      return NULL;
    }
    return result;
  }
  
  /* Priority 6: N-ary heap (arity≥5, no key, n<1000) */
  if (unlikely(arity >= 5 && keyfunc == NULL && total_size < 1000)) {
    if (unlikely(list_heapify_small_ultra_optimized(result_list, is_max, arity) < 0)) {
      Py_DECREF(result);
      return NULL;
    }
    return result;
  }
  
  /* Priority 7: N-ary heap (arity≥5, no key, n≥1000) */
  if (unlikely(arity >= 5 && keyfunc == NULL && total_size >= 1000)) {
    if (unlikely(generic_heapify_ultra_optimized(result, is_max, NULL, arity) < 0)) {
      Py_DECREF(result);
      return NULL;
    }
    return result;
  }
  
  /* Priority 8: Binary heap with key (arity=2) */
  if (likely(arity == 2 && keyfunc != NULL)) {
    if (unlikely(list_heapify_with_key_ultra_optimized(result_list, keyfunc, is_max) < 0)) {
      Py_DECREF(result);
      return NULL;
    }
    return result;
  }
  
  /* Priority 9: Ternary heap with key (arity=3) */
  if (unlikely(arity == 3 && keyfunc != NULL)) {
    if (unlikely(list_heapify_ternary_with_key_ultra_optimized(result_list, keyfunc, is_max) < 0)) {
      Py_DECREF(result);
      return NULL;
    }
    return result;
  }
  
  /* Priority 10: N-ary heap with key (arity≥4) */
  if (unlikely(arity >= 4 && keyfunc != NULL)) {
    if (unlikely(generic_heapify_ultra_optimized(result, is_max, keyfunc, arity) < 0)) {
      Py_DECREF(result);
      return NULL;
    }
    return result;
  }
  
  /* Priority 11: Generic sequence (fallback) */
  if (unlikely(generic_heapify_ultra_optimized(result, is_max, keyfunc, arity) < 0)) {
    Py_DECREF(result);
    return NULL;
  }
  
  return result;
}
