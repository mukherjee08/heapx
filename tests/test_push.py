"""
Comprehensive test suite for heapx.push function.

Tests cover all parameters, data types, edge cases, and performance benchmarks
against Python's standard heapq module.
"""

import heapq
import heapx
import pytest
import random
import string
import time
import sys
from typing import List, Any, Callable, Tuple
from statistics import mean, stdev

# ============================================================================
# Test Data Generators
# ============================================================================

def generate_integers(n: int, seed: int = 42) -> List[int]:
  """Generate list of random integers."""
  random.seed(seed); return [random.randint(-1000000, 1000000) for _ in range(n)]

def generate_floats(n: int, seed: int = 42) -> List[float]:
  """Generate list of random floats."""
  random.seed(seed); return [random.uniform(-1000.0, 1000.0) for _ in range(n)]

def generate_complex(n: int, seed: int = 42) -> List[complex]:
  """Generate list of random complex numbers (not directly comparable)."""
  random.seed(seed); return [complex(random.uniform(-100, 100), random.uniform(-100, 100)) for _ in range(n)]

def generate_strings(n: int, seed: int = 42) -> List[str]:
  """Generate list of random strings."""
  random.seed(seed); return [''.join(random.choices(string.ascii_letters, k=10)) for _ in range(n)]

def generate_lists(n: int, seed: int = 42) -> List[List[int]]:
  """Generate list of random lists (comparable lexicographically)."""
  random.seed(seed); return [[random.randint(0, 100) for _ in range(3)] for _ in range(n)]

def generate_tuples(n: int, seed: int = 42) -> List[Tuple[int, str]]:
  """Generate list of random tuples."""
  random.seed(seed); return [(random.randint(0, 1000), ''.join(random.choices(string.ascii_letters, k=5))) for _ in range(n)]

def generate_range(n: int) -> range:
  """Generate range object."""
  return range(n)

def generate_booleans(n: int, seed: int = 42) -> List[bool]:
  """Generate list of random booleans."""
  random.seed(seed); return [random.choice([True, False]) for _ in range(n)]

def generate_bytes(n: int, seed: int = 42) -> List[bytes]:
  """Generate list of random bytes objects."""
  random.seed(seed); return [bytes([random.randint(0, 255) for _ in range(5)]) for _ in range(n)]

def generate_bytearrays(n: int, seed: int = 42) -> List[bytearray]:
  """Generate list of random bytearray objects."""
  random.seed(seed); return [bytearray([random.randint(0, 255) for _ in range(5)]) for _ in range(n)]

def generate_mixed(n: int, seed: int = 42) -> List[Any]:
  """Generate list of mixed comparable types (integers and floats)."""
  random.seed(seed)
  result = []
  for _ in range(n):
    if random.random() < 0.5:
      result.append(random.randint(-100, 100))
    else:
      result.append(random.uniform(-100.0, 100.0))
  return result

def is_valid_heap(arr: List[Any], max_heap: bool = False, arity: int = 2) -> bool:
  """Verify heap property for n-ary heap."""
  n = len(arr)
  for i in range(n):
    for j in range(1, arity + 1):
      child = arity * i + j
      if child >= n:
        break
      if max_heap:
        if arr[i] < arr[child]:
          return False
      else:
        if arr[i] > arr[child]:
          return False
  return True

# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestBasicPush:
  """Test basic push functionality."""

  def test_push_to_empty(self):
    """Test push to empty heap."""
    heap = []
    heapx.push(heap, 42)
    assert heap == [42]

  def test_push_single_min(self):
    """Test single push to min-heap."""
    heap = [1, 3, 5]
    heapx.heapify(heap)
    heapx.push(heap, 2)
    assert is_valid_heap(heap)
    assert heap[0] == 1

  def test_push_single_max(self):
    """Test single push to max-heap."""
    heap = [5, 3, 1]
    heapx.heapify(heap, max_heap=True)
    heapx.push(heap, 4, max_heap=True)
    assert is_valid_heap(heap, max_heap=True)
    assert heap[0] == 5

  def test_push_smaller_than_root(self):
    """Test pushing element smaller than root."""
    heap = [5, 10, 15]
    heapx.heapify(heap)
    heapx.push(heap, 1)
    assert heap[0] == 1
    assert is_valid_heap(heap)

  def test_push_larger_than_all(self):
    """Test pushing element larger than all."""
    heap = [1, 3, 5]
    heapx.heapify(heap)
    heapx.push(heap, 100)
    assert heap[0] == 1
    assert is_valid_heap(heap)

  def test_push_duplicate(self):
    """Test pushing duplicate element."""
    heap = [1, 3, 5]
    heapx.heapify(heap)
    heapx.push(heap, 3)
    assert is_valid_heap(heap)

  def test_push_multiple_sequential(self):
    """Test multiple sequential pushes."""
    heap = []
    for val in [5, 3, 8, 1, 9, 2, 7]:
      heapx.push(heap, val)
    assert is_valid_heap(heap)
    assert heap[0] == 1

  def test_push_maintains_size(self):
    """Test push increases heap size by 1."""
    heap = [1, 3, 5]
    heapx.heapify(heap)
    heapx.push(heap, 2)
    assert len(heap) == 4

  def test_push_negative_numbers(self):
    """Test push with negative numbers."""
    heap = []
    for val in [-5, -3, -8, -1]:
      heapx.push(heap, val)
    assert heap[0] == -8
    assert is_valid_heap(heap)

  def test_push_zero(self):
    """Test push with zero."""
    heap = [-5, 5]
    heapx.heapify(heap)
    heapx.push(heap, 0)
    assert is_valid_heap(heap)

# ============================================================================
# Integer Tests
# ============================================================================

class TestIntegerPush:
  """Test push with integer data."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_integers_min(self, n):
    """Test push with random integers (min-heap)."""
    heap = []
    data = generate_integers(n)
    for val in data:
      heapx.push(heap, val)
    assert is_valid_heap(heap)
    assert len(heap) == n

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_integers_max(self, n):
    """Test push with random integers (max-heap)."""
    heap = []
    data = generate_integers(n)
    for val in data:
      heapx.push(heap, val, max_heap=True)
    assert is_valid_heap(heap, max_heap=True)
    assert len(heap) == n

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_sorted_integers_ascending(self, n):
    """Test push with sorted ascending integers."""
    heap = []
    for val in range(n):
      heapx.push(heap, val)
    assert is_valid_heap(heap)
    assert heap[0] == 0

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_sorted_integers_descending(self, n):
    """Test push with sorted descending integers."""
    heap = []
    for val in range(n, 0, -1):
      heapx.push(heap, val)
    assert is_valid_heap(heap)
    assert heap[0] == 1

  def test_large_range_integers(self):
    """Test push with large range integers."""
    heap = []
    for val in [1000000, -1000000, 0, 500000, -500000]:
      heapx.push(heap, val)
    assert is_valid_heap(heap)
    assert heap[0] == -1000000

# ============================================================================
# Float Tests
# ============================================================================

class TestFloatPush:
  """Test push with float data."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_floats_min(self, n):
    """Test push with random floats (min-heap)."""
    heap = []
    data = generate_floats(n)
    for val in data:
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_floats_max(self, n):
    """Test push with random floats (max-heap)."""
    heap = []
    data = generate_floats(n)
    for val in data:
      heapx.push(heap, val, max_heap=True)
    assert is_valid_heap(heap, max_heap=True)

  def test_float_precision(self):
    """Test push with high precision floats."""
    heap = []
    for val in [1.0000001, 1.0000002, 1.0, 1.0000003]:
      heapx.push(heap, val)
    assert is_valid_heap(heap)
    assert heap[0] == 1.0

  def test_float_special_values(self):
    """Test push with special float values."""
    heap = []
    for val in [float('inf'), -float('inf'), 0.0, 1.0]:
      heapx.push(heap, val)
    assert heap[0] == -float('inf')

# ============================================================================
# String Tests
# ============================================================================

