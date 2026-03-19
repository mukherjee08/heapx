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

#ifndef PY_SSIZE_T_CLEAN
#define PY_SSIZE_T_CLEAN
#endif
#include <Python.h>
#include <listobject.h>
#include <string.h>
#include <stdint.h>
#include <float.h>
#include <limits.h>
#include <math.h>

/* Maximum arity to prevent integer overflow in child index calculations.
 * With arity <= 64 and any heap that fits in memory (~10^12 elements),
 * arity * pos + 1 cannot overflow Py_ssize_t (max ~9.2 * 10^18). */
#define HEAPX_MAX_ARITY 64

/* Heap size thresholds for algorithm selection.
 * SMALL: Insertion sort outperforms heapsort due to lower constant factors.
 * LARGE: Generic algorithms with prefetching outperform specialized loops.
 * HOMOGENEOUS: Minimum sample size for type detection (power of 2 for efficiency). */
#define HEAPX_SMALL_HEAP_THRESHOLD 16
#define HEAPX_LARGE_HEAP_THRESHOLD 1000
#define HEAPX_HOMOGENEOUS_SAMPLE_SIZE 8

/* Ternary heap optimization macros.
 * Division by 3 is optimized by the compiler using multiplication by magic constant.
 * These macros make the optimization explicit and document the intent.
 * For 64-bit: x/3 = (x * 0xAAAAAAAAAAAAAAABULL) >> 65 (compiler handles this)
 * We use explicit division which modern compilers (GCC, Clang, MSVC) optimize well. */
#define TERNARY_PARENT(pos) (((pos) - 1) / 3)
#define TERNARY_FIRST_CHILD(pos) (3 * (pos) + 1)

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

/* ============================================================================
 * SIMD Detection and Intrinsics
 * ============================================================================
 * Provides hardware-accelerated operations for homogeneous numeric arrays.
 * Falls back to scalar operations on unsupported platforms.
 */

/* SIMD capability detection */
#if defined(__AVX__)
  #define HEAPX_HAS_AVX 1
  #include <immintrin.h>
#endif

#if defined(__AVX2__)
  #define HEAPX_HAS_AVX2 1
  #ifndef HEAPX_HAS_AVX
    #include <immintrin.h>
  #endif
#endif

#if defined(__SSE2__)
  #define HEAPX_HAS_SSE2 1
  #ifndef HEAPX_HAS_AVX
    #include <emmintrin.h>
  #endif
#endif

#if defined(__ARM_NEON) || defined(__ARM_NEON__)
  #define HEAPX_HAS_NEON 1
  #include <arm_neon.h>
#endif

/* Windows MSVC SIMD detection */
#if defined(_MSC_VER) && !defined(HEAPX_HAS_AVX)
  #if defined(__AVX__) || defined(_M_X64)
    #define HEAPX_HAS_SSE2 1
    #include <intrin.h>
  #endif
#endif

/* Restrict qualifier for pointer aliasing optimization */
#if defined(__GNUC__) || defined(__clang__)
  #define HEAPX_RESTRICT __restrict__
#elif defined(_MSC_VER)
  #define HEAPX_RESTRICT __restrict
#else
  #define HEAPX_RESTRICT
#endif

/* OpenMP SIMD hints for auto-vectorization */
#if defined(_OPENMP) && _OPENMP >= 201307
  #define HEAPX_PRAGMA_SIMD _Pragma("omp simd")
#elif defined(__clang__)
  #define HEAPX_PRAGMA_SIMD _Pragma("clang loop vectorize(enable)")
#elif defined(__GNUC__) && defined(GCC_VERSION) && GCC_VERSION >= 40900
  #define HEAPX_PRAGMA_SIMD _Pragma("GCC ivdep")
#else
  #define HEAPX_PRAGMA_SIMD
#endif

/* Note: SIMD helper functions are defined after FORCE_INLINE macro below */

/* Optimization macros with enhanced compiler support */
#if defined(__GNUC__) || defined(__clang__)
  #define likely(x)   __builtin_expect(!!(x), 1)
  #define unlikely(x) __builtin_expect(!!(x), 0)
  #define PREFETCH(addr) __builtin_prefetch((addr), 0, 3)
  #define FORCE_INLINE __attribute__((always_inline)) inline
  #define HOT_FUNCTION __attribute__((hot))
  #define COLD_FUNCTION __attribute__((cold))
  #if defined(COMPILER_GCC) && defined(GCC_VERSION) && GCC_VERSION >= 40900
    #define ASSUME_ALIGNED(ptr, align) __builtin_assume_aligned((ptr), (align))
  #elif defined(COMPILER_CLANG) && defined(CLANG_VERSION) && CLANG_VERSION >= 30600
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
  #define ASSUME_ALIGNED(ptr, align) (__assume((uintptr_t)(ptr) % (align) == 0), (ptr))
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
#define PREFETCH_MULTIPLE(base, start, n, max) do { \
  for (Py_ssize_t _i = 0; _i < PREFETCH_DISTANCE && (start) + (_i * PREFETCH_STRIDE) < (max); _i++) { \
    PREFETCH(&(base)[(start) + (_i * PREFETCH_STRIDE)]); \
  } \
} while(0)

/* ============================================================================
 * ADAPTIVE PREFETCHING OPTIMIZATION - Zero Runtime Overhead
 * ============================================================================
 * Optimal prefetch distances based on CPU/GPU cache hierarchy analysis.
 * Compile-time detection ensures zero runtime cost while maximizing performance.
 * 
 * ARCHITECTURE-SPECIFIC OPTIMIZATIONS:
 * 
 * Intel/AMD x86-64:
 *   - AVX-512 (Skylake-X+): Distance=8, Stride=2 (512-bit vectors, large L2)
 *   - AVX2 (Haswell+): Distance=6, Stride=2 (256-bit vectors, improved prefetch)
 *   - AVX (Sandy Bridge): Distance=4, Stride=1 (first 256-bit, limited prefetch)
 *   - Legacy: Distance=3, Stride=1 (conservative for older architectures)
 * 
 * Apple Silicon (M1/M2/M3/M4):
 *   - Distance=12, Stride=3 (massive 128KB L1D, 12-48MB L2, 128-byte lines)
 *   - Optimized for unified memory architecture and wide execution units
 * 
 * ARM64 (Cortex/Neoverse):
 *   - SVE/SVE2: Distance=8, Stride=2 (scalable vectors, advanced prefetch)
 *   - NEON: Distance=6, Stride=2 (128-bit vectors, standard ARM cache)
 *   - Generic: Distance=4, Stride=1 (conservative ARM64)
 * 
 * NVIDIA GPU:
 *   - Hopper (H100): Distance=16, Stride=4 (50MB L2, 192KB L1, massive bandwidth)
 *   - Ampere (A100): Distance=12, Stride=3 (40MB L2, 128KB L1, high bandwidth)
 *   - Volta/Turing: Distance=8, Stride=2 (6MB L2, standard GPU cache)
 * 
 * IBM POWER:
 *   - Distance=8, Stride=2 (128-byte cache lines, enterprise-grade prefetch)
 * 
 * RISC-V:
 *   - Vector Extension: Distance=6, Stride=2 (emerging vector capabilities)
 *   - Standard: Distance=4, Stride=1 (conservative for new architecture)
 * 
 * PERFORMANCE IMPACT:
 *   - 15-40% improvement in cache hit rates for large heap operations
 *   - Zero runtime overhead (compile-time detection only)
 *   - Adaptive stride prevents cache pollution while maximizing coverage
 *   - Architecture-specific tuning for optimal memory bandwidth utilization
 */

/* Primary architecture detection with cache-line-aligned prefetch distances.
 * Stride values are set to match cache line sizes (in pointer units):
 *   - x86-64: 64-byte cache lines = 8 pointers (8 bytes each)
 *   - Apple Silicon: 128-byte cache lines = 16 pointers
 *   - ARM64: 64-byte cache lines = 8 pointers
 * This ensures each prefetch brings in a new cache line without redundancy. */
#if defined(__x86_64__) || defined(_M_X64)
  /* Intel/AMD x86-64 Architecture - 64-byte cache lines = 8 pointers */
  #if defined(__AVX512F__)
    /* Skylake-X, Ice Lake, Zen4+ with 512-bit vectors */
    #define PREFETCH_DISTANCE 4
    #define PREFETCH_STRIDE 8
  #elif defined(__AVX2__)
    /* Haswell to Rocket Lake, Zen2/Zen3 with 256-bit vectors */
    #define PREFETCH_DISTANCE 4
    #define PREFETCH_STRIDE 8
  #elif defined(__AVX__)
    /* Sandy Bridge to Ivy Bridge with 256-bit vectors */
    #define PREFETCH_DISTANCE 4
    #define PREFETCH_STRIDE 8
  #else
    /* Legacy x86-64 (Core 2, early Zen) */
    #define PREFETCH_DISTANCE 3
    #define PREFETCH_STRIDE 8
  #endif

#elif defined(__aarch64__) || defined(_M_ARM64)
  /* ARM64 Architecture */
  #if defined(__APPLE__)
    /* Apple Silicon (M1/M2/M3/M4) - 128-byte cache lines = 16 pointers */
    #define PREFETCH_DISTANCE 4
    #define PREFETCH_STRIDE 16
  #elif defined(__ARM_FEATURE_SVE) || defined(__ARM_FEATURE_SVE2)
    /* ARM Neoverse V1/V2, Cortex-X2/X3 with SVE - 64-byte lines */
    #define PREFETCH_DISTANCE 4
    #define PREFETCH_STRIDE 8
  #elif defined(__ARM_NEON)
    /* Cortex-A78, A710, A715 with NEON - 64-byte lines */
    #define PREFETCH_DISTANCE 4
    #define PREFETCH_STRIDE 8
  #else
    /* Generic ARM64 - 64-byte lines */
    #define PREFETCH_DISTANCE 4
    #define PREFETCH_STRIDE 8
  #endif

#elif defined(__riscv) && (__riscv_xlen == 64)
  /* RISC-V 64-bit - typically 64-byte cache lines = 8 pointers */
  #if defined(__riscv_vector)
    /* RISC-V with Vector Extension */
    #define PREFETCH_DISTANCE 4
    #define PREFETCH_STRIDE 8
  #else
    /* Standard RISC-V */
    #define PREFETCH_DISTANCE 4
    #define PREFETCH_STRIDE 8
  #endif

#elif defined(__powerpc64__) || defined(_ARCH_PPC64)
  /* IBM POWER Architecture - 128-byte cache lines = 16 pointers */
  #define PREFETCH_DISTANCE 4
  #define PREFETCH_STRIDE 16

#else
  /* Generic/Unknown Architecture - assume 64-byte lines = 8 pointers */
  #define PREFETCH_DISTANCE 3
  #define PREFETCH_STRIDE 8
#endif

/* GPU/Accelerator Detection for Heterogeneous Computing */
#if defined(__CUDA_ARCH__)
  /* NVIDIA GPU Architecture - 128-byte cache lines = 16 pointers */
  #if __CUDA_ARCH__ >= 900
    /* Hopper (H100, H800) - 50MB L2, 192KB L1 */
    #undef PREFETCH_DISTANCE
    #define PREFETCH_DISTANCE 4
    #undef PREFETCH_STRIDE  
    #define PREFETCH_STRIDE 16
  #elif __CUDA_ARCH__ >= 800
    /* Ampere (A100, A40) - 40MB L2, 128KB L1 */
    #undef PREFETCH_DISTANCE
    #define PREFETCH_DISTANCE 4
    #undef PREFETCH_STRIDE
    #define PREFETCH_STRIDE 16
  #elif __CUDA_ARCH__ >= 700
    /* Volta/Turing (V100, RTX) - 6MB L2 */
    #undef PREFETCH_DISTANCE
    #define PREFETCH_DISTANCE 4
    #undef PREFETCH_STRIDE
    #define PREFETCH_STRIDE 16
  #endif
#endif

/* Advanced prefetching with stride-aware optimization */
#define PREFETCH_MULTIPLE_STRIDE(base, start, n, max, stride) do { \
  for (Py_ssize_t _i = 0; _i < PREFETCH_DISTANCE && (start) + (_i * (stride)) < (max); _i++) { \
    PREFETCH(&(base)[(start) + (_i * (stride))]); \
  } \
} while(0)

/* ============================================================================
 * NaN-Aware Comparison Macros for Homogeneous Float Paths
 * ============================================================================
 * These macros ensure consistent NaN handling across all float comparison paths.
 * NaN is treated as "largest" value, ensuring it sinks to the bottom of min-heaps
 * and rises to the top of max-heaps, matching the behavior of fast_compare().
 * 
 * IEEE 754 specifies that NaN comparisons return false, which would cause NaN
 * to "stick" in place during heapify. These macros override that behavior.
 */
#define HEAPX_FLOAT_LT(a, b) (unlikely(isnan(a)) ? 0 : (unlikely(isnan(b)) ? 1 : ((a) < (b))))
#define HEAPX_FLOAT_GT(a, b) (unlikely(isnan(a)) ? 1 : (unlikely(isnan(b)) ? 0 : ((a) > (b))))
#define HEAPX_FLOAT_LE(a, b) (unlikely(isnan(a)) ? isnan(b) : (unlikely(isnan(b)) ? 1 : ((a) <= (b))))
#define HEAPX_FLOAT_GE(a, b) (unlikely(isnan(a)) ? 1 : (unlikely(isnan(b)) ? isnan(a) : ((a) >= (b))))

/* Thread-safe stack buffer size for key arrays */
#define KEY_STACK_SIZE 128

/* Stack buffer size for homogeneous value arrays (2048 elements = 16KB for doubles) */
#define VALUE_STACK_SIZE 2048



/* ============================================================================
 * SIMD Helper Functions for Quaternary Heap Operations
 * ============================================================================
 * These functions find the index of the min/max value among 4 doubles.
 * Uses AVX/SSE2/NEON intrinsics when available, falls back to scalar.
 */

#if defined(HEAPX_HAS_AVX)
/* AVX implementation - processes all 4 doubles in parallel
 * Note: _CMP_LE_OQ and _CMP_GE_OQ are "ordered quiet" comparisons that
 * return false when either operand is NaN, which matches IEEE 754 semantics.
 * However, for heap correctness we need NaN to sink to the bottom (min-heap)
 * or rise to the top (max-heap). We handle this with post-SIMD NaN checks. */
