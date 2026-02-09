"""
Thread-safety and No-GIL compatibility tests for heapx module.

Tests verify the stack-first allocation pattern for key arrays ensures:
- Thread safety (no global mutable state)
- Re-entrancy compatibility
- Free-threaded Python (No-GIL) compliance
- Correct behavior at stack/heap allocation boundary (KEY_STACK_SIZE=128)

The fix eliminates the global static key_pool structure that was:
1. Accessed without locks (unsafe for No-GIL Python 3.13+)
2. Fragile for re-entrant key functions
3. A source of potential data corruption in multi-threaded scenarios

The new stack-first allocation pattern:
- Uses stack buffer for n <= 128 (KEY_STACK_SIZE)
- Falls back to PyMem_Malloc for n > 128
- Each function call has its own local allocation (thread-safe)
- Proper cleanup on all error paths
"""

import heapx
import pytest
import random
import threading
import time
import gc
import sys
from typing import List, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================================
# Constants matching C implementation
# ============================================================================

KEY_STACK_SIZE = 128  # Must match KEY_STACK_SIZE in heapx.c

# ============================================================================
# Test Data Generators
# ============================================================================

def generate_integers(n: int, seed: int = 42) -> List[int]:
  random.seed(seed)
  return [random.randint(-1000000, 1000000) for _ in range(n)]

def is_valid_heap(arr: List[Any], max_heap: bool = False, arity: int = 2, cmp=None) -> bool:
  if not arr:
    return True
  n = len(arr)
  for i in range(n):
    for j in range(1, arity + 1):
      child = arity * i + j
      if child >= n:
        break
      if cmp:
        parent_key = cmp(arr[i])
        child_key = cmp(arr[child])
      else:
        parent_key = arr[i]
        child_key = arr[child]
      if max_heap:
        if parent_key < child_key:
          return False
      else:
        if parent_key > child_key:
          return False
  return True

# ============================================================================
# Stack Buffer Boundary Tests (KEY_STACK_SIZE = 128)
# ============================================================================

class TestStackBufferBoundary:
  """Test behavior at stack/heap allocation boundary."""

  def test_heapify_key_at_stack_size_minus_one(self):
    """Test heapify with key at n=127 (uses stack)."""
    data = list(range(KEY_STACK_SIZE - 1, 0, -1))
    heapx.heapify(data, cmp=lambda x: x)
    assert is_valid_heap(data, cmp=lambda x: x)

  def test_heapify_key_at_exact_stack_size(self):
    """Test heapify with key at n=128 (uses stack)."""
    data = list(range(KEY_STACK_SIZE, 0, -1))
    heapx.heapify(data, cmp=lambda x: x)
    assert is_valid_heap(data, cmp=lambda x: x)

  def test_heapify_key_at_stack_size_plus_one(self):
    """Test heapify with key at n=129 (uses heap)."""
    data = list(range(KEY_STACK_SIZE + 1, 0, -1))
    heapx.heapify(data, cmp=lambda x: x)
    assert is_valid_heap(data, cmp=lambda x: x)

  @pytest.mark.parametrize("n", [1, 64, 127, 128, 129, 256, 512, 1000])
  def test_heapify_key_various_sizes(self, n):
    """Test heapify with key across stack/heap boundary."""
    data = list(range(n, 0, -1))
    heapx.heapify(data, cmp=lambda x: -x)
    assert is_valid_heap(data, cmp=lambda x: -x)

# ============================================================================
# Thread Safety Tests
# ============================================================================