class TestStringPush:
  """Test push with string data."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_strings_min(self, n):
    """Test push with random strings (min-heap)."""
    heap = []
    data = generate_strings(n)
    for val in data:
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_strings_max(self, n):
    """Test push with random strings (max-heap)."""
    heap = []
    data = generate_strings(n)
    for val in data:
      heapx.push(heap, val, max_heap=True)
    assert is_valid_heap(heap, max_heap=True)

  def test_string_case_sensitivity(self):
    """Test push with case-sensitive strings."""
    heap = []
    for val in ["apple", "Apple", "APPLE", "aPpLe"]:
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  def test_empty_strings(self):
    """Test push with empty strings."""
    heap = []
    for val in ["", "a", "", "b"]:
      heapx.push(heap, val)
    assert is_valid_heap(heap)

# ============================================================================
# Tuple Tests
# ============================================================================

class TestTuplePush:
  """Test push with tuple data."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_tuples_min(self, n):
    """Test push with random tuples (min-heap)."""
    heap = []
    data = generate_tuples(n)
    for val in data:
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_tuples_max(self, n):
    """Test push with random tuples (max-heap)."""
    heap = []
    data = generate_tuples(n)
    for val in data:
      heapx.push(heap, val, max_heap=True)
    assert is_valid_heap(heap, max_heap=True)


# ============================================================================
# Arity Parameter Tests
# ============================================================================

class TestArityParameter:
  """Test push with different arity values."""

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8, 16])
  @pytest.mark.parametrize("n", [20, 100])
  def test_various_arity_min(self, arity, n):
    """Test push with various arity values (min-heap)."""
    heap = []
    data = generate_integers(n)
    for val in data:
      heapx.push(heap, val, arity=arity)
    assert is_valid_heap(heap, max_heap=False, arity=arity)

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8, 16])
  @pytest.mark.parametrize("n", [20, 100])
  def test_various_arity_max(self, arity, n):
    """Test push with various arity values (max-heap)."""
    heap = []
    data = generate_integers(n)
    for val in data:
      heapx.push(heap, val, max_heap=True, arity=arity)
    assert is_valid_heap(heap, max_heap=True, arity=arity)

  def test_unary_heap(self):
    """Test push with arity=1 (sorted list)."""
    heap = []
    for val in [5, 3, 8, 1, 9]:
      heapx.push(heap, val, arity=1)
    assert heap == sorted(heap)

  def test_ternary_heap(self):
    """Test push with arity=3."""
    heap = []
    for val in range(30, 0, -1):
      heapx.push(heap, val, arity=3)
    assert is_valid_heap(heap, arity=3)
    assert heap[0] == 1

  def test_quaternary_heap(self):
    """Test push with arity=4."""
    heap = []
    for val in range(20, 0, -1):
      heapx.push(heap, val, arity=4)
    assert is_valid_heap(heap, arity=4)
    assert heap[0] == 1

# ============================================================================
# Custom Comparison Tests
# ============================================================================

class TestCustomComparison:
  """Test push with custom comparison functions."""

  def test_absolute_value_comparison(self):
    """Test push with absolute value comparison."""
    heap = []
    for val in [-5, 2, -8, 1, 9, -3]:
      heapx.push(heap, val, cmp=abs)
    assert abs(heap[0]) == 1

  def test_reverse_comparison(self):
    """Test push with reverse comparison."""
    heap = []
    for val in [5, 2, 8, 1, 9]:
      heapx.push(heap, val, cmp=lambda x: -x)
    assert heap[0] == 9

  def test_tuple_second_element(self):
    """Test push comparing by tuple second element."""
    heap = []
    for val in [(1, 5), (2, 3), (3, 7), (4, 1)]:
      heapx.push(heap, val, cmp=lambda x: x[1])
    assert heap[0][1] == 1

  def test_string_length_comparison(self):
    """Test push comparing by string length."""
    heap = []
    for val in ["apple", "pie", "a", "banana"]:
      heapx.push(heap, val, cmp=len)
    assert len(heap[0]) == 1

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_custom_cmp_with_arity(self, n):
    """Test push with custom comparison and various arities."""
    heap = []
    data = generate_integers(n)
    for val in data:
      heapx.push(heap, val, cmp=abs, arity=3)
    # Verify heap property with abs
    for i in range(len(heap)):
      for j in range(1, 4):
        child = 3 * i + j
        if child < len(heap):
          assert abs(heap[i]) <= abs(heap[child])