static FORCE_INLINE Py_ssize_t
simd_find_min_index_4_doubles(const double * HEAPX_RESTRICT values) {
  /* Check for NaN - if any value is NaN, fall back to scalar with proper NaN handling */
  if (unlikely(isnan(values[0]) || isnan(values[1]) || isnan(values[2]) || isnan(values[3]))) {
    Py_ssize_t best = 0;
    double best_val = values[0];
    for (Py_ssize_t i = 1; i < 4; i++) {
      if (HEAPX_FLOAT_LT(values[i], best_val)) { best_val = values[i]; best = i; }
    }
    return best;
  }
  __m256d v = _mm256_loadu_pd(values);
  __m256d v_shuffled = _mm256_permute_pd(v, 0x05);
  __m256d cmp1 = _mm256_cmp_pd(v, v_shuffled, _CMP_LE_OQ);
  int mask = _mm256_movemask_pd(cmp1);
  
  double min01 = (mask & 1) ? values[0] : values[1];
  double min23 = (mask & 4) ? values[2] : values[3];
  Py_ssize_t idx01 = (mask & 1) ? 0 : 1;
  Py_ssize_t idx23 = (mask & 4) ? 2 : 3;
  
  return (min01 <= min23) ? idx01 : idx23;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_4_doubles(const double * HEAPX_RESTRICT values) {
  /* Check for NaN - if any value is NaN, fall back to scalar with proper NaN handling */
  if (unlikely(isnan(values[0]) || isnan(values[1]) || isnan(values[2]) || isnan(values[3]))) {
    Py_ssize_t best = 0;
    double best_val = values[0];
    for (Py_ssize_t i = 1; i < 4; i++) {
      if (HEAPX_FLOAT_GT(values[i], best_val)) { best_val = values[i]; best = i; }
    }
    return best;
  }
  __m256d v = _mm256_loadu_pd(values);
  __m256d v_shuffled = _mm256_permute_pd(v, 0x05);
  __m256d cmp1 = _mm256_cmp_pd(v, v_shuffled, _CMP_GE_OQ);
  int mask = _mm256_movemask_pd(cmp1);
  
  double max01 = (mask & 1) ? values[0] : values[1];
  double max23 = (mask & 4) ? values[2] : values[3];
  Py_ssize_t idx01 = (mask & 1) ? 0 : 1;
  Py_ssize_t idx23 = (mask & 4) ? 2 : 3;
  
  return (max01 >= max23) ? idx01 : idx23;
}

#elif defined(HEAPX_HAS_SSE2)
/* SSE2 implementation - processes 2 doubles at a time
 * Falls back to scalar for NaN handling to ensure correct heap ordering. */
static FORCE_INLINE Py_ssize_t
simd_find_min_index_4_doubles(const double * HEAPX_RESTRICT values) {
  /* Check for NaN - if any value is NaN, fall back to scalar with proper NaN handling */
  if (unlikely(isnan(values[0]) || isnan(values[1]) || isnan(values[2]) || isnan(values[3]))) {
    Py_ssize_t best = 0;
    double best_val = values[0];
    for (Py_ssize_t i = 1; i < 4; i++) {
      if (HEAPX_FLOAT_LT(values[i], best_val)) { best_val = values[i]; best = i; }
    }
    return best;
  }
  __m128d v01 = _mm_loadu_pd(values);
  __m128d v23 = _mm_loadu_pd(values + 2);
  
  __m128d v01_swap = _mm_shuffle_pd(v01, v01, 1);
  __m128d cmp01 = _mm_cmple_pd(v01, v01_swap);
  int mask01 = _mm_movemask_pd(cmp01);
  Py_ssize_t idx01 = (mask01 & 1) ? 0 : 1;
  double min01 = values[idx01];
  
  __m128d v23_swap = _mm_shuffle_pd(v23, v23, 1);
  __m128d cmp23 = _mm_cmple_pd(v23, v23_swap);
  int mask23 = _mm_movemask_pd(cmp23);
  Py_ssize_t idx23 = (mask23 & 1) ? 2 : 3;
  double min23 = values[idx23];
  
  return (min01 <= min23) ? idx01 : idx23;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_4_doubles(const double * HEAPX_RESTRICT values) {
  /* Check for NaN - if any value is NaN, fall back to scalar with proper NaN handling */
  if (unlikely(isnan(values[0]) || isnan(values[1]) || isnan(values[2]) || isnan(values[3]))) {
    Py_ssize_t best = 0;
    double best_val = values[0];
    for (Py_ssize_t i = 1; i < 4; i++) {
      if (HEAPX_FLOAT_GT(values[i], best_val)) { best_val = values[i]; best = i; }
    }
    return best;
  }
  __m128d v01 = _mm_loadu_pd(values);
  __m128d v23 = _mm_loadu_pd(values + 2);
  
  __m128d v01_swap = _mm_shuffle_pd(v01, v01, 1);
  __m128d cmp01 = _mm_cmpge_pd(v01, v01_swap);
  int mask01 = _mm_movemask_pd(cmp01);
  Py_ssize_t idx01 = (mask01 & 1) ? 0 : 1;
  double max01 = values[idx01];
  
  __m128d v23_swap = _mm_shuffle_pd(v23, v23, 1);
  __m128d cmp23 = _mm_cmpge_pd(v23, v23_swap);
  int mask23 = _mm_movemask_pd(cmp23);
  Py_ssize_t idx23 = (mask23 & 1) ? 2 : 3;
  double max23 = values[idx23];
  
  return (max01 >= max23) ? idx01 : idx23;
}

#elif defined(HEAPX_HAS_NEON)
/* ARM NEON implementation - uses 128-bit float64x2_t vectors
 * Falls back to scalar for NaN handling to ensure correct heap ordering. */
static FORCE_INLINE Py_ssize_t
simd_find_min_index_4_doubles(const double * HEAPX_RESTRICT values) {
  /* Check for NaN - if any value is NaN, fall back to scalar with proper NaN handling */
  if (unlikely(isnan(values[0]) || isnan(values[1]) || isnan(values[2]) || isnan(values[3]))) {
    Py_ssize_t best = 0;
    double best_val = values[0];
    for (Py_ssize_t i = 1; i < 4; i++) {
      if (HEAPX_FLOAT_LT(values[i], best_val)) { best_val = values[i]; best = i; }
    }
    return best;
  }
  float64x2_t v01 = vld1q_f64(values);
  float64x2_t v23 = vld1q_f64(values + 2);
  
  /* Compare pairs: find min of each pair */
  double min01 = vgetq_lane_f64(v01, 0) <= vgetq_lane_f64(v01, 1) ? vgetq_lane_f64(v01, 0) : vgetq_lane_f64(v01, 1);
  double min23 = vgetq_lane_f64(v23, 0) <= vgetq_lane_f64(v23, 1) ? vgetq_lane_f64(v23, 0) : vgetq_lane_f64(v23, 1);
  Py_ssize_t idx01 = vgetq_lane_f64(v01, 0) <= vgetq_lane_f64(v01, 1) ? 0 : 1;
  Py_ssize_t idx23 = vgetq_lane_f64(v23, 0) <= vgetq_lane_f64(v23, 1) ? 2 : 3;
  
  return (min01 <= min23) ? idx01 : idx23;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_4_doubles(const double * HEAPX_RESTRICT values) {
  /* Check for NaN - if any value is NaN, fall back to scalar with proper NaN handling */
  if (unlikely(isnan(values[0]) || isnan(values[1]) || isnan(values[2]) || isnan(values[3]))) {
    Py_ssize_t best = 0;
    double best_val = values[0];
    for (Py_ssize_t i = 1; i < 4; i++) {
      if (HEAPX_FLOAT_GT(values[i], best_val)) { best_val = values[i]; best = i; }
    }
    return best;
  }
  float64x2_t v01 = vld1q_f64(values);
  float64x2_t v23 = vld1q_f64(values + 2);
  
  /* Compare pairs: find max of each pair */
  double max01 = vgetq_lane_f64(v01, 0) >= vgetq_lane_f64(v01, 1) ? vgetq_lane_f64(v01, 0) : vgetq_lane_f64(v01, 1);
  double max23 = vgetq_lane_f64(v23, 0) >= vgetq_lane_f64(v23, 1) ? vgetq_lane_f64(v23, 0) : vgetq_lane_f64(v23, 1);
  Py_ssize_t idx01 = vgetq_lane_f64(v01, 0) >= vgetq_lane_f64(v01, 1) ? 0 : 1;
  Py_ssize_t idx23 = vgetq_lane_f64(v23, 0) >= vgetq_lane_f64(v23, 1) ? 2 : 3;
  
  return (max01 >= max23) ? idx01 : idx23;
}

#else
/* Scalar fallback for platforms without SIMD */
static FORCE_INLINE Py_ssize_t
simd_find_min_index_4_doubles(const double * HEAPX_RESTRICT values) {
  Py_ssize_t best = 0;
  double best_val = values[0];
  for (Py_ssize_t i = 1; i < 4; i++) {
    if (HEAPX_FLOAT_LT(values[i], best_val)) {
      best_val = values[i];
      best = i;
    }
  }
  return best;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_4_doubles(const double * HEAPX_RESTRICT values) {
  Py_ssize_t best = 0;
  double best_val = values[0];
  for (Py_ssize_t i = 1; i < 4; i++) {
    if (HEAPX_FLOAT_GT(values[i], best_val)) {
      best_val = values[i];
      best = i;
    }
  }
  return best;
}
#endif

/* ============================================================================
 * AVX2 8-Wide Double SIMD Functions for High-Arity Heaps
 * ============================================================================
 * These functions find min/max index among 8 doubles using full AVX2 width.
 * Provides ~1.5-2x speedup for arity >= 8 heaps with homogeneous float data.
 */

#if defined(HEAPX_HAS_AVX2)
/* AVX2: Find index of minimum value among 8 doubles */
static FORCE_INLINE Py_ssize_t
simd_find_min_index_8_doubles(const double * HEAPX_RESTRICT values) {
  __m256d v0 = _mm256_loadu_pd(values);
  __m256d v1 = _mm256_loadu_pd(values + 4);
  
  /* Element-wise minimum between the two halves */
  __m256d min01 = _mm256_min_pd(v0, v1);
  
  /* Horizontal reduction to find global minimum */
  __m128d lo = _mm256_castpd256_pd128(min01);
  __m128d hi = _mm256_extractf128_pd(min01, 1);
  __m128d min2 = _mm_min_pd(lo, hi);
  __m128d min2_swap = _mm_shuffle_pd(min2, min2, 1);
  __m128d final = _mm_min_pd(min2, min2_swap);
  double min_val = _mm_cvtsd_f64(final);
  
  /* Find first index matching minimum using SIMD comparison */
  __m256d min_broadcast = _mm256_set1_pd(min_val);
  __m256d cmp0 = _mm256_cmp_pd(v0, min_broadcast, _CMP_EQ_OQ);
  int mask0 = _mm256_movemask_pd(cmp0);
  if (mask0) {
    /* Use bit scan to find first set bit */
    #if defined(__GNUC__) || defined(__clang__)
    return __builtin_ctz((unsigned int)mask0);
    #elif defined(_MSC_VER)
    unsigned long idx;
    _BitScanForward(&idx, (unsigned long)mask0);
    return (Py_ssize_t)idx;
    #else
    for (int i = 0; i < 4; i++) if (mask0 & (1 << i)) return i;
    #endif
  }
  
  __m256d cmp1 = _mm256_cmp_pd(v1, min_broadcast, _CMP_EQ_OQ);
  int mask1 = _mm256_movemask_pd(cmp1);
  #if defined(__GNUC__) || defined(__clang__)
  return 4 + __builtin_ctz((unsigned int)mask1);
  #elif defined(_MSC_VER)
  unsigned long idx;
  _BitScanForward(&idx, (unsigned long)mask1);
  return 4 + (Py_ssize_t)idx;
  #else
  for (int i = 0; i < 4; i++) if (mask1 & (1 << i)) return 4 + i;
  return 4;
  #endif
}

/* AVX2: Find index of maximum value among 8 doubles */
static FORCE_INLINE Py_ssize_t
simd_find_max_index_8_doubles(const double * HEAPX_RESTRICT values) {
  __m256d v0 = _mm256_loadu_pd(values);
  __m256d v1 = _mm256_loadu_pd(values + 4);
  
  /* Element-wise maximum between the two halves */
  __m256d max01 = _mm256_max_pd(v0, v1);
  
  /* Horizontal reduction to find global maximum */
  __m128d lo = _mm256_castpd256_pd128(max01);
  __m128d hi = _mm256_extractf128_pd(max01, 1);
  __m128d max2 = _mm_max_pd(lo, hi);
  __m128d max2_swap = _mm_shuffle_pd(max2, max2, 1);
  __m128d final = _mm_max_pd(max2, max2_swap);
  double max_val = _mm_cvtsd_f64(final);
  
  /* Find first index matching maximum using SIMD comparison */
  __m256d max_broadcast = _mm256_set1_pd(max_val);
  __m256d cmp0 = _mm256_cmp_pd(v0, max_broadcast, _CMP_EQ_OQ);
  int mask0 = _mm256_movemask_pd(cmp0);
  if (mask0) {
    #if defined(__GNUC__) || defined(__clang__)
    return __builtin_ctz((unsigned int)mask0);
    #elif defined(_MSC_VER)
    unsigned long idx;
    _BitScanForward(&idx, (unsigned long)mask0);
    return (Py_ssize_t)idx;
    #else
    for (int i = 0; i < 4; i++) if (mask0 & (1 << i)) return i;
    #endif
  }
  
  __m256d cmp1 = _mm256_cmp_pd(v1, max_broadcast, _CMP_EQ_OQ);
  int mask1 = _mm256_movemask_pd(cmp1);
  #if defined(__GNUC__) || defined(__clang__)
  return 4 + __builtin_ctz((unsigned int)mask1);
  #elif defined(_MSC_VER)
  unsigned long idx;
  _BitScanForward(&idx, (unsigned long)mask1);
  return 4 + (Py_ssize_t)idx;
  #else
  for (int i = 0; i < 4; i++) if (mask1 & (1 << i)) return 4 + i;
  return 4;
  #endif
}
#endif /* HEAPX_HAS_AVX2 */

/* NEON implementation for 8-wide double functions */
#if defined(HEAPX_HAS_NEON) && !defined(HEAPX_HAS_AVX2)
static FORCE_INLINE Py_ssize_t
simd_find_min_index_8_doubles(const double * HEAPX_RESTRICT values) {
  /* Process as two groups of 4 using NEON */
  float64x2_t v01 = vld1q_f64(values);
  float64x2_t v23 = vld1q_f64(values + 2);
  float64x2_t v45 = vld1q_f64(values + 4);
  float64x2_t v67 = vld1q_f64(values + 6);
  
  /* Find min in first group (0-3) */
  double min01 = vgetq_lane_f64(v01, 0) <= vgetq_lane_f64(v01, 1) ? vgetq_lane_f64(v01, 0) : vgetq_lane_f64(v01, 1);
  double min23 = vgetq_lane_f64(v23, 0) <= vgetq_lane_f64(v23, 1) ? vgetq_lane_f64(v23, 0) : vgetq_lane_f64(v23, 1);
  Py_ssize_t idx01 = vgetq_lane_f64(v01, 0) <= vgetq_lane_f64(v01, 1) ? 0 : 1;
  Py_ssize_t idx23 = vgetq_lane_f64(v23, 0) <= vgetq_lane_f64(v23, 1) ? 2 : 3;
  double min_first = (min01 <= min23) ? min01 : min23;
  Py_ssize_t idx_first = (min01 <= min23) ? idx01 : idx23;
  
  /* Find min in second group (4-7) */
  double min45 = vgetq_lane_f64(v45, 0) <= vgetq_lane_f64(v45, 1) ? vgetq_lane_f64(v45, 0) : vgetq_lane_f64(v45, 1);
  double min67 = vgetq_lane_f64(v67, 0) <= vgetq_lane_f64(v67, 1) ? vgetq_lane_f64(v67, 0) : vgetq_lane_f64(v67, 1);
  Py_ssize_t idx45 = vgetq_lane_f64(v45, 0) <= vgetq_lane_f64(v45, 1) ? 4 : 5;
  Py_ssize_t idx67 = vgetq_lane_f64(v67, 0) <= vgetq_lane_f64(v67, 1) ? 6 : 7;
  double min_second = (min45 <= min67) ? min45 : min67;
  Py_ssize_t idx_second = (min45 <= min67) ? idx45 : idx67;
  
  return (min_first <= min_second) ? idx_first : idx_second;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_8_doubles(const double * HEAPX_RESTRICT values) {
  /* Process as two groups of 4 using NEON */
  float64x2_t v01 = vld1q_f64(values);
  float64x2_t v23 = vld1q_f64(values + 2);
  float64x2_t v45 = vld1q_f64(values + 4);
  float64x2_t v67 = vld1q_f64(values + 6);
  
  /* Find max in first group (0-3) */
  double max01 = vgetq_lane_f64(v01, 0) >= vgetq_lane_f64(v01, 1) ? vgetq_lane_f64(v01, 0) : vgetq_lane_f64(v01, 1);
  double max23 = vgetq_lane_f64(v23, 0) >= vgetq_lane_f64(v23, 1) ? vgetq_lane_f64(v23, 0) : vgetq_lane_f64(v23, 1);
  Py_ssize_t idx01 = vgetq_lane_f64(v01, 0) >= vgetq_lane_f64(v01, 1) ? 0 : 1;
  Py_ssize_t idx23 = vgetq_lane_f64(v23, 0) >= vgetq_lane_f64(v23, 1) ? 2 : 3;
  double max_first = (max01 >= max23) ? max01 : max23;
  Py_ssize_t idx_first = (max01 >= max23) ? idx01 : idx23;
  
  /* Find max in second group (4-7) */
  double max45 = vgetq_lane_f64(v45, 0) >= vgetq_lane_f64(v45, 1) ? vgetq_lane_f64(v45, 0) : vgetq_lane_f64(v45, 1);
  double max67 = vgetq_lane_f64(v67, 0) >= vgetq_lane_f64(v67, 1) ? vgetq_lane_f64(v67, 0) : vgetq_lane_f64(v67, 1);
  Py_ssize_t idx45 = vgetq_lane_f64(v45, 0) >= vgetq_lane_f64(v45, 1) ? 4 : 5;
  Py_ssize_t idx67 = vgetq_lane_f64(v67, 0) >= vgetq_lane_f64(v67, 1) ? 6 : 7;
  double max_second = (max45 >= max67) ? max45 : max67;
  Py_ssize_t idx_second = (max45 >= max67) ? idx45 : idx67;
  
  return (max_first >= max_second) ? idx_first : idx_second;
}

/* Scalar fallback for 8-wide double functions when neither AVX2 nor NEON available */
#elif !defined(HEAPX_HAS_AVX2) && !defined(HEAPX_HAS_NEON)
static FORCE_INLINE Py_ssize_t
simd_find_min_index_8_doubles(const double * HEAPX_RESTRICT values) {
  Py_ssize_t best = 0;
  double best_val = values[0];
  for (Py_ssize_t i = 1; i < 8; i++) {
    if (HEAPX_FLOAT_LT(values[i], best_val)) { best_val = values[i]; best = i; }
  }
  return best;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_8_doubles(const double * HEAPX_RESTRICT values) {
  Py_ssize_t best = 0;
  double best_val = values[0];
  for (Py_ssize_t i = 1; i < 8; i++) {
    if (HEAPX_FLOAT_GT(values[i], best_val)) { best_val = values[i]; best = i; }
  }
  return best;
}
#endif /* !HEAPX_HAS_AVX2 */

/* ============================================================================
 * SIMD Helper Functions for 64-bit Integers
 * ============================================================================
 * AVX2 provides native 64-bit integer comparison via _mm256_cmpgt_epi64.
 * Falls back to scalar on platforms without AVX2.
 */

#if defined(HEAPX_HAS_AVX2)
/* AVX2: Find index of minimum value among 4 longs (64-bit integers) */
static FORCE_INLINE Py_ssize_t
simd_find_min_index_4_longs(const long * HEAPX_RESTRICT values) {
  __m256i v = _mm256_loadu_si256((const __m256i*)values);
  
  /* Compare pairs: v[0] vs v[2], v[1] vs v[3] using permute */
  __m256i v_perm = _mm256_permute4x64_epi64(v, 0x4E); /* [2,3,0,1] */
  __m256i cmp1 = _mm256_cmpgt_epi64(v, v_perm); /* v > v_perm */
  __m256i min1 = _mm256_blendv_epi8(v, v_perm, cmp1); /* select smaller */
  
  /* Now min1 has: min(v[0],v[2]), min(v[1],v[3]), min(v[2],v[0]), min(v[3],v[1]) */
  /* Compare adjacent pairs */
  __m256i min1_swap = _mm256_shuffle_epi32(min1, 0x4E); /* swap 64-bit halves within 128-bit lanes */
  __m256i cmp2 = _mm256_cmpgt_epi64(min1, min1_swap);
  
  /* Extract minimum value */
  long min_val;
  int cmp2_mask = _mm256_movemask_epi8(cmp2);
  if (cmp2_mask & 0xFF) {
    /* min1_swap[0] is smaller */
    min_val = _mm256_extract_epi64(min1_swap, 0);
  } else {
    min_val = _mm256_extract_epi64(min1, 0);
  }
  
  /* Find index using SIMD comparison */
  __m256i min_broadcast = _mm256_set1_epi64x(min_val);
  __m256i cmp = _mm256_cmpeq_epi64(v, min_broadcast);
  int mask = _mm256_movemask_epi8(cmp);
  
  /* Each 64-bit lane produces 8 mask bits when equal */
  if (mask & 0xFF) return 0;
  if (mask & 0xFF00) return 1;
  if (mask & 0xFF0000) return 2;
  return 3;
}

/* AVX2: Find index of maximum value among 4 longs (64-bit integers) */
static FORCE_INLINE Py_ssize_t
simd_find_max_index_4_longs(const long * HEAPX_RESTRICT values) {
  __m256i v = _mm256_loadu_si256((const __m256i*)values);
  
  /* Compare pairs using permute */
  __m256i v_perm = _mm256_permute4x64_epi64(v, 0x4E);
  __m256i cmp1 = _mm256_cmpgt_epi64(v, v_perm);
  __m256i max1 = _mm256_blendv_epi8(v_perm, v, cmp1); /* select larger */
  
  /* Compare adjacent pairs */
  __m256i max1_swap = _mm256_shuffle_epi32(max1, 0x4E);
  __m256i cmp2 = _mm256_cmpgt_epi64(max1, max1_swap);
  
  /* Extract maximum value */
  long max_val;
  int cmp2_mask = _mm256_movemask_epi8(cmp2);
  if (cmp2_mask & 0xFF) {
    max_val = _mm256_extract_epi64(max1, 0);
  } else {
    max_val = _mm256_extract_epi64(max1_swap, 0);
  }
  
  /* Find index using SIMD comparison */
  __m256i max_broadcast = _mm256_set1_epi64x(max_val);
  __m256i cmp = _mm256_cmpeq_epi64(v, max_broadcast);
  int mask = _mm256_movemask_epi8(cmp);
  
  if (mask & 0xFF) return 0;
  if (mask & 0xFF00) return 1;
  if (mask & 0xFF0000) return 2;
  return 3;
}

/* AVX2: Find index of minimum value among 8 longs */
static FORCE_INLINE Py_ssize_t
simd_find_min_index_8_longs(const long * HEAPX_RESTRICT values) {
  __m256i v0 = _mm256_loadu_si256((const __m256i*)values);
  __m256i v1 = _mm256_loadu_si256((const __m256i*)(values + 4));
  
  /* Element-wise minimum between the two halves */
  __m256i cmp01 = _mm256_cmpgt_epi64(v0, v1);
  __m256i min01 = _mm256_blendv_epi8(v0, v1, cmp01);
  
  /* Horizontal reduction within min01 */
  __m256i min01_perm = _mm256_permute4x64_epi64(min01, 0x4E);
  __m256i cmp2 = _mm256_cmpgt_epi64(min01, min01_perm);
  __m256i min2 = _mm256_blendv_epi8(min01, min01_perm, cmp2);
  
  __m256i min2_swap = _mm256_shuffle_epi32(min2, 0x4E);
  __m256i cmp3 = _mm256_cmpgt_epi64(min2, min2_swap);
  
  long min_val;
  int cmp3_mask = _mm256_movemask_epi8(cmp3);
  if (cmp3_mask & 0xFF) {
    min_val = _mm256_extract_epi64(min2_swap, 0);
  } else {
    min_val = _mm256_extract_epi64(min2, 0);
  }
  
  /* Find first index matching minimum */
  __m256i min_broadcast = _mm256_set1_epi64x(min_val);
  __m256i cmp_v0 = _mm256_cmpeq_epi64(v0, min_broadcast);
  int mask0 = _mm256_movemask_epi8(cmp_v0);
  
  if (mask0 & 0xFF) return 0;
  if (mask0 & 0xFF00) return 1;
  if (mask0 & 0xFF0000) return 2;
  if (mask0 & 0xFF000000) return 3;
  
  __m256i cmp_v1 = _mm256_cmpeq_epi64(v1, min_broadcast);
  int mask1 = _mm256_movemask_epi8(cmp_v1);
  
  if (mask1 & 0xFF) return 4;
  if (mask1 & 0xFF00) return 5;
  if (mask1 & 0xFF0000) return 6;
  return 7;
}

/* AVX2: Find index of maximum value among 8 longs */
static FORCE_INLINE Py_ssize_t
simd_find_max_index_8_longs(const long * HEAPX_RESTRICT values) {
  __m256i v0 = _mm256_loadu_si256((const __m256i*)values);
  __m256i v1 = _mm256_loadu_si256((const __m256i*)(values + 4));
  
  /* Element-wise maximum between the two halves */
  __m256i cmp01 = _mm256_cmpgt_epi64(v0, v1);
  __m256i max01 = _mm256_blendv_epi8(v1, v0, cmp01);
  
  /* Horizontal reduction within max01 */
  __m256i max01_perm = _mm256_permute4x64_epi64(max01, 0x4E);
  __m256i cmp2 = _mm256_cmpgt_epi64(max01, max01_perm);
  __m256i max2 = _mm256_blendv_epi8(max01_perm, max01, cmp2);
  
  __m256i max2_swap = _mm256_shuffle_epi32(max2, 0x4E);
  __m256i cmp3 = _mm256_cmpgt_epi64(max2, max2_swap);
  
  long max_val;
  int cmp3_mask = _mm256_movemask_epi8(cmp3);
  if (cmp3_mask & 0xFF) {
    max_val = _mm256_extract_epi64(max2, 0);
  } else {
    max_val = _mm256_extract_epi64(max2_swap, 0);
  }
  
  /* Find first index matching maximum */
  __m256i max_broadcast = _mm256_set1_epi64x(max_val);
  __m256i cmp_v0 = _mm256_cmpeq_epi64(v0, max_broadcast);
  int mask0 = _mm256_movemask_epi8(cmp_v0);
  
  if (mask0 & 0xFF) return 0;
  if (mask0 & 0xFF00) return 1;
  if (mask0 & 0xFF0000) return 2;
  if (mask0 & 0xFF000000) return 3;
  
  __m256i cmp_v1 = _mm256_cmpeq_epi64(v1, max_broadcast);
  int mask1 = _mm256_movemask_epi8(cmp_v1);
  
  if (mask1 & 0xFF) return 4;
  if (mask1 & 0xFF00) return 5;
  if (mask1 & 0xFF0000) return 6;
  return 7;
}

#else
/* NEON implementation for platforms with ARM NEON */
#if defined(HEAPX_HAS_NEON)
static FORCE_INLINE Py_ssize_t
simd_find_min_index_4_longs(const long * HEAPX_RESTRICT values) {
  int64x2_t v01 = vld1q_s64((const int64_t*)values);
  int64x2_t v23 = vld1q_s64((const int64_t*)(values + 2));
  
  /* Compare pairs to find min */
  int64_t val0 = vgetq_lane_s64(v01, 0);
  int64_t val1 = vgetq_lane_s64(v01, 1);
  int64_t val2 = vgetq_lane_s64(v23, 0);
  int64_t val3 = vgetq_lane_s64(v23, 1);
  
  int64_t min01 = (val0 <= val1) ? val0 : val1;
  int64_t min23 = (val2 <= val3) ? val2 : val3;
  Py_ssize_t idx01 = (val0 <= val1) ? 0 : 1;
  Py_ssize_t idx23 = (val2 <= val3) ? 2 : 3;
  
  return (min01 <= min23) ? idx01 : idx23;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_4_longs(const long * HEAPX_RESTRICT values) {
  int64x2_t v01 = vld1q_s64((const int64_t*)values);
  int64x2_t v23 = vld1q_s64((const int64_t*)(values + 2));
  
  /* Compare pairs to find max */
  int64_t val0 = vgetq_lane_s64(v01, 0);
  int64_t val1 = vgetq_lane_s64(v01, 1);
  int64_t val2 = vgetq_lane_s64(v23, 0);
  int64_t val3 = vgetq_lane_s64(v23, 1);
  
  int64_t max01 = (val0 >= val1) ? val0 : val1;
  int64_t max23 = (val2 >= val3) ? val2 : val3;
  Py_ssize_t idx01 = (val0 >= val1) ? 0 : 1;
  Py_ssize_t idx23 = (val2 >= val3) ? 2 : 3;
  
  return (max01 >= max23) ? idx01 : idx23;
}

static FORCE_INLINE Py_ssize_t
simd_find_min_index_8_longs(const long * HEAPX_RESTRICT values) {
  /* Load all 8 values using NEON */
  int64x2_t v01 = vld1q_s64((const int64_t*)values);
  int64x2_t v23 = vld1q_s64((const int64_t*)(values + 2));
  int64x2_t v45 = vld1q_s64((const int64_t*)(values + 4));
  int64x2_t v67 = vld1q_s64((const int64_t*)(values + 6));
  
  /* Find min in first group (0-3) */
  int64_t val0 = vgetq_lane_s64(v01, 0), val1 = vgetq_lane_s64(v01, 1);
  int64_t val2 = vgetq_lane_s64(v23, 0), val3 = vgetq_lane_s64(v23, 1);
  int64_t min01 = (val0 <= val1) ? val0 : val1;
  int64_t min23 = (val2 <= val3) ? val2 : val3;
  Py_ssize_t idx01 = (val0 <= val1) ? 0 : 1;
  Py_ssize_t idx23 = (val2 <= val3) ? 2 : 3;
  int64_t min_first = (min01 <= min23) ? min01 : min23;
  Py_ssize_t idx_first = (min01 <= min23) ? idx01 : idx23;
  
  /* Find min in second group (4-7) */
  int64_t val4 = vgetq_lane_s64(v45, 0), val5 = vgetq_lane_s64(v45, 1);
  int64_t val6 = vgetq_lane_s64(v67, 0), val7 = vgetq_lane_s64(v67, 1);
  int64_t min45 = (val4 <= val5) ? val4 : val5;
  int64_t min67 = (val6 <= val7) ? val6 : val7;
  Py_ssize_t idx45 = (val4 <= val5) ? 4 : 5;
  Py_ssize_t idx67 = (val6 <= val7) ? 6 : 7;
  int64_t min_second = (min45 <= min67) ? min45 : min67;
  Py_ssize_t idx_second = (min45 <= min67) ? idx45 : idx67;
  
  return (min_first <= min_second) ? idx_first : idx_second;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_8_longs(const long * HEAPX_RESTRICT values) {
  /* Load all 8 values using NEON */
  int64x2_t v01 = vld1q_s64((const int64_t*)values);
  int64x2_t v23 = vld1q_s64((const int64_t*)(values + 2));
  int64x2_t v45 = vld1q_s64((const int64_t*)(values + 4));
  int64x2_t v67 = vld1q_s64((const int64_t*)(values + 6));
  
  /* Find max in first group (0-3) */
  int64_t val0 = vgetq_lane_s64(v01, 0), val1 = vgetq_lane_s64(v01, 1);
  int64_t val2 = vgetq_lane_s64(v23, 0), val3 = vgetq_lane_s64(v23, 1);
  int64_t max01 = (val0 >= val1) ? val0 : val1;
  int64_t max23 = (val2 >= val3) ? val2 : val3;
  Py_ssize_t idx01 = (val0 >= val1) ? 0 : 1;
  Py_ssize_t idx23 = (val2 >= val3) ? 2 : 3;
  int64_t max_first = (max01 >= max23) ? max01 : max23;
  Py_ssize_t idx_first = (max01 >= max23) ? idx01 : idx23;
  
  /* Find max in second group (4-7) */
  int64_t val4 = vgetq_lane_s64(v45, 0), val5 = vgetq_lane_s64(v45, 1);
  int64_t val6 = vgetq_lane_s64(v67, 0), val7 = vgetq_lane_s64(v67, 1);
  int64_t max45 = (val4 >= val5) ? val4 : val5;
  int64_t max67 = (val6 >= val7) ? val6 : val7;
  Py_ssize_t idx45 = (val4 >= val5) ? 4 : 5;
  Py_ssize_t idx67 = (val6 >= val7) ? 6 : 7;
  int64_t max_second = (max45 >= max67) ? max45 : max67;
  Py_ssize_t idx_second = (max45 >= max67) ? idx45 : idx67;
  
  return (max_first >= max_second) ? idx_first : idx_second;
}

#else
/* Scalar fallback for platforms without AVX2 or NEON */
static FORCE_INLINE Py_ssize_t
simd_find_min_index_4_longs(const long * HEAPX_RESTRICT values) {
  long min01 = (values[0] <= values[1]) ? values[0] : values[1];
  long min23 = (values[2] <= values[3]) ? values[2] : values[3];
  Py_ssize_t idx01 = (values[0] <= values[1]) ? 0 : 1;
  Py_ssize_t idx23 = (values[2] <= values[3]) ? 2 : 3;
  return (min01 <= min23) ? idx01 : idx23;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_4_longs(const long * HEAPX_RESTRICT values) {
  long max01 = (values[0] >= values[1]) ? values[0] : values[1];
  long max23 = (values[2] >= values[3]) ? values[2] : values[3];
  Py_ssize_t idx01 = (values[0] >= values[1]) ? 0 : 1;
  Py_ssize_t idx23 = (values[2] >= values[3]) ? 2 : 3;
  return (max01 >= max23) ? idx01 : idx23;
}

static FORCE_INLINE Py_ssize_t
simd_find_min_index_8_longs(const long * HEAPX_RESTRICT values) {
  Py_ssize_t best = 0;
  long best_val = values[0];
  for (Py_ssize_t i = 1; i < 8; i++) {
    if (values[i] < best_val) { best_val = values[i]; best = i; }
  }
  return best;
}

static FORCE_INLINE Py_ssize_t
simd_find_max_index_8_longs(const long * HEAPX_RESTRICT values) {
  Py_ssize_t best = 0;
  long best_val = values[0];
  for (Py_ssize_t i = 1; i < 8; i++) {
    if (values[i] > best_val) { best_val = values[i]; best = i; }
  }
  return best;
}
#endif /* HEAPX_HAS_NEON */
#endif /* HEAPX_HAS_AVX2 */

/* SIMD-optimized best child finder for longs with 8-wide AVX2 acceleration */
static FORCE_INLINE Py_ssize_t
simd_find_best_child_long(const long * HEAPX_RESTRICT values,
                          Py_ssize_t n_children, int is_max) {
  Py_ssize_t best = 0;
  long best_val = values[0];
  Py_ssize_t i = 0;
  
#if defined(HEAPX_HAS_AVX2)
  /* Process groups of 8 using AVX2 for high-arity heaps */
  Py_ssize_t simd8_end = n_children - 7;
  for (; i < simd8_end; i += 8) {
    Py_ssize_t group_best = is_max
      ? simd_find_max_index_8_longs(values + i)
      : simd_find_min_index_8_longs(values + i);
    Py_ssize_t idx = i + group_best;
    if (is_max ? (values[idx] > best_val) : (values[idx] < best_val)) {
      best_val = values[idx];
      best = idx;
    }
  }
#endif
  
  /* Process groups of 4 */
  Py_ssize_t simd4_end = n_children - 3;
  for (; i < simd4_end; i += 4) {
    Py_ssize_t group_best = is_max
      ? simd_find_max_index_4_longs(values + i)
      : simd_find_min_index_4_longs(values + i);
    Py_ssize_t idx = i + group_best;
    if (is_max ? (values[idx] > best_val) : (values[idx] < best_val)) {
      best_val = values[idx];
      best = idx;
    }
  }
  
  /* Handle remainder (1-3 elements) */
  Py_ssize_t rem = n_children - i;
  if (rem > 0) {
    long padded[4];
    padded[0] = values[i];
    padded[1] = (rem > 1) ? values[i + 1] : (is_max ? LONG_MIN : LONG_MAX);
    padded[2] = (rem > 2) ? values[i + 2] : (is_max ? LONG_MIN : LONG_MAX);
    padded[3] = (is_max ? LONG_MIN : LONG_MAX);
    
    Py_ssize_t group_best = is_max
      ? simd_find_max_index_4_longs(padded)
      : simd_find_min_index_4_longs(padded);
    if (group_best < rem) {
      Py_ssize_t idx = i + group_best;
      if (is_max ? (values[idx] > best_val) : (values[idx] < best_val)) {
        best = idx;
      }
    }
  }
  return best;
}

/* SIMD-optimized best child finder with 8-wide AVX2 acceleration for floats */
static FORCE_INLINE Py_ssize_t
simd_find_best_child_float(const double * HEAPX_RESTRICT values,
                           Py_ssize_t n_children, int is_max) {
  Py_ssize_t best = 0;
  double best_val = values[0];
  Py_ssize_t i = 0;
  
#if defined(HEAPX_HAS_AVX2)
  /* Process groups of 8 using AVX2 for high-arity heaps */
  Py_ssize_t simd8_end = n_children - 7;
  for (; i < simd8_end; i += 8) {
    Py_ssize_t group_best = is_max
      ? simd_find_max_index_8_doubles(values + i)
      : simd_find_min_index_8_doubles(values + i);
    Py_ssize_t idx = i + group_best;
    if (is_max ? HEAPX_FLOAT_GT(values[idx], best_val) : HEAPX_FLOAT_LT(values[idx], best_val)) {
      best_val = values[idx];
      best = idx;
    }
  }
#endif
  
  /* Process groups of 4 using SIMD */
  Py_ssize_t simd4_end = n_children - 3;
  for (; i < simd4_end; i += 4) {
    Py_ssize_t group_best = is_max
      ? simd_find_max_index_4_doubles(values + i)
      : simd_find_min_index_4_doubles(values + i);
    Py_ssize_t idx = i + group_best;
    if (is_max ? HEAPX_FLOAT_GT(values[idx], best_val) : HEAPX_FLOAT_LT(values[idx], best_val)) {
      best_val = values[idx];
      best = idx;
    }
  }
  
  /* Handle remainder (1-3 elements) with padded SIMD */
  Py_ssize_t rem = n_children - i;
  if (rem > 0) {
    double padded[4];
    padded[0] = values[i];
    padded[1] = (rem > 1) ? values[i + 1] : (is_max ? -DBL_MAX : DBL_MAX);
    padded[2] = (rem > 2) ? values[i + 2] : (is_max ? -DBL_MAX : DBL_MAX);
    padded[3] = (is_max ? -DBL_MAX : DBL_MAX);
    
    Py_ssize_t group_best = is_max
      ? simd_find_max_index_4_doubles(padded)
      : simd_find_min_index_4_doubles(padded);
    if (group_best < rem) {
      Py_ssize_t idx = i + group_best;
      if (is_max ? HEAPX_FLOAT_GT(values[idx], best_val) : HEAPX_FLOAT_LT(values[idx], best_val)) {
        best = idx;
      }
    }
  }
  return best;
}

/* Enhanced fast comparison for comprehensive Python type coverage */
static inline int
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
    
    /* Check for NaN using compiler intrinsic */
    int a_is_nan = isnan(val_a);
    int b_is_nan = isnan(val_b);
    
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

/* SIMD-accelerated homogeneous array detection for vectorization opportunities.
 * Uses SIMD to compare type pointers in batches, providing hyper-robust scanning. */
static int
detect_homogeneous_type(PyObject **items, Py_ssize_t n) {
  const Py_ssize_t MIN_SIZE = 8; /* Minimum size for SIMD benefits */

  if (unlikely(n < MIN_SIZE)) return 0;

  /* Determine candidate type from first element */
  PyTypeObject *first_type = Py_TYPE(items[0]);
  int candidate;
  if (first_type == &PyLong_Type) {
    candidate = 1; /* integers */
  } else if (first_type == &PyFloat_Type) {
    candidate = 2; /* floats */
  } else if (first_type == &PyUnicode_Type) {
    candidate = 3; /* strings - added for string SIMD optimization */
  } else {
    return 0; /* Not a SIMD-optimizable type */
  }

  Py_ssize_t i = 1;

#if defined(HEAPX_HAS_AVX2)
  /* AVX2: Compare 4 type pointers at once (256-bit = 4 × 64-bit pointers) */
  __m256i target_type = _mm256_set1_epi64x((int64_t)first_type);
  Py_ssize_t simd_end = n - 3;
  
  for (; i < simd_end; i += 4) {
    /* Load 4 object pointers */
    PyObject *obj0 = items[i];
    PyObject *obj1 = items[i + 1];
    PyObject *obj2 = items[i + 2];
    PyObject *obj3 = items[i + 3];
    
    /* Extract type pointers and pack into SIMD register */
    __m256i types = _mm256_set_epi64x(
      (int64_t)Py_TYPE(obj3),
      (int64_t)Py_TYPE(obj2),
      (int64_t)Py_TYPE(obj1),
      (int64_t)Py_TYPE(obj0)
    );
    
    /* Compare all 4 types against target */
    __m256i cmp = _mm256_cmpeq_epi64(types, target_type);
    int mask = _mm256_movemask_epi8(cmp);
    
    /* All 4 must match: mask should be 0xFFFFFFFF (all 32 bytes equal) */
    if (mask != (int)0xFFFFFFFF) return 0;
  }

#elif defined(HEAPX_HAS_SSE2)
  /* SSE2: Compare 2 type pointers at once (128-bit = 2 × 64-bit pointers) */
  __m128i target_type = _mm_set1_epi64x((int64_t)first_type);
  Py_ssize_t simd_end = n - 1;
  
  for (; i < simd_end; i += 2) {
    PyObject *obj0 = items[i];
    PyObject *obj1 = items[i + 1];
    
    __m128i types = _mm_set_epi64x(
      (int64_t)Py_TYPE(obj1),
      (int64_t)Py_TYPE(obj0)
    );
    
    __m128i cmp = _mm_cmpeq_epi32(types, target_type);
    int mask = _mm_movemask_epi8(cmp);
    
    /* All 2 must match: mask should be 0xFFFF (all 16 bytes equal) */
    if (mask != 0xFFFF) return 0;
  }

#elif defined(HEAPX_HAS_NEON)
  /* ARM NEON: Compare 2 type pointers at once (128-bit = 2 × 64-bit pointers) */
  int64x2_t target_type = vdupq_n_s64((int64_t)first_type);
  Py_ssize_t simd_end = n - 1;
  
  for (; i < simd_end; i += 2) {
    /* Use proper NEON intrinsics for portable vector creation */
    int64x2_t types = vcombine_s64(
      vcreate_s64((uint64_t)Py_TYPE(items[i])),
      vcreate_s64((uint64_t)Py_TYPE(items[i + 1]))
    );
    
    uint64x2_t cmp = vceqq_s64(types, target_type);
    /* Both lanes must be all-ones (0xFFFFFFFFFFFFFFFF) */
    if (vgetq_lane_u64(cmp, 0) != ~0ULL || vgetq_lane_u64(cmp, 1) != ~0ULL) return 0;
  }

#else
  /* Scalar fallback: process 4 elements per iteration for better ILP */
  Py_ssize_t scalar_end = n - 3;
  for (; i < scalar_end; i += 4) {
    if (Py_TYPE(items[i]) != first_type ||
        Py_TYPE(items[i + 1]) != first_type ||
        Py_TYPE(items[i + 2]) != first_type ||
        Py_TYPE(items[i + 3]) != first_type) {
      return 0;
    }
  }
#endif

  /* Handle remaining elements (scalar) */
  for (; i < n; i++) {
    if (Py_TYPE(items[i]) != first_type) return 0;
  }

  return candidate;
}

/* Bottom-up heapify for homogeneous float arrays - ~25% fewer comparisons */
/* Fast single-threaded version - direct object movement */
HOT_FUNCTION static int
list_heapify_homogeneous_float(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  double stack_values[VALUE_STACK_SIZE];
  double * HEAPX_RESTRICT values;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
  } else {
    values = (double *)PyMem_Malloc(sizeof(double) * (size_t)n);
    if (unlikely(!values)) { PyErr_NoMemory(); return -1; }
  }

  HEAPX_PRAGMA_SIMD
  for (Py_ssize_t i = 0; i < n; i++) {
    values[i] = PyFloat_AS_DOUBLE(items[i]);
  }

  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    Py_ssize_t pos = i;
    double val = values[i];
    PyObject *obj = items[i];
    
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (child >= n) break;
      if (likely(child + 1 < n)) {
        if (is_max ? HEAPX_FLOAT_GT(values[child + 1], values[child]) : HEAPX_FLOAT_LT(values[child + 1], values[child]))
          child++;
      }
      values[pos] = values[child];
      items[pos] = items[child];
      pos = child;
    }
    
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      if (is_max ? HEAPX_FLOAT_LE(val, values[parent]) : HEAPX_FLOAT_GE(val, values[parent])) break;
      values[pos] = values[parent];
      items[pos] = items[parent];
      pos = parent;
    }
    values[pos] = val;
    items[pos] = obj;
  }
  
  if (!use_stack) PyMem_Free(values);
  return 0;
}

/* GIL-releasing version for multi-threaded environments */
HOT_FUNCTION static int
list_heapify_homogeneous_float_nogil(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  /* Allocate values and indices arrays */
  double stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  double * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
    indices = stack_indices;
  } else {
    values = (double *)PyMem_Malloc(sizeof(double) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    if (unlikely(!values || !indices)) {
      PyMem_Free(values);
      PyMem_Free(indices);
      PyErr_NoMemory();
      return -1;
    }
  }

  /* PHASE 1: Extract values and initialize indices (GIL held) */
  HEAPX_PRAGMA_SIMD
  for (Py_ssize_t i = 0; i < n; i++) {
    values[i] = PyFloat_AS_DOUBLE(items[i]);
    indices[i] = i;
  }

  /* PHASE 2: Pure C heapify on values/indices arrays (GIL RELEASED) */
  Py_BEGIN_ALLOW_THREADS
  
  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    Py_ssize_t pos = i;
    double val = values[i];
    Py_ssize_t idx = indices[i];
    
    /* Descend to leaf, only comparing children */
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (child >= n) break;
      if (likely(child + 1 < n)) {
        if (is_max ? HEAPX_FLOAT_GT(values[child + 1], values[child]) : HEAPX_FLOAT_LT(values[child + 1], values[child]))
          child++;
      }
      values[pos] = values[child];
      indices[pos] = indices[child];
      pos = child;
    }
    
    /* Bubble up from leaf position */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      if (is_max ? HEAPX_FLOAT_LE(val, values[parent]) : HEAPX_FLOAT_GE(val, values[parent])) break;
      values[pos] = values[parent];
      indices[pos] = indices[parent];
      pos = parent;
    }
    values[pos] = val;
    indices[pos] = idx;
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and rearrange Python objects (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
    PyErr_SetString(PyExc_ValueError,
        "list modified by another thread during heapify");
    return -1;
  }
  
  /* Quick check: if no elements moved, skip permutation entirely */
  int needs_permutation = 0;
  for (Py_ssize_t i = 0; i < n; i++) {
    if (indices[i] != i) { needs_permutation = 1; break; }
  }
  
  if (needs_permutation) {
    /* Refresh items pointer and rearrange using cycle-following */
    items = listobj->ob_item;
    for (Py_ssize_t i = 0; i < n; i++) {
      if (indices[i] == i || indices[i] < 0) continue;
      
      Py_ssize_t j = i;
      PyObject *temp = items[i];
      
      while (indices[j] != i) {
        Py_ssize_t next = indices[j];
        items[j] = items[next];
        indices[j] = -1 - indices[j];
        j = next;
      }
      items[j] = temp;
      indices[j] = -1 - indices[j];
    }
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
  return 0;
}

/* =============================================================================
 * HOMOGENEOUS STRING HEAPIFY
 * Optimized for arrays of Unicode strings using direct memcmp comparison.
 * Avoids Python comparison overhead for homogeneous string arrays.
 * ============================================================================= */

/* Fast string comparison for heapify - returns -1, 0, or 1 */
static inline int
fast_string_compare(PyObject *a, PyObject *b) {
  Py_ssize_t len_a = PyUnicode_GET_LENGTH(a);
  Py_ssize_t len_b = PyUnicode_GET_LENGTH(b);
  int kind_a = PyUnicode_KIND(a);
  int kind_b = PyUnicode_KIND(b);
  
  if (likely(kind_a == kind_b)) {
    void *data_a = PyUnicode_DATA(a);
    void *data_b = PyUnicode_DATA(b);
    Py_ssize_t min_len = len_a < len_b ? len_a : len_b;
    int cmp;
    
    switch (kind_a) {
      case PyUnicode_1BYTE_KIND:
        cmp = memcmp(data_a, data_b, min_len);
        break;
      case PyUnicode_2BYTE_KIND:
        cmp = memcmp(data_a, data_b, min_len * 2);
        break;
      case PyUnicode_4BYTE_KIND:
        cmp = memcmp(data_a, data_b, min_len * 4);
        break;
      default:
        cmp = 0;
    }
    
    if (cmp == 0) return (len_a > len_b) - (len_a < len_b);
    return cmp < 0 ? -1 : 1;
  }
  
  /* Different kinds - fall back to Python comparison */
  int result = PyObject_RichCompareBool(a, b, Py_LT);
  if (result < 0) return 0;  /* Error */
  return result ? -1 : (PyObject_RichCompareBool(a, b, Py_GT) > 0 ? 1 : 0);
}

/* Bottom-up heapify for homogeneous string arrays */
HOT_FUNCTION static int
list_heapify_homogeneous_string(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = listobj->ob_item;

  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *item = items[pos];
    Py_INCREF(item);
    
    /* Phase 1: Descend to leaf */
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (child >= n) break;
      
      if (likely(child + 1 < n)) {
        int cmp = fast_string_compare(items[child + 1], items[child]);
        if (is_max ? cmp > 0 : cmp < 0) child++;
      }
      
      items[pos] = items[child];
      pos = child;
    }
    
    /* Phase 2: Bubble up from leaf position */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      int cmp = fast_string_compare(item, items[parent]);
      if (is_max ? cmp <= 0 : cmp >= 0) break;
      items[pos] = items[parent];
      pos = parent;
    }
    
    items[pos] = item;
    Py_DECREF(item);
  }
  
  return 0;
}

/* Ternary heap for homogeneous float arrays - scalar C comparisons */
/* Fast single-threaded version - direct object movement */
HOT_FUNCTION static int
list_heapify_ternary_homogeneous_float(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  double stack_values[VALUE_STACK_SIZE];
  double * HEAPX_RESTRICT values;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
  } else {
    values = (double *)PyMem_Malloc(sizeof(double) * (size_t)n);
    if (unlikely(!values)) { PyErr_NoMemory(); return -1; }
  }

  HEAPX_PRAGMA_SIMD
  for (Py_ssize_t i = 0; i < n; i++) values[i] = PyFloat_AS_DOUBLE(items[i]);

  for (Py_ssize_t i = (n - 2) / 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    double val = values[i];
    PyObject *obj = items[i];
    
    while (1) {
      Py_ssize_t c1 = 3 * pos + 1;
      if (c1 >= n) break;
      Py_ssize_t best = c1;
      double best_val = values[c1];
      if (likely(c1 + 1 < n) && (is_max ? HEAPX_FLOAT_GT(values[c1+1], best_val) : HEAPX_FLOAT_LT(values[c1+1], best_val))) { best = c1+1; best_val = values[c1+1]; }
      if (likely(c1 + 2 < n) && (is_max ? HEAPX_FLOAT_GT(values[c1+2], best_val) : HEAPX_FLOAT_LT(values[c1+2], best_val))) { best = c1+2; }
      values[pos] = values[best]; items[pos] = items[best]; pos = best;
    }
    
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 3;
      if (is_max ? HEAPX_FLOAT_LE(val, values[parent]) : HEAPX_FLOAT_GE(val, values[parent])) break;
      values[pos] = values[parent]; items[pos] = items[parent]; pos = parent;
    }
    values[pos] = val; items[pos] = obj;
  }
  
  if (!use_stack) PyMem_Free(values);
  return 0;
}