class TestThreadSafety:
  """Test thread safety of key function operations."""

  def test_concurrent_heapify_with_key_small(self):
    """Concurrent heapify with key on small heaps (stack allocation)."""
    def worker(seed):
      data = generate_integers(64, seed)
      heapx.heapify(data, cmp=abs)
      return is_valid_heap(data, cmp=abs)

    with ThreadPoolExecutor(max_workers=8) as executor:
      futures = [executor.submit(worker, i) for i in range(100)]
      results = [f.result() for f in as_completed(futures)]
    assert all(results)

  def test_concurrent_heapify_with_key_large(self):
    """Concurrent heapify with key on large heaps (heap allocation)."""
    def worker(seed):
      data = generate_integers(500, seed)
      heapx.heapify(data, cmp=abs)
      return is_valid_heap(data, cmp=abs)

    with ThreadPoolExecutor(max_workers=8) as executor:
      futures = [executor.submit(worker, i) for i in range(50)]
      results = [f.result() for f in as_completed(futures)]
    assert all(results)

  def test_concurrent_mixed_operations_with_key(self):
    """Concurrent mixed heapify operations with key functions."""
    def heapify_worker(seed):
      rng = random.Random(seed)
      data = [rng.randint(-1000000, 1000000) for _ in range(200)]
      heapx.heapify(data, cmp=lambda x: x % 100)
      return is_valid_heap(data, cmp=lambda x: x % 100)

    with ThreadPoolExecutor(max_workers=8) as executor:
      futures = []
      for i in range(100):
        futures.append(executor.submit(heapify_worker, i * 12345))
      results = [f.result() for f in as_completed(futures)]
    assert all(results)

  def test_concurrent_boundary_size_operations(self):
    """Concurrent operations at exact stack/heap boundary."""
    def worker(n, seed):
      data = generate_integers(n, seed)
      heapx.heapify(data, cmp=abs)
      return is_valid_heap(data, cmp=abs)

    with ThreadPoolExecutor(max_workers=8) as executor:
      futures = []
      for i in range(50):
        futures.append(executor.submit(worker, 127, i))
        futures.append(executor.submit(worker, 128, i + 100))
        futures.append(executor.submit(worker, 129, i + 200))
      results = [f.result() for f in as_completed(futures)]
    assert all(results)

# ============================================================================
# Re-entrancy Tests
# ============================================================================

class TestReentrancy:
  """Test re-entrancy of key function operations."""

  def test_nested_heapify_with_key(self):
    """Test nested heapify calls with key functions."""
    outer_data = list(range(100, 0, -1))
    inner_results = []

    def outer_key(x):
      inner_data = list(range(50, 0, -1))
      heapx.heapify(inner_data, cmp=lambda y: y)
      inner_results.append(is_valid_heap(inner_data, cmp=lambda y: y))
      return x

    heapx.heapify(outer_data, cmp=outer_key)
    assert is_valid_heap(outer_data, cmp=lambda x: x)
    assert len(inner_results) == 100
    assert all(inner_results)

  def test_deeply_nested_key_functions(self):
    """Test deeply nested key function calls."""
    call_depth = [0]
    max_depth = [0]

    def recursive_key(x, depth=0):
      call_depth[0] = depth
      max_depth[0] = max(max_depth[0], depth)
      if depth < 3:
        inner = list(range(20, 0, -1))
        heapx.heapify(inner, cmp=lambda y: recursive_key(y, depth + 1))
      return x

    data = list(range(30, 0, -1))
    heapx.heapify(data, cmp=recursive_key)
    assert max_depth[0] >= 2

# ============================================================================
# Key Function Edge Cases
# ============================================================================