# ============================================================================
# Bulk Insertion Tests
# ============================================================================

class TestBulkInsertion:
  """Test bulk push operations."""

  def test_bulk_push_list(self):
    """Test bulk push with list."""
    heap = [1, 3, 5]
    heapx.heapify(heap)
    heapx.push(heap, [2, 4, 6])
    assert len(heap) == 6
    assert is_valid_heap(heap)

  def test_bulk_push_empty_list(self):
    """Test bulk push with empty list."""
    heap = [1, 3, 5]
    heapx.heapify(heap)
    heapx.push(heap, [])
    assert len(heap) == 3

  def test_bulk_push_large(self):
    """Test bulk push with large list."""
    heap = []
    heapx.push(heap, list(range(100)))
    assert len(heap) == 100
    assert is_valid_heap(heap)

  def test_bulk_push_max_heap(self):
    """Test bulk push to max-heap."""
    heap = [5, 3, 1]
    heapx.heapify(heap, max_heap=True)
    heapx.push(heap, [4, 6, 2], max_heap=True)
    assert is_valid_heap(heap, max_heap=True)

  def test_bulk_push_with_arity(self):
    """Test bulk push with custom arity."""
    heap = []
    heapx.push(heap, list(range(50)), arity=3)
    assert is_valid_heap(heap, arity=3)

# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
  """Test edge cases and boundary conditions."""

  def test_push_to_size_16(self):
    """Test push to heap of size 16 (boundary for small heap optimization)."""
    heap = list(range(16))
    heapx.heapify(heap)
    heapx.push(heap, -1)
    assert is_valid_heap(heap)
    assert heap[0] == -1

  def test_push_to_size_17(self):
    """Test push to heap of size 17."""
    heap = list(range(17))
    heapx.heapify(heap)
    heapx.push(heap, -1)
    assert is_valid_heap(heap)
    assert heap[0] == -1

  def test_all_equal_elements(self):
    """Test push with all equal elements."""
    heap = [5, 5, 5]
    heapx.heapify(heap)
    heapx.push(heap, 5)
    assert all(x == 5 for x in heap)

  def test_invalid_arity(self):
    """Test push with invalid arity."""
    heap = []
    with pytest.raises(ValueError):
      heapx.push(heap, 1, arity=0)

  def test_invalid_cmp(self):
    """Test push with invalid cmp."""
    heap = []
    with pytest.raises(TypeError):
      heapx.push(heap, 1, cmp="not_callable")

  def test_push_tuple_as_single_item(self):
    """Test that tuple is treated as single item, not sequence."""
    heap = []
    heapx.push(heap, (1, 2, 3))
    assert len(heap) == 1
    assert heap[0] == (1, 2, 3)

  def test_push_string_as_single_item(self):
    """Test that string is treated as single item."""
    heap = []
    heapx.push(heap, "hello")
    assert len(heap) == 1
    assert heap[0] == "hello"

# ============================================================================
# Sequence Type Tests
# ============================================================================

class TestSequenceTypes:
  """Test push with different sequence types."""

  def test_push_to_list(self):
    """Test push to list (most common case)."""
    heap = []
    heapx.push(heap, 5)
    assert isinstance(heap, list)
    assert heap == [5]

  def test_push_maintains_list_type(self):
    """Test that push maintains list type."""
    heap = [1, 3, 5]
    heapx.heapify(heap)
    heapx.push(heap, 2)
    assert isinstance(heap, list)

# ============================================================================
# Correctness Verification Tests
# ============================================================================