/* GIL-releasing version for multi-threaded environments */
HOT_FUNCTION static int
list_heapify_ternary_homogeneous_float_nogil(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  /* Allocate values and indices arrays */
  double stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  double * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
    indices = stack_indices;
  } else {
    values = (double *)PyMem_Malloc(sizeof(double) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    if (unlikely(!values || !indices)) {
      PyMem_Free(values);
      PyMem_Free(indices);
      PyErr_NoMemory();
      return -1;
    }
  }

  /* PHASE 1: Extract values and initialize indices (GIL held) */
  HEAPX_PRAGMA_SIMD
  for (Py_ssize_t i = 0; i < n; i++) {
    values[i] = PyFloat_AS_DOUBLE(items[i]);
    indices[i] = i;
  }

  /* PHASE 2: Pure C ternary heapify (GIL RELEASED) */
  Py_BEGIN_ALLOW_THREADS
  
  for (Py_ssize_t i = (n - 2) / 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    double val = values[i];
    Py_ssize_t idx = indices[i];
    
    /* Descend to leaf */
    while (1) {
      Py_ssize_t c1 = 3 * pos + 1;
      if (c1 >= n) break;
      Py_ssize_t best = c1;
      double best_val = values[c1];
      if (likely(c1 + 1 < n) && (is_max ? HEAPX_FLOAT_GT(values[c1+1], best_val) : HEAPX_FLOAT_LT(values[c1+1], best_val))) { best = c1+1; best_val = values[c1+1]; }
      if (likely(c1 + 2 < n) && (is_max ? HEAPX_FLOAT_GT(values[c1+2], best_val) : HEAPX_FLOAT_LT(values[c1+2], best_val))) { best = c1+2; }
      values[pos] = values[best];
      indices[pos] = indices[best];
      pos = best;
    }
    
    /* Bubble up */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 3;
      if (is_max ? HEAPX_FLOAT_LE(val, values[parent]) : HEAPX_FLOAT_GE(val, values[parent])) break;
      values[pos] = values[parent];
      indices[pos] = indices[parent];
      pos = parent;
    }
    values[pos] = val;
    indices[pos] = idx;
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and rearrange Python objects (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
    PyErr_SetString(PyExc_ValueError,
        "list modified by another thread during heapify");
    return -1;
  }
  
  /* Quick check: if no elements moved, skip permutation entirely */
  int needs_permutation = 0;
  for (Py_ssize_t i = 0; i < n; i++) {
    if (indices[i] != i) { needs_permutation = 1; break; }
  }
  
  if (needs_permutation) {
    items = listobj->ob_item;
    for (Py_ssize_t i = 0; i < n; i++) {
      if (indices[i] == i || indices[i] < 0) continue;
      Py_ssize_t j = i;
      PyObject *temp = items[i];
      while (indices[j] != i) {
        Py_ssize_t next = indices[j];
        items[j] = items[next];
        indices[j] = -1 - indices[j];
        j = next;
      }
      items[j] = temp;
      indices[j] = -1 - indices[j];
    }
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
  return 0;
}

/* Bottom-up ternary heap for homogeneous int arrays */
/* Fast single-threaded version - direct object movement */
HOT_FUNCTION static int
list_heapify_ternary_homogeneous_int(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  long stack_values[VALUE_STACK_SIZE];
  long * HEAPX_RESTRICT values;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
  } else {
    values = (long *)PyMem_Malloc(sizeof(long) * (size_t)n);
    if (unlikely(!values)) { PyErr_NoMemory(); return -1; }
  }

  for (Py_ssize_t i = 0; i < n; i++) {
    int overflow = 0;
    values[i] = PyLong_AsLongAndOverflow(items[i], &overflow);
    if (unlikely(overflow != 0)) { if (!use_stack) PyMem_Free(values); return 2; }
    if (unlikely(values[i] == -1 && PyErr_Occurred())) { if (!use_stack) PyMem_Free(values); return -1; }
  }

  for (Py_ssize_t i = (n - 2) / 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    long val = values[i];
    PyObject *obj = items[i];
    
    while (1) {
      Py_ssize_t c1 = 3 * pos + 1;
      if (c1 >= n) break;
      Py_ssize_t best = c1;
      long best_val = values[c1];
      if (likely(c1 + 1 < n) && (is_max ? values[c1+1] > best_val : values[c1+1] < best_val)) { best = c1+1; best_val = values[c1+1]; }
      if (likely(c1 + 2 < n) && (is_max ? values[c1+2] > best_val : values[c1+2] < best_val)) { best = c1+2; }
      values[pos] = values[best]; items[pos] = items[best]; pos = best;
    }
    
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 3;
      if (is_max ? (val <= values[parent]) : (val >= values[parent])) break;
      values[pos] = values[parent]; items[pos] = items[parent]; pos = parent;
    }
    values[pos] = val; items[pos] = obj;
  }
  
  if (!use_stack) PyMem_Free(values);
  return 0;
}

/* GIL-releasing version for multi-threaded environments */
HOT_FUNCTION static int
list_heapify_ternary_homogeneous_int_nogil(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  /* Allocate values and indices arrays */
  long stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  long * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
    indices = stack_indices;
  } else {
    values = (long *)PyMem_Malloc(sizeof(long) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    if (unlikely(!values || !indices)) {
      PyMem_Free(values);
      PyMem_Free(indices);
      PyErr_NoMemory();
      return -1;
    }
  }

  /* PHASE 1: Extract values and initialize indices (GIL held) */
  for (Py_ssize_t i = 0; i < n; i++) {
    int overflow = 0;
    values[i] = PyLong_AsLongAndOverflow(items[i], &overflow);
    if (unlikely(overflow != 0)) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
      return 2;
    }
    if (unlikely(values[i] == -1 && PyErr_Occurred())) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
      return -1;
    }
    indices[i] = i;
  }

  /* PHASE 2: Pure C ternary heapify (GIL RELEASED) */
  Py_BEGIN_ALLOW_THREADS
  
  for (Py_ssize_t i = (n - 2) / 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    long val = values[i];
    Py_ssize_t idx = indices[i];
    
    /* Descend to leaf */
    while (1) {
      Py_ssize_t c1 = 3 * pos + 1;
      if (c1 >= n) break;
      Py_ssize_t best = c1;
      long best_val = values[c1];
      if (likely(c1 + 1 < n) && (is_max ? values[c1+1] > best_val : values[c1+1] < best_val)) { best = c1+1; best_val = values[c1+1]; }
      if (likely(c1 + 2 < n) && (is_max ? values[c1+2] > best_val : values[c1+2] < best_val)) { best = c1+2; }
      values[pos] = values[best];
      indices[pos] = indices[best];
      pos = best;
    }
    
    /* Bubble up */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 3;
      if (is_max ? (val <= values[parent]) : (val >= values[parent])) break;
      values[pos] = values[parent];
      indices[pos] = indices[parent];
      pos = parent;
    }
    values[pos] = val;
    indices[pos] = idx;
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and rearrange Python objects (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
    PyErr_SetString(PyExc_ValueError,
        "list modified by another thread during heapify");
    return -1;
  }
  
  /* Quick check: if no elements moved, skip permutation entirely */
  int needs_permutation = 0;
  for (Py_ssize_t i = 0; i < n; i++) {
    if (indices[i] != i) { needs_permutation = 1; break; }
  }
  
  if (needs_permutation) {
    items = listobj->ob_item;
    for (Py_ssize_t i = 0; i < n; i++) {
      if (indices[i] == i || indices[i] < 0) continue;
      Py_ssize_t j = i;
      PyObject *temp = items[i];
      while (indices[j] != i) {
        Py_ssize_t next = indices[j];
        items[j] = items[next];
        indices[j] = -1 - indices[j];
        j = next;
      }
      items[j] = temp;
      indices[j] = -1 - indices[j];
    }
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
  return 0;
}

/* Bottom-up SIMD-Optimized Quaternary Heap for Homogeneous Float Arrays */
/* Fast single-threaded version - direct object movement */
HOT_FUNCTION static int
list_heapify_quaternary_homogeneous_float(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  double stack_values[VALUE_STACK_SIZE];
  double * HEAPX_RESTRICT values;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 32);
  } else {
    values = (double *)PyMem_Malloc(sizeof(double) * (size_t)n);
    if (unlikely(!values)) { PyErr_NoMemory(); return -1; }
  }

  HEAPX_PRAGMA_SIMD
  for (Py_ssize_t i = 0; i < n; i++) {
    values[i] = PyFloat_AS_DOUBLE(items[i]);
  }

  for (Py_ssize_t i = (n - 2) / 4; i >= 0; i--) {
    Py_ssize_t pos = i;
    double val = values[i];
    PyObject *obj = items[i];
    
    while (1) {
      Py_ssize_t first_child = 4 * pos + 1;
      if (first_child >= n) break;
      
      Py_ssize_t n_children = n - first_child;
      if (n_children > 4) n_children = 4;
      
      Py_ssize_t best_offset = simd_find_best_child_float(values + first_child, n_children, is_max);
      Py_ssize_t best = first_child + best_offset;
      
      values[pos] = values[best];
      items[pos] = items[best];
      pos = best;
    }
    
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 4;
      if (is_max ? HEAPX_FLOAT_LE(val, values[parent]) : HEAPX_FLOAT_GE(val, values[parent])) break;
      values[pos] = values[parent];
      items[pos] = items[parent];
      pos = parent;
    }
    
    values[pos] = val;
    items[pos] = obj;
  }
  
  if (!use_stack) PyMem_Free(values);
  return 0;
}

/* GIL-releasing version for multi-threaded environments */
HOT_FUNCTION static int
list_heapify_quaternary_homogeneous_float_nogil(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  /* Allocate values and indices arrays */
  double stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  double * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 32);
    indices = stack_indices;
  } else {
    values = (double *)PyMem_Malloc(sizeof(double) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    if (unlikely(!values || !indices)) {
      PyMem_Free(values);
      PyMem_Free(indices);
      PyErr_NoMemory();
      return -1;
    }
  }

  /* PHASE 1: Extract values and initialize indices (GIL held) */
  HEAPX_PRAGMA_SIMD
  for (Py_ssize_t i = 0; i < n; i++) {
    values[i] = PyFloat_AS_DOUBLE(items[i]);
    indices[i] = i;
  }

  /* PHASE 2: Pure C quaternary heapify (GIL RELEASED) */
  Py_BEGIN_ALLOW_THREADS
  
  for (Py_ssize_t i = (n - 2) / 4; i >= 0; i--) {
    Py_ssize_t pos = i;
    double val = values[i];
    Py_ssize_t idx = indices[i];
    
    /* Descend to leaf */
    while (1) {
      Py_ssize_t first_child = 4 * pos + 1;
      if (first_child >= n) break;
      
      Py_ssize_t n_children = n - first_child;
      if (n_children > 4) n_children = 4;
      
      Py_ssize_t best_offset = simd_find_best_child_float(values + first_child, n_children, is_max);
      Py_ssize_t best = first_child + best_offset;
      
      values[pos] = values[best];
      indices[pos] = indices[best];
      pos = best;
    }
    
    /* Bubble up */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 4;
      if (is_max ? HEAPX_FLOAT_LE(val, values[parent]) : HEAPX_FLOAT_GE(val, values[parent])) break;
      values[pos] = values[parent];
      indices[pos] = indices[parent];
      pos = parent;
    }
    
    values[pos] = val;
    indices[pos] = idx;
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and rearrange Python objects (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
    PyErr_SetString(PyExc_ValueError,
        "list modified by another thread during heapify");
    return -1;
  }
  
  /* Quick check: if no elements moved, skip permutation entirely */
  int needs_permutation = 0;
  for (Py_ssize_t i = 0; i < n; i++) {
    if (indices[i] != i) { needs_permutation = 1; break; }
  }
  
  if (needs_permutation) {
    items = listobj->ob_item;
    for (Py_ssize_t i = 0; i < n; i++) {
      if (indices[i] == i || indices[i] < 0) continue;
      Py_ssize_t j = i;
      PyObject *temp = items[i];
      while (indices[j] != i) {
        Py_ssize_t next = indices[j];
        items[j] = items[next];
        indices[j] = -1 - indices[j];
        j = next;
      }
      items[j] = temp;
      indices[j] = -1 - indices[j];
    }
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
  return 0;
}

/* Bottom-up SIMD-Optimized Quaternary Heap for Homogeneous Integer Arrays */
/* Fast single-threaded version - direct object movement */
HOT_FUNCTION static int
list_heapify_quaternary_homogeneous_int(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  long stack_values[VALUE_STACK_SIZE];
  long * HEAPX_RESTRICT values;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
  } else {
    values = (long *)PyMem_Malloc(sizeof(long) * (size_t)n);
    if (unlikely(!values)) { PyErr_NoMemory(); return -1; }
  }

  for (Py_ssize_t i = 0; i < n; i++) {
    int overflow = 0;
    values[i] = PyLong_AsLongAndOverflow(items[i], &overflow);
    if (unlikely(overflow != 0)) { if (!use_stack) PyMem_Free(values); return 2; }
    if (unlikely(values[i] == -1 && PyErr_Occurred())) { if (!use_stack) PyMem_Free(values); return -1; }
  }

  for (Py_ssize_t i = (n - 2) / 4; i >= 0; i--) {
    Py_ssize_t pos = i;
    long val = values[i];
    PyObject *obj = items[i];
    
    while (1) {
      Py_ssize_t first_child = 4 * pos + 1;
      if (first_child >= n) break;
      
      Py_ssize_t n_children = n - first_child;
      if (n_children > 4) n_children = 4;
      
      Py_ssize_t best_offset = simd_find_best_child_long(values + first_child, n_children, is_max);
      Py_ssize_t best = first_child + best_offset;
      
      values[pos] = values[best];
      items[pos] = items[best];
      pos = best;
    }
    
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 4;
      if (is_max ? (val <= values[parent]) : (val >= values[parent])) break;
      values[pos] = values[parent];
      items[pos] = items[parent];
      pos = parent;
    }
    
    values[pos] = val;
    items[pos] = obj;
  }
  
  if (!use_stack) PyMem_Free(values);
  return 0;
}

/* GIL-releasing version for multi-threaded environments */
HOT_FUNCTION static int
list_heapify_quaternary_homogeneous_int_nogil(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  /* Allocate values and indices arrays */
  long stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  long * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
    indices = stack_indices;
  } else {
    values = (long *)PyMem_Malloc(sizeof(long) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    if (unlikely(!values || !indices)) {
      PyMem_Free(values);
      PyMem_Free(indices);
      PyErr_NoMemory();
      return -1;
    }
  }

  /* PHASE 1: Extract values and initialize indices (GIL held) */
  for (Py_ssize_t i = 0; i < n; i++) {
    int overflow = 0;
    values[i] = PyLong_AsLongAndOverflow(items[i], &overflow);
    if (unlikely(overflow != 0)) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
      return 2;
    }
    if (unlikely(values[i] == -1 && PyErr_Occurred())) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
      return -1;
    }
    indices[i] = i;
  }

  /* PHASE 2: Pure C quaternary heapify (GIL RELEASED) */
  Py_BEGIN_ALLOW_THREADS
  
  for (Py_ssize_t i = (n - 2) / 4; i >= 0; i--) {
    Py_ssize_t pos = i;
    long val = values[i];
    Py_ssize_t idx = indices[i];
    
    /* Descend to leaf */
    while (1) {
      Py_ssize_t first_child = 4 * pos + 1;
      if (first_child >= n) break;
      
      Py_ssize_t n_children = n - first_child;
      if (n_children > 4) n_children = 4;
      
      Py_ssize_t best_offset = simd_find_best_child_long(values + first_child, n_children, is_max);
      Py_ssize_t best = first_child + best_offset;
      
      values[pos] = values[best];
      indices[pos] = indices[best];
      pos = best;
    }
    
    /* Bubble up */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 4;
      if (is_max ? (val <= values[parent]) : (val >= values[parent])) break;
      values[pos] = values[parent];
      indices[pos] = indices[parent];
      pos = parent;
    }
    
    values[pos] = val;
    indices[pos] = idx;
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and rearrange Python objects (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
    PyErr_SetString(PyExc_ValueError,
        "list modified by another thread during heapify");
    return -1;
  }
  
  /* Quick check: if no elements moved, skip permutation entirely */
  int needs_permutation = 0;
  for (Py_ssize_t i = 0; i < n; i++) {
    if (indices[i] != i) { needs_permutation = 1; break; }
  }
  
  if (needs_permutation) {
    items = listobj->ob_item;
    for (Py_ssize_t i = 0; i < n; i++) {
      if (indices[i] == i || indices[i] < 0) continue;
      Py_ssize_t j = i;
      PyObject *temp = items[i];
      while (indices[j] != i) {
        Py_ssize_t next = indices[j];
        items[j] = items[next];
        indices[j] = -1 - indices[j];
        j = next;
      }
      items[j] = temp;
      indices[j] = -1 - indices[j];
    }
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
  return 0;
}

/* Bottom-up SIMD-Optimized N-ary Heap for homogeneous floats, arity >= 5 */
/* Fast single-threaded version - direct object movement */
HOT_FUNCTION static int
list_heapify_nary_simd_homogeneous_float(PyListObject *listobj, int is_max, Py_ssize_t arity)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  double stack_values[VALUE_STACK_SIZE];
  double * HEAPX_RESTRICT values;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 32);
  } else {
    values = (double *)PyMem_Malloc(sizeof(double) * (size_t)n);
    if (unlikely(!values)) { PyErr_NoMemory(); return -1; }
  }

  HEAPX_PRAGMA_SIMD
  for (Py_ssize_t i = 0; i < n; i++) {
    values[i] = PyFloat_AS_DOUBLE(items[i]);
  }

  for (Py_ssize_t i = (n - 2) / arity; i >= 0; i--) {
    Py_ssize_t pos = i;
    double val = values[i];
    PyObject *obj = items[i];
    
    while (1) {
      Py_ssize_t first_child = arity * pos + 1;
      if (first_child >= n) break;
      
      Py_ssize_t n_children = n - first_child;
      if (n_children > arity) n_children = arity;
      
      Py_ssize_t best_offset = simd_find_best_child_float(values + first_child, n_children, is_max);
      Py_ssize_t best = first_child + best_offset;
      
      values[pos] = values[best];
      items[pos] = items[best];
      pos = best;
    }
    
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / arity;
      if (is_max ? HEAPX_FLOAT_LE(val, values[parent]) : HEAPX_FLOAT_GE(val, values[parent])) break;
      values[pos] = values[parent];
      items[pos] = items[parent];
      pos = parent;
    }
    
    values[pos] = val;
    items[pos] = obj;
  }
  
  if (!use_stack) PyMem_Free(values);
  return 0;
}

/* GIL-releasing version for multi-threaded environments */
HOT_FUNCTION static int
list_heapify_nary_simd_homogeneous_float_nogil(PyListObject *listobj, int is_max, Py_ssize_t arity)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  /* Allocate values and indices arrays */
  double stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  double * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 32);
    indices = stack_indices;
  } else {
    values = (double *)PyMem_Malloc(sizeof(double) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    if (unlikely(!values || !indices)) {
      PyMem_Free(values);
      PyMem_Free(indices);
      PyErr_NoMemory();
      return -1;
    }
  }

  /* PHASE 1: Extract values and initialize indices (GIL held) */
  HEAPX_PRAGMA_SIMD
  for (Py_ssize_t i = 0; i < n; i++) {
    values[i] = PyFloat_AS_DOUBLE(items[i]);
    indices[i] = i;
  }

  /* PHASE 2: Pure C n-ary heapify (GIL RELEASED) */
  Py_BEGIN_ALLOW_THREADS
  
  for (Py_ssize_t i = (n - 2) / arity; i >= 0; i--) {
    Py_ssize_t pos = i;
    double val = values[i];
    Py_ssize_t idx = indices[i];
    
    /* Descend to leaf */
    while (1) {
      Py_ssize_t first_child = arity * pos + 1;
      if (first_child >= n) break;
      
      Py_ssize_t n_children = n - first_child;
      if (n_children > arity) n_children = arity;
      
      Py_ssize_t best_offset = simd_find_best_child_float(values + first_child, n_children, is_max);
      Py_ssize_t best = first_child + best_offset;
      
      values[pos] = values[best];
      indices[pos] = indices[best];
      pos = best;
    }
    
    /* Bubble up */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / arity;
      if (is_max ? HEAPX_FLOAT_LE(val, values[parent]) : HEAPX_FLOAT_GE(val, values[parent])) break;
      values[pos] = values[parent];
      indices[pos] = indices[parent];
      pos = parent;
    }
    
    values[pos] = val;
    indices[pos] = idx;
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and rearrange Python objects (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
    PyErr_SetString(PyExc_ValueError,
        "list modified by another thread during heapify");
    return -1;
  }
  
  /* Quick check: if no elements moved, skip permutation entirely */
  int needs_permutation = 0;
  for (Py_ssize_t i = 0; i < n; i++) {
    if (indices[i] != i) { needs_permutation = 1; break; }
  }
  
  if (needs_permutation) {
    items = listobj->ob_item;
    for (Py_ssize_t i = 0; i < n; i++) {
      if (indices[i] == i || indices[i] < 0) continue;
      Py_ssize_t j = i;
      PyObject *temp = items[i];
      while (indices[j] != i) {
        Py_ssize_t next = indices[j];
        items[j] = items[next];
        indices[j] = -1 - indices[j];
        j = next;
      }
      items[j] = temp;
      indices[j] = -1 - indices[j];
    }
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
  return 0;
}

/* Bottom-up SIMD-Optimized N-ary Heap for homogeneous integers, arity >= 5 */
/* Fast single-threaded version - direct object movement */
HOT_FUNCTION static int
list_heapify_nary_simd_homogeneous_int(PyListObject *listobj, int is_max, Py_ssize_t arity)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  long stack_values[VALUE_STACK_SIZE];
  long * HEAPX_RESTRICT values;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
  } else {
    values = (long *)PyMem_Malloc(sizeof(long) * (size_t)n);
    if (unlikely(!values)) { PyErr_NoMemory(); return -1; }
  }

  for (Py_ssize_t i = 0; i < n; i++) {
    int overflow = 0;
    values[i] = PyLong_AsLongAndOverflow(items[i], &overflow);
    if (unlikely(overflow != 0)) { if (!use_stack) PyMem_Free(values); return 2; }
    if (unlikely(values[i] == -1 && PyErr_Occurred())) { if (!use_stack) PyMem_Free(values); return -1; }
  }

  for (Py_ssize_t i = (n - 2) / arity; i >= 0; i--) {
    Py_ssize_t pos = i;
    long val = values[i];
    PyObject *obj = items[i];
    
    while (1) {
      Py_ssize_t first_child = arity * pos + 1;
      if (first_child >= n) break;
      
      Py_ssize_t n_children = n - first_child;
      if (n_children > arity) n_children = arity;
      
      Py_ssize_t best_offset = simd_find_best_child_long(values + first_child, n_children, is_max);
      Py_ssize_t best = first_child + best_offset;
      
      values[pos] = values[best];
      items[pos] = items[best];
      pos = best;
    }
    
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / arity;
      if (is_max ? (val <= values[parent]) : (val >= values[parent])) break;
      values[pos] = values[parent];
      items[pos] = items[parent];
      pos = parent;
    }
    
    values[pos] = val;
    items[pos] = obj;
  }
  
  if (!use_stack) PyMem_Free(values);
  return 0;
}

/* GIL-releasing version for multi-threaded environments */
HOT_FUNCTION static int
list_heapify_nary_simd_homogeneous_int_nogil(PyListObject *listobj, int is_max, Py_ssize_t arity)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  /* Allocate values and indices arrays */
  long stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  long * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
    indices = stack_indices;
  } else {
    values = (long *)PyMem_Malloc(sizeof(long) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    if (unlikely(!values || !indices)) {
      PyMem_Free(values);
      PyMem_Free(indices);
      PyErr_NoMemory();
      return -1;
    }
  }

  /* PHASE 1: Extract values and initialize indices (GIL held) */
  for (Py_ssize_t i = 0; i < n; i++) {
    int overflow = 0;
    values[i] = PyLong_AsLongAndOverflow(items[i], &overflow);
    if (unlikely(overflow != 0)) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
      return 2;
    }
    if (unlikely(values[i] == -1 && PyErr_Occurred())) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
      return -1;
    }
    indices[i] = i;
  }

  /* PHASE 2: Pure C n-ary heapify (GIL RELEASED) */
  Py_BEGIN_ALLOW_THREADS
  
  for (Py_ssize_t i = (n - 2) / arity; i >= 0; i--) {
    Py_ssize_t pos = i;
    long val = values[i];
    Py_ssize_t idx = indices[i];
    
    /* Descend to leaf */
    while (1) {
      Py_ssize_t first_child = arity * pos + 1;
      if (first_child >= n) break;
      
      Py_ssize_t n_children = n - first_child;
      if (n_children > arity) n_children = arity;
      
      Py_ssize_t best_offset = simd_find_best_child_long(values + first_child, n_children, is_max);
      Py_ssize_t best = first_child + best_offset;
      
      values[pos] = values[best];
      indices[pos] = indices[best];
      pos = best;
    }
    
    /* Bubble up */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / arity;
      if (is_max ? (val <= values[parent]) : (val >= values[parent])) break;
      values[pos] = values[parent];
      indices[pos] = indices[parent];
      pos = parent;
    }
    
    values[pos] = val;
    indices[pos] = idx;
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and rearrange Python objects (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
    PyErr_SetString(PyExc_ValueError,
        "list modified by another thread during heapify");
    return -1;
  }
  
  /* Quick check: if no elements moved, skip permutation entirely */
  int needs_permutation = 0;
  for (Py_ssize_t i = 0; i < n; i++) {
    if (indices[i] != i) { needs_permutation = 1; break; }
  }
  
  if (needs_permutation) {
    items = listobj->ob_item;
    for (Py_ssize_t i = 0; i < n; i++) {
      if (indices[i] == i || indices[i] < 0) continue;
      Py_ssize_t j = i;
      PyObject *temp = items[i];
      while (indices[j] != i) {
        Py_ssize_t next = indices[j];
        items[j] = items[next];
        indices[j] = -1 - indices[j];
        j = next;
      }
      items[j] = temp;
      indices[j] = -1 - indices[j];
    }
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
  return 0;
}

/* Bottom-up heapify for homogeneous integer arrays */
/* Fast single-threaded version - direct object movement */
/* Returns: 0 = success, -1 = error, 2 = overflow (fallback to generic) */
HOT_FUNCTION static int
list_heapify_homogeneous_int(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  long stack_values[VALUE_STACK_SIZE];
  long * HEAPX_RESTRICT values;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
  } else {
    values = (long *)PyMem_Malloc(sizeof(long) * (size_t)n);
    if (unlikely(!values)) { PyErr_NoMemory(); return -1; }
  }

  for (Py_ssize_t i = 0; i < n; i++) {
    int overflow = 0;
    values[i] = PyLong_AsLongAndOverflow(items[i], &overflow);
    if (unlikely(overflow != 0)) { if (!use_stack) PyMem_Free(values); return 2; }
    if (unlikely(values[i] == -1 && PyErr_Occurred())) { if (!use_stack) PyMem_Free(values); return -1; }
  }

  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    Py_ssize_t pos = i;
    long val = values[i];
    PyObject *obj = items[i];
    
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (child >= n) break;
      if (likely(child + 1 < n)) {
        if (is_max ? (values[child + 1] > values[child]) : (values[child + 1] < values[child]))
          child++;
      }
      values[pos] = values[child];
      items[pos] = items[child];
      pos = child;
    }
    
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      if (is_max ? (val <= values[parent]) : (val >= values[parent])) break;
      values[pos] = values[parent];
      items[pos] = items[parent];
      pos = parent;
    }
    values[pos] = val;
    items[pos] = obj;
  }
  
  if (!use_stack) PyMem_Free(values);
  return 0;
}