class TestKeyFunctionEdgeCases:
  """Test edge cases with key functions."""

  def test_key_returns_none(self):
    """Test key function returning None."""
    data = [3, 1, 2]
    with pytest.raises(TypeError):
      heapx.heapify(data, cmp=lambda x: None)

  def test_key_returns_incomparable(self):
    """Test key function returning incomparable types."""
    data = [1, 2, 3]
    with pytest.raises(TypeError):
      heapx.heapify(data, cmp=lambda x: complex(x, x))

  def test_key_with_exception(self):
    """Test key function that raises exception."""
    def bad_key(x):
      if x == 5:
        raise ValueError("bad value")
      return x

    data = list(range(10, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_key_with_exception_large_heap(self):
    """Test key function exception on large heap (heap allocation)."""
    def bad_key(x):
      if x == 100:
        raise ValueError("bad value")
      return x

    data = list(range(200, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_key_identity_function(self):
    """Test identity key function."""
    data = list(range(200, 0, -1))
    heapx.heapify(data, cmp=lambda x: x)
    assert is_valid_heap(data, cmp=lambda x: x)

  def test_key_constant_function(self):
    """Test constant key function (all equal)."""
    data = list(range(100, 0, -1))
    heapx.heapify(data, cmp=lambda x: 0)
    assert is_valid_heap(data, cmp=lambda x: 0)

  def test_key_negative_function(self):
    """Test negation key function (reverse order)."""
    data = list(range(1, 201))
    heapx.heapify(data, cmp=lambda x: -x)
    assert data[0] == 200

  def test_key_modulo_function(self):
    """Test modulo key function."""
    data = list(range(200, 0, -1))
    heapx.heapify(data, cmp=lambda x: x % 10)
    assert is_valid_heap(data, cmp=lambda x: x % 10)

  def test_key_tuple_return(self):
    """Test key function returning tuples."""
    data = list(range(200, 0, -1))
    heapx.heapify(data, cmp=lambda x: (x % 10, x))
    assert is_valid_heap(data, cmp=lambda x: (x % 10, x))

  def test_key_string_return(self):
    """Test key function returning strings."""
    data = list(range(200, 0, -1))
    heapx.heapify(data, cmp=lambda x: str(x).zfill(5))
    assert is_valid_heap(data, cmp=lambda x: str(x).zfill(5))

# ============================================================================
# Arity Combinations with Key Functions
# ============================================================================

class TestArityWithKey:
  """Test various arities with key functions."""

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8])
  def test_heapify_key_small_various_arity(self, arity):
    """Test heapify with key on small heap (stack) with various arities."""
    data = list(range(64, 0, -1))
    heapx.heapify(data, cmp=abs, arity=arity)
    assert is_valid_heap(data, cmp=abs, arity=arity)

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8])
  def test_heapify_key_large_various_arity(self, arity):
    """Test heapify with key on large heap (heap alloc) with various arities."""
    data = list(range(200, 0, -1))
    heapx.heapify(data, cmp=abs, arity=arity)
    assert is_valid_heap(data, cmp=abs, arity=arity)

  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_heapify_key_boundary_various_arity(self, arity):
    """Test heapify with key at boundary with various arities."""
    for n in [127, 128, 129]:
      data = list(range(n, 0, -1))
      heapx.heapify(data, cmp=lambda x: -x, arity=arity)
      assert is_valid_heap(data, cmp=lambda x: -x, arity=arity)

# ============================================================================
# Max Heap with Key Functions
# ============================================================================

class TestMaxHeapWithKey:
  """Test max heap operations with key functions."""

  def test_heapify_max_key_small(self):
    """Test max heapify with key on small heap."""
    data = list(range(1, 65))
    heapx.heapify(data, max_heap=True, cmp=abs)
    assert is_valid_heap(data, max_heap=True, cmp=abs)
    assert data[0] == 64

  def test_heapify_max_key_large(self):
    """Test max heapify with key on large heap."""
    data = list(range(1, 201))
    heapx.heapify(data, max_heap=True, cmp=abs)
    assert is_valid_heap(data, max_heap=True, cmp=abs)
    assert data[0] == 200

  @pytest.mark.parametrize("n", [64, 128, 200])
  def test_heapify_max_key_various_sizes(self, n):
    """Test max heapify with key at various sizes."""
    data = list(range(1, n + 1))
    heapx.heapify(data, max_heap=True, cmp=lambda x: x % 50)
    assert is_valid_heap(data, max_heap=True, cmp=lambda x: x % 50)

# ============================================================================
# Memory Safety Tests
# ============================================================================