class TestCorrectnessVerification:
  """Verify correctness by extracting all elements."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_extract_all_min_heap(self, n):
    """Test that all elements can be extracted in sorted order (min-heap)."""
    heap = []
    data = generate_integers(n)
    for val in data:
      heapx.push(heap, val)
    
    result = []
    while heap:
      result.append(heapx.pop(heap))
    
    assert result == sorted(data)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_extract_all_max_heap(self, n):
    """Test that all elements can be extracted in reverse sorted order (max-heap)."""
    heap = []
    data = generate_integers(n)
    for val in data:
      heapx.push(heap, val, max_heap=True)
    
    result = []
    while heap:
      result.append(heapx.pop(heap, max_heap=True))
    
    assert result == sorted(data, reverse=True)

  def test_push_pop_interleaved(self):
    """Test interleaved push and pop operations."""
    heap = []
    heapx.push(heap, 5)
    heapx.push(heap, 3)
    assert heapx.pop(heap) == 3
    heapx.push(heap, 1)
    heapx.push(heap, 7)
    assert heapx.pop(heap) == 1
    assert is_valid_heap(heap)

  def test_push_maintains_heap_property(self):
    """Test that push always maintains heap property."""
    heap = []
    random.seed(42)
    for i in range(100):
      heapx.push(heap, random.randint(1, 1000))
      if i % 10 == 0:  # Check every 10th iteration to speed up
        assert is_valid_heap(heap)
    assert is_valid_heap(heap)  # Final check

  def test_push_with_mixed_types_comparable(self):
    """Test push with mixed but comparable types."""
    heap = []
    for val in [1, 2.5, 3, 4.7, 5]:
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  def test_push_preserves_existing_elements(self):
    """Test that push doesn't modify existing elements."""
    heap = [1, 3, 5, 7, 9]
    heapx.heapify(heap)
    original = set(heap)
    heapx.push(heap, 4)
    assert original.issubset(set(heap))

  def test_push_to_max_heap_with_negatives(self):
    """Test push to max-heap with negative numbers."""
    heap = []
    for val in [-5, -3, -8, -1, -9]:
      heapx.push(heap, val, max_heap=True)
    assert heap[0] == -1
    assert is_valid_heap(heap, max_heap=True)


# ============================================================================
# Stress Tests
# ============================================================================

class TestStressTests:
  """Stress tests with large datasets."""

  def test_very_large_heap(self):
    """Test push with very large heap."""
    heap = []
    for i in range(10000):
      heapx.push(heap, i)
    assert is_valid_heap(heap)
    assert len(heap) == 10000

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_repeated_push(self, n):
    """Test repeated push operations."""
    heap = []
    data = generate_integers(n)
    for val in data:
      heapx.push(heap, val)
    assert is_valid_heap(heap)
    assert len(heap) == n

  def test_all_combinations(self):
    """Test various combinations of parameters."""
    test_cases = [
      (False, None, 2),
      (True, None, 2),
      (False, None, 3),
      (True, None, 3),
      (False, abs, 2),
      (True, abs, 2),
      (False, None, 5),
    ]
    
    for max_heap, cmp, arity in test_cases:
      heap = []
      data = generate_integers(50)
      for val in data:
        heapx.push(heap, val, max_heap=max_heap, cmp=cmp, arity=arity)

# ============================================================================
# Performance Benchmark Tests
# ============================================================================