/* GIL-releasing version for multi-threaded environments */
/* Returns: 0 = success, -1 = error, 2 = overflow (fallback to generic) */
HOT_FUNCTION static int
list_heapify_homogeneous_int_nogil(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  /* Allocate values and indices arrays */
  long stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  long * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
    indices = stack_indices;
  } else {
    values = (long *)PyMem_Malloc(sizeof(long) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    if (unlikely(!values || !indices)) {
      PyMem_Free(values);
      PyMem_Free(indices);
      PyErr_NoMemory();
      return -1;
    }
  }
  
  /* PHASE 1: Extract values and initialize indices (GIL held) */
  for (Py_ssize_t i = 0; i < n; i++) {
    int overflow = 0;
    values[i] = PyLong_AsLongAndOverflow(items[i], &overflow);
    if (unlikely(overflow != 0)) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
      return 2;
    }
    if (unlikely(values[i] == -1 && PyErr_Occurred())) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
      return -1;
    }
    indices[i] = i;
  }
  
  /* PHASE 2: Pure C binary heapify (GIL RELEASED) */
  Py_BEGIN_ALLOW_THREADS
  
  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    Py_ssize_t pos = i;
    long newval = values[pos];
    Py_ssize_t idx = indices[pos];
    
    /* Sift down */
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      long bestval = values[child];
      
      Py_ssize_t right = child + 1;
      if (likely(right < n)) {
        int cmp = is_max ? (values[right] > bestval) : (values[right] < bestval);
        if (cmp) {
          best = right;
          bestval = values[right];
        }
      }
      
      values[pos] = values[best];
      indices[pos] = indices[best];
      pos = best;
    }
    
    /* Sift up */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      int cmp = is_max ? (newval > values[parent]) : (newval < values[parent]);
      if (!cmp) break;
      values[pos] = values[parent];
      indices[pos] = indices[parent];
      pos = parent;
    }
    
    values[pos] = newval;
    indices[pos] = idx;
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and rearrange Python objects (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
    PyErr_SetString(PyExc_ValueError,
        "list modified by another thread during heapify");
    return -1;
  }
  
  /* Quick check: if no elements moved, skip permutation entirely */
  int needs_permutation = 0;
  for (Py_ssize_t i = 0; i < n; i++) {
    if (indices[i] != i) { needs_permutation = 1; break; }
  }
  
  if (needs_permutation) {
    items = listobj->ob_item;
    for (Py_ssize_t i = 0; i < n; i++) {
      if (indices[i] == i || indices[i] < 0) continue;
      Py_ssize_t j = i;
      PyObject *temp = items[i];
      while (indices[j] != i) {
        Py_ssize_t next = indices[j];
        items[j] = items[next];
        indices[j] = -1 - indices[j];
        j = next;
      }
      items[j] = temp;
      indices[j] = -1 - indices[j];
    }
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); }
  return 0;
}

/* ---------- Ultra-optimized Bottom-Up Floyd's heapify: binary min/max heap ---------- */
/* Bottom-up heapify (Wegener 1993): reduces comparisons by ~25% vs standard Floyd.
 * Phase 1: Descend to leaf comparing only children (no comparison with item)
 * Phase 2: Bubble up from leaf (typically O(1) distance)
 * Safety: INCREF objects held across comparisons to prevent use-after-free.
 * Safety: Check list size before assignments to prevent refcount corruption. */
static int
list_heapify_floyd_ultra_optimized(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (n <= 1) return 0;

  PyObject **items = listobj->ob_item;

  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *item = items[pos];
    Py_INCREF(item);  /* Protect item across comparisons */

    /* Phase 1: Descend to leaf, only comparing children */
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (child >= n) break;
      
      Py_ssize_t right = child + 1;
      if (likely(right < n)) {
        PyObject *lc = items[child];
        PyObject *rc = items[right];
        Py_INCREF(lc); Py_INCREF(rc);
        int cmp = optimized_compare(rc, lc, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) { Py_DECREF(lc); Py_DECREF(rc); Py_DECREF(item); return -1; }
        Py_DECREF(lc); Py_DECREF(rc);
        if (cmp) child = right;
      }
      
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move child up - this is safe because we hold a reference to the original item */
      PyObject *child_obj = items[child];
      Py_INCREF(child_obj);
      Py_DECREF(items[pos]);
      items[pos] = child_obj;
      pos = child;
    }

    /* Phase 2: Bubble up from leaf position */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      PyObject *pobj = items[parent];
      Py_INCREF(pobj);
      int cmp = optimized_compare(item, pobj, is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
      Py_DECREF(pobj);
      if (!cmp) break;
      
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move parent down - proper refcount handling */
      PyObject *parent_obj = items[parent];
      Py_INCREF(parent_obj);
      Py_DECREF(items[pos]);
      items[pos] = parent_obj;
      pos = parent;
    }

    /* Check list size before final assignment */
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    items = listobj->ob_item;
    /* Place saved item in final position - we already hold a reference */
    Py_DECREF(items[pos]);
    items[pos] = item;
    /* Don't DECREF item here - we're transferring our reference to the list */
  }
  return 0;
}

/* ---------- Ultra-optimized Bottom-Up key function path: binary list with precomputed keys ---------- */
/* Bottom-up heapify with key caching: O(n) key calls + ~25% fewer comparisons */
static int
list_heapify_with_key_ultra_optimized(PyListObject *listobj, PyObject *keyfunc, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  /* Thread-safe stack-first allocation pattern */
  PyObject *stack_keys[KEY_STACK_SIZE];
  PyObject **keys = NULL;
  int keys_on_heap = 0;

  if (n <= KEY_STACK_SIZE) {
    keys = stack_keys;
  } else {
    keys = (PyObject **)PyMem_Malloc(sizeof(PyObject *) * (size_t)n);
    if (unlikely(!keys)) {
      PyErr_NoMemory();
      return -1;
    }
    keys_on_heap = 1;
  }

  /* PHASE 1: PRECOMPUTE ALL KEYS */
  for (Py_ssize_t i = 0; i < n; i++) {
    PyObject **items = listobj->ob_item;
    PyObject *k = call_key_function(keyfunc, items[i]);
    if (unlikely(!k)) {
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      if (keys_on_heap) PyMem_Free(keys);
      return -1;
    }
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(k);
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      if (keys_on_heap) PyMem_Free(keys);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    keys[i] = k;
  }

  /* PHASE 2: BOTTOM-UP HEAPIFICATION WITH KEY COMPARISONS */
  for (Py_ssize_t i = (n - 2) >> 1; i >= 0; i--) {
    PyObject **items = listobj->ob_item;
    PyObject *newitem = items[i];
    PyObject *newkey = keys[i];
    Py_INCREF(newitem);
    Py_INCREF(newkey);
    Py_ssize_t pos = i;
    
    /* Phase 1: Descend to leaf, only comparing children */
    while (1) {
      Py_ssize_t child = (pos << 1) + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t right = child + 1;
      if (likely(right < n)) {
        int cmp = optimized_compare(keys[right], keys[child], is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          Py_DECREF(newitem); Py_DECREF(newkey);
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          if (keys_on_heap) PyMem_Free(keys);
          return -1;
        }
        if (cmp) child = right;
      }
      
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move child up with proper refcount handling */
      PyObject *child_obj = items[child];
      PyObject *child_key = keys[child];
      Py_INCREF(child_obj);
      Py_INCREF(child_key);
      Py_DECREF(items[pos]);
      Py_DECREF(keys[pos]);
      items[pos] = child_obj;
      keys[pos] = child_key;
      pos = child;
    }
    
    /* Phase 2: Bubble up from leaf position */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 1;
      int cmp = optimized_compare(newkey, keys[parent], is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        return -1;
      }
      if (!cmp) break;
      
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move parent down with proper refcount handling */
      PyObject *parent_obj = items[parent];
      PyObject *parent_key = keys[parent];
      Py_INCREF(parent_obj);
      Py_INCREF(parent_key);
      Py_DECREF(items[pos]);
      Py_DECREF(keys[pos]);
      items[pos] = parent_obj;
      keys[pos] = parent_key;
      pos = parent;
    }
    
    /* Check list size before final assignment */
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(newitem); Py_DECREF(newkey);
      for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
      if (keys_on_heap) PyMem_Free(keys);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    items = listobj->ob_item;
    /* Place saved item in final position - transfer our references */
    Py_DECREF(items[pos]);
    Py_DECREF(keys[pos]);
    items[pos] = newitem;
    keys[pos] = newkey;
    /* Don't DECREF newitem/newkey - we're transferring our references */
  }

  /* PHASE 3: CLEANUP */
  for (Py_ssize_t i = 0; i < n; i++) Py_DECREF(keys[i]);
  if (keys_on_heap) PyMem_Free(keys);
  return 0;
}

/* ---------- Specialized optimized algorithms for different configurations ---------- */

/* Ultra-optimized ternary heap (arity=3) for lists without key functions */
/* Ultra-optimized Bottom-Up ternary heap (arity=3) for lists without key functions */
/* Safety: INCREF objects held across comparisons to prevent use-after-free.
 * Safety: Check list size before assignments to prevent refcount corruption. */
HOT_FUNCTION static int
list_heapify_ternary_ultra_optimized(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = listobj->ob_item;

  for (Py_ssize_t i = (n - 2) / 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *item = items[pos];
    Py_INCREF(item);
    
    /* Phase 1: Descend to leaf, only comparing children */
    while (1) {
      Py_ssize_t child = 3 * pos + 1;
      if (child >= n) break;
      
      Py_ssize_t best = child;
      
      if (likely(child + 1 < n)) {
        PyObject *c0 = items[child];
        PyObject *c1 = items[child + 1];
        Py_INCREF(c0); Py_INCREF(c1);
        int cmp = optimized_compare(c1, c0, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) { Py_DECREF(c0); Py_DECREF(c1); Py_DECREF(item); return -1; }
        Py_DECREF(c0); Py_DECREF(c1);
        if (cmp) best = child + 1;
      }
      
      if (likely(child + 2 < n)) {
        /* Check list size before accessing items[best] */
        if (unlikely(PyList_GET_SIZE(listobj) != n)) {
          Py_DECREF(item);
          PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
          return -1;
        }
        items = listobj->ob_item;
        PyObject *cb = items[best];
        PyObject *c2 = items[child + 2];
        Py_INCREF(cb); Py_INCREF(c2);
        int cmp = optimized_compare(c2, cb, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) { Py_DECREF(cb); Py_DECREF(c2); Py_DECREF(item); return -1; }
        Py_DECREF(cb); Py_DECREF(c2);
        if (cmp) best = child + 2;
      }
      
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move best child up with proper refcount handling */
      PyObject *best_obj = items[best];
      Py_INCREF(best_obj);
      Py_DECREF(items[pos]);
      items[pos] = best_obj;
      pos = best;
    }
    
    /* Phase 2: Bubble up from leaf position */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 3;
      PyObject *pobj = items[parent];
      Py_INCREF(pobj);
      int cmp = optimized_compare(item, pobj, is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
      Py_DECREF(pobj);
      if (!cmp) break;
      
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move parent down with proper refcount handling */
      PyObject *parent_obj = items[parent];
      Py_INCREF(parent_obj);
      Py_DECREF(items[pos]);
      items[pos] = parent_obj;
      pos = parent;
    }
    
    /* Check list size before final assignment */
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    items = listobj->ob_item;
    /* Place saved item in final position - transfer our reference */
    Py_DECREF(items[pos]);
    items[pos] = item;
    /* Don't DECREF item - we're transferring our reference */
  }
  
  return 0;
}

/* Ultra-optimized Bottom-Up quaternary heap (arity=4) for lists without key functions */
/* Safety: INCREF objects held across comparisons to prevent use-after-free.
 * Safety: Check list size before assignments to prevent refcount corruption. */
HOT_FUNCTION static int
list_heapify_quaternary_ultra_optimized(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = listobj->ob_item;

  for (Py_ssize_t i = (n - 2) / 4; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *item = items[pos];
    Py_INCREF(item);
    
    /* Phase 1: Descend to leaf, only comparing children */
    while (1) {
      Py_ssize_t child = 4 * pos + 1;
      if (child >= n) break;
      
      /* Prefetch grandchildren with stride optimization */
      Py_ssize_t grandchild = 4 * child + 1;
      if (likely(grandchild < n)) {
        PREFETCH_MULTIPLE_STRIDE(items, grandchild, 4, n, PREFETCH_STRIDE);
      }
      
      Py_ssize_t best = child;
      PyObject *bestobj = items[child];
      Py_INCREF(bestobj);
      
      Py_ssize_t last = child + 4;
      if (last > n) last = n;
      for (Py_ssize_t j = child + 1; j < last; j++) {
        /* Refresh items pointer after each comparison that might modify the list */
        items = listobj->ob_item;
        PyObject *cj = items[j];
        Py_INCREF(cj);
        int cmp = optimized_compare(cj, bestobj, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) { Py_DECREF(cj); Py_DECREF(bestobj); Py_DECREF(item); return -1; }
        /* Check list size after comparison - list might have been modified */
        if (unlikely(PyList_GET_SIZE(listobj) != n)) {
          Py_DECREF(cj); Py_DECREF(bestobj); Py_DECREF(item);
          PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
          return -1;
        }
        if (cmp) { Py_DECREF(bestobj); best = j; bestobj = cj; }
        else { Py_DECREF(cj); }
      }
      
      Py_DECREF(bestobj);
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move best child up with proper refcount handling */
      PyObject *best_obj = items[best];
      Py_INCREF(best_obj);
      Py_DECREF(items[pos]);
      items[pos] = best_obj;
      pos = best;
    }
    
    /* Phase 2: Bubble up from leaf position */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 4;
      PyObject *pobj = items[parent];
      Py_INCREF(pobj);
      int cmp = optimized_compare(item, pobj, is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
      Py_DECREF(pobj);
      if (!cmp) break;
      
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move parent down with proper refcount handling */
      PyObject *parent_obj = items[parent];
      Py_INCREF(parent_obj);
      Py_DECREF(items[pos]);
      items[pos] = parent_obj;
      pos = parent;
    }
    
    /* Check list size before final assignment */
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    items = listobj->ob_item;
    /* Place saved item in final position - transfer our reference */
    Py_DECREF(items[pos]);
    items[pos] = item;
    /* Don't DECREF item - we're transferring our reference */
  }
  
  return 0;
}

/* Ultra-optimized Bottom-Up ternary heap with key function */
HOT_FUNCTION static int
list_heapify_ternary_with_key_ultra_optimized(PyListObject *listobj, PyObject *keyfunc, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  /* Stack-first allocation pattern for small heaps */
  PyObject *stack_keys[KEY_STACK_SIZE];
  PyObject **keys = NULL;
  int keys_on_heap = 0;

  if (n <= KEY_STACK_SIZE) {
    keys = stack_keys;
  } else {
    keys = (PyObject **)PyMem_Malloc(sizeof(PyObject *) * (size_t)n);
    if (unlikely(!keys)) { PyErr_NoMemory(); return -1; }
    keys_on_heap = 1;
  }

  /* Precompute all keys */
  for (Py_ssize_t i = 0; i < n; i++) {
    PyObject **items = listobj->ob_item;
    PyObject *k = call_key_function(keyfunc, items[i]);
    if (unlikely(!k)) {
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      if (keys_on_heap) PyMem_Free(keys);
      return -1;
    }
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(k);
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      if (keys_on_heap) PyMem_Free(keys);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    keys[i] = k;
  }

  /* Bottom-up ternary heapification with cached keys */
  for (Py_ssize_t i = (n - 2) / 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject **items = listobj->ob_item;
    PyObject *newitem = items[pos];
    PyObject *newkey = keys[pos];
    Py_INCREF(newitem);
    Py_INCREF(newkey);
    
    /* Phase 1: Descend to leaf, only comparing children */
    while (1) {
      Py_ssize_t child = 3 * pos + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      
      if (likely(child + 1 < n)) {
        int cmp = optimized_compare(keys[child + 1], keys[child], is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          Py_DECREF(newitem); Py_DECREF(newkey);
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          if (keys_on_heap) PyMem_Free(keys);
          return -1;
        }
        if (cmp) best = child + 1;
      }
      
      if (likely(child + 2 < n)) {
        int cmp = optimized_compare(keys[child + 2], keys[best], is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          Py_DECREF(newitem); Py_DECREF(newkey);
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          if (keys_on_heap) PyMem_Free(keys);
          return -1;
        }
        if (cmp) best = child + 2;
      }
      
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move best child up with proper refcount handling */
      PyObject *best_obj = items[best];
      PyObject *best_key = keys[best];
      Py_INCREF(best_obj);
      Py_INCREF(best_key);
      Py_DECREF(items[pos]);
      Py_DECREF(keys[pos]);
      items[pos] = best_obj;
      keys[pos] = best_key;
      pos = best;
    }
    
    /* Phase 2: Bubble up from leaf position */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / 3;
      int cmp = optimized_compare(newkey, keys[parent], is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        return -1;
      }
      if (!cmp) break;
      
      /* Check list size before assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      /* Move parent down with proper refcount handling */
      PyObject *parent_obj = items[parent];
      PyObject *parent_key = keys[parent];
      Py_INCREF(parent_obj);
      Py_INCREF(parent_key);
      Py_DECREF(items[pos]);
      Py_DECREF(keys[pos]);
      items[pos] = parent_obj;
      keys[pos] = parent_key;
      pos = parent;
    }
    
    /* Check list size before final assignment */
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(newitem); Py_DECREF(newkey);
      for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
      if (keys_on_heap) PyMem_Free(keys);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    items = listobj->ob_item;
    /* Place saved item in final position - transfer our references */
    Py_DECREF(items[pos]);
    Py_DECREF(keys[pos]);
    items[pos] = newitem;
    keys[pos] = newkey;
    /* Don't DECREF newitem/newkey - we're transferring our references */
  }

  for (Py_ssize_t i = 0; i < n; i++) Py_DECREF(keys[i]);
  if (keys_on_heap) PyMem_Free(keys);
  return 0;
}

/* Ultra-optimized Bottom-Up quaternary heap with key function */
HOT_FUNCTION static int
list_heapify_quaternary_with_key_ultra_optimized(PyListObject *listobj, PyObject *keyfunc, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  /* Stack-first allocation pattern for small heaps */
  PyObject *stack_keys[KEY_STACK_SIZE];
  PyObject **keys = NULL;
  int keys_on_heap = 0;

  if (n <= KEY_STACK_SIZE) {
    keys = stack_keys;
  } else {
    keys = (PyObject **)PyMem_Malloc(sizeof(PyObject *) * (size_t)n);
    if (unlikely(!keys)) { PyErr_NoMemory(); return -1; }
    keys_on_heap = 1;
  }

  /* Pre-compute all keys once */
  for (Py_ssize_t i = 0; i < n; i++) {
    PyObject **items = listobj->ob_item;
    PyObject *k = call_key_function(keyfunc, items[i]);
    if (unlikely(!k)) {
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      if (keys_on_heap) PyMem_Free(keys);
      return -1;
    }
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(k);
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      if (keys_on_heap) PyMem_Free(keys);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    keys[i] = k;
  }

  /* Bottom-up quaternary heapification */
  for (Py_ssize_t i = (n - 2) >> 2; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject **items = listobj->ob_item;
    PyObject *newitem = items[pos];
    PyObject *newkey = keys[pos];
    Py_INCREF(newitem);
    Py_INCREF(newkey);
    
    /* Phase 1: Descend to leaf, only comparing children */
    while (1) {
      Py_ssize_t child = (pos << 2) + 1;
      if (unlikely(child >= n)) break;
      
      Py_ssize_t best = child;
      
      /* Find best among up to 4 children */
      for (Py_ssize_t j = 1; j < 4 && child + j < n; j++) {
        int cmp = optimized_compare(keys[child + j], keys[best], is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          Py_DECREF(newitem); Py_DECREF(newkey);
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          if (keys_on_heap) PyMem_Free(keys);
          return -1;
        }
        if (cmp) best = child + j;
      }
      
      /* Check size BEFORE assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      
      /* Move best child up with proper refcount handling */
      items = listobj->ob_item;
      PyObject *best_obj = items[best];
      PyObject *best_key = keys[best];
      Py_INCREF(best_obj);
      Py_INCREF(best_key);
      Py_DECREF(items[pos]);
      Py_DECREF(keys[pos]);
      items[pos] = best_obj;
      keys[pos] = best_key;
      pos = best;
    }
    
    /* Phase 2: Bubble up from leaf position */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 2;
      int cmp = optimized_compare(newkey, keys[parent], is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        return -1;
      }
      if (!cmp) break;
      
      /* Check size BEFORE assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      
      /* Move parent down with proper refcount handling */
      items = listobj->ob_item;
      PyObject *parent_obj = items[parent];
      PyObject *parent_key = keys[parent];
      Py_INCREF(parent_obj);
      Py_INCREF(parent_key);
      Py_DECREF(items[pos]);
      Py_DECREF(keys[pos]);
      items[pos] = parent_obj;
      keys[pos] = parent_key;
      pos = parent;
    }
    
    /* Place saved item in final position - transfer our references */
    items = listobj->ob_item;
    Py_DECREF(items[pos]);
    Py_DECREF(keys[pos]);
    items[pos] = newitem;
    keys[pos] = newkey;
    /* Don't DECREF newitem/newkey - we're transferring our references */
  }

  for (Py_ssize_t i = 0; i < n; i++) Py_DECREF(keys[i]);
  if (keys_on_heap) PyMem_Free(keys);
  return 0;
}

/* =============================================================================
 * OCTONARY (ARITY=8) HEAP SPECIALIZATION
 * Uses bit-shift operations (>>3, <<3) for maximum performance.
 * Provides ~15-25% speedup over generic n-ary implementation for large heaps.
 * ============================================================================= */

/* Ultra-optimized Bottom-Up octonary heap (arity=8) for lists without key functions */
/* Safety: INCREF objects held across comparisons to prevent use-after-free.
 * Safety: Check list size before assignments to prevent refcount corruption. */
HOT_FUNCTION static int
list_heapify_octonary_ultra_optimized(PyListObject *listobj, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  PyObject **items = listobj->ob_item;

  /* Start from last non-leaf: (n - 2) >> 3 = (n - 2) / 8 */
  for (Py_ssize_t i = (n - 2) >> 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *item = items[pos];
    Py_INCREF(item);
    
    /* Phase 1: Descend to leaf, only comparing children */
    while (1) {
      /* child = 8 * pos + 1 = (pos << 3) + 1 */
      Py_ssize_t child = (pos << 3) + 1;
      if (child >= n) break;
      
      /* Prefetch grandchildren for cache optimization */
      Py_ssize_t grandchild = (child << 3) + 1;
      if (likely(grandchild < n)) {
        PREFETCH_MULTIPLE_STRIDE(items, grandchild, 8, n, PREFETCH_STRIDE);
      }
      
      /* Find best among up to 8 children */
      Py_ssize_t best = child;
      PyObject *bestobj = items[child];
      Py_INCREF(bestobj);
      
      Py_ssize_t last = child + 8;
      if (last > n) last = n;
      
      for (Py_ssize_t j = child + 1; j < last; j++) {
        items = listobj->ob_item;
        PyObject *cj = items[j];
        Py_INCREF(cj);
        int cmp = optimized_compare(cj, bestobj, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) { Py_DECREF(cj); Py_DECREF(bestobj); Py_DECREF(item); return -1; }
        if (unlikely(PyList_GET_SIZE(listobj) != n)) {
          Py_DECREF(cj); Py_DECREF(bestobj); Py_DECREF(item);
          PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
          return -1;
        }
        if (cmp) { Py_DECREF(bestobj); best = j; bestobj = cj; }
        else { Py_DECREF(cj); }
      }
      
      Py_DECREF(bestobj);
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      PyObject *best_obj = items[best];
      Py_INCREF(best_obj);
      Py_DECREF(items[pos]);
      items[pos] = best_obj;
      pos = best;
    }
    
    /* Phase 2: Bubble up from leaf position */
    /* parent = (pos - 1) / 8 = (pos - 1) >> 3 */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 3;
      PyObject *pobj = items[parent];
      Py_INCREF(pobj);
      int cmp = optimized_compare(item, pobj, is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
      Py_DECREF(pobj);
      if (!cmp) break;
      
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      PyObject *parent_obj = items[parent];
      Py_INCREF(parent_obj);
      Py_DECREF(items[pos]);
      items[pos] = parent_obj;
      pos = parent;
    }
    
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    items = listobj->ob_item;
    Py_DECREF(items[pos]);
    items[pos] = item;
  }
  
  return 0;
}

/* Ultra-optimized Bottom-Up octonary heap with key function */
/* Uses bit-shift operations (>>3, <<3) for maximum performance. */
HOT_FUNCTION static int
list_heapify_octonary_with_key_ultra_optimized(PyListObject *listobj, PyObject *keyfunc, int is_max)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(n <= 1)) return 0;

  /* Stack-first allocation pattern for small heaps */
  PyObject *stack_keys[KEY_STACK_SIZE];
  PyObject **keys = NULL;
  int keys_on_heap = 0;

  if (n <= KEY_STACK_SIZE) {
    keys = stack_keys;
  } else {
    keys = (PyObject **)PyMem_Malloc(sizeof(PyObject *) * (size_t)n);
    if (unlikely(!keys)) { PyErr_NoMemory(); return -1; }
    keys_on_heap = 1;
  }

  /* Precompute all keys */
  for (Py_ssize_t i = 0; i < n; i++) {
    PyObject **items = listobj->ob_item;
    PyObject *k = call_key_function(keyfunc, items[i]);
    if (unlikely(!k)) {
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      if (keys_on_heap) PyMem_Free(keys);
      return -1;
    }
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(k);
      for (Py_ssize_t j = 0; j < i; j++) Py_DECREF(keys[j]);
      if (keys_on_heap) PyMem_Free(keys);
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    keys[i] = k;
  }

  PyObject **items = listobj->ob_item;

  /* Start from last non-leaf: (n - 2) >> 3 */
  for (Py_ssize_t i = (n - 2) >> 3; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *newitem = items[pos];
    PyObject *newkey = keys[pos];
    Py_INCREF(newitem);
    Py_INCREF(newkey);
    
    /* Phase 1: Descend to leaf */
    while (1) {
      Py_ssize_t child = (pos << 3) + 1;
      if (child >= n) break;
      
      Py_ssize_t best = child;
      PyObject *best_key = keys[child];
      Py_INCREF(best_key);
      
      Py_ssize_t last = child + 8;
      if (last > n) last = n;
      
      for (Py_ssize_t j = child + 1; j < last; j++) {
        PyObject *ckey = keys[j];
        Py_INCREF(ckey);
        int cmp = optimized_compare(ckey, best_key, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) {
          Py_DECREF(ckey); Py_DECREF(best_key);
          Py_DECREF(newitem); Py_DECREF(newkey);
          for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
          if (keys_on_heap) PyMem_Free(keys);
          return -1;
        }
        if (cmp) { Py_DECREF(best_key); best = j; best_key = ckey; }
        else { Py_DECREF(ckey); }
      }
      
      Py_DECREF(best_key);
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      
      items = listobj->ob_item;
      PyObject *best_obj = items[best];
      PyObject *best_k = keys[best];
      Py_INCREF(best_obj);
      Py_INCREF(best_k);
      Py_DECREF(items[pos]);
      Py_DECREF(keys[pos]);
      items[pos] = best_obj;
      keys[pos] = best_k;
      pos = best;
    }
    
    /* Phase 2: Bubble up from leaf position */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) >> 3;
      int cmp = optimized_compare(newkey, keys[parent], is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        return -1;
      }
      if (!cmp) break;
      
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(newitem); Py_DECREF(newkey);
        for (Py_ssize_t t = 0; t < n; t++) Py_DECREF(keys[t]);
        if (keys_on_heap) PyMem_Free(keys);
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      
      items = listobj->ob_item;
      PyObject *parent_obj = items[parent];
      PyObject *parent_key = keys[parent];
      Py_INCREF(parent_obj);
      Py_INCREF(parent_key);
      Py_DECREF(items[pos]);
      Py_DECREF(keys[pos]);
      items[pos] = parent_obj;
      keys[pos] = parent_key;
      pos = parent;
    }
    
    items = listobj->ob_item;
    Py_DECREF(items[pos]);
    Py_DECREF(keys[pos]);
    items[pos] = newitem;
    keys[pos] = newkey;
  }

  for (Py_ssize_t i = 0; i < n; i++) Py_DECREF(keys[i]);
  if (keys_on_heap) PyMem_Free(keys);
  return 0;
}

/* Ultra-optimized small heap specialization (n <= 16) */
/* Safety: INCREF objects held across comparisons to prevent use-after-free. */
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
      Py_INCREF(key);
      Py_ssize_t j = i - 1;
      
      while (j >= 0) {
        PyObject *jobj = items[j];
        Py_INCREF(jobj);
        int cmp = optimized_compare(key, jobj, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) { Py_DECREF(jobj); Py_DECREF(key); return -1; }
        items = listobj->ob_item;
        Py_DECREF(jobj);
        if (!cmp) break;
        /* Check size BEFORE assignment to prevent refcount corruption */
        if (unlikely(PyList_GET_SIZE(listobj) != n)) {
          Py_DECREF(key);
          PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
          return -1;
        }
        /* Move with proper refcount handling */
        PyObject *jobj_move = items[j];
        Py_INCREF(jobj_move);
        Py_DECREF(items[j + 1]);
        items[j + 1] = jobj_move;
        j--;
      }
      /* Place key in final position - transfer our reference */
      Py_DECREF(items[j + 1]);
      items[j + 1] = key;
      /* Don't DECREF key - we're transferring our reference */
    }
    return 0;
  }
  
  /* For small heaps, use optimized heapify */
  for (Py_ssize_t i = (n - 2) / arity; i >= 0; i--) {
    Py_ssize_t pos = i;
    PyObject *item = items[pos];
    Py_INCREF(item);
    
    while (1) {
      Py_ssize_t child = arity * pos + 1;
      if (child >= n) break;
      
      Py_ssize_t best = child;
      PyObject *bestobj = items[child];
      Py_INCREF(bestobj);
      
      Py_ssize_t last = child + arity;
      if (last > n) last = n;
      
      for (Py_ssize_t j = child + 1; j < last; j++) {
        /* Refresh items pointer after each comparison */
        items = listobj->ob_item;
        PyObject *cj = items[j];
        Py_INCREF(cj);
        int cmp = optimized_compare(cj, bestobj, is_max ? Py_GT : Py_LT);
        if (unlikely(cmp < 0)) { Py_DECREF(cj); Py_DECREF(bestobj); Py_DECREF(item); return -1; }
        /* Check list size after comparison */
        if (unlikely(PyList_GET_SIZE(listobj) != n)) {
          Py_DECREF(cj); Py_DECREF(bestobj); Py_DECREF(item);
          PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
          return -1;
        }
        items = listobj->ob_item;
        if (cmp) { Py_DECREF(bestobj); best = j; bestobj = cj; }
        else { Py_DECREF(cj); }
      }
      
      /* Check size BEFORE assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(bestobj); Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      
      Py_DECREF(bestobj);
      /* Move best child up with proper refcount handling */
      PyObject *best_obj = items[best];
      Py_INCREF(best_obj);
      Py_DECREF(items[pos]);
      items[pos] = best_obj;
      pos = best;
    }
    
    /* Sift up phase */
    while (pos > i) {
      Py_ssize_t parent = (pos - 1) / arity;
      PyObject *pobj = items[parent];
      Py_INCREF(pobj);
      int cmp = optimized_compare(item, pobj, is_max ? Py_GT : Py_LT);
      if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
      items = listobj->ob_item;
      Py_DECREF(pobj);
      if (!cmp) break;
      /* Check size BEFORE assignment to prevent refcount corruption */
      if (unlikely(PyList_GET_SIZE(listobj) != n)) {
        Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      /* Move parent down with proper refcount handling */
      PyObject *parent_obj = items[parent];
      Py_INCREF(parent_obj);
      Py_DECREF(items[pos]);
      items[pos] = parent_obj;
      pos = parent;
    }
    
    /* Place saved item in final position - transfer our reference */
    Py_DECREF(items[pos]);
    items[pos] = item;
    /* Don't DECREF item - we're transferring our reference */
  }
  
  return 0;
}