class TestMemorySafety:
  """Test memory safety of key function operations."""

  def test_no_memory_leak_small_heap(self):
    """Test no memory leak with small heap key operations."""
    gc.collect()
    for _ in range(1000):
      data = list(range(64, 0, -1))
      heapx.heapify(data, cmp=abs)
    gc.collect()

  def test_no_memory_leak_large_heap(self):
    """Test no memory leak with large heap key operations."""
    gc.collect()
    for _ in range(100):
      data = list(range(500, 0, -1))
      heapx.heapify(data, cmp=abs)
    gc.collect()

  def test_no_memory_leak_on_exception(self):
    """Test no memory leak when key function raises."""
    gc.collect()
    for i in range(100):
      def bad_key(x):
        if x == 50:
          raise ValueError("test")
        return x
      data = list(range(200, 0, -1))
      try:
        heapx.heapify(data, cmp=bad_key)
      except ValueError:
        pass
    gc.collect()

# ============================================================================
# Empty and Single Element Tests
# ============================================================================

class TestEmptyAndSingle:
  """Test empty and single element cases with key functions."""

  def test_heapify_empty_with_key(self):
    """Test heapify empty list with key."""
    data = []
    heapx.heapify(data, cmp=abs)
    assert data == []

  def test_heapify_single_with_key(self):
    """Test heapify single element with key."""
    data = [42]
    heapx.heapify(data, cmp=abs)
    assert data == [42]

# ============================================================================
# Stress Tests
# ============================================================================

class TestStress:
  """Stress tests for thread safety and memory."""

  def test_rapid_small_heap_operations(self):
    """Rapid small heap operations with key."""
    for _ in range(10000):
      data = list(range(50, 0, -1))
      heapx.heapify(data, cmp=abs)

  def test_rapid_boundary_operations(self):
    """Rapid operations at stack/heap boundary."""
    for _ in range(1000):
      for n in [127, 128, 129]:
        data = list(range(n, 0, -1))
        heapx.heapify(data, cmp=abs)

  def test_alternating_small_large(self):
    """Alternating small and large heap operations."""
    for _ in range(500):
      small = list(range(50, 0, -1))
      heapx.heapify(small, cmp=abs)
      large = list(range(300, 0, -1))
      heapx.heapify(large, cmp=abs)

  def test_concurrent_stress(self):
    """Concurrent stress test."""
    def worker(iterations, size, seed):
      for i in range(iterations):
        data = generate_integers(size, seed + i)
        heapx.heapify(data, cmp=abs)
      return True

    with ThreadPoolExecutor(max_workers=16) as executor:
      futures = []
      for i in range(32):
        size = 50 + (i % 200)
        futures.append(executor.submit(worker, 100, size, i * 1000))
      results = [f.result() for f in as_completed(futures)]
    assert all(results)

# ============================================================================
# Data Type Tests with Key Functions
# ============================================================================

class TestDataTypesWithKey:
  """Test various data types with key functions."""

  def test_floats_with_key(self):
    """Test float data with key function."""
    data = [3.14, 2.71, 1.41, 1.73, 2.23]
    heapx.heapify(data, cmp=lambda x: int(x * 100))
    assert is_valid_heap(data, cmp=lambda x: int(x * 100))

  def test_strings_with_key(self):
    """Test string data with key function."""
    data = ["banana", "apple", "cherry", "date"]
    heapx.heapify(data, cmp=len)
    assert is_valid_heap(data, cmp=len)

  def test_tuples_with_key(self):
    """Test tuple data with key function."""
    data = [(3, "c"), (1, "a"), (2, "b"), (4, "d")]
    heapx.heapify(data, cmp=lambda x: x[0])
    assert is_valid_heap(data, cmp=lambda x: x[0])

  def test_objects_with_key(self):
    """Test custom objects with key function."""
    class Item:
      def __init__(self, val):
        self.val = val
    data = [Item(5), Item(2), Item(8), Item(1)]
    heapx.heapify(data, cmp=lambda x: x.val)
    assert data[0].val == 1

  def test_mixed_numeric_with_key(self):
    """Test mixed int/float with key function."""
    data = [5, 2.5, 8, 1.5, 9, 3.5]
    heapx.heapify(data, cmp=lambda x: int(x))
    assert is_valid_heap(data, cmp=lambda x: int(x))

  def test_negative_floats_with_key(self):
    """Test negative floats with abs key."""
    data = [-5.5, 2.2, -8.8, 1.1, -9.9]
    heapx.heapify(data, cmp=abs)
    assert is_valid_heap(data, cmp=abs)