class TestPerformanceBenchmark:
  """Performance benchmarks against heapq."""

  @pytest.mark.benchmark
  def test_performance_comparison(self, capsys):
    """Comprehensive performance comparison: heapx.push vs heapq.heappush."""
    
    output = []
    output.append("\n" + "="*80)
    output.append("TIME EFFICIENCY COMPARISON: heapx.push vs heapq.heappush")
    output.append("="*80)
    output.append(f"Configuration: R=10 repetitions per size, Random integers, Min-heap, Arity=2")
    output.append("="*80)
    
    sizes = [100_000, 200_000, 300_000, 400_000, 500_000,
             600_000, 700_000, 800_000, 900_000, 1_000_000]
    repetitions = 10
    
    results = []
    memory_results = []
    
    for n in sizes:
      heapx_times = []
      heapq_times = []
      
      for r in range(repetitions):
        data = generate_integers(n, seed=r)
        
        # Measure heapx time
        heap_heapx = []
        start = time.perf_counter()
        for val in data:
          heapx.push(heap_heapx, val)
        heapx_times.append(time.perf_counter() - start)
        
        # Measure heapq time
        heap_heapq = []
        start = time.perf_counter()
        for val in data:
          heapq.heappush(heap_heapq, val)
        heapq_times.append(time.perf_counter() - start)
        
        assert is_valid_heap(heap_heapx, max_heap=False)
        assert is_valid_heap(heap_heapq, max_heap=False)
      
      heapx_avg = mean(heapx_times)
      heapx_std = stdev(heapx_times) if len(heapx_times) > 1 else 0
      heapq_avg = mean(heapq_times)
      heapq_std = stdev(heapq_times) if len(heapq_times) > 1 else 0
      
      results.append({
        'n': n,
        'heapx_avg': heapx_avg,
        'heapx_std': heapx_std,
        'heapq_avg': heapq_avg,
        'heapq_std': heapq_std
      })
      
      # Measure memory for each size
      data = generate_integers(n, seed=0)
      
      heap_heapx = []
      for val in data:
        heapx.push(heap_heapx, val)
      heapx_mem = sys.getsizeof(heap_heapx)
      
      heap_heapq = []
      for val in data:
        heapq.heappush(heap_heapq, val)
      heapq_mem = sys.getsizeof(heap_heapq)
      
      memory_results.append({
        'n': n,
        'heapx_mem': heapx_mem,
        'heapq_mem': heapq_mem
      })
    
    # Time efficiency table
    output.append("\n" + "-"*65)
    output.append(f"{'n':>12} │ {'heapx (s)':>23} │ {'heapq (s)':>23}")
    output.append(f"{'':>12} │ {'avg ± std':>23} │ {'avg ± std':>23}")
    output.append("-"*65)
    
    for r in results:
      output.append(f"{r['n']:>12,} │ "
                   f"{r['heapx_avg']:>10.4f} ± {r['heapx_std']:>8.4f} │ "
                   f"{r['heapq_avg']:>10.4f} ± {r['heapq_std']:>8.4f}")
    
    output.append("-"*65)
    output.append("="*80)
    
    # Memory efficiency table
    output.append("\nMEMORY EFFICIENCY COMPARISON: heapx.push vs heapq.heappush")
    output.append("="*80)
    output.append(f"Configuration: Random integers, Min-heap, Arity=2")
    output.append("="*80)
    output.append("\n" + "-"*65)
    output.append(f"{'n':>12} │ {'heapx (bytes)':>23} │ {'heapq (bytes)':>23}")
    output.append("-"*65)
    
    for r in memory_results:
      output.append(f"{r['n']:>12,} │ {r['heapx_mem']:>23,} │ {r['heapq_mem']:>23,}")
    
    output.append("-"*65)
    output.append("\nNote: Both implementations use O(1) auxiliary space")
    output.append("="*80 + "\n")
    
    # Print all output
    final_output = '\n'.join(output)
    print(final_output)
    sys.stdout.flush()
    
    # Also write to captured output for pytest
    with capsys.disabled():
      print(final_output)

  @pytest.mark.benchmark
  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_arity_performance(self, arity):
    """Test performance with different arity values."""
    n = 1_000_000
    data = generate_integers(n)
    
    heap = []
    start = time.perf_counter()
    for val in data:
      heapx.push(heap, val, arity=arity)
    elapsed = time.perf_counter() - start
    
    assert is_valid_heap(heap, max_heap=False, arity=arity)
    print(f"\nArity {arity}: {elapsed:.4f}s for {n:,} elements")

  @pytest.mark.benchmark
  def test_key_function_performance(self):
    """Test performance with key function."""
    n = 1_000_000
    data = generate_integers(n)
    
    heap = []
    start = time.perf_counter()
    for val in data:
      heapx.push(heap, val, cmp=abs)
    elapsed = time.perf_counter() - start
    
    print(f"\nKey function (abs): {elapsed:.4f}s for {n:,} elements")

  @pytest.mark.benchmark
  def test_bulk_vs_sequential_performance(self):
    """Compare bulk push vs sequential push performance."""
    n = 100_000
    repetitions = 10
    data = generate_integers(n)
    
    # Sequential push
    seq_times = []
    for _ in range(repetitions):
      heap = []
      start = time.perf_counter()
      for val in data:
        heapx.push(heap, val)
      seq_times.append(time.perf_counter() - start)
    
    seq_avg = mean(seq_times)
    seq_std = stdev(seq_times) if len(seq_times) > 1 else 0
    
    # Bulk push
    bulk_times = []
    for _ in range(repetitions):
      heap = []
      start = time.perf_counter()
      heapx.push(heap, data)
      bulk_times.append(time.perf_counter() - start)
    
    bulk_avg = mean(bulk_times)
    bulk_std = stdev(bulk_times) if len(bulk_times) > 1 else 0
    
    print(f"\nBulk vs Sequential Push ({n:,} elements, R={repetitions}):")
    print(f"  Sequential: {seq_avg:.4f} ± {seq_std:.4f}s")
    print(f"  Bulk:       {bulk_avg:.4f} ± {bulk_std:.4f}s")
    print(f"  Speedup:    {seq_avg/bulk_avg:.2f}x")