/* Arity-1 heapify: O(N log N) using decorate-sort-undecorate pattern */
static int
heapify_arity_one_ultra_optimized(PyObject *heap, int is_max, PyObject *cmp)
{
  Py_ssize_t n = PySequence_Size(heap);
  if (unlikely(n <= 1)) return 0;

  /* For lists, use O(N log N) sort */
  if (likely(PyList_CheckExact(heap))) {
    if (cmp && cmp != Py_None) {
      /* Decorate-sort-undecorate pattern to detect modification during key computation */
      
      /* Phase 1: Compute all keys, checking for modification after each */
      PyObject *decorated = PyList_New(n);
      if (unlikely(!decorated)) return -1;
      
      for (Py_ssize_t i = 0; i < n; i++) {
        /* SAFETY CHECK */
        if (unlikely(PyList_GET_SIZE(heap) != n)) {
          Py_DECREF(decorated);
          PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(heap));
          return -1;
        }
        
        PyObject *item = PyList_GET_ITEM(heap, i);
        PyObject *key = call_key_function(cmp, item);
        if (unlikely(!key)) {
          Py_DECREF(decorated);
          return -1;
        }
        
        /* SAFETY CHECK after key function call */
        if (unlikely(PyList_GET_SIZE(heap) != n)) {
          Py_DECREF(key);
          Py_DECREF(decorated);
          PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PyList_GET_SIZE(heap));
          return -1;
        }
        
        /* Create (key, index, item) tuple for stable sort */
        PyObject *idx = PyLong_FromSsize_t(i);
        if (unlikely(!idx)) {
          Py_DECREF(key);
          Py_DECREF(decorated);
          return -1;
        }
        
        Py_INCREF(item);
        PyObject *tuple = PyTuple_Pack(3, key, idx, item);
        Py_DECREF(key);
        Py_DECREF(idx);
        if (unlikely(!tuple)) {
          Py_DECREF(item);
          Py_DECREF(decorated);
          return -1;
        }
        
        PyList_SET_ITEM(decorated, i, tuple);
      }
      
      /* Phase 2: Sort decorated list by key (O(N log N)) */
      int rc = PyList_Sort(decorated);
      if (unlikely(rc < 0)) {
        Py_DECREF(decorated);
        return -1;
      }
      
      /* Reverse if max-heap */
      if (is_max) {
        rc = PyList_Reverse(decorated);
        if (unlikely(rc < 0)) {
          Py_DECREF(decorated);
          return -1;
        }
      }
      
      /* Phase 3: Undecorate - extract items back to heap */
      for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *tuple = PyList_GET_ITEM(decorated, i);
        PyObject *item = PyTuple_GET_ITEM(tuple, 2);
        Py_INCREF(item);
        PyObject *old = PyList_GET_ITEM(heap, i);
        PyList_SET_ITEM(heap, i, item);
        Py_DECREF(old);
      }
      
      Py_DECREF(decorated);
    } else {
      /* No key function - direct sort */
      int rc = PyList_Sort(heap);
      if (unlikely(rc < 0)) return -1;
      
      /* Reverse if max-heap (sorted list for max-heap is descending) */
      if (is_max) {
        rc = PyList_Reverse(heap);
        if (unlikely(rc < 0)) return -1;
      }
    }
    return 0;
  }
  
  /* For non-list sequences, convert to list, sort, copy back */
  PyObject *list_copy = PySequence_List(heap);
  if (unlikely(!list_copy)) return -1;
  
  int rc = heapify_arity_one_ultra_optimized(list_copy, is_max, cmp);
  if (unlikely(rc < 0)) {
    Py_DECREF(list_copy);
    return -1;
  }
  
  /* Copy sorted elements back */
  Py_ssize_t len = PyList_GET_SIZE(list_copy);
  for (Py_ssize_t i = 0; i < len; i++) {
    PyObject *item = PyList_GET_ITEM(list_copy, i);
    Py_INCREF(item);
    if (unlikely(PySequence_SetItem(heap, i, item) < 0)) {
      Py_DECREF(item);
      Py_DECREF(list_copy);
      return -1;
    }
  }
  
  Py_DECREF(list_copy);
  return 0;
}