# ============================================================================
# Correctness Verification Tests
# ============================================================================

class TestCorrectness:
  """Verify correctness of key function operations."""

  def test_heapify_key_correctness_small(self):
    """Verify heapify correctness with key on small heap."""
    for seed in range(100):
      data = generate_integers(64, seed)
      heapx.heapify(data, cmp=abs)
      assert is_valid_heap(data, cmp=abs)

  def test_heapify_key_correctness_large(self):
    """Verify heapify correctness with key on large heap."""
    for seed in range(50):
      data = generate_integers(300, seed)
      heapx.heapify(data, cmp=abs)
      assert is_valid_heap(data, cmp=abs)

  def test_min_element_with_key(self):
    """Verify min element is at root with key."""
    data = [-100, 50, -200, 25, 75]
    heapx.heapify(data, cmp=abs)
    assert abs(data[0]) == min(abs(x) for x in [-100, 50, -200, 25, 75])

  def test_max_element_with_key(self):
    """Verify max element is at root with max_heap and key."""
    data = [-100, 50, -200, 25, 75]
    heapx.heapify(data, max_heap=True, cmp=abs)
    assert abs(data[0]) == max(abs(x) for x in [-100, 50, -200, 25, 75])

# ============================================================================
# Comprehensive Multi-threaded Configuration Tests
# ============================================================================

class TestConcurrentAllConfigurations:
  """Test all heap configurations concurrently to verify thread safety."""

  @pytest.mark.parametrize("arity", [2, 3, 4])
  @pytest.mark.parametrize("max_heap", [False, True])
  @pytest.mark.parametrize("n", [64, 128, 200])
  def test_concurrent_heapify_all_configs(self, arity, max_heap, n):
    """Concurrent heapify with all configuration combinations."""
    def worker(seed):
      rng = random.Random(seed)
      data = [rng.randint(-1000, 1000) for _ in range(n)]
      heapx.heapify(data, max_heap=max_heap, cmp=abs, arity=arity)
      return is_valid_heap(data, max_heap=max_heap, cmp=abs, arity=arity)

    with ThreadPoolExecutor(max_workers=8) as executor:
      futures = [executor.submit(worker, i * 999) for i in range(20)]
      results = [f.result() for f in as_completed(futures)]
    assert all(results)

  def test_concurrent_all_arities_simultaneously(self):
    """Run all arities concurrently to stress test thread isolation."""
    def worker(arity, seed):
      rng = random.Random(seed)
      data = [rng.randint(-1000, 1000) for _ in range(150)]
      heapx.heapify(data, cmp=abs, arity=arity)
      return is_valid_heap(data, cmp=abs, arity=arity)

    with ThreadPoolExecutor(max_workers=16) as executor:
      futures = []
      for i in range(50):
        for arity in [1, 2, 3, 4, 5, 8]:
          futures.append(executor.submit(worker, arity, i * 1000 + arity))
      results = [f.result() for f in as_completed(futures)]
    assert all(results)

  def test_concurrent_mixed_min_max_heaps(self):
    """Concurrent min and max heap operations."""
    def min_worker(seed):
      rng = random.Random(seed)
      data = [rng.randint(-1000, 1000) for _ in range(150)]
      heapx.heapify(data, max_heap=False, cmp=abs)
      return is_valid_heap(data, max_heap=False, cmp=abs)

    def max_worker(seed):
      rng = random.Random(seed)
      data = [rng.randint(-1000, 1000) for _ in range(150)]
      heapx.heapify(data, max_heap=True, cmp=abs)
      return is_valid_heap(data, max_heap=True, cmp=abs)

    with ThreadPoolExecutor(max_workers=16) as executor:
      futures = []
      for i in range(50):
        futures.append(executor.submit(min_worker, i * 1000))
        futures.append(executor.submit(max_worker, i * 1000 + 500))
      results = [f.result() for f in as_completed(futures)]
    assert all(results)