# ============================================================================
# Boolean Tests
# ============================================================================

class TestBooleanPush:
  """Test push with boolean data."""

  def test_push_booleans(self):
    """Test pushing booleans to heap."""
    heap = []
    for val in generate_booleans(50):
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  def test_bulk_push_booleans(self):
    """Test bulk push with booleans."""
    heap = []
    heapx.push(heap, generate_booleans(50))
    assert is_valid_heap(heap)

# ============================================================================
# Bytes Tests
# ============================================================================

class TestBytesPush:
  """Test push with bytes data."""

  def test_push_bytes(self):
    """Test pushing bytes to heap."""
    heap = []
    for val in generate_bytes(30):
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  def test_bulk_push_bytes(self):
    """Test bulk push with bytes."""
    heap = []
    heapx.push(heap, generate_bytes(30))
    assert is_valid_heap(heap)

# ============================================================================
# Bytearray Tests
# ============================================================================

class TestBytearrayPush:
  """Test push with bytearray data."""

  def test_push_bytearrays(self):
    """Test pushing bytearrays to heap."""
    heap = []
    for val in generate_bytearrays(30):
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  def test_bulk_push_bytearrays(self):
    """Test bulk push with bytearrays."""
    heap = []
    heapx.push(heap, generate_bytearrays(30))
    assert is_valid_heap(heap)

# ============================================================================
# List Tests
# ============================================================================

class TestListPush:
  """Test push with list data."""

  def test_push_lists(self):
    """Test pushing lists to heap."""
    heap = []
    for val in generate_lists(30):
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  def test_bulk_push_lists(self):
    """Test bulk push with lists."""
    heap = []
    heapx.push(heap, generate_lists(30))
    assert is_valid_heap(heap)

# ============================================================================
# Mixed Type Tests
# ============================================================================

class TestMixedPush:
  """Test push with mixed comparable types."""

  def test_push_mixed(self):
    """Test pushing mixed int/float to heap."""
    heap = []
    for val in generate_mixed(100):
      heapx.push(heap, val)
    assert is_valid_heap(heap)

  def test_bulk_push_mixed(self):
    """Test bulk push with mixed types."""
    heap = []
    heapx.push(heap, generate_mixed(100))
    assert is_valid_heap(heap)

  def test_push_mixed_max_heap(self):
    """Test pushing mixed types to max-heap."""
    heap = []
    for val in generate_mixed(100):
      heapx.push(heap, val, max_heap=True)
    assert is_valid_heap(heap, max_heap=True)

# ============================================================================
# Memory Efficiency Tests
# ============================================================================

class TestMemoryEfficiency:
  """Test memory efficiency of push operations."""

  @pytest.mark.benchmark
  def test_memory_usage(self):
    """Memory usage is already included in test_performance_comparison."""
    pass