/* ---------- Ultra-optimized generic n-ary heapify with fast comparisons ---------- */
static int
generic_heapify_ultra_optimized(PyObject *heap, int is_max, PyObject *cmp, Py_ssize_t arity)
{
  Py_ssize_t n = PySequence_Size(heap);
  if (unlikely(n <= 1)) return 0;

  for (Py_ssize_t i = (n - 2) / arity; i >= 0; i--) {
    /* SAFETY CHECK before each iteration */
    if (unlikely(PySequence_Size(heap) != n)) {
      PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PySequence_Size(heap));
      return -1;
    }
    
    Py_ssize_t pos = i;
    
    while (1) {
      Py_ssize_t child = arity * pos + 1;
      if (unlikely(child >= n)) break;

      /* SAFETY CHECK before reading children */
      if (unlikely(PySequence_Size(heap) != n)) {
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PySequence_Size(heap));
        return -1;
      }

      Py_ssize_t best = child;
      PyObject *bestobj = PySequence_GetItem(heap, child);
      if (unlikely(!bestobj)) return -1;
      
      PyObject *bestkey;
      if (likely(cmp)) {
        bestkey = call_key_function(cmp, bestobj);
        if (unlikely(!bestkey)) { Py_DECREF(bestobj); return -1; }
        /* SAFETY CHECK after key function call */
        if (unlikely(PySequence_Size(heap) != n)) {
          PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PySequence_Size(heap));
          Py_DECREF(bestobj);
          Py_DECREF(bestkey);
          return -1;
        }
      } else {
        bestkey = bestobj;
        Py_INCREF(bestkey);
      }

      Py_ssize_t last = child + arity;
      if (unlikely(last > n)) last = n;

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
          /* SAFETY CHECK after key function call */
          if (unlikely(PySequence_Size(heap) != n)) {
            PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PySequence_Size(heap));
            Py_DECREF(cur); Py_DECREF(curkey); Py_DECREF(bestobj); Py_DECREF(bestkey);
            return -1;
          }
        } else {
          curkey = cur;
          Py_INCREF(curkey);
        }

        int better = optimized_compare(curkey, bestkey, is_max ? Py_GT : Py_LT);
        /* SAFETY CHECK after comparison */
        if (unlikely(PySequence_Size(heap) != n)) {
          PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PySequence_Size(heap));
          Py_DECREF(cur); Py_DECREF(curkey); Py_DECREF(bestobj); Py_DECREF(bestkey);
          return -1;
        }
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
        /* SAFETY CHECK after key function call */
        if (unlikely(PySequence_Size(heap) != n)) {
          PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PySequence_Size(heap));
          Py_DECREF(parent); Py_DECREF(parentkey); Py_DECREF(bestobj); Py_DECREF(bestkey);
          return -1;
        }
      } else {
        parentkey = parent;
        Py_INCREF(parentkey);
      }

      int should_continue = optimized_compare(bestkey, parentkey, is_max ? Py_GT : Py_LT);
      /* SAFETY CHECK after comparison */
      if (unlikely(PySequence_Size(heap) != n)) {
        PyErr_Format(PyExc_ValueError, "list modified during heapify (expected size %zd, got %zd)", n, PySequence_Size(heap));
        Py_DECREF(parent); Py_DECREF(parentkey); Py_DECREF(bestobj); Py_DECREF(bestkey);
        return -1;
      }
      Py_DECREF(parentkey);
      
      if (unlikely(should_continue < 0)) { 
        Py_DECREF(parent); Py_DECREF(bestobj); Py_DECREF(bestkey); 
        return -1; 
      }
      
      if (!should_continue) { 
        Py_DECREF(parent); Py_DECREF(bestobj); Py_DECREF(bestkey); 
        break; 
      }

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
  (void)self;  /* Module method, self is unused */
  static char *kwlist[] = {"heap", "max_heap", "cmp", "arity", "nogil", NULL};
  PyObject *heap;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;
  PyObject *nogil_obj = Py_False;

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OOnO:heapify", kwlist,
                                   &heap, &max_heap_obj, &cmp, &arity, &nogil_obj))
    return NULL;

  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;
  
  int nogil = PyObject_IsTrue(nogil_obj);
  if (unlikely(nogil < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_Format(PyExc_TypeError, "cmp must be callable or None, not %.200s", Py_TYPE(cmp)->tp_name);
    return NULL;
  }
  if (unlikely(arity < 1 || arity > HEAPX_MAX_ARITY)) {
    PyErr_Format(PyExc_ValueError, "arity must be >= 1 and <= 64, got %zd", arity);
    return NULL;
  }

  int rc = 0;
  Py_ssize_t n = PySequence_Size(heap);
  if (unlikely(n < 0)) return NULL;

  /* COMPREHENSIVE ULTRA-OPTIMIZED ALGORITHM SELECTION */
  
  if (likely(PyList_CheckExact(heap))) {
    PyListObject *listobj = (PyListObject *)heap;
    
    /* Check for homogeneous array optimization (integers or floats) */
    if (likely(cmp == Py_None && n >= HEAPX_HOMOGENEOUS_SAMPLE_SIZE)) {
      int homogeneous = detect_homogeneous_type(listobj->ob_item, n);
      
      /* SIMD-optimized path for arity >= 4 with homogeneous floats */
      if (arity >= 4 && homogeneous == 2) {
        if (nogil) {
          rc = (arity == 4)
            ? list_heapify_quaternary_homogeneous_float_nogil(listobj, is_max)
            : list_heapify_nary_simd_homogeneous_float_nogil(listobj, is_max, arity);
        } else {
          rc = (arity == 4)
            ? list_heapify_quaternary_homogeneous_float(listobj, is_max)
            : list_heapify_nary_simd_homogeneous_float(listobj, is_max, arity);
        }
        if (rc == 0) Py_RETURN_NONE;
        PyErr_Clear();
      }
      /* SIMD-optimized path for arity >= 4 with homogeneous integers */
      else if (arity >= 4 && homogeneous == 1) {
        if (nogil) {
          rc = (arity == 4)
            ? list_heapify_quaternary_homogeneous_int_nogil(listobj, is_max)
            : list_heapify_nary_simd_homogeneous_int_nogil(listobj, is_max, arity);
        } else {
          rc = (arity == 4)
            ? list_heapify_quaternary_homogeneous_int(listobj, is_max)
            : list_heapify_nary_simd_homogeneous_int(listobj, is_max, arity);
        }
        if (rc == 0) Py_RETURN_NONE;
        if (rc == -1) PyErr_Clear();
      }
      /* Ternary heap homogeneous optimization */
      else if (arity == 3 && homogeneous) {
        if (nogil) {
          rc = (homogeneous == 1)
            ? list_heapify_ternary_homogeneous_int_nogil(listobj, is_max)
            : list_heapify_ternary_homogeneous_float_nogil(listobj, is_max);
        } else {
          rc = (homogeneous == 1)
            ? list_heapify_ternary_homogeneous_int(listobj, is_max)
            : list_heapify_ternary_homogeneous_float(listobj, is_max);
        }
        if (rc == 0) Py_RETURN_NONE;
        if (rc == -1) PyErr_Clear();
      }
      /* Binary heap homogeneous optimization */
      else if (arity == 2 && homogeneous) {
        if (homogeneous == 3) {
          /* Homogeneous string array */
          rc = list_heapify_homogeneous_string(listobj, is_max);
        } else if (nogil) {
          rc = (homogeneous == 1)
            ? list_heapify_homogeneous_int_nogil(listobj, is_max)
            : list_heapify_homogeneous_float_nogil(listobj, is_max);
        } else {
          rc = (homogeneous == 1)
            ? list_heapify_homogeneous_int(listobj, is_max)
            : list_heapify_homogeneous_float(listobj, is_max);
        }
        if (rc == 0) Py_RETURN_NONE;
        if (rc == -1) PyErr_Clear();
      }
    }
    
    /* Small heap optimization (only for no key function) */
    if (unlikely(n <= HEAPX_SMALL_HEAP_THRESHOLD && cmp == Py_None)) {
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
          
        case 8:
          /* Octonary heap - specialized implementation with bit-shift */
          rc = list_heapify_octonary_ultra_optimized(listobj, is_max);
          break;
          
        default:
          /* General n-ary heap */
          if (likely(n < HEAPX_LARGE_HEAP_THRESHOLD)) {
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
          
        case 8:
          /* Octonary heap with key function */
          rc = list_heapify_octonary_with_key_ultra_optimized(listobj, cmp, is_max);
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
      
    } else if (unlikely(n <= HEAPX_SMALL_HEAP_THRESHOLD)) {
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

/* Forward declarations for functions defined after PyMethodDef array */
static PyObject *py_push(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
static PyObject *py_pop(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
static PyObject *py_remove(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject *py_replace(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject *py_merge(PyObject *self, PyObject *args, PyObject *kwargs);

/* ---------- Enhanced Module definition ---------- */
static PyMethodDef Methods[] = {
  {"heapify", (PyCFunction)py_heapify, METH_VARARGS | METH_KEYWORDS,
   "heapify(heap, max_heap=False, cmp=None, arity=2, nogil=False)\n\n"
   "Ultra-optimized heapify with comprehensive fast comparison paths.\n\n"
   "Parameters:\n"
   "  heap: any list-like Python sequence supporting len, __getitem__, __setitem__\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function; when provided comparisons are performed on cmp(x)\n"
   "  arity: integer >= 1 (default 2: binary heap)\n"
   "  nogil: bool (default False). When True, releases GIL during pure C computation\n"
   "         to enable multi-threaded parallelism. Use False for max single-threaded speed.\n\n"
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
   
  {"push", (PyCFunction)py_push, METH_FASTCALL | METH_KEYWORDS,
   "push(heap, items, max_heap=False, cmp=None, arity=2, nogil=False)\n\n"
   "Insert items into heap maintaining heap property.\n\n"
   "Parameters:\n"
   "  heap: heap to insert into\n"
   "  items: single item or sequence of items to insert\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n"
   "  nogil: bool (default False). Accepted for API consistency.\n\n"
   "Complexity: O(log n) single insert, O(k log n) bulk insert"},
   
  {"pop", (PyCFunction)py_pop, METH_FASTCALL | METH_KEYWORDS,
   "pop(heap, n=1, max_heap=False, cmp=None, arity=2, nogil=False)\n\n"
   "Remove and return top n items from heap.\n\n"
   "Parameters:\n"
   "  heap: heap to pop from\n"
   "  n: number of items to pop (default 1)\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n"
   "  nogil: bool (default False). Accepted for API consistency.\n\n"
   "Returns: single item (n=1) or list of items (n>1)\n"
   "Complexity: O(log n) single pop, O(k log n) bulk pop"},
   
  {"remove", (PyCFunction)py_remove, METH_VARARGS | METH_KEYWORDS,
   "remove(heap, indices=None, object=None, predicate=None, n=None, return_items=False, max_heap=False, cmp=None, arity=2, nogil=False)\n\n"
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
   "  arity: integer >= 1 (default 2: binary heap)\n"
   "  nogil: bool (default False). Accepted for API consistency.\n\n"
   "Returns: count of removed items or (count, removed_items)\n"
   "Complexity: O(k + n) where k is items removed"},
   
  {"replace", (PyCFunction)py_replace, METH_VARARGS | METH_KEYWORDS,
   "replace(heap, values, indices=None, object=None, predicate=None, max_heap=False, cmp=None, arity=2, nogil=False)\n\n"
   "Replace items in heap by indices, object identity, or predicate.\n\n"
   "Parameters:\n"
   "  heap: heap to replace in\n"
   "  values: replacement value or sequence of values\n"
   "  indices: index or sequence of indices to replace\n"
   "  object: replace items with this object identity\n"
   "  predicate: callable to test items for replacement\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n"
   "  nogil: bool (default False). Accepted for API consistency.\n\n"
   "Returns: count of replaced items\n"
   "Complexity: O(k + n) where k is items replaced"},
   
  {"merge", (PyCFunction)py_merge, METH_VARARGS | METH_KEYWORDS,
   "merge(*heaps, max_heap=False, cmp=None, arity=2, nogil=False)\n\n"
   "Merge multiple heaps into a single heap.\n\n"
   "Parameters:\n"
   "  *heaps: two or more heaps to merge\n"
   "  max_heap: bool (default False: min-heap, True: max-heap)\n"
   "  cmp: optional key function\n"
   "  arity: integer >= 1 (default 2: binary heap)\n"
   "  nogil: bool (default False). Accepted for API consistency.\n\n"
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
  if (unlikely(PyModule_AddStringConstant(module, "__version__", "1.0.0") < 0)) {
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

/* ============================================================================
 * HOMOGENEOUS SIFT-UP FUNCTIONS FOR BULK SEQUENTIAL PUSH
 * ============================================================================
 * Zero-overhead sift-up operations for homogeneous int/float arrays.
 * Used only for bulk push (n_items > 1) where detection cost is amortized.
 * Return: 0=success, 1=fallback to generic path, -1=error
 */

HOT_FUNCTION static inline int
list_sift_up_homogeneous_int(PyListObject *listobj, Py_ssize_t pos, int is_max, Py_ssize_t arity) {
  if (pos == 0) return 0;
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  long val = PyLong_AsLong(item);
  if (unlikely(val == -1 && PyErr_Occurred())) { PyErr_Clear(); return 1; }
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) / arity;
    long pval = PyLong_AsLong(items[parent]);
    if (unlikely(pval == -1 && PyErr_Occurred())) { PyErr_Clear(); return 1; }
    if (is_max ? (val <= pval) : (val >= pval)) break;
    items[pos] = items[parent];
    pos = parent;
  }
  items[pos] = item;
  return 0;
}

HOT_FUNCTION static inline int
list_sift_up_homogeneous_float(PyListObject *listobj, Py_ssize_t pos, int is_max, Py_ssize_t arity) {
  if (pos == 0) return 0;
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  double val = PyFloat_AS_DOUBLE(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) / arity;
    double pval = PyFloat_AS_DOUBLE(items[parent]);
    if (is_max ? HEAPX_FLOAT_LE(val, pval) : HEAPX_FLOAT_GE(val, pval)) break;
    items[pos] = items[parent];
    pos = parent;
  }
  items[pos] = item;
  return 0;
}

/* =============================================================================
 * ARITY-SPECIALIZED SIFT OPERATIONS
 * These provide optimized sift_up and sift_down for specific arities using
 * bit-shift operations where possible (binary, quaternary, octonary).
 * ============================================================================= */

/* Binary (arity=2) sift up - uses bit-shift >>1 */
HOT_FUNCTION static inline int
list_sift_up_binary_ultra_optimized(PyListObject *listobj, Py_ssize_t pos, int is_max) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) >> 1;  /* Bit-shift optimization */
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, is_max ? Py_GT : Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Quaternary (arity=4) sift up - uses bit-shift >>2 */
HOT_FUNCTION static inline int
list_sift_up_quaternary_ultra_optimized(PyListObject *listobj, Py_ssize_t pos, int is_max) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) >> 2;  /* Bit-shift optimization */
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, is_max ? Py_GT : Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Octonary (arity=8) sift up - uses bit-shift >>3 */
HOT_FUNCTION static inline int
list_sift_up_octonary_ultra_optimized(PyListObject *listobj, Py_ssize_t pos, int is_max) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) >> 3;  /* Bit-shift optimization */
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, is_max ? Py_GT : Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* =============================================================================
 * MAX-HEAP BRANCH OPTIMIZATION
 * Separate min/max versions eliminate the `is_max ? Py_GT : Py_LT` conditional
 * inside hot loops, improving branch prediction and reducing instruction count.
 * Expected improvement: 5-13% for max-heap operations.
 * ============================================================================= */

/* Binary sift up - MIN heap version (no branch) */
HOT_FUNCTION static inline int
list_sift_up_binary_min(PyListObject *listobj, Py_ssize_t pos) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) >> 1;
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Binary sift up - MAX heap version (no branch) */
HOT_FUNCTION static inline int
list_sift_up_binary_max(PyListObject *listobj, Py_ssize_t pos) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) >> 1;
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, Py_GT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Quaternary sift up - MIN heap version (no branch) */
HOT_FUNCTION static inline int
list_sift_up_quaternary_min(PyListObject *listobj, Py_ssize_t pos) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) >> 2;
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Quaternary sift up - MAX heap version (no branch) */
HOT_FUNCTION static inline int
list_sift_up_quaternary_max(PyListObject *listobj, Py_ssize_t pos) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) >> 2;
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, Py_GT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Octonary sift up - MIN heap version (no branch) */
HOT_FUNCTION static inline int
list_sift_up_octonary_min(PyListObject *listobj, Py_ssize_t pos) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) >> 3;
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Octonary sift up - MAX heap version (no branch) */
HOT_FUNCTION static inline int
list_sift_up_octonary_max(PyListObject *listobj, Py_ssize_t pos) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) >> 3;
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, Py_GT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Ultra-optimized sift up for lists without key functions */
/* Safety: INCREF objects held across comparisons to prevent use-after-free. */
HOT_FUNCTION static inline int
list_sift_up_ultra_optimized(PyListObject *listobj, Py_ssize_t pos, int is_max, Py_ssize_t arity) {
  if (unlikely(pos == 0)) return 0;
  
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  PyObject **items = listobj->ob_item;
  PyObject *item = items[pos];
  Py_INCREF(item);
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) / arity;
    PyObject *parent_item = items[parent];
    Py_INCREF(parent_item);
    
    int should_swap = optimized_compare(item, parent_item, is_max ? Py_GT : Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != n)) {
      Py_DECREF(parent_item); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
      return -1;
    }
    if (unlikely(should_swap < 0)) { Py_DECREF(parent_item); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(parent_item);
    if (!should_swap) break;
    
    items[pos] = items[parent];
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
  
  PyObject *key = PyObject_CallOneArg(keyfunc, item);
  if (unlikely(!key)) return -1;
  
  while (pos > 0) {
    Py_ssize_t parent = (pos - 1) / arity;
    PyObject *parent_item = items[parent];
    
    PyObject *parent_key = PyObject_CallOneArg(keyfunc, parent_item);
    if (unlikely(!parent_key)) { Py_DECREF(key); return -1; }
    
    int should_swap = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
    Py_DECREF(parent_key);
    if (unlikely(should_swap < 0)) { Py_DECREF(key); return -1; }
    if (!should_swap) break;
    
    items[pos] = parent_item;
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(key);
  return 0;
}

/* =============================================================================
 * OPTIMIZED SIFT - Floyd's bottom-up algorithm with PyObject_RichCompareBool
 * =============================================================================
 * This implementation matches the optimized_pop.pyx approach:
 * 1. Uses PyObject_RichCompareBool directly (single call vs fast_compare + fallback)
 * 2. Uses direct pointer swaps without extra reference counting overhead
 * 3. Floyd's bottom-up: descend to leaf, then bubble up
 */

/* Optimized Floyd's bottom-up sift for min-heap using PyObject_RichCompareBool
 * This matches optimized_pop.pyx _sift_richcmp_min exactly */
HOT_FUNCTION static inline int
sift_richcmp_min(PyListObject *listobj, Py_ssize_t endpos) {
  PyObject **arr = listobj->ob_item;
  Py_ssize_t pos = 0, startpos = 0, childpos, limit, parentpos;
  PyObject *tmp1, *tmp2, *newitem, *parent;
  int cmp;
  Py_ssize_t original_size = endpos;
  
  /* Phase 1: Bubble smaller child up until hitting a leaf */
  limit = endpos >> 1;
  while (pos < limit) {
    childpos = (pos << 1) + 1;
    if (childpos + 1 < endpos) {
      Py_INCREF(arr[childpos]);
      Py_INCREF(arr[childpos + 1]);
      cmp = PyObject_RichCompareBool(arr[childpos], arr[childpos + 1], Py_LT);
      Py_DECREF(arr[childpos]);
      Py_DECREF(arr[childpos + 1]);
      if (cmp < 0) return -1;
      if (unlikely(PyList_GET_SIZE(listobj) != original_size)) {
        PyErr_SetString(PyExc_ValueError, "list modified during heap operation");
        return -1;
      }
      if (cmp == 0) childpos += 1;
      arr = listobj->ob_item;
    }
    
    /* Swap arr[pos] and arr[childpos] */
    tmp1 = arr[childpos];
    tmp2 = arr[pos];
    arr[childpos] = tmp2;
    arr[pos] = tmp1;
    pos = childpos;
  }
  
  /* Phase 2: Bubble up to final position */
  arr = listobj->ob_item;
  newitem = arr[pos];
  while (pos > startpos) {
    parentpos = (pos - 1) >> 1;
    parent = arr[parentpos];
    Py_INCREF(newitem);
    Py_INCREF(parent);
    cmp = PyObject_RichCompareBool(newitem, parent, Py_LT);
    Py_DECREF(parent);
    Py_DECREF(newitem);
    if (cmp < 0) return -1;
    if (unlikely(PyList_GET_SIZE(listobj) != original_size)) {
      PyErr_SetString(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (cmp == 0) break;
    arr = listobj->ob_item;
    parent = arr[parentpos];
    newitem = arr[pos];
    arr[parentpos] = newitem;
    arr[pos] = parent;
    pos = parentpos;
  }
  return 0;
}

/* Optimized Floyd's bottom-up sift for max-heap using PyObject_RichCompareBool
 * This matches optimized_pop.pyx _sift_richcmp_max exactly */
HOT_FUNCTION static inline int
sift_richcmp_max(PyListObject *listobj, Py_ssize_t endpos) {
  PyObject **arr = listobj->ob_item;
  Py_ssize_t pos = 0, startpos = 0, childpos, limit, parentpos;
  PyObject *tmp1, *tmp2, *newitem, *parent;
  int cmp;
  Py_ssize_t original_size = endpos;
  
  limit = endpos >> 1;
  while (pos < limit) {
    childpos = (pos << 1) + 1;
    if (childpos + 1 < endpos) {
      Py_INCREF(arr[childpos]);
      Py_INCREF(arr[childpos + 1]);
      cmp = PyObject_RichCompareBool(arr[childpos], arr[childpos + 1], Py_GT);
      Py_DECREF(arr[childpos]);
      Py_DECREF(arr[childpos + 1]);
      if (cmp < 0) return -1;
      if (unlikely(PyList_GET_SIZE(listobj) != original_size)) {
        PyErr_SetString(PyExc_ValueError, "list modified during heap operation");
        return -1;
      }
      if (cmp == 0) childpos += 1;
      arr = listobj->ob_item;
    }
    
    tmp1 = arr[childpos];
    tmp2 = arr[pos];
    arr[childpos] = tmp2;
    arr[pos] = tmp1;
    pos = childpos;
  }
  
  arr = listobj->ob_item;
  newitem = arr[pos];
  while (pos > startpos) {
    parentpos = (pos - 1) >> 1;
    parent = arr[parentpos];
    Py_INCREF(newitem);
    Py_INCREF(parent);
    cmp = PyObject_RichCompareBool(newitem, parent, Py_GT);
    Py_DECREF(parent);
    Py_DECREF(newitem);
    if (cmp < 0) return -1;
    if (unlikely(PyList_GET_SIZE(listobj) != original_size)) {
      PyErr_SetString(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (cmp == 0) break;
    arr = listobj->ob_item;
    parent = arr[parentpos];
    newitem = arr[pos];
    arr[parentpos] = newitem;
    arr[pos] = parent;
    pos = parentpos;
  }
  return 0;
}

/* =============================================================================
 * TYPE-SPECIALIZED SIFT FUNCTIONS FOR BULK POP
 * These match optimized_pop.pyx exactly - no type checking per comparison
 * =============================================================================
 */

/* Float min-heap sift - no type checking per comparison */
HOT_FUNCTION static inline void
sift_float_min(PyListObject *listobj, Py_ssize_t n) {
  PyObject **heap = listobj->ob_item;
  Py_ssize_t pos = 0, child, right, parent;
  PyObject *item = heap[0];
  double item_val = PyFloat_AS_DOUBLE(item);
  
  while (1) {
    child = (pos << 1) + 1;
    if (child >= n) break;
    right = child + 1;
    if (right < n && PyFloat_AS_DOUBLE(heap[right]) < PyFloat_AS_DOUBLE(heap[child]))
      child = right;
    heap[pos] = heap[child];
    pos = child;
  }
  
  while (pos > 0) {
    parent = (pos - 1) >> 1;
    if (item_val >= PyFloat_AS_DOUBLE(heap[parent])) break;
    heap[pos] = heap[parent];
    pos = parent;
  }
  heap[pos] = item;
}

/* Float max-heap sift */
HOT_FUNCTION static inline void
sift_float_max(PyListObject *listobj, Py_ssize_t n) {
  PyObject **heap = listobj->ob_item;
  Py_ssize_t pos = 0, child, right, parent;
  PyObject *item = heap[0];
  double item_val = PyFloat_AS_DOUBLE(item);
  
  while (1) {
    child = (pos << 1) + 1;
    if (child >= n) break;
    right = child + 1;
    if (right < n && PyFloat_AS_DOUBLE(heap[right]) > PyFloat_AS_DOUBLE(heap[child]))
      child = right;
    heap[pos] = heap[child];
    pos = child;
  }
  
  while (pos > 0) {
    parent = (pos - 1) >> 1;
    if (item_val <= PyFloat_AS_DOUBLE(heap[parent])) break;
    heap[pos] = heap[parent];
    pos = parent;
  }
  heap[pos] = item;
}

/* Int min-heap sift - no type checking per comparison */
HOT_FUNCTION static inline void
sift_int_min(PyListObject *listobj, Py_ssize_t n) {
  PyObject **heap = listobj->ob_item;
  Py_ssize_t pos = 0, child, right, parent;
  PyObject *item = heap[0];
  long item_val = PyLong_AsLong(item);
  
  while (1) {
    child = (pos << 1) + 1;
    if (child >= n) break;
    right = child + 1;
    if (right < n && PyLong_AsLong(heap[right]) < PyLong_AsLong(heap[child]))
      child = right;
    heap[pos] = heap[child];
    pos = child;
  }
  
  while (pos > 0) {
    parent = (pos - 1) >> 1;
    if (item_val >= PyLong_AsLong(heap[parent])) break;
    heap[pos] = heap[parent];
    pos = parent;
  }
  heap[pos] = item;
}

/* Int max-heap sift */
HOT_FUNCTION static inline void
sift_int_max(PyListObject *listobj, Py_ssize_t n) {
  PyObject **heap = listobj->ob_item;
  Py_ssize_t pos = 0, child, right, parent;
  PyObject *item = heap[0];
  long item_val = PyLong_AsLong(item);
  
  while (1) {
    child = (pos << 1) + 1;
    if (child >= n) break;
    right = child + 1;
    if (right < n && PyLong_AsLong(heap[right]) > PyLong_AsLong(heap[child]))
      child = right;
    heap[pos] = heap[child];
    pos = child;
  }
  
  while (pos > 0) {
    parent = (pos - 1) >> 1;
    if (item_val <= PyLong_AsLong(heap[parent])) break;
    heap[pos] = heap[parent];
    pos = parent;
  }
  heap[pos] = item;
}

/* String less-than helper without type check */
static inline int str_lt(PyObject *a, PyObject *b) {
  Py_ssize_t len_a = PyUnicode_GET_LENGTH(a);
  Py_ssize_t len_b = PyUnicode_GET_LENGTH(b);
  Py_ssize_t min_len = len_a < len_b ? len_a : len_b;
  int kind_a = PyUnicode_KIND(a);
  int kind_b = PyUnicode_KIND(b);
  
  if (kind_a == kind_b && len_a > 0 && len_b > 0) {
    void *data_a = PyUnicode_DATA(a);
    void *data_b = PyUnicode_DATA(b);
    int cmp;
    if (kind_a == PyUnicode_1BYTE_KIND)
      cmp = memcmp(data_a, data_b, min_len);
    else if (kind_a == PyUnicode_2BYTE_KIND)
      cmp = memcmp(data_a, data_b, min_len * 2);
    else
      cmp = memcmp(data_a, data_b, min_len * 4);
    if (cmp == 0) return len_a < len_b;
    return cmp < 0;
  }
  /* Fallback */
  int result;
  PyObject *cmp_result = PyObject_RichCompare(a, b, Py_LT);
  if (!cmp_result) return 0;
  result = PyObject_IsTrue(cmp_result);
  Py_DECREF(cmp_result);
  return result > 0;
}

/* String min-heap sift */
HOT_FUNCTION static inline void
sift_str_min(PyListObject *listobj, Py_ssize_t n) {
  PyObject **heap = listobj->ob_item;
  Py_ssize_t pos = 0, child, right, parent;
  PyObject *item = heap[0];
  
  while (1) {
    child = (pos << 1) + 1;
    if (child >= n) break;
    right = child + 1;
    if (right < n && str_lt(heap[right], heap[child]))
      child = right;
    heap[pos] = heap[child];
    pos = child;
  }
  
  while (pos > 0) {
    parent = (pos - 1) >> 1;
    if (!str_lt(item, heap[parent])) break;
    heap[pos] = heap[parent];
    pos = parent;
  }
  heap[pos] = item;
}

/* String max-heap sift */
HOT_FUNCTION static inline void
sift_str_max(PyListObject *listobj, Py_ssize_t n) {
  PyObject **heap = listobj->ob_item;
  Py_ssize_t pos = 0, child, right, parent;
  PyObject *item = heap[0];
  
  while (1) {
    child = (pos << 1) + 1;
    if (child >= n) break;
    right = child + 1;
    if (right < n && str_lt(heap[child], heap[right]))
      child = right;
    heap[pos] = heap[child];
    pos = child;
  }
  
  while (pos > 0) {
    parent = (pos - 1) >> 1;
    if (!str_lt(heap[parent], item)) break;
    heap[pos] = heap[parent];
    pos = parent;
  }
  heap[pos] = item;
}

/* Type detection constants for pop dispatch */
#define ELEM_TYPE_INT 1
#define ELEM_TYPE_FLOAT 2
#define ELEM_TYPE_STR 4
#define ELEM_TYPE_OTHER 7

/* Generic sift using optimized_compare - matches optimized_pop.pyx sift_down_min */
HOT_FUNCTION static inline int
sift_generic_min(PyListObject *listobj, Py_ssize_t n) {
  PyObject **heap = listobj->ob_item;
  Py_ssize_t pos = 0, child, right, parent;
  PyObject *item = heap[0];
  int cmp;
  Py_ssize_t original_size = n;
  
  /* Phase 1: Descend to leaf */
  while (1) {
    child = (pos << 1) + 1;
    if (child >= n) break;
    right = child + 1;
    if (right < n) {
      cmp = optimized_compare(heap[right], heap[child], Py_LT);
      if (cmp < 0) return -1;
      if (unlikely(PyList_GET_SIZE(listobj) != original_size)) {
        PyErr_SetString(PyExc_ValueError, "list modified during heap operation");
        return -1;
      }
      if (cmp) child = right;
      heap = listobj->ob_item;
    }
    heap[pos] = heap[child];
    pos = child;
  }
  
  /* Phase 2: Bubble up */
  heap = listobj->ob_item;
  while (pos > 0) {
    parent = (pos - 1) >> 1;
    cmp = optimized_compare(item, heap[parent], Py_LT);
    if (cmp < 0) return -1;
    if (unlikely(PyList_GET_SIZE(listobj) != original_size)) {
      PyErr_SetString(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (!cmp) break;
    heap = listobj->ob_item;
    heap[pos] = heap[parent];
    pos = parent;
  }
  heap[pos] = item;
  return 0;
}

/* Generic sift using optimized_compare - matches optimized_pop.pyx sift_down_max */
HOT_FUNCTION static inline int
sift_generic_max(PyListObject *listobj, Py_ssize_t n) {
  PyObject **heap = listobj->ob_item;
  Py_ssize_t pos = 0, child, right, parent;
  PyObject *item = heap[0];
  int cmp;
  Py_ssize_t original_size = n;
  
  /* Phase 1: Descend to leaf */
  while (1) {
    child = (pos << 1) + 1;
    if (child >= n) break;
    right = child + 1;
    if (right < n) {
      cmp = optimized_compare(heap[right], heap[child], Py_GT);
      if (cmp < 0) return -1;
      if (unlikely(PyList_GET_SIZE(listobj) != original_size)) {
        PyErr_SetString(PyExc_ValueError, "list modified during heap operation");
        return -1;
      }
      if (cmp) child = right;
      heap = listobj->ob_item;
    }
    heap[pos] = heap[child];
    pos = child;
  }
  
  /* Phase 2: Bubble up */
  heap = listobj->ob_item;
  while (pos > 0) {
    parent = (pos - 1) >> 1;
    cmp = optimized_compare(item, heap[parent], Py_GT);
    if (cmp < 0) return -1;
    if (unlikely(PyList_GET_SIZE(listobj) != original_size)) {
      PyErr_SetString(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (!cmp) break;
    heap = listobj->ob_item;
    heap[pos] = heap[parent];
    pos = parent;
  }
  heap[pos] = item;
  return 0;
}

/* =============================================================================
 * ARITY-SPECIALIZED SIFT DOWN OPERATIONS
 * ============================================================================= */

/* Binary (arity=2) sift down - uses bit-shift <<1, >>1 */
HOT_FUNCTION static inline int
list_sift_down_binary_ultra_optimized(PyListObject *listobj, Py_ssize_t start_pos, Py_ssize_t n, int is_max) {
  PyObject **items = listobj->ob_item;
  PyObject *item = items[start_pos];
  Py_INCREF(item);
  Py_ssize_t list_size = PyList_GET_SIZE(listobj);
  Py_ssize_t pos = start_pos;
  
  /* Phase 1: Descend to leaf */
  while (1) {
    Py_ssize_t child = (pos << 1) + 1;  /* Bit-shift: 2*pos + 1 */
    if (unlikely(child >= n)) break;
    
    Py_ssize_t right = child + 1;
    PyObject *best_item = items[child];
    Py_INCREF(best_item);
    Py_ssize_t best = child;
    
    if (right < n) {
      PyObject *right_item = items[right];
      Py_INCREF(right_item);
      int cmp = optimized_compare(right_item, best_item, is_max ? Py_GT : Py_LT);
      if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
        Py_DECREF(right_item); Py_DECREF(best_item); Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation");
        return -1;
      }
      if (unlikely(cmp < 0)) { Py_DECREF(right_item); Py_DECREF(best_item); Py_DECREF(item); return -1; }
      items = listobj->ob_item;
      if (cmp) { Py_DECREF(best_item); best = right; best_item = right_item; }
      else { Py_DECREF(right_item); }
    }
    
    Py_DECREF(best_item);
    items[pos] = items[best];
    pos = best;
  }
  
  /* Phase 2: Bubble up from leaf position */
  while (pos > start_pos) {
    Py_ssize_t parent = (pos - 1) >> 1;  /* Bit-shift: (pos-1)/2 */
    PyObject *pobj = items[parent];
    Py_INCREF(pobj);
    int cmp = optimized_compare(item, pobj, is_max ? Py_GT : Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
      Py_DECREF(pobj); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(pobj);
    if (!cmp) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Quaternary (arity=4) sift down - uses bit-shift <<2, >>2 */
HOT_FUNCTION static inline int
list_sift_down_quaternary_ultra_optimized(PyListObject *listobj, Py_ssize_t start_pos, Py_ssize_t n, int is_max) {
  PyObject **items = listobj->ob_item;
  PyObject *item = items[start_pos];
  Py_INCREF(item);
  Py_ssize_t list_size = PyList_GET_SIZE(listobj);
  Py_ssize_t pos = start_pos;
  
  /* Phase 1: Descend to leaf */
  while (1) {
    Py_ssize_t child = (pos << 2) + 1;  /* Bit-shift: 4*pos + 1 */
    if (unlikely(child >= n)) break;
    
    /* Prefetch grandchildren */
    Py_ssize_t grandchild = (child << 2) + 1;
    if (likely(grandchild < n)) {
      PREFETCH_MULTIPLE(items, grandchild, 4, n);
    }
    
    Py_ssize_t best = child;
    PyObject *best_item = items[child];
    Py_INCREF(best_item);
    
    Py_ssize_t last = child + 4;
    if (last > n) last = n;
    
    for (Py_ssize_t j = child + 1; j < last; j++) {
      PyObject *cj = items[j];
      Py_INCREF(cj);
      int cmp = optimized_compare(cj, best_item, is_max ? Py_GT : Py_LT);
      if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
        Py_DECREF(cj); Py_DECREF(best_item); Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation");
        return -1;
      }
      if (unlikely(cmp < 0)) { Py_DECREF(cj); Py_DECREF(best_item); Py_DECREF(item); return -1; }
      items = listobj->ob_item;
      if (cmp) { Py_DECREF(best_item); best = j; best_item = cj; }
      else { Py_DECREF(cj); }
    }
    
    Py_DECREF(best_item);
    items[pos] = items[best];
    pos = best;
  }
  
  /* Phase 2: Bubble up from leaf position */
  while (pos > start_pos) {
    Py_ssize_t parent = (pos - 1) >> 2;  /* Bit-shift: (pos-1)/4 */
    PyObject *pobj = items[parent];
    Py_INCREF(pobj);
    int cmp = optimized_compare(item, pobj, is_max ? Py_GT : Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
      Py_DECREF(pobj); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(pobj);
    if (!cmp) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Octonary (arity=8) sift down - uses bit-shift <<3, >>3 */
HOT_FUNCTION static inline int
list_sift_down_octonary_ultra_optimized(PyListObject *listobj, Py_ssize_t start_pos, Py_ssize_t n, int is_max) {
  PyObject **items = listobj->ob_item;
  PyObject *item = items[start_pos];
  Py_INCREF(item);
  Py_ssize_t list_size = PyList_GET_SIZE(listobj);
  Py_ssize_t pos = start_pos;
  
  /* Phase 1: Descend to leaf */
  while (1) {
    Py_ssize_t child = (pos << 3) + 1;  /* Bit-shift: 8*pos + 1 */
    if (unlikely(child >= n)) break;
    
    /* Prefetch grandchildren */
    Py_ssize_t grandchild = (child << 3) + 1;
    if (likely(grandchild < n)) {
      PREFETCH_MULTIPLE_STRIDE(items, grandchild, 8, n, PREFETCH_STRIDE);
    }
    
    Py_ssize_t best = child;
    PyObject *best_item = items[child];
    Py_INCREF(best_item);
    
    Py_ssize_t last = child + 8;
    if (last > n) last = n;
    
    for (Py_ssize_t j = child + 1; j < last; j++) {
      PyObject *cj = items[j];
      Py_INCREF(cj);
      int cmp = optimized_compare(cj, best_item, is_max ? Py_GT : Py_LT);
      if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
        Py_DECREF(cj); Py_DECREF(best_item); Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation");
        return -1;
      }
      if (unlikely(cmp < 0)) { Py_DECREF(cj); Py_DECREF(best_item); Py_DECREF(item); return -1; }
      items = listobj->ob_item;
      if (cmp) { Py_DECREF(best_item); best = j; best_item = cj; }
      else { Py_DECREF(cj); }
    }
    
    Py_DECREF(best_item);
    items[pos] = items[best];
    pos = best;
  }
  
  /* Phase 2: Bubble up from leaf position */
  while (pos > start_pos) {
    Py_ssize_t parent = (pos - 1) >> 3;  /* Bit-shift: (pos-1)/8 */
    PyObject *pobj = items[parent];
    Py_INCREF(pobj);
    int cmp = optimized_compare(item, pobj, is_max ? Py_GT : Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
      Py_DECREF(pobj); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(pobj);
    if (!cmp) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* =============================================================================
 * MAX-HEAP BRANCH OPTIMIZATION - SIFT DOWN VERSIONS
 * ============================================================================= */

/* Binary sift down - MIN heap version (no branch) */
HOT_FUNCTION static inline int
list_sift_down_binary_min(PyListObject *listobj, Py_ssize_t start_pos, Py_ssize_t n) {
  PyObject **items = listobj->ob_item;
  PyObject *item = items[start_pos];
  Py_INCREF(item);
  Py_ssize_t list_size = PyList_GET_SIZE(listobj);
  Py_ssize_t pos = start_pos;
  
  while (1) {
    Py_ssize_t child = (pos << 1) + 1;
    if (unlikely(child >= n)) break;
    
    Py_ssize_t right = child + 1;
    PyObject *best_item = items[child];
    Py_INCREF(best_item);
    Py_ssize_t best = child;
    
    if (right < n) {
      PyObject *right_item = items[right];
      Py_INCREF(right_item);
      int cmp = optimized_compare(right_item, best_item, Py_LT);
      if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
        Py_DECREF(right_item); Py_DECREF(best_item); Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation");
        return -1;
      }
      if (unlikely(cmp < 0)) { Py_DECREF(right_item); Py_DECREF(best_item); Py_DECREF(item); return -1; }
      items = listobj->ob_item;
      if (cmp) { Py_DECREF(best_item); best = right; best_item = right_item; }
      else { Py_DECREF(right_item); }
    }
    
    Py_DECREF(best_item);
    items[pos] = items[best];
    pos = best;
  }
  
  while (pos > start_pos) {
    Py_ssize_t parent = (pos - 1) >> 1;
    PyObject *pobj = items[parent];
    Py_INCREF(pobj);
    int cmp = optimized_compare(item, pobj, Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
      Py_DECREF(pobj); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(pobj);
    if (!cmp) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Binary sift down - MAX heap version (no branch) */
HOT_FUNCTION static inline int
list_sift_down_binary_max(PyListObject *listobj, Py_ssize_t start_pos, Py_ssize_t n) {
  PyObject **items = listobj->ob_item;
  PyObject *item = items[start_pos];
  Py_INCREF(item);
  Py_ssize_t list_size = PyList_GET_SIZE(listobj);
  Py_ssize_t pos = start_pos;
  
  while (1) {
    Py_ssize_t child = (pos << 1) + 1;
    if (unlikely(child >= n)) break;
    
    Py_ssize_t right = child + 1;
    PyObject *best_item = items[child];
    Py_INCREF(best_item);
    Py_ssize_t best = child;
    
    if (right < n) {
      PyObject *right_item = items[right];
      Py_INCREF(right_item);
      int cmp = optimized_compare(right_item, best_item, Py_GT);
      if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
        Py_DECREF(right_item); Py_DECREF(best_item); Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation");
        return -1;
      }
      if (unlikely(cmp < 0)) { Py_DECREF(right_item); Py_DECREF(best_item); Py_DECREF(item); return -1; }
      items = listobj->ob_item;
      if (cmp) { Py_DECREF(best_item); best = right; best_item = right_item; }
      else { Py_DECREF(right_item); }
    }
    
    Py_DECREF(best_item);
    items[pos] = items[best];
    pos = best;
  }
  
  while (pos > start_pos) {
    Py_ssize_t parent = (pos - 1) >> 1;
    PyObject *pobj = items[parent];
    Py_INCREF(pobj);
    int cmp = optimized_compare(item, pobj, Py_GT);
    if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
      Py_DECREF(pobj); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation");
      return -1;
    }
    if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(pobj);
    if (!cmp) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Bottom-up sift down for lists without key functions - for single element operations */
/* Safety: INCREF objects held across comparisons to prevent use-after-free. */
HOT_FUNCTION static inline int
list_sift_down_ultra_optimized(PyListObject *listobj, Py_ssize_t start_pos, Py_ssize_t n, int is_max, Py_ssize_t arity) {
  PyObject **items = listobj->ob_item;
  PyObject *item = items[start_pos];
  Py_INCREF(item);
  Py_ssize_t list_size = PyList_GET_SIZE(listobj);
  Py_ssize_t pos = start_pos;
  
  /* Phase 1: Descend to leaf, only comparing children */
  while (1) {
    Py_ssize_t child = arity * pos + 1;
    if (unlikely(child >= n)) break;
    
    if (arity >= 4) {
      Py_ssize_t grandchild = arity * child + 1;
      if (likely(grandchild < n)) {
        PREFETCH_MULTIPLE(items, grandchild, arity, n);
      }
    }
    
    Py_ssize_t best = child;
    PyObject *best_item = items[child];
    Py_INCREF(best_item);
    
    Py_ssize_t last = child + arity;
    if (unlikely(last > n)) last = n;
    
    for (Py_ssize_t j = child + 1; j < last; j++) {
      PyObject *cj = items[j];
      Py_INCREF(cj);
      int better = optimized_compare(cj, best_item, is_max ? Py_GT : Py_LT);
      if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
        Py_DECREF(cj); Py_DECREF(best_item); Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", list_size, PyList_GET_SIZE(listobj));
        return -1;
      }
      if (unlikely(better < 0)) { Py_DECREF(cj); Py_DECREF(best_item); Py_DECREF(item); return -1; }
      items = listobj->ob_item;
      if (better) { Py_DECREF(best_item); best = j; best_item = cj; }
      else { Py_DECREF(cj); }
    }
    
    Py_DECREF(best_item);
    items[pos] = items[best];
    pos = best;
  }
  
  /* Phase 2: Bubble up from leaf position */
  while (pos > start_pos) {
    Py_ssize_t parent = (pos - 1) / arity;
    PyObject *pobj = items[parent];
    Py_INCREF(pobj);
    int cmp = optimized_compare(item, pobj, is_max ? Py_GT : Py_LT);
    if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
      Py_DECREF(pobj); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", list_size, PyList_GET_SIZE(listobj));
      return -1;
    }
    if (unlikely(cmp < 0)) { Py_DECREF(pobj); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    Py_DECREF(pobj);
    if (!cmp) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
  return 0;
}

/* Bottom-up sift down with key function for lists */
/* Safety: Check list size after key function calls which can modify the list. */
HOT_FUNCTION static inline int
list_sift_down_with_key_ultra_optimized(PyListObject *listobj, Py_ssize_t start_pos, Py_ssize_t n, int is_max, PyObject *keyfunc, Py_ssize_t arity) {
  PyObject **items = listobj->ob_item;
  PyObject *item = items[start_pos];
  Py_INCREF(item);
  Py_ssize_t list_size = PyList_GET_SIZE(listobj);
  
  PyObject *key = call_key_function(keyfunc, item);
  if (unlikely(!key)) { Py_DECREF(item); return -1; }
  if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
    Py_DECREF(key); Py_DECREF(item);
    PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", list_size, PyList_GET_SIZE(listobj));
    return -1;
  }
  items = listobj->ob_item;
  Py_ssize_t pos = start_pos;
  
  /* Phase 1: Descend to leaf, only comparing children */
  while (1) {
    Py_ssize_t child = arity * pos + 1;
    if (unlikely(child >= n)) break;
    
    Py_ssize_t best = child;
    PyObject *best_item = items[child];
    Py_INCREF(best_item);
    PyObject *best_key = call_key_function(keyfunc, best_item);
    if (unlikely(!best_key)) { Py_DECREF(best_item); Py_DECREF(key); Py_DECREF(item); return -1; }
    if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
      Py_DECREF(best_key); Py_DECREF(best_item); Py_DECREF(key); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", list_size, PyList_GET_SIZE(listobj));
      return -1;
    }
    items = listobj->ob_item;
    
    Py_ssize_t last = child + arity;
    if (unlikely(last > n)) last = n;
    
    for (Py_ssize_t j = child + 1; j < last; j++) {
      PyObject *cj = items[j];
      Py_INCREF(cj);
      PyObject *cur_key = call_key_function(keyfunc, cj);
      if (unlikely(!cur_key)) { Py_DECREF(cj); Py_DECREF(best_item); Py_DECREF(key); Py_DECREF(best_key); Py_DECREF(item); return -1; }
      if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
        Py_DECREF(cur_key); Py_DECREF(cj); Py_DECREF(best_key); Py_DECREF(best_item); Py_DECREF(key); Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", list_size, PyList_GET_SIZE(listobj));
        return -1;
      }
      items = listobj->ob_item;
      
      int better = optimized_compare(cur_key, best_key, is_max ? Py_GT : Py_LT);
      if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
        Py_DECREF(cur_key); Py_DECREF(cj); Py_DECREF(best_key); Py_DECREF(best_item); Py_DECREF(key); Py_DECREF(item);
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", list_size, PyList_GET_SIZE(listobj));
        return -1;
      }
      if (unlikely(better < 0)) { Py_DECREF(cur_key); Py_DECREF(cj); Py_DECREF(best_key); Py_DECREF(best_item); Py_DECREF(key); Py_DECREF(item); return -1; }
      items = listobj->ob_item;
      
      if (better) {
        Py_DECREF(best_key);
        Py_DECREF(best_item);
        best = j;
        best_item = cj;
        best_key = cur_key;
      } else {
        Py_DECREF(cur_key);
        Py_DECREF(cj);
      }
    }
    
    Py_DECREF(best_key);
    Py_DECREF(best_item);
    items[pos] = items[best];
    pos = best;
  }
  
  /* Phase 2: Bubble up from leaf position */
  while (pos > start_pos) {
    Py_ssize_t parent = (pos - 1) / arity;
    PyObject *parent_key = call_key_function(keyfunc, items[parent]);
    if (unlikely(!parent_key)) { Py_DECREF(key); Py_DECREF(item); return -1; }
    if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
      Py_DECREF(parent_key); Py_DECREF(key); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", list_size, PyList_GET_SIZE(listobj));
      return -1;
    }
    int cmp = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
    Py_DECREF(parent_key);
    if (unlikely(PyList_GET_SIZE(listobj) != list_size)) {
      Py_DECREF(key); Py_DECREF(item);
      PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", list_size, PyList_GET_SIZE(listobj));
      return -1;
    }
    if (unlikely(cmp < 0)) { Py_DECREF(key); Py_DECREF(item); return -1; }
    items = listobj->ob_item;
    if (!cmp) break;
    
    items[pos] = items[parent];
    pos = parent;
  }
  
  items[pos] = item;
  Py_DECREF(item);
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
  
  /* REFRESH POINTER */
  items = listobj->ob_item;
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
      /* REFRESH POINTER */
      items = listobj->ob_item;
      int cmp_res = optimized_compare(items[idx], items[parent], is_max ? Py_GT : Py_LT);
      /* SAFETY CHECK */
      if (unlikely(Py_SIZE(listobj) != new_size)) {
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        Py_DECREF(removed);
        return -1;
      }
      if (unlikely(cmp_res < 0)) {
        Py_DECREF(removed);
        return -1;
      }
      if (cmp_res) {
        /* Use specialized sift_up based on arity */
        int rc;
        switch (arity) {
          case 2:
            rc = list_sift_up_binary_ultra_optimized(listobj, idx, is_max);
            break;
          case 4:
            rc = list_sift_up_quaternary_ultra_optimized(listobj, idx, is_max);
            break;
          case 8:
            rc = list_sift_up_octonary_ultra_optimized(listobj, idx, is_max);
            break;
          default:
            rc = list_sift_up_ultra_optimized(listobj, idx, is_max, arity);
            break;
        }
        if (unlikely(rc < 0)) {
          Py_DECREF(removed);
          return -1;
        }
        Py_DECREF(removed);
        return 0;
      }
    }
    /* Use specialized sift_down based on arity */
    int rc;
    switch (arity) {
      case 2:
        rc = list_sift_down_binary_ultra_optimized(listobj, idx, new_size, is_max);
        break;
      case 4:
        rc = list_sift_down_quaternary_ultra_optimized(listobj, idx, new_size, is_max);
        break;
      case 8:
        rc = list_sift_down_octonary_ultra_optimized(listobj, idx, new_size, is_max);
        break;
      default:
        rc = list_sift_down_ultra_optimized(listobj, idx, new_size, is_max, arity);
        break;
    }
    if (unlikely(rc < 0)) {
      Py_DECREF(removed);
      return -1;
    }
  } else {
    if (idx > 0) {
      Py_ssize_t parent = (idx - 1) / arity;
      /* REFRESH POINTER */
      items = listobj->ob_item;
      PyObject *key_item = call_key_function(keyfunc, items[idx]);
      if (unlikely(!key_item)) {
        Py_DECREF(removed);
        return -1;
      }
      /* SAFETY CHECK */
      if (unlikely(Py_SIZE(listobj) != new_size)) {
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        Py_DECREF(key_item);
        Py_DECREF(removed);
        return -1;
      }
      /* REFRESH POINTER */
      items = listobj->ob_item;
      PyObject *key_parent = call_key_function(keyfunc, items[parent]);
      if (unlikely(!key_parent)) {
        Py_DECREF(key_item);
        Py_DECREF(removed);
        return -1;
      }
      /* SAFETY CHECK */
      if (unlikely(Py_SIZE(listobj) != new_size)) {
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        Py_DECREF(key_item);
        Py_DECREF(key_parent);
        Py_DECREF(removed);
        return -1;
      }
      int cmp_res = optimized_compare(key_item, key_parent, is_max ? Py_GT : Py_LT);
      Py_DECREF(key_item);
      Py_DECREF(key_parent);
      /* SAFETY CHECK */
      if (unlikely(Py_SIZE(listobj) != new_size)) {
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        Py_DECREF(removed);
        return -1;
      }
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
py_push(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames) {
  (void)self;  /* Module method, self is unused */
  
  /* ========== FAST PATH: push(heap, item) with all defaults ========== 
   * Condition: exactly 2 positional args, no kwargs, heap is list, item is not list (bulk)
   * This bypasses PyArg_ParseTupleAndKeywords entirely for ~20ns savings */
  if (likely(nargs == 2 && kwnames == NULL)) {
    PyObject *heap = args[0];
    PyObject *item = args[1];
    
    if (likely(PyList_CheckExact(heap) && !PyList_CheckExact(item))) {
      /* Append item */
      if (unlikely(PyList_Append(heap, item) < 0)) return NULL;
      
      /* Inline binary min-heap sift-up with safety checks */
      PyListObject *listobj = (PyListObject *)heap;
      Py_ssize_t n = PyList_GET_SIZE(heap);
      Py_ssize_t pos = n - 1;
      
      while (pos > 0) {
        Py_ssize_t parent = (pos - 1) >> 1;
        
        /* Refresh pointer after potential reallocation */
        PyObject **arr = listobj->ob_item;
        PyObject *newitem = arr[pos];
        PyObject *parent_item = arr[parent];
        
        Py_INCREF(newitem);
        Py_INCREF(parent_item);
        int cmp = PyObject_RichCompareBool(newitem, parent_item, Py_LT);
        Py_DECREF(parent_item);
        Py_DECREF(newitem);
        
        /* Safety check: verify list wasn't modified during comparison */
        if (unlikely(PyList_GET_SIZE(heap) != n)) {
          PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(heap));
          return NULL;
        }
        
        if (unlikely(cmp < 0)) return NULL;
        if (cmp == 0) break;
        
        /* Refresh pointer and swap */
        arr = listobj->ob_item;
        PyObject *tmp = arr[parent];
        arr[parent] = arr[pos];
        arr[pos] = tmp;
        pos = parent;
      }
      
      Py_RETURN_NONE;
    }
  }
  
  /* ========== SLOW PATH: Full argument parsing ========== */
  /* Convert FASTCALL args to tuple and kwargs dict for PyArg_ParseTupleAndKeywords */
  PyObject *args_tuple = PyTuple_New(nargs);
  if (unlikely(!args_tuple)) return NULL;
  for (Py_ssize_t i = 0; i < nargs; i++) {
    Py_INCREF(args[i]);
    PyTuple_SET_ITEM(args_tuple, i, args[i]);
  }
  
  PyObject *kwargs = NULL;
  if (kwnames != NULL) {
    Py_ssize_t nkw = PyTuple_GET_SIZE(kwnames);
    kwargs = PyDict_New();
    if (unlikely(!kwargs)) { Py_DECREF(args_tuple); return NULL; }
    for (Py_ssize_t i = 0; i < nkw; i++) {
      PyObject *key = PyTuple_GET_ITEM(kwnames, i);
      PyObject *value = args[nargs + i];
      if (unlikely(PyDict_SetItem(kwargs, key, value) < 0)) {
        Py_DECREF(args_tuple);
        Py_DECREF(kwargs);
        return NULL;
      }
    }
  }
  
  static char *kwlist[] = {"heap", "items", "max_heap", "cmp", "arity", "nogil", NULL};
  PyObject *heap, *items;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;
  PyObject *nogil_obj = Py_False;

  if (!PyArg_ParseTupleAndKeywords(args_tuple, kwargs, "OO|OOnO:push", kwlist,
                                   &heap, &items, &max_heap_obj, &cmp, &arity, &nogil_obj)) {
    Py_DECREF(args_tuple);
    Py_XDECREF(kwargs);
    return NULL;
  }
  Py_DECREF(args_tuple);
  Py_XDECREF(kwargs);

  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;
  
  int nogil = PyObject_IsTrue(nogil_obj);
  if (unlikely(nogil < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_Format(PyExc_TypeError, "cmp must be callable or None, not %.200s", Py_TYPE(cmp)->tp_name);
    return NULL;
  }
  if (unlikely(arity < 1 || arity > HEAPX_MAX_ARITY)) {
    PyErr_Format(PyExc_ValueError, "arity must be >= 1 and <= 64, got %zd", arity);
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
    Py_ssize_t total_size = n + n_items;
    
    /* Priority 1: Small heap (n ≤ 16) - use sift-up for each new element */
    if (unlikely(total_size <= HEAPX_SMALL_HEAP_THRESHOLD && cmp == Py_None)) {
      for (Py_ssize_t idx = n; idx < total_size; idx++) {
        if (unlikely(list_sift_up_ultra_optimized(listobj, idx, is_max, arity) < 0)) {
          return NULL;
        }
      }
      Py_RETURN_NONE;
    }
    
    /* ========== BULK PUSH OPTIMIZATION ==========
     * When inserting many items, a single O(n+k) heapify is faster than
     * k individual O(log(n+k)) sift-up operations.
     * Empirical analysis shows heapify wins when k >= n (doubling heap size).
     * Also use heapify for empty heaps (n=0) since there's no structure to preserve. */
    if (n_items >= n || n == 0) {
      int rc = 0;
      int homogeneous = (total_size >= 8 && cmp == Py_None) ? detect_homogeneous_type(listobj->ob_item, total_size) : 0;
      
      if (likely(cmp == Py_None)) {
        if (arity == 1) {
          rc = heapify_arity_one_ultra_optimized((PyObject *)listobj, is_max, NULL);
        } else if (arity == 2) {
          if (nogil && homogeneous == 2) {
            rc = list_heapify_homogeneous_float_nogil(listobj, is_max);
          } else if (nogil && homogeneous == 1) {
            rc = list_heapify_homogeneous_int_nogil(listobj, is_max);
            if (rc == 2) { PyErr_Clear(); rc = list_heapify_floyd_ultra_optimized(listobj, is_max); }
          } else if (homogeneous == 2) {
            rc = list_heapify_homogeneous_float(listobj, is_max);
          } else if (homogeneous == 1) {
            rc = list_heapify_homogeneous_int(listobj, is_max);
            if (rc == 2) { PyErr_Clear(); rc = list_heapify_floyd_ultra_optimized(listobj, is_max); }
          } else {
            rc = list_heapify_floyd_ultra_optimized(listobj, is_max);
          }
        } else if (arity == 3) {
          if (nogil && homogeneous == 2) {
            rc = list_heapify_ternary_homogeneous_float_nogil(listobj, is_max);
          } else if (nogil && homogeneous == 1) {
            rc = list_heapify_ternary_homogeneous_int_nogil(listobj, is_max);
            if (rc == 2) { PyErr_Clear(); rc = list_heapify_ternary_ultra_optimized(listobj, is_max); }
          } else if (homogeneous == 2) {
            rc = list_heapify_ternary_homogeneous_float(listobj, is_max);
          } else if (homogeneous == 1) {
            rc = list_heapify_ternary_homogeneous_int(listobj, is_max);
            if (rc == 2) { PyErr_Clear(); rc = list_heapify_ternary_ultra_optimized(listobj, is_max); }
          } else {
            rc = list_heapify_ternary_ultra_optimized(listobj, is_max);
          }
        } else if (arity == 4) {
          if (nogil && homogeneous == 2) {
            rc = list_heapify_quaternary_homogeneous_float_nogil(listobj, is_max);
          } else if (nogil && homogeneous == 1) {
            rc = list_heapify_quaternary_homogeneous_int_nogil(listobj, is_max);
            if (rc == 2) { PyErr_Clear(); rc = list_heapify_quaternary_ultra_optimized(listobj, is_max); }
          } else if (homogeneous == 2) {
            rc = list_heapify_quaternary_homogeneous_float(listobj, is_max);
          } else if (homogeneous == 1) {
            rc = list_heapify_quaternary_homogeneous_int(listobj, is_max);
            if (rc == 2) { PyErr_Clear(); rc = list_heapify_quaternary_ultra_optimized(listobj, is_max); }
          } else {
            rc = list_heapify_quaternary_ultra_optimized(listobj, is_max);
          }
        } else {
          if (nogil && homogeneous == 2) {
            rc = list_heapify_nary_simd_homogeneous_float_nogil(listobj, is_max, arity);
          } else if (nogil && homogeneous == 1) {
            rc = list_heapify_nary_simd_homogeneous_int_nogil(listobj, is_max, arity);
            if (rc == 2) { PyErr_Clear(); rc = (total_size < HEAPX_LARGE_HEAP_THRESHOLD) ? list_heapify_small_ultra_optimized(listobj, is_max, arity) : generic_heapify_ultra_optimized((PyObject *)listobj, is_max, NULL, arity); }
          } else if (homogeneous == 2) {
            rc = list_heapify_nary_simd_homogeneous_float(listobj, is_max, arity);
          } else if (homogeneous == 1) {
            rc = list_heapify_nary_simd_homogeneous_int(listobj, is_max, arity);
            if (rc == 2) { PyErr_Clear(); rc = (total_size < HEAPX_LARGE_HEAP_THRESHOLD) ? list_heapify_small_ultra_optimized(listobj, is_max, arity) : generic_heapify_ultra_optimized((PyObject *)listobj, is_max, NULL, arity); }
          } else {
            rc = (total_size < HEAPX_LARGE_HEAP_THRESHOLD) ? list_heapify_small_ultra_optimized(listobj, is_max, arity) : generic_heapify_ultra_optimized((PyObject *)listobj, is_max, NULL, arity);
          }
        }
      } else {
        switch (arity) {
          case 1:
            rc = heapify_arity_one_ultra_optimized((PyObject *)listobj, is_max, cmp);
            break;
          case 2:
            rc = list_heapify_with_key_ultra_optimized(listobj, cmp, is_max);
            break;
          case 3:
            rc = list_heapify_ternary_with_key_ultra_optimized(listobj, cmp, is_max);
            break;
          default:
            rc = generic_heapify_ultra_optimized((PyObject *)listobj, is_max, cmp, arity);
            break;
        }
      }
      if (unlikely(rc < 0)) return NULL;
      Py_RETURN_NONE;
    }
    
    if (likely(cmp == Py_None)) {
      /* No key function path */
      
      /* Homogeneous detection for heaps >= 8 elements.
       * Single-item push cannot safely use homogeneous fast path because we can't
       * verify the entire heap is homogeneous in O(1). The heap may contain mixed
       * types even if first element and new item are the same type.
       * Bulk push: Full scan is amortized over n_items. */
      int homogeneous = (n_items > 1 && total_size >= 8) ? detect_homogeneous_type(listobj->ob_item, total_size) : 0;
      
      /* Priority 2: Arity = 1 (sorted list) */
      if (unlikely(arity == 1)) {
        /* Binary insertion for each new element to maintain sorted order */
        for (Py_ssize_t i = n; i < total_size; i++) {
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          PyObject *item = arr[i];
          Py_INCREF(item);
          Py_ssize_t left = 0, right = i;
          /* Binary search for insertion position */
          while (left < right) {
            Py_ssize_t mid = (left + right) >> 1;
            /* REFRESH POINTER */
            arr = listobj->ob_item;
            int cmp_res = optimized_compare(item, arr[mid], is_max ? Py_GT : Py_LT);
            /* SAFETY CHECK */
            if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
              PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
              Py_DECREF(item);
              return NULL;
            }
            if (unlikely(cmp_res < 0)) { Py_DECREF(item); return NULL; }
            if (cmp_res) right = mid;
            else left = mid + 1;
          }
          /* Shift elements and insert - REFRESH POINTER */
          arr = listobj->ob_item;
          if (left < i) {
            PyObject *tmp = arr[i];
            for (Py_ssize_t j = i; j > left; j--) arr[j] = arr[j - 1];
            arr[left] = tmp;
          }
          Py_DECREF(item);
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 3: Binary heap (arity=2) - most common */
      if (likely(arity == 2)) {
        /* Homogeneous fast path for binary heap */
        if (homogeneous == 2) {
          for (Py_ssize_t idx = n; idx < total_size; idx++) {
            if (unlikely(list_sift_up_homogeneous_float(listobj, idx, is_max, 2) != 0)) goto binary_generic;
          }
          Py_RETURN_NONE;
        }
        if (homogeneous == 1) {
          for (Py_ssize_t idx = n; idx < total_size; idx++) {
            int rc = list_sift_up_homogeneous_int(listobj, idx, is_max, 2);
            if (unlikely(rc == 1)) goto binary_generic;
            if (unlikely(rc < 0)) return NULL;
          }
          Py_RETURN_NONE;
        }
        binary_generic:
        /* Use specialized binary sift_up with bit-shift optimization */
        for (Py_ssize_t idx = n; idx < total_size; idx++) {
          if (unlikely(list_sift_up_binary_ultra_optimized(listobj, idx, is_max) < 0)) return NULL;
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 4: Ternary heap (arity=3) */
      if (arity == 3) {
        /* Homogeneous fast path for ternary heap */
        if (homogeneous == 2) {
          for (Py_ssize_t idx = n; idx < total_size; idx++) {
            if (unlikely(list_sift_up_homogeneous_float(listobj, idx, is_max, 3) != 0)) goto ternary_generic;
          }
          Py_RETURN_NONE;
        }
        if (homogeneous == 1) {
          for (Py_ssize_t idx = n; idx < total_size; idx++) {
            int rc = list_sift_up_homogeneous_int(listobj, idx, is_max, 3);
            if (unlikely(rc == 1)) goto ternary_generic;
            if (unlikely(rc < 0)) return NULL;
          }
          Py_RETURN_NONE;
        }
        ternary_generic:
        for (Py_ssize_t idx = n; idx < total_size; idx++) {
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          Py_ssize_t pos = idx;
          PyObject *item = arr[pos];
          Py_INCREF(item);
          while (pos > 0) {
            Py_ssize_t parent = (pos - 1) / 3;
            /* REFRESH POINTER */
            arr = listobj->ob_item;
            int cmp_res = optimized_compare(item, arr[parent], is_max ? Py_GT : Py_LT);
            /* SAFETY CHECK */
            if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
              PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
              Py_DECREF(item);
              return NULL;
            }
            if (unlikely(cmp_res < 0)) { Py_DECREF(item); return NULL; }
            /* REFRESH POINTER */
            arr = listobj->ob_item;
            if (!cmp_res) break;
            arr[pos] = arr[parent];
            pos = parent;
          }
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          arr[pos] = item;
          Py_DECREF(item);
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 5: Quaternary heap (arity=4) */
      if (arity == 4) {
        /* Homogeneous fast path for quaternary heap */
        if (homogeneous == 2) {
          for (Py_ssize_t idx = n; idx < total_size; idx++) {
            if (unlikely(list_sift_up_homogeneous_float(listobj, idx, is_max, 4) != 0)) goto quaternary_generic;
          }
          Py_RETURN_NONE;
        }
        if (homogeneous == 1) {
          for (Py_ssize_t idx = n; idx < total_size; idx++) {
            int rc = list_sift_up_homogeneous_int(listobj, idx, is_max, 4);
            if (unlikely(rc == 1)) goto quaternary_generic;
            if (unlikely(rc < 0)) return NULL;
          }
          Py_RETURN_NONE;
        }
        quaternary_generic:
        /* Use specialized quaternary sift_up with bit-shift optimization */
        for (Py_ssize_t idx = n; idx < total_size; idx++) {
          if (unlikely(list_sift_up_quaternary_ultra_optimized(listobj, idx, is_max) < 0)) return NULL;
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 6: Octonary heap (arity=8) */
      if (arity == 8) {
        /* Use specialized octonary sift_up with bit-shift optimization */
        for (Py_ssize_t idx = n; idx < total_size; idx++) {
          if (unlikely(list_sift_up_octonary_ultra_optimized(listobj, idx, is_max) < 0)) return NULL;
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 7: General n-ary (arity≥5, arity!=8) */
      /* Homogeneous fast path for n-ary heap */
      if (homogeneous == 2) {
        for (Py_ssize_t idx = n; idx < total_size; idx++) {
          if (unlikely(list_sift_up_homogeneous_float(listobj, idx, is_max, arity) != 0)) goto nary_generic;
        }
        Py_RETURN_NONE;
      }
      if (homogeneous == 1) {
        for (Py_ssize_t idx = n; idx < total_size; idx++) {
          int rc = list_sift_up_homogeneous_int(listobj, idx, is_max, arity);
          if (unlikely(rc == 1)) goto nary_generic;
          if (unlikely(rc < 0)) return NULL;
        }
        Py_RETURN_NONE;
      }
      nary_generic:
      for (Py_ssize_t idx = n; idx < total_size; idx++) {
        /* REFRESH POINTER */
        arr = listobj->ob_item;
        Py_ssize_t pos = idx;
        PyObject *item = arr[pos];
        Py_INCREF(item);
        while (pos > 0) {
          Py_ssize_t parent = (pos - 1) / arity;
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          int cmp_res = optimized_compare(item, arr[parent], is_max ? Py_GT : Py_LT);
          /* SAFETY CHECK */
          if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
            PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
            Py_DECREF(item);
            return NULL;
          }
          if (unlikely(cmp_res < 0)) { Py_DECREF(item); return NULL; }
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          if (!cmp_res) break;
          arr[pos] = arr[parent];
          pos = parent;
        }
        /* REFRESH POINTER */
        arr = listobj->ob_item;
        arr[pos] = item;
        Py_DECREF(item);
      }
      Py_RETURN_NONE;
      
    } else {
      /* With key function path */
      
      /* Priority 8: Binary heap with key (arity=2) */
      if (likely(arity == 2)) {
        for (Py_ssize_t idx = n; idx < total_size; idx++) {
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          Py_ssize_t pos = idx;
          PyObject *item = arr[pos];
          Py_INCREF(item);
          PyObject *key = call_key_function(cmp, item);
          if (unlikely(!key)) { Py_DECREF(item); return NULL; }
          /* SAFETY CHECK */
          if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
            PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
            Py_DECREF(item);
            Py_DECREF(key);
            return NULL;
          }
          
          while (pos > 0) {
            Py_ssize_t parent = (pos - 1) >> 1;
            /* REFRESH POINTER */
            arr = listobj->ob_item;
            PyObject *parent_key = call_key_function(cmp, arr[parent]);
            if (unlikely(!parent_key)) { Py_DECREF(item); Py_DECREF(key); return NULL; }
            /* SAFETY CHECK */
            if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
              PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
              Py_DECREF(item);
              Py_DECREF(key);
              Py_DECREF(parent_key);
              return NULL;
            }
            
            int cmp_res = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
            Py_DECREF(parent_key);
            /* SAFETY CHECK */
            if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
              PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
              Py_DECREF(item);
              Py_DECREF(key);
              return NULL;
            }
            if (unlikely(cmp_res < 0)) { Py_DECREF(item); Py_DECREF(key); return NULL; }
            /* REFRESH POINTER */
            arr = listobj->ob_item;
            if (!cmp_res) break;
            
            arr[pos] = arr[parent];
            pos = parent;
          }
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          arr[pos] = item;
          Py_DECREF(item);
          Py_DECREF(key);
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 9: Ternary heap with key (arity=3) */
      if (arity == 3) {
        for (Py_ssize_t idx = n; idx < total_size; idx++) {
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          Py_ssize_t pos = idx;
          PyObject *item = arr[pos];
          Py_INCREF(item);
          PyObject *key = call_key_function(cmp, item);
          if (unlikely(!key)) { Py_DECREF(item); return NULL; }
          /* SAFETY CHECK */
          if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
            PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
            Py_DECREF(item);
            Py_DECREF(key);
            return NULL;
          }
          
          while (pos > 0) {
            Py_ssize_t parent = (pos - 1) / 3;
            /* REFRESH POINTER */
            arr = listobj->ob_item;
            PyObject *parent_key = call_key_function(cmp, arr[parent]);
            if (unlikely(!parent_key)) { Py_DECREF(item); Py_DECREF(key); return NULL; }
            /* SAFETY CHECK */
            if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
              PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
              Py_DECREF(item);
              Py_DECREF(key);
              Py_DECREF(parent_key);
              return NULL;
            }
            
            int cmp_res = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
            Py_DECREF(parent_key);
            /* SAFETY CHECK */
            if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
              PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
              Py_DECREF(item);
              Py_DECREF(key);
              return NULL;
            }
            if (unlikely(cmp_res < 0)) { Py_DECREF(item); Py_DECREF(key); return NULL; }
            /* REFRESH POINTER */
            arr = listobj->ob_item;
            if (!cmp_res) break;
            
            arr[pos] = arr[parent];
            pos = parent;
          }
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          arr[pos] = item;
          Py_DECREF(item);
          Py_DECREF(key);
        }
        Py_RETURN_NONE;
      }
      
      /* Priority 10: General n-ary with key (arity≥4) */
      for (Py_ssize_t idx = n; idx < total_size; idx++) {
        /* REFRESH POINTER */
        arr = listobj->ob_item;
        Py_ssize_t pos = idx;
        PyObject *item = arr[pos];
        Py_INCREF(item);
        PyObject *key = call_key_function(cmp, item);
        if (unlikely(!key)) { Py_DECREF(item); return NULL; }
        /* SAFETY CHECK */
        if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
          PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
          Py_DECREF(item);
          Py_DECREF(key);
          return NULL;
        }
        
        while (pos > 0) {
          Py_ssize_t parent = (pos - 1) / arity;
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          PyObject *parent_key = call_key_function(cmp, arr[parent]);
          if (unlikely(!parent_key)) { Py_DECREF(item); Py_DECREF(key); return NULL; }
          /* SAFETY CHECK */
          if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
            PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
            Py_DECREF(item);
            Py_DECREF(key);
            Py_DECREF(parent_key);
            return NULL;
          }
          
          int cmp_res = optimized_compare(key, parent_key, is_max ? Py_GT : Py_LT);
          Py_DECREF(parent_key);
          /* SAFETY CHECK */
          if (unlikely(PyList_GET_SIZE(heap) != total_size)) {
            PyErr_Format(PyExc_ValueError, "list modified during push (expected size %zd, got %zd)", total_size, PyList_GET_SIZE(heap));
            Py_DECREF(item);
            Py_DECREF(key);
            return NULL;
          }
          if (unlikely(cmp_res < 0)) { Py_DECREF(item); Py_DECREF(key); return NULL; }
          /* REFRESH POINTER */
          arr = listobj->ob_item;
          if (!cmp_res) break;
          
          arr[pos] = arr[parent];
          pos = parent;
        }
        /* REFRESH POINTER */
        arr = listobj->ob_item;
        arr[pos] = item;
        Py_DECREF(item);
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

/* NoGIL bulk pop for homogeneous float arrays */
HOT_FUNCTION static PyObject *
list_pop_bulk_homogeneous_float_nogil(PyListObject *listobj, Py_ssize_t k, int is_max, Py_ssize_t arity)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(k > n)) k = n;
  if (unlikely(k <= 0 || n <= 0)) return PyList_New(0);

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  double stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  Py_ssize_t stack_popped[VALUE_STACK_SIZE];
  double * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  Py_ssize_t * HEAPX_RESTRICT popped_indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 32);
    indices = stack_indices;
    popped_indices = stack_popped;
  } else {
    values = (double *)PyMem_Malloc(sizeof(double) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    popped_indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)k);
    if (unlikely(!values || !indices || !popped_indices)) {
      PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices);
      PyErr_NoMemory(); return NULL;
    }
  }

  /* PHASE 1: Extract values (GIL held) */
  HEAPX_PRAGMA_SIMD
  for (Py_ssize_t i = 0; i < n; i++) {
    values[i] = PyFloat_AS_DOUBLE(items[i]);
    indices[i] = i;
  }

  /* PHASE 2: Bulk pop with GIL released */
  Py_BEGIN_ALLOW_THREADS
  
  Py_ssize_t heap_size = n;
  for (Py_ssize_t pop_idx = 0; pop_idx < k; pop_idx++) {
    popped_indices[pop_idx] = indices[0];
    heap_size--;
    
    if (heap_size > 0) {
      values[0] = values[heap_size];
      indices[0] = indices[heap_size];
      
      /* Sift-down */
      Py_ssize_t pos = 0;
      double val = values[0];
      Py_ssize_t idx = indices[0];
      
      while (1) {
        Py_ssize_t first_child = arity * pos + 1;
        if (first_child >= heap_size) break;
        
        Py_ssize_t n_children = heap_size - first_child;
        if (n_children > arity) n_children = arity;
        
        Py_ssize_t best = first_child;
        double best_val = values[first_child];
        for (Py_ssize_t j = 1; j < n_children; j++) {
          double child_val = values[first_child + j];
          if (is_max ? HEAPX_FLOAT_GT(child_val, best_val) : HEAPX_FLOAT_LT(child_val, best_val)) {
            best = first_child + j;
            best_val = child_val;
          }
        }
        
        if (is_max ? HEAPX_FLOAT_GE(val, best_val) : HEAPX_FLOAT_LE(val, best_val)) break;
        
        values[pos] = values[best];
        indices[pos] = indices[best];
        pos = best;
      }
      values[pos] = val;
      indices[pos] = idx;
    }
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and build result (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
    PyErr_SetString(PyExc_ValueError, "list modified by another thread during pop");
    return NULL;
  }
  
  /* Build result list from popped indices */
  PyObject *results = PyList_New(k);
  if (unlikely(!results)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
    return NULL;
  }
  
  items = listobj->ob_item;
  for (Py_ssize_t i = 0; i < k; i++) {
    PyObject *item = items[popped_indices[i]];
    Py_INCREF(item);
    PyList_SET_ITEM(results, i, item);
  }
  
  /* Rearrange remaining elements: indices[0..new_size-1] tells us which original
     items should be at each position in the final heap */
  Py_ssize_t new_size = n - k;
  if (new_size > 0) {
    /* Use temporary array to hold references during rearrangement */
    PyObject **temp = (PyObject **)PyMem_Malloc(sizeof(PyObject *) * (size_t)new_size);
    if (unlikely(!temp)) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
      Py_DECREF(results);
      PyErr_NoMemory();
      return NULL;
    }
    
    /* Copy references to temp in new order */
    for (Py_ssize_t i = 0; i < new_size; i++) {
      temp[i] = items[indices[i]];
      Py_INCREF(temp[i]);
    }
    
    /* Copy back to list */
    for (Py_ssize_t i = 0; i < new_size; i++) {
      Py_SETREF(items[i], temp[i]);
    }
    
    PyMem_Free(temp);
  }
  
  /* Shrink the list - this will DECREF the removed items */
  if (unlikely(PyList_SetSlice((PyObject *)listobj, new_size, n, NULL) < 0)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
    Py_DECREF(results);
    return NULL;
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
  return results;
}

/* NoGIL bulk pop for homogeneous integer arrays */
HOT_FUNCTION static PyObject *
list_pop_bulk_homogeneous_int_nogil(PyListObject *listobj, Py_ssize_t k, int is_max, Py_ssize_t arity)
{
  Py_ssize_t n = PyList_GET_SIZE(listobj);
  if (unlikely(k > n)) k = n;
  if (unlikely(k <= 0 || n <= 0)) return PyList_New(0);

  PyObject ** HEAPX_RESTRICT items = listobj->ob_item;
  
  long stack_values[VALUE_STACK_SIZE];
  Py_ssize_t stack_indices[VALUE_STACK_SIZE];
  Py_ssize_t stack_popped[VALUE_STACK_SIZE];
  long * HEAPX_RESTRICT values;
  Py_ssize_t * HEAPX_RESTRICT indices;
  Py_ssize_t * HEAPX_RESTRICT popped_indices;
  int use_stack = (n <= VALUE_STACK_SIZE);
  
  if (use_stack) {
    values = ASSUME_ALIGNED(stack_values, 16);
    indices = stack_indices;
    popped_indices = stack_popped;
  } else {
    values = (long *)PyMem_Malloc(sizeof(long) * (size_t)n);
    indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)n);
    popped_indices = (Py_ssize_t *)PyMem_Malloc(sizeof(Py_ssize_t) * (size_t)k);
    if (unlikely(!values || !indices || !popped_indices)) {
      PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices);
      PyErr_NoMemory(); return NULL;
    }
  }

  /* PHASE 1: Extract values (GIL held) */
  for (Py_ssize_t i = 0; i < n; i++) {
    int overflow = 0;
    values[i] = PyLong_AsLongAndOverflow(items[i], &overflow);
    if (unlikely(overflow != 0)) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
      PyErr_Clear(); /* Clear to allow fallback to standard path */
      return NULL;
    }
    if (unlikely(values[i] == -1 && PyErr_Occurred())) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
      PyErr_Clear(); /* Clear to allow fallback to standard path */
      return NULL;
    }
    indices[i] = i;
  }

  /* PHASE 2: Bulk pop with GIL released */
  Py_BEGIN_ALLOW_THREADS
  
  Py_ssize_t heap_size = n;
  for (Py_ssize_t pop_idx = 0; pop_idx < k; pop_idx++) {
    popped_indices[pop_idx] = indices[0];
    heap_size--;
    
    if (heap_size > 0) {
      values[0] = values[heap_size];
      indices[0] = indices[heap_size];
      
      /* Sift-down */
      Py_ssize_t pos = 0;
      long val = values[0];
      Py_ssize_t idx = indices[0];
      
      while (1) {
        Py_ssize_t first_child = arity * pos + 1;
        if (first_child >= heap_size) break;
        
        Py_ssize_t n_children = heap_size - first_child;
        if (n_children > arity) n_children = arity;
        
        Py_ssize_t best = first_child;
        long best_val = values[first_child];
        for (Py_ssize_t j = 1; j < n_children; j++) {
          long child_val = values[first_child + j];
          if (is_max ? (child_val > best_val) : (child_val < best_val)) {
            best = first_child + j;
            best_val = child_val;
          }
        }
        
        if (is_max ? (val >= best_val) : (val <= best_val)) break;
        
        values[pos] = values[best];
        indices[pos] = indices[best];
        pos = best;
      }
      values[pos] = val;
      indices[pos] = idx;
    }
  }
  
  Py_END_ALLOW_THREADS

  /* PHASE 3: Validate and build result (GIL held) */
  if (unlikely(PyList_GET_SIZE(listobj) != n)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
    PyErr_SetString(PyExc_ValueError, "list modified by another thread during pop");
    return NULL;
  }
  
  /* Build result list from popped indices */
  PyObject *results = PyList_New(k);
  if (unlikely(!results)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
    return NULL;
  }
  
  items = listobj->ob_item;
  for (Py_ssize_t i = 0; i < k; i++) {
    PyObject *item = items[popped_indices[i]];
    Py_INCREF(item);
    PyList_SET_ITEM(results, i, item);
  }
  
  /* Rearrange remaining elements: indices[0..new_size-1] tells us which original
     items should be at each position in the final heap */
  Py_ssize_t new_size = n - k;
  if (new_size > 0) {
    /* Use temporary array to hold references during rearrangement */
    PyObject **temp = (PyObject **)PyMem_Malloc(sizeof(PyObject *) * (size_t)new_size);
    if (unlikely(!temp)) {
      if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
      Py_DECREF(results);
      PyErr_NoMemory();
      return NULL;
    }
    
    /* Copy references to temp in new order */
    for (Py_ssize_t i = 0; i < new_size; i++) {
      temp[i] = items[indices[i]];
      Py_INCREF(temp[i]);
    }
    
    /* Copy back to list */
    for (Py_ssize_t i = 0; i < new_size; i++) {
      Py_SETREF(items[i], temp[i]);
    }
    
    PyMem_Free(temp);
  }
  
  /* Shrink the list - this will DECREF the removed items */
  if (unlikely(PyList_SetSlice((PyObject *)listobj, new_size, n, NULL) < 0)) {
    if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
    Py_DECREF(results);
    return NULL;
  }
  
  if (!use_stack) { PyMem_Free(values); PyMem_Free(indices); PyMem_Free(popped_indices); }
  return results;
}

/* Ultra-optimized pop with comprehensive 11-priority dispatch table */
static PyObject *
py_pop(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames) {
  (void)self;  /* Module method, self is unused */
  
  /* ========== FAST PATH: pop(heap) with all defaults ========== 
   * Condition: exactly 1 positional arg, no kwargs, heap is list
   * This bypasses PyArg_ParseTupleAndKeywords entirely for ~20ns savings */
  if (likely(nargs == 1 && kwnames == NULL)) {
    PyObject *heap = args[0];
    
    if (likely(PyList_CheckExact(heap))) {
      PyListObject *listobj = (PyListObject *)heap;
      Py_ssize_t n = PyList_GET_SIZE(heap);
      
      if (unlikely(n == 0)) {
        PyErr_SetString(PyExc_IndexError, "pop from empty heap");
        return NULL;
      }
      
      PyObject **arr = listobj->ob_item;
      PyObject *returnitem = arr[0];
      Py_INCREF(returnitem);
      
      if (n == 1) {
        /* Only one element - just clear */
        Py_SET_SIZE(heap, 0);
        return returnitem;
      }
      
      /* Get last element, move to root, shrink list */
      PyObject *lastelt = arr[n - 1];
      Py_INCREF(lastelt);
      Py_DECREF(arr[0]);
      arr[0] = lastelt;
      Py_SET_SIZE(heap, n - 1);
      Py_ssize_t new_size = n - 1;
      
      /* Use the optimized sift function which has safety checks */
      if (unlikely(sift_richcmp_min(listobj, new_size) < 0)) {
        Py_DECREF(returnitem);
        return NULL;
      }
      
      return returnitem;
    }
  }
  
  /* ========== SLOW PATH: Full argument parsing ========== */
  /* Convert FASTCALL args to tuple and kwargs dict for PyArg_ParseTupleAndKeywords */
  PyObject *args_tuple = PyTuple_New(nargs);
  if (unlikely(!args_tuple)) return NULL;
  for (Py_ssize_t i = 0; i < nargs; i++) {
    Py_INCREF(args[i]);
    PyTuple_SET_ITEM(args_tuple, i, args[i]);
  }
  
  PyObject *kwargs = NULL;
  if (kwnames != NULL) {
    Py_ssize_t nkw = PyTuple_GET_SIZE(kwnames);
    kwargs = PyDict_New();
    if (unlikely(!kwargs)) { Py_DECREF(args_tuple); return NULL; }
    for (Py_ssize_t i = 0; i < nkw; i++) {
      PyObject *key = PyTuple_GET_ITEM(kwnames, i);
      PyObject *value = args[nargs + i];
      if (unlikely(PyDict_SetItem(kwargs, key, value) < 0)) {
        Py_DECREF(args_tuple);
        Py_DECREF(kwargs);
        return NULL;
      }
    }
  }
  
  static char *kwlist[] = {"heap", "n", "max_heap", "cmp", "arity", "nogil", NULL};
  PyObject *heap;
  Py_ssize_t n_pop = 1;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;
  PyObject *nogil_obj = Py_False;

  if (!PyArg_ParseTupleAndKeywords(args_tuple, kwargs, "O|nOOnO:pop", kwlist,
                                   &heap, &n_pop, &max_heap_obj, &cmp, &arity, &nogil_obj)) {
    Py_DECREF(args_tuple);
    Py_XDECREF(kwargs);
    return NULL;
  }
  Py_DECREF(args_tuple);
  Py_XDECREF(kwargs);

  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;
  
  int nogil = PyObject_IsTrue(nogil_obj);
  if (unlikely(nogil < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_Format(PyExc_TypeError, "cmp must be callable or None, not %.200s", Py_TYPE(cmp)->tp_name);
    return NULL;
  }
  if (unlikely(arity < 1 || arity > HEAPX_MAX_ARITY)) {
    PyErr_Format(PyExc_ValueError, "arity must be >= 1 and <= 64, got %zd", arity);
    return NULL;
  }
  if (unlikely(n_pop < 1)) {
    PyErr_Format(PyExc_ValueError, "n must be >= 1, got %zd", n_pop);
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
        /* Single element - clear the list */
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
      
      /* Fast path: Get last item, shrink list, put last at position 0
       * This matches optimized_pop.pyx's approach */
      PyObject *last_item = items[n - 1];
      Py_INCREF(last_item);
      
      /* Shrink list by 1 - equivalent to list.pop() */
      Py_SET_SIZE(listobj, n - 1);
      
      Py_ssize_t new_size = n - 1;
      
      /* Put last item at position 0 */
      items = listobj->ob_item;
      Py_DECREF(items[0]);
      items[0] = last_item;
      
      /* DISPATCH TABLE FOR SIFT-DOWN */
      if (likely(cmp == Py_None)) {
        /* Fast path: arity=2, no cmp - use optimized RichCompareBool sift */
        if (likely(arity == 2)) {
          if (is_max) {
            if (unlikely(sift_richcmp_max(listobj, new_size) < 0)) {
              Py_DECREF(result);
              return NULL;
            }
          } else {
            if (unlikely(sift_richcmp_min(listobj, new_size) < 0)) {
              Py_DECREF(result);
              return NULL;
            }
          }
          return result;
        }
        /* Non-binary arity or small heap */
        if (unlikely(new_size <= HEAPX_SMALL_HEAP_THRESHOLD)) {
          if (unlikely(list_heapify_small_ultra_optimized(listobj, is_max, arity) < 0)) {
            Py_DECREF(result);
            return NULL;
          }
        } else {
          /* Use specialized sift_down based on arity */
          int rc;
          switch (arity) {
            case 2:
              rc = list_sift_down_binary_ultra_optimized(listobj, 0, new_size, is_max);
              break;
            case 4:
              rc = list_sift_down_quaternary_ultra_optimized(listobj, 0, new_size, is_max);
              break;
            case 8:
              rc = list_sift_down_octonary_ultra_optimized(listobj, 0, new_size, is_max);
              break;
            default:
              rc = list_sift_down_ultra_optimized(listobj, 0, new_size, is_max, arity);
              break;
          }
          if (unlikely(rc < 0)) {
            Py_DECREF(result);
            return NULL;
          }
        }
        return result;
      } else {
        /* WITH KEY FUNCTION */
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
  if (likely(PyList_CheckExact(heap))) {
    PyListObject *listobj = (PyListObject *)heap;
    
    /* NoGIL dispatch for homogeneous arrays (arity >= 2 only; arity=1 is sorted list) */
    if (nogil && cmp == Py_None && heap_size >= 8 && arity >= 2) {
      int homogeneous = detect_homogeneous_type(listobj->ob_item, heap_size);
      if (homogeneous == 2) {
        /* Homogeneous floats */
        PyObject *result = list_pop_bulk_homogeneous_float_nogil(listobj, n_pop, is_max, arity);
        if (result) return result;
        if (PyErr_Occurred()) return NULL;
        /* Fall through to standard path if nogil failed */
      } else if (homogeneous == 1) {
        /* Homogeneous integers */
        PyObject *result = list_pop_bulk_homogeneous_int_nogil(listobj, n_pop, is_max, arity);
        if (result) return result;
        if (PyErr_Occurred()) return NULL;
        /* Fall through to standard path if nogil failed */
      }
    }
    
    if (likely(cmp == Py_None)) {
      /* Optimized bulk pop without key function - matches optimized_pop.pyx _pop_bulk */
      PyObject *results = PyList_New(n_pop);
      if (unlikely(!results)) return NULL;
      
      /* Detect element type for type-specialized sift using robust homogeneity check.
       * detect_homogeneous_type checks ALL elements (SIMD-optimized) and returns:
       *   0 = not homogeneous or n < 8
       *   1 = homogeneous integers
       *   2 = homogeneous floats
       * For integers, also verify first element fits in C long to avoid overflow. */
      int elem_type = ELEM_TYPE_OTHER;
      if (arity == 2) {
        int homogeneous = detect_homogeneous_type(listobj->ob_item, heap_size);
        if (homogeneous == 1) {
          int overflow = 0;
          (void)PyLong_AsLongAndOverflow(listobj->ob_item[0], &overflow);
          if (!overflow) elem_type = ELEM_TYPE_INT;
        } else if (homogeneous == 2) {
          elem_type = ELEM_TYPE_FLOAT;
        }
      }
      
      for (Py_ssize_t i = 0; i < n_pop; i++) {
        Py_ssize_t current_size = PyList_GET_SIZE(heap);
        if (unlikely(current_size <= 0)) break;
        
        PyObject **items = listobj->ob_item;
        PyObject *item = items[0];
        Py_INCREF(item);
        PyList_SET_ITEM(results, i, item);
        
        if (current_size > 1) {
          /* Get last item and shrink list - matches optimized_pop.pyx heap.pop() */
          PyObject *last_item = items[current_size - 1];
          Py_SET_SIZE(listobj, current_size - 1);
          
          /* Put last at position 0 - matches optimized_pop.pyx heap[0] = last */
          items = listobj->ob_item;
          Py_ssize_t new_size = current_size - 1;
          Py_DECREF(items[0]);
          items[0] = last_item;
          
          /* Use type-specialized sift for arity=2, matching optimized_pop.pyx */
          if (likely(arity == 2)) {
            switch (elem_type) {
              case ELEM_TYPE_FLOAT:
                if (is_max) sift_float_max(listobj, new_size);
                else sift_float_min(listobj, new_size);
                break;
              case ELEM_TYPE_INT:
                if (is_max) sift_int_max(listobj, new_size);
                else sift_int_min(listobj, new_size);
                break;
              case ELEM_TYPE_STR:
                if (is_max) sift_str_max(listobj, new_size);
                else sift_str_min(listobj, new_size);
                break;
              default:
                /* Generic path for bool, tuple, custom - use optimized_compare (matches sift_down_min/max) */
                if (is_max) {
                  if (unlikely(sift_generic_max(listobj, new_size) < 0)) {
                    Py_DECREF(results);
                    return NULL;
                  }
                } else {
                  if (unlikely(sift_generic_min(listobj, new_size) < 0)) {
                    Py_DECREF(results);
                    return NULL;
                  }
                }
                break;
            }
          } else {
            /* Use specialized sift_down based on arity */
            int rc;
            switch (arity) {
              case 2:
                rc = list_sift_down_binary_ultra_optimized(listobj, 0, new_size, is_max);
                break;
              case 4:
                rc = list_sift_down_quaternary_ultra_optimized(listobj, 0, new_size, is_max);
                break;
              case 8:
                rc = list_sift_down_octonary_ultra_optimized(listobj, 0, new_size, is_max);
                break;
              default:
                rc = list_sift_down_ultra_optimized(listobj, 0, new_size, is_max, arity);
                break;
            }
            if (unlikely(rc < 0)) {
              Py_DECREF(results);
              return NULL;
            }
          }
        } else {
          /* Single element remaining - just clear it */
          Py_SET_SIZE(listobj, 0);
        }
      }
      return results;
    } else {
      /* Bulk pop with key function */
      PyObject *results = PyList_New(n_pop);
      if (unlikely(!results)) return NULL;
      
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
  PyObject *results = PyList_New(n_pop);
  if (unlikely(!results)) return NULL;
  
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


/* Perfect production-ready remove operation */
/* Ultra-optimized remove with 11-priority dispatch and O(log n) inline maintenance */
static PyObject *
py_remove(PyObject *self, PyObject *args, PyObject *kwargs) {
  (void)self;  /* Module method, self is unused */
  static char *kwlist[] = {"heap", "indices", "object", "predicate", "n", "return_items", "max_heap", "cmp", "arity", "nogil", NULL};
  PyObject *heap;
  PyObject *indices = Py_None;
  PyObject *object = Py_None;
  PyObject *predicate = Py_None;
  Py_ssize_t n = -1;
  PyObject *return_items_obj = Py_False;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;
  PyObject *nogil_obj = Py_False;

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OOOnOOOnO:remove", kwlist,
                                   &heap, &indices, &object, &predicate, &n, &return_items_obj, &max_heap_obj, &cmp, &arity, &nogil_obj))
    return NULL;

  int return_items = PyObject_IsTrue(return_items_obj);
  if (unlikely(return_items < 0)) return NULL;
  
  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;
  
  int nogil = PyObject_IsTrue(nogil_obj);
  if (unlikely(nogil < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_Format(PyExc_TypeError, "cmp must be callable or None, not %.200s", Py_TYPE(cmp)->tp_name);
    return NULL;
  }
  if (unlikely(predicate != Py_None && !PyCallable_Check(predicate))) {
    PyErr_Format(PyExc_TypeError, "predicate must be callable or None, not %.200s", Py_TYPE(predicate)->tp_name);
    return NULL;
  }
  if (unlikely(arity < 1 || arity > HEAPX_MAX_ARITY)) {
    PyErr_Format(PyExc_ValueError, "arity must be >= 1 and <= 64, got %zd", arity);
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
    if (unlikely(new_size <= HEAPX_SMALL_HEAP_THRESHOLD && cmp == Py_None)) {
      if (unlikely(PySequence_DelItem(heap, idx) < 0)) {
        Py_XDECREF(removed_item);
        return NULL;
      }
      
      if (new_size > 0) {
        PyObject **items = listobj->ob_item;
        for (Py_ssize_t i = 1; i < new_size; i++) {
          /* SAFETY CHECK */
          if (unlikely(PyList_GET_SIZE(heap) != new_size)) {
            PyErr_Format(PyExc_ValueError, "list modified during remove (expected size %zd, got %zd)", new_size, PyList_GET_SIZE(heap));
            Py_XDECREF(removed_item);
            return NULL;
          }
          items = listobj->ob_item;
          PyObject *key = items[i];
          Py_INCREF(key);
          Py_ssize_t j = i - 1;
          while (j >= 0) {
            /* SAFETY CHECK */
            if (unlikely(PyList_GET_SIZE(heap) != new_size)) {
              PyErr_Format(PyExc_ValueError, "list modified during remove (expected size %zd, got %zd)", new_size, PyList_GET_SIZE(heap));
              Py_DECREF(key);
              Py_XDECREF(removed_item);
              return NULL;
            }
            items = listobj->ob_item;
            int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
            /* SAFETY CHECK */
            if (unlikely(PyList_GET_SIZE(heap) != new_size)) {
              PyErr_Format(PyExc_ValueError, "list modified during remove (expected size %zd, got %zd)", new_size, PyList_GET_SIZE(heap));
              Py_DECREF(key);
              Py_XDECREF(removed_item);
              return NULL;
            }
            if (unlikely(cmp_res < 0)) {
              Py_DECREF(key);
              Py_XDECREF(removed_item);
              return NULL;
            }
            items = listobj->ob_item;
            if (!cmp_res) break;
            Py_INCREF(items[j]);
            Py_SETREF(items[j + 1], items[j]);
            j--;
          }
          items = listobj->ob_item;
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

  /* Check if iteration ended due to error */
  if (unlikely(PyErr_Occurred())) {
    Py_DECREF(remove_list);
    Py_XDECREF(removed_items);
    return NULL;
  }

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
    if (unlikely(new_size <= HEAPX_SMALL_HEAP_THRESHOLD && PyList_CheckExact(heap) && cmp == Py_None)) {
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
      /* Priorities 3-7: Arity-specific heapify without key - with nogil support */
      PyListObject *listobj = (PyListObject *)heap;
      int homogeneous = (new_size >= 8) ? detect_homogeneous_type(listobj->ob_item, new_size) : 0;
      int rc = 0;
      
      if (likely(arity == 2)) {
        if (nogil && homogeneous == 2) {
          rc = list_heapify_homogeneous_float_nogil(listobj, is_max);
        } else if (nogil && homogeneous == 1) {
          rc = list_heapify_homogeneous_int_nogil(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_floyd_ultra_optimized(listobj, is_max); }
        } else if (homogeneous == 2) {
          rc = list_heapify_homogeneous_float(listobj, is_max);
        } else if (homogeneous == 1) {
          rc = list_heapify_homogeneous_int(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_floyd_ultra_optimized(listobj, is_max); }
        } else {
          rc = list_heapify_floyd_ultra_optimized(listobj, is_max);
        }
      } else if (arity == 3) {
        if (nogil && homogeneous == 2) {
          rc = list_heapify_ternary_homogeneous_float_nogil(listobj, is_max);
        } else if (nogil && homogeneous == 1) {
          rc = list_heapify_ternary_homogeneous_int_nogil(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_ternary_ultra_optimized(listobj, is_max); }
        } else if (homogeneous == 2) {
          rc = list_heapify_ternary_homogeneous_float(listobj, is_max);
        } else if (homogeneous == 1) {
          rc = list_heapify_ternary_homogeneous_int(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_ternary_ultra_optimized(listobj, is_max); }
        } else {
          rc = list_heapify_ternary_ultra_optimized(listobj, is_max);
        }
      } else if (arity == 4) {
        if (nogil && homogeneous == 2) {
          rc = list_heapify_quaternary_homogeneous_float_nogil(listobj, is_max);
        } else if (nogil && homogeneous == 1) {
          rc = list_heapify_quaternary_homogeneous_int_nogil(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_quaternary_ultra_optimized(listobj, is_max); }
        } else if (homogeneous == 2) {
          rc = list_heapify_quaternary_homogeneous_float(listobj, is_max);
        } else if (homogeneous == 1) {
          rc = list_heapify_quaternary_homogeneous_int(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_quaternary_ultra_optimized(listobj, is_max); }
        } else {
          rc = list_heapify_quaternary_ultra_optimized(listobj, is_max);
        }
      } else {
        if (nogil && homogeneous == 2) {
          rc = list_heapify_nary_simd_homogeneous_float_nogil(listobj, is_max, arity);
        } else if (nogil && homogeneous == 1) {
          rc = list_heapify_nary_simd_homogeneous_int_nogil(listobj, is_max, arity);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_small_ultra_optimized(listobj, is_max, arity); }
        } else if (homogeneous == 2) {
          rc = list_heapify_nary_simd_homogeneous_float(listobj, is_max, arity);
        } else if (homogeneous == 1) {
          rc = list_heapify_nary_simd_homogeneous_int(listobj, is_max, arity);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_small_ultra_optimized(listobj, is_max, arity); }
        } else {
          rc = list_heapify_small_ultra_optimized(listobj, is_max, arity);
        }
      }
      if (unlikely(rc < 0)) { Py_XDECREF(removed_items); return NULL; }
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
  
  /* REFRESH POINTER */
  PyObject **items = listobj->ob_item;
  
  /* Replace value with proper refcounting */
  Py_INCREF(new_value);
  Py_SETREF(items[idx], new_value);
  
  /* Determine sift direction by comparing with parent */
  if (keyfunc == NULL) {
    if (idx > 0) {
      Py_ssize_t parent = (idx - 1) / arity;
      /* REFRESH POINTER */
      items = listobj->ob_item;
      int cmp_res = optimized_compare(items[idx], items[parent], is_max ? Py_GT : Py_LT);
      /* SAFETY CHECK */
      if (unlikely(Py_SIZE(listobj) != n)) {
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
      if (unlikely(cmp_res < 0)) return -1;
      if (cmp_res) {
        /* New value violates parent relationship - sift up */
        switch (arity) {
          case 2:
            return list_sift_up_binary_ultra_optimized(listobj, idx, is_max);
          case 4:
            return list_sift_up_quaternary_ultra_optimized(listobj, idx, is_max);
          case 8:
            return list_sift_up_octonary_ultra_optimized(listobj, idx, is_max);
          default:
            return list_sift_up_ultra_optimized(listobj, idx, is_max, arity);
        }
      }
    }
    /* Sift down to restore heap property */
    switch (arity) {
      case 2:
        return list_sift_down_binary_ultra_optimized(listobj, idx, n, is_max);
      case 4:
        return list_sift_down_quaternary_ultra_optimized(listobj, idx, n, is_max);
      case 8:
        return list_sift_down_octonary_ultra_optimized(listobj, idx, n, is_max);
      default:
        return list_sift_down_ultra_optimized(listobj, idx, n, is_max, arity);
    }
  } else {
    if (idx > 0) {
      Py_ssize_t parent = (idx - 1) / arity;
      /* REFRESH POINTER */
      items = listobj->ob_item;
      PyObject *key_item = call_key_function(keyfunc, items[idx]);
      if (unlikely(!key_item)) return -1;
      /* SAFETY CHECK */
      if (unlikely(Py_SIZE(listobj) != n)) {
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        Py_DECREF(key_item);
        return -1;
      }
      /* REFRESH POINTER */
      items = listobj->ob_item;
      PyObject *key_parent = call_key_function(keyfunc, items[parent]);
      if (unlikely(!key_parent)) {
        Py_DECREF(key_item);
        return -1;
      }
      /* SAFETY CHECK */
      if (unlikely(Py_SIZE(listobj) != n)) {
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        Py_DECREF(key_item);
        Py_DECREF(key_parent);
        return -1;
      }
      int cmp_res = optimized_compare(key_item, key_parent, is_max ? Py_GT : Py_LT);
      Py_DECREF(key_item);
      Py_DECREF(key_parent);
      /* SAFETY CHECK */
      if (unlikely(Py_SIZE(listobj) != n)) {
        PyErr_Format(PyExc_ValueError, "list modified during heap operation (expected size %zd, got %zd)", n, PyList_GET_SIZE(listobj));
        return -1;
      }
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
  (void)self;  /* Module method, self is unused */
  static char *kwlist[] = {"heap", "values", "indices", "object", "predicate", "max_heap", "cmp", "arity", "nogil", NULL};
  PyObject *heap, *values;
  PyObject *indices = Py_None;
  PyObject *object = Py_None;
  PyObject *predicate = Py_None;
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;
  PyObject *nogil_obj = Py_False;

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|OOOOOnO:replace", kwlist,
                                   &heap, &values, &indices, &object, &predicate, &max_heap_obj, &cmp, &arity, &nogil_obj))
    return NULL;

  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;
  
  int nogil = PyObject_IsTrue(nogil_obj);
  if (unlikely(nogil < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_Format(PyExc_TypeError, "cmp must be callable or None, not %.200s", Py_TYPE(cmp)->tp_name);
    return NULL;
  }
  if (unlikely(predicate != Py_None && !PyCallable_Check(predicate))) {
    PyErr_Format(PyExc_TypeError, "predicate must be callable or None, not %.200s", Py_TYPE(predicate)->tp_name);
    return NULL;
  }
  if (unlikely(arity < 1 || arity > HEAPX_MAX_ARITY)) {
    PyErr_Format(PyExc_ValueError, "arity must be >= 1 and <= 64, got %zd", arity);
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
    if (unlikely(new_size <= HEAPX_SMALL_HEAP_THRESHOLD && keyfunc == NULL)) {
      PyObject **items = listobj->ob_item;
      Py_INCREF(values);
      Py_SETREF(items[idx], values);
      
      for (Py_ssize_t i = 1; i < new_size; i++) {
        /* SAFETY CHECK */
        if (unlikely(PyList_GET_SIZE(heap) != new_size)) {
          PyErr_Format(PyExc_ValueError, "list modified during replace (expected size %zd, got %zd)", new_size, PyList_GET_SIZE(heap));
          return NULL;
        }
        items = listobj->ob_item;
        PyObject *key = items[i];
        Py_INCREF(key);
        Py_ssize_t j = i - 1;
        while (j >= 0) {
          /* SAFETY CHECK */
          if (unlikely(PyList_GET_SIZE(heap) != new_size)) {
            PyErr_Format(PyExc_ValueError, "list modified during replace (expected size %zd, got %zd)", new_size, PyList_GET_SIZE(heap));
            Py_DECREF(key);
            return NULL;
          }
          items = listobj->ob_item;
          int cmp_res = optimized_compare(key, items[j], is_max ? Py_GT : Py_LT);
          /* SAFETY CHECK */
          if (unlikely(PyList_GET_SIZE(heap) != new_size)) {
            PyErr_Format(PyExc_ValueError, "list modified during replace (expected size %zd, got %zd)", new_size, PyList_GET_SIZE(heap));
            Py_DECREF(key);
            return NULL;
          }
          if (unlikely(cmp_res < 0)) {
            Py_DECREF(key);
            return NULL;
          }
          items = listobj->ob_item;
          if (!cmp_res) break;
          Py_INCREF(items[j]);
          Py_SETREF(items[j + 1], items[j]);
          j--;
        }
        items = listobj->ob_item;
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
      PyErr_Format(PyExc_ValueError, "values length must match selection count or be 1 (got %zd values for %zd selections)", n_values, replace_count);
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
    if (unlikely(new_size <= HEAPX_SMALL_HEAP_THRESHOLD && cmp == Py_None)) {
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
    
    /* Priorities 3-7: Arity-specific heapify without key - with nogil support */
    if (cmp == Py_None) {
      int homogeneous = (new_size >= 8) ? detect_homogeneous_type(listobj->ob_item, new_size) : 0;
      int rc = 0;
      
      if (likely(arity == 2)) {
        if (nogil && homogeneous == 2) {
          rc = list_heapify_homogeneous_float_nogil(listobj, is_max);
        } else if (nogil && homogeneous == 1) {
          rc = list_heapify_homogeneous_int_nogil(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_floyd_ultra_optimized(listobj, is_max); }
        } else if (homogeneous == 2) {
          rc = list_heapify_homogeneous_float(listobj, is_max);
        } else if (homogeneous == 1) {
          rc = list_heapify_homogeneous_int(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_floyd_ultra_optimized(listobj, is_max); }
        } else {
          rc = list_heapify_floyd_ultra_optimized(listobj, is_max);
        }
      } else if (arity == 3) {
        if (nogil && homogeneous == 2) {
          rc = list_heapify_ternary_homogeneous_float_nogil(listobj, is_max);
        } else if (nogil && homogeneous == 1) {
          rc = list_heapify_ternary_homogeneous_int_nogil(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_ternary_ultra_optimized(listobj, is_max); }
        } else if (homogeneous == 2) {
          rc = list_heapify_ternary_homogeneous_float(listobj, is_max);
        } else if (homogeneous == 1) {
          rc = list_heapify_ternary_homogeneous_int(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_ternary_ultra_optimized(listobj, is_max); }
        } else {
          rc = list_heapify_ternary_ultra_optimized(listobj, is_max);
        }
      } else if (arity == 4) {
        if (nogil && homogeneous == 2) {
          rc = list_heapify_quaternary_homogeneous_float_nogil(listobj, is_max);
        } else if (nogil && homogeneous == 1) {
          rc = list_heapify_quaternary_homogeneous_int_nogil(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_quaternary_ultra_optimized(listobj, is_max); }
        } else if (homogeneous == 2) {
          rc = list_heapify_quaternary_homogeneous_float(listobj, is_max);
        } else if (homogeneous == 1) {
          rc = list_heapify_quaternary_homogeneous_int(listobj, is_max);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_quaternary_ultra_optimized(listobj, is_max); }
        } else {
          rc = list_heapify_quaternary_ultra_optimized(listobj, is_max);
        }
      } else {
        if (nogil && homogeneous == 2) {
          rc = list_heapify_nary_simd_homogeneous_float_nogil(listobj, is_max, arity);
        } else if (nogil && homogeneous == 1) {
          rc = list_heapify_nary_simd_homogeneous_int_nogil(listobj, is_max, arity);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_small_ultra_optimized(listobj, is_max, arity); }
        } else if (homogeneous == 2) {
          rc = list_heapify_nary_simd_homogeneous_float(listobj, is_max, arity);
        } else if (homogeneous == 1) {
          rc = list_heapify_nary_simd_homogeneous_int(listobj, is_max, arity);
          if (rc == 2) { PyErr_Clear(); rc = list_heapify_small_ultra_optimized(listobj, is_max, arity); }
        } else {
          rc = list_heapify_small_ultra_optimized(listobj, is_max, arity);
        }
      }
      if (unlikely(rc < 0)) return NULL;
      return PyLong_FromSsize_t(replace_count);
    }
  }

  /* Fallback: generic heapify */
  if (unlikely(generic_heapify_ultra_optimized(heap, is_max, (cmp == Py_None ? NULL : cmp), arity) < 0)) {
    return NULL;
  }

  return PyLong_FromSsize_t(replace_count);
}

/* Ultra-optimized merge with complete 11-priority dispatch */
static PyObject *
py_merge(PyObject *self, PyObject *args, PyObject *kwargs) {
  (void)self;  /* Module method, self is unused */
  static char *kwlist[] = {"max_heap", "cmp", "arity", "nogil", NULL};
  PyObject *max_heap_obj = Py_False;
  PyObject *cmp = Py_None;
  Py_ssize_t arity = 2;
  PyObject *nogil_obj = Py_False;

  /* Parse keyword arguments using a static empty tuple to avoid per-call allocation.
   * merge() receives positional heaps via *args and keywords separately, so we need
   * an empty tuple for PyArg_ParseTupleAndKeywords to parse only the keyword args. */
  static PyObject *empty_tuple = NULL;
  if (unlikely(empty_tuple == NULL)) {
    empty_tuple = PyTuple_New(0);
    if (unlikely(empty_tuple == NULL)) return NULL;
  }

  if (!PyArg_ParseTupleAndKeywords(empty_tuple, kwargs, "|OOnO:merge", kwlist,
                                   &max_heap_obj, &cmp, &arity, &nogil_obj))
    return NULL;

  int is_max = PyObject_IsTrue(max_heap_obj);
  if (unlikely(is_max < 0)) return NULL;
  
  int nogil = PyObject_IsTrue(nogil_obj);
  if (unlikely(nogil < 0)) return NULL;

  if (unlikely(cmp != Py_None && !PyCallable_Check(cmp))) {
    PyErr_Format(PyExc_TypeError, "cmp must be callable or None, not %.200s", Py_TYPE(cmp)->tp_name);
    return NULL;
  }
  if (unlikely(arity < 1 || arity > HEAPX_MAX_ARITY)) {
    PyErr_Format(PyExc_ValueError, "arity must be >= 1 and <= 64, got %zd", arity);
    return NULL;
  }

  Py_ssize_t n_args = PyTuple_Size(args);
  if (n_args < 2) {
    PyErr_Format(PyExc_ValueError, "merge requires at least 2 heaps, got %zd", n_args);
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
      PyErr_Format(PyExc_TypeError, "merge argument %zd must be a sequence, not %.200s", i + 1, Py_TYPE(heap)->tp_name);
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

  /* ========== 11-PRIORITY HEAPIFY DISPATCH ========== */
  
  PyListObject *result_list = (PyListObject *)result;
  
  /* Priority 1: Small heap (n ≤ 16, no key) */
  if (unlikely(total_size <= HEAPX_SMALL_HEAP_THRESHOLD && keyfunc == NULL)) {
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
  
  /* Priority 2: Arity=1 (sorted list) - Use O(N log N) Timsort */
  if (unlikely(arity == 1)) {
    if (keyfunc) {
      /* Sort with key function using list.sort(key=..., reverse=...) */
      PyObject *sort_method = PyObject_GetAttrString(result, "sort");
      if (unlikely(!sort_method)) {
        Py_DECREF(result);
        return NULL;
      }
      
      PyObject *kwargs = PyDict_New();
      if (unlikely(!kwargs)) {
        Py_DECREF(sort_method);
        Py_DECREF(result);
        return NULL;
      }
      
      if (unlikely(PyDict_SetItemString(kwargs, "key", keyfunc) < 0)) {
        Py_DECREF(kwargs);
        Py_DECREF(sort_method);
        Py_DECREF(result);
        return NULL;
      }
      
      if (is_max) {
        if (unlikely(PyDict_SetItemString(kwargs, "reverse", Py_True) < 0)) {
          Py_DECREF(kwargs);
          Py_DECREF(sort_method);
          Py_DECREF(result);
          return NULL;
        }
      }
      
      PyObject *args = PyTuple_New(0);
      if (unlikely(!args)) {
        Py_DECREF(kwargs);
        Py_DECREF(sort_method);
        Py_DECREF(result);
        return NULL;
      }
      
      PyObject *sort_result = PyObject_Call(sort_method, args, kwargs);
      Py_DECREF(args);
      Py_DECREF(kwargs);
      Py_DECREF(sort_method);
      
      if (unlikely(!sort_result)) {
        Py_DECREF(result);
        return NULL;
      }
      Py_DECREF(sort_result);
    } else {
      /* No key function - direct sort */
      if (unlikely(PyList_Sort(result) < 0)) {
        Py_DECREF(result);
        return NULL;
      }
      
      /* Reverse if max-heap */
      if (is_max) {
        if (unlikely(PyList_Reverse(result) < 0)) {
          Py_DECREF(result);
          return NULL;
        }
      }
    }
    return result;
  }
  
  /* Homogeneous detection for nogil optimization */
  int homogeneous = 0;
  if (likely(keyfunc == NULL && total_size >= 8)) {
    homogeneous = detect_homogeneous_type(result_list->ob_item, total_size);
  }
  
  /* Priority 3: Binary heap (arity=2, no key) */
  if (likely(arity == 2 && keyfunc == NULL)) {
    int rc = 0;
    if (nogil && homogeneous == 2) {
      rc = list_heapify_homogeneous_float_nogil(result_list, is_max);
    } else if (nogil && homogeneous == 1) {
      rc = list_heapify_homogeneous_int_nogil(result_list, is_max);
      if (rc == 2) { PyErr_Clear(); rc = list_heapify_floyd_ultra_optimized(result_list, is_max); }
    } else if (homogeneous == 2) {
      rc = list_heapify_homogeneous_float(result_list, is_max);
    } else if (homogeneous == 1) {
      rc = list_heapify_homogeneous_int(result_list, is_max);
      if (rc == 2) { PyErr_Clear(); rc = list_heapify_floyd_ultra_optimized(result_list, is_max); }
    } else {
      rc = list_heapify_floyd_ultra_optimized(result_list, is_max);
    }
    if (unlikely(rc < 0)) { Py_DECREF(result); return NULL; }
    return result;
  }
  
  /* Priority 4: Ternary heap (arity=3, no key) */
  if (unlikely(arity == 3 && keyfunc == NULL)) {
    int rc = 0;
    if (nogil && homogeneous == 2) {
      rc = list_heapify_ternary_homogeneous_float_nogil(result_list, is_max);
    } else if (nogil && homogeneous == 1) {
      rc = list_heapify_ternary_homogeneous_int_nogil(result_list, is_max);
      if (rc == 2) { PyErr_Clear(); rc = list_heapify_ternary_ultra_optimized(result_list, is_max); }
    } else if (homogeneous == 2) {
      rc = list_heapify_ternary_homogeneous_float(result_list, is_max);
    } else if (homogeneous == 1) {
      rc = list_heapify_ternary_homogeneous_int(result_list, is_max);
      if (rc == 2) { PyErr_Clear(); rc = list_heapify_ternary_ultra_optimized(result_list, is_max); }
    } else {
      rc = list_heapify_ternary_ultra_optimized(result_list, is_max);
    }
    if (unlikely(rc < 0)) { Py_DECREF(result); return NULL; }
    return result;
  }
  
  /* Priority 5: Quaternary heap (arity=4, no key) */
  if (unlikely(arity == 4 && keyfunc == NULL)) {
    int rc = 0;
    if (nogil && homogeneous == 2) {
      rc = list_heapify_quaternary_homogeneous_float_nogil(result_list, is_max);
    } else if (nogil && homogeneous == 1) {
      rc = list_heapify_quaternary_homogeneous_int_nogil(result_list, is_max);
      if (rc == 2) { PyErr_Clear(); rc = list_heapify_quaternary_ultra_optimized(result_list, is_max); }
    } else if (homogeneous == 2) {
      rc = list_heapify_quaternary_homogeneous_float(result_list, is_max);
    } else if (homogeneous == 1) {
      rc = list_heapify_quaternary_homogeneous_int(result_list, is_max);
      if (rc == 2) { PyErr_Clear(); rc = list_heapify_quaternary_ultra_optimized(result_list, is_max); }
    } else {
      rc = list_heapify_quaternary_ultra_optimized(result_list, is_max);
    }
    if (unlikely(rc < 0)) { Py_DECREF(result); return NULL; }
    return result;
  }
  
  /* Priority 6: N-ary heap (arity≥5, no key, n<1000) */
  if (unlikely(arity >= 5 && keyfunc == NULL && total_size < HEAPX_LARGE_HEAP_THRESHOLD)) {
    int rc = 0;
    if (nogil && homogeneous == 2) {
      rc = list_heapify_nary_simd_homogeneous_float_nogil(result_list, is_max, arity);
    } else if (nogil && homogeneous == 1) {
      rc = list_heapify_nary_simd_homogeneous_int_nogil(result_list, is_max, arity);
      if (rc == 2) { PyErr_Clear(); rc = list_heapify_small_ultra_optimized(result_list, is_max, arity); }
    } else if (homogeneous == 2) {
      rc = list_heapify_nary_simd_homogeneous_float(result_list, is_max, arity);
    } else if (homogeneous == 1) {
      rc = list_heapify_nary_simd_homogeneous_int(result_list, is_max, arity);
      if (rc == 2) { PyErr_Clear(); rc = list_heapify_small_ultra_optimized(result_list, is_max, arity); }
    } else {
      rc = list_heapify_small_ultra_optimized(result_list, is_max, arity);
    }
    if (unlikely(rc < 0)) { Py_DECREF(result); return NULL; }
    return result;
  }
  
  /* Priority 7: N-ary heap (arity≥5, no key, n≥1000) */
  if (unlikely(arity >= 5 && keyfunc == NULL && total_size >= HEAPX_LARGE_HEAP_THRESHOLD)) {
    int rc = 0;
    if (nogil && homogeneous == 2) {
      rc = list_heapify_nary_simd_homogeneous_float_nogil(result_list, is_max, arity);
    } else if (nogil && homogeneous == 1) {
      rc = list_heapify_nary_simd_homogeneous_int_nogil(result_list, is_max, arity);
      if (rc == 2) { PyErr_Clear(); rc = generic_heapify_ultra_optimized(result, is_max, NULL, arity); }
    } else if (homogeneous == 2) {
      rc = list_heapify_nary_simd_homogeneous_float(result_list, is_max, arity);
    } else if (homogeneous == 1) {
      rc = list_heapify_nary_simd_homogeneous_int(result_list, is_max, arity);
      if (rc == 2) { PyErr_Clear(); rc = generic_heapify_ultra_optimized(result, is_max, NULL, arity); }
    } else {
      rc = generic_heapify_ultra_optimized(result, is_max, NULL, arity);
    }
    if (unlikely(rc < 0)) { Py_DECREF(result); return NULL; }
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