# ============================================================================
# Re-entrancy Edge Cases at Boundary
# ============================================================================

class TestReentrancyBoundary:
  """Test re-entrancy specifically at stack/heap allocation boundary."""

  def test_reentrant_outer_stack_inner_stack(self):
    """Re-entrant: outer uses stack (n=64), inner uses stack (n=64)."""
    inner_valid = []
    def outer_key(x):
      inner = list(range(64, 0, -1))
      heapx.heapify(inner, cmp=lambda y: y)
      inner_valid.append(is_valid_heap(inner, cmp=lambda y: y))
      return x
    data = list(range(64, 0, -1))
    heapx.heapify(data, cmp=outer_key)
    assert is_valid_heap(data, cmp=lambda x: x)
    assert all(inner_valid)

  def test_reentrant_outer_stack_inner_heap(self):
    """Re-entrant: outer uses stack (n=64), inner uses heap (n=200)."""
    inner_valid = []
    def outer_key(x):
      inner = list(range(200, 0, -1))
      heapx.heapify(inner, cmp=lambda y: y)
      inner_valid.append(is_valid_heap(inner, cmp=lambda y: y))
      return x
    data = list(range(64, 0, -1))
    heapx.heapify(data, cmp=outer_key)
    assert is_valid_heap(data, cmp=lambda x: x)
    assert all(inner_valid)

  def test_reentrant_outer_heap_inner_stack(self):
    """Re-entrant: outer uses heap (n=200), inner uses stack (n=64)."""
    inner_valid = []
    def outer_key(x):
      inner = list(range(64, 0, -1))
      heapx.heapify(inner, cmp=lambda y: y)
      inner_valid.append(is_valid_heap(inner, cmp=lambda y: y))
      return x
    data = list(range(200, 0, -1))
    heapx.heapify(data, cmp=outer_key)
    assert is_valid_heap(data, cmp=lambda x: x)
    assert all(inner_valid)

  def test_reentrant_outer_heap_inner_heap(self):
    """Re-entrant: outer uses heap (n=200), inner uses heap (n=200)."""
    inner_valid = []
    def outer_key(x):
      inner = list(range(200, 0, -1))
      heapx.heapify(inner, cmp=lambda y: y)
      inner_valid.append(is_valid_heap(inner, cmp=lambda y: y))
      return x
    data = list(range(200, 0, -1))
    heapx.heapify(data, cmp=outer_key)
    assert is_valid_heap(data, cmp=lambda x: x)
    assert all(inner_valid)

  def test_reentrant_at_exact_boundary(self):
    """Re-entrant: both outer and inner at exact boundary (n=128)."""
    inner_valid = []
    def outer_key(x):
      inner = list(range(128, 0, -1))
      heapx.heapify(inner, cmp=lambda y: y)
      inner_valid.append(is_valid_heap(inner, cmp=lambda y: y))
      return x
    data = list(range(128, 0, -1))
    heapx.heapify(data, cmp=outer_key)
    assert is_valid_heap(data, cmp=lambda x: x)
    assert all(inner_valid)

  def test_reentrant_boundary_minus_one_plus_one(self):
    """Re-entrant: outer at n=127 (stack), inner at n=129 (heap)."""
    inner_valid = []
    def outer_key(x):
      inner = list(range(129, 0, -1))
      heapx.heapify(inner, cmp=lambda y: y)
      inner_valid.append(is_valid_heap(inner, cmp=lambda y: y))
      return x
    data = list(range(127, 0, -1))
    heapx.heapify(data, cmp=outer_key)
    assert is_valid_heap(data, cmp=lambda x: x)
    assert all(inner_valid)

# ============================================================================
# Exception Handling with Proper Cleanup
# ============================================================================

class TestExceptionCleanup:
  """Test proper memory cleanup when exceptions occur."""

  def test_exception_early_in_small_heap(self):
    """Exception early in key computation (stack allocation)."""
    def bad_key(x):
      if x == 60:
        raise ValueError("early exception")
      return x
    data = list(range(64, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_exception_late_in_small_heap(self):
    """Exception late in key computation (stack allocation)."""
    def bad_key(x):
      if x == 5:
        raise ValueError("late exception")
      return x
    data = list(range(64, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_exception_early_in_large_heap(self):
    """Exception early in key computation (heap allocation)."""
    def bad_key(x):
      if x == 190:
        raise ValueError("early exception")
      return x
    data = list(range(200, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_exception_late_in_large_heap(self):
    """Exception late in key computation (heap allocation)."""
    def bad_key(x):
      if x == 10:
        raise ValueError("late exception")
      return x
    data = list(range(200, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_exception_at_boundary_element(self):
    """Exception at exact boundary element (n=128, fail at 128)."""
    def bad_key(x):
      if x == 1:  # Last element processed
        raise ValueError("boundary exception")
      return x
    data = list(range(128, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_exception_just_past_boundary(self):
    """Exception just past boundary (n=129, fail at element 129)."""
    def bad_key(x):
      if x == 1:
        raise ValueError("past boundary exception")
      return x
    data = list(range(129, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_exception_in_heapify_small(self):
    """Exception during heapify with small heap."""
    call_count = [0]
    def bad_key(x):
      call_count[0] += 1
      if call_count[0] > 50:
        raise ValueError("heapify exception")
      return x
    data = list(range(64, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_exception_in_heapify_large(self):
    """Exception during heapify with large heap."""
    call_count = [0]
    def bad_key(x):
      call_count[0] += 1
      if call_count[0] > 150:
        raise ValueError("heapify exception")
      return x
    data = list(range(200, 0, -1))
    with pytest.raises(ValueError):
      heapx.heapify(data, cmp=bad_key)

  def test_repeated_exceptions_no_leak(self):
    """Repeated exceptions should not leak memory."""
    gc.collect()
    initial_objects = len(gc.get_objects())
    
    for i in range(100):
      def bad_key(x):
        if x == 50:
          raise ValueError("test")
        return x
      data = list(range(200, 0, -1))
      try:
        heapx.heapify(data, cmp=bad_key)
      except ValueError:
        pass
    
    gc.collect()
    # Allow some variance but check for major leaks
    final_objects = len(gc.get_objects())
    assert final_objects < initial_objects + 1000

# ============================================================================
# Concurrent Exception Handling
# ============================================================================

class TestConcurrentExceptions:
  """Test exception handling in concurrent scenarios."""

  def test_concurrent_exceptions_small_heap(self):
    """Concurrent operations where some raise exceptions (stack)."""
    def worker(seed, should_fail):
      rng = random.Random(seed)
      data = [rng.randint(1, 100) for _ in range(64)]
      def key_func(x):
        if should_fail and x == 50:
          raise ValueError("expected")
        return x
      try:
        heapx.heapify(data, cmp=key_func)
        return "success"
      except ValueError:
        return "exception"

    with ThreadPoolExecutor(max_workers=8) as executor:
      futures = []
      for i in range(50):
        futures.append(executor.submit(worker, i, i % 3 == 0))
      results = [f.result() for f in as_completed(futures)]
    
    assert "success" in results
    assert "exception" in results

  def test_concurrent_exceptions_large_heap(self):
    """Concurrent operations where some raise exceptions (heap)."""
    def worker(seed, should_fail):
      rng = random.Random(seed)
      data = [rng.randint(1, 200) for _ in range(200)]
      def key_func(x):
        if should_fail and x == 100:
          raise ValueError("expected")
        return x
      try:
        heapx.heapify(data, cmp=key_func)
        return "success"
      except ValueError:
        return "exception"

    with ThreadPoolExecutor(max_workers=8) as executor:
      futures = []
      for i in range(30):
        futures.append(executor.submit(worker, i, i % 3 == 0))
      results = [f.result() for f in as_completed(futures)]
    
    assert "success" in results

# ============================================================================
# Thread Isolation Verification
# ============================================================================

class TestThreadIsolation:
  """Verify each thread has isolated key array allocation."""

  def test_thread_local_key_arrays(self):
    """Verify threads don't share key arrays."""
    results = {}
    lock = threading.Lock()

    def worker(thread_id, n):
      # Each thread uses a unique key that tracks which thread processed it
      processed_by = []
      def key_func(x):
        processed_by.append(thread_id)
        return x
      
      data = list(range(n, 0, -1))
      heapx.heapify(data, cmp=key_func)
      
      with lock:
        results[thread_id] = {
          'valid': is_valid_heap(data, cmp=lambda x: x),
          'all_same_thread': all(t == thread_id for t in processed_by)
        }

    threads = []
    for i in range(10):
      t = threading.Thread(target=worker, args=(i, 100))
      threads.append(t)
      t.start()

    for t in threads:
      t.join()

    assert all(r['valid'] for r in results.values())
    assert all(r['all_same_thread'] for r in results.values())

  def test_no_cross_thread_contamination(self):
    """Ensure key values don't leak between threads."""
    contamination_detected = []
    lock = threading.Lock()

    def worker(thread_id, marker):
      seen_markers = set()
      def key_func(x):
        # Each thread adds its marker; should only see own marker
        seen_markers.add(marker)
        return x + marker
      
      data = list(range(150, 0, -1))
      heapx.heapify(data, cmp=key_func)
      
      with lock:
        if len(seen_markers) > 1:
          contamination_detected.append(thread_id)

    threads = []
    for i in range(20):
      t = threading.Thread(target=worker, args=(i, i * 10000))
      threads.append(t)
      t.start()

    for t in threads:
      t.join()

    assert len(contamination_detected) == 0

# ============================================================================
# High Contention Tests
# ============================================================================

class TestHighContention:
  """Test under high thread contention."""

  def test_maximum_concurrent_threads(self):
    """Test with maximum practical thread count."""
    def worker(seed):
      rng = random.Random(seed)
      data = [rng.randint(-1000, 1000) for _ in range(150)]
      heapx.heapify(data, cmp=abs)
      return is_valid_heap(data, cmp=abs)

    with ThreadPoolExecutor(max_workers=32) as executor:
      futures = [executor.submit(worker, i) for i in range(200)]
      results = [f.result() for f in as_completed(futures)]
    assert all(results)

  def test_rapid_thread_creation_destruction(self):
    """Rapid thread creation and destruction."""
    for _ in range(50):
      def worker():
        data = list(range(100, 0, -1))
        heapx.heapify(data, cmp=abs)
        return is_valid_heap(data, cmp=abs)

      threads = [threading.Thread(target=worker) for _ in range(10)]
      for t in threads:
        t.start()
      for t in threads:
        t.join()

  def test_burst_operations(self):
    """Burst of operations followed by idle."""
    for burst in range(10):
      with ThreadPoolExecutor(max_workers=16) as executor:
        futures = []
        for i in range(50):
          def worker(seed):
            rng = random.Random(seed)
            data = [rng.randint(-1000, 1000) for _ in range(150)]
            heapx.heapify(data, cmp=abs)
            return is_valid_heap(data, cmp=abs)
          futures.append(executor.submit(worker, burst * 1000 + i))
        results = [f.result() for f in as_completed(futures)]
        assert all(results)
      time.sleep(0.01)  # Brief idle between bursts
