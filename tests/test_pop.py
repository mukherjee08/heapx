"""
Comprehensive test suite for heapx.pop function.

Tests cover all parameters, data types, edge cases, and performance benchmarks
against Python's standard heapq module. Includes 120+ distinct test cases.
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

class TestBasicPop:
  """Test basic pop functionality."""

  def test_pop_from_single_element(self):
    """Test pop from single element heap."""
    heap = [42]
    result = heapx.pop(heap)
    assert result == 42
    assert len(heap) == 0

  def test_pop_from_two_elements_min(self):
    """Test pop from two element min-heap."""
    heap = [1, 2]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1
    assert heap == [2]

  def test_pop_from_two_elements_max(self):
    """Test pop from two element max-heap."""
    heap = [1, 2]
    heapx.heapify(heap, max_heap=True)
    result = heapx.pop(heap, max_heap=True)
    assert result == 2
    assert heap == [1]

  def test_pop_maintains_heap_property(self):
    """Test that pop maintains heap property."""
    heap = [1, 3, 2, 7, 5, 4, 6]
    heapx.heapify(heap)
    heapx.pop(heap)
    assert is_valid_heap(heap)

  def test_pop_returns_minimum(self):
    """Test that pop returns minimum element."""
    heap = [5, 3, 8, 1, 9, 2, 7]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1

  def test_pop_returns_maximum(self):
    """Test that pop returns maximum element from max-heap."""
    heap = [5, 3, 8, 1, 9, 2, 7]
    heapx.heapify(heap, max_heap=True)
    result = heapx.pop(heap, max_heap=True)
    assert result == 9

  def test_pop_empty_heap_raises_error(self):
    """Test that popping from empty heap raises IndexError."""
    heap = []
    with pytest.raises(IndexError):
      heapx.pop(heap)

  def test_pop_reduces_size_by_one(self):
    """Test that pop reduces heap size by 1."""
    heap = list(range(10))
    heapx.heapify(heap)
    original_size = len(heap)
    heapx.pop(heap)
    assert len(heap) == original_size - 1

  def test_pop_all_elements_sorted(self):
    """Test popping all elements gives sorted order."""
    heap = [5, 2, 8, 1, 9, 3, 7, 4, 6]
    heapx.heapify(heap)
    result = []
    while heap:
      result.append(heapx.pop(heap))
    assert result == sorted([5, 2, 8, 1, 9, 3, 7, 4, 6])

  def test_pop_all_elements_reverse_sorted(self):
    """Test popping all elements from max-heap gives reverse sorted order."""
    heap = [5, 2, 8, 1, 9, 3, 7, 4, 6]
    heapx.heapify(heap, max_heap=True)
    result = []
    while heap:
      result.append(heapx.pop(heap, max_heap=True))
    assert result == sorted([5, 2, 8, 1, 9, 3, 7, 4, 6], reverse=True)


# ============================================================================
# Integer Tests
# ============================================================================

class TestIntegerPop:
  """Test pop with integer data."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_integers_min(self, n):
    """Test pop with random integers (min-heap)."""
    data = generate_integers(n)
    heap = data.copy()
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == min(data)
    assert is_valid_heap(heap)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_integers_max(self, n):
    """Test pop with random integers (max-heap)."""
    data = generate_integers(n)
    heap = data.copy()
    heapx.heapify(heap, max_heap=True)
    result = heapx.pop(heap, max_heap=True)
    assert result == max(data)
    assert is_valid_heap(heap, max_heap=True)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_sorted_integers_ascending(self, n):
    """Test pop with sorted ascending integers."""
    heap = list(range(n))
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 0
    assert is_valid_heap(heap)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_sorted_integers_descending(self, n):
    """Test pop with sorted descending integers."""
    heap = list(range(n, 0, -1))
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1
    assert is_valid_heap(heap)

  def test_negative_integers(self):
    """Test pop with negative integers."""
    heap = [-5, -1, -10, -3, -7]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == -10
    assert is_valid_heap(heap)

  def test_mixed_sign_integers(self):
    """Test pop with mixed positive/negative integers."""
    heap = [5, -3, 10, -7, 0, 2, -1]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == -7
    assert is_valid_heap(heap)

  def test_duplicate_integers(self):
    """Test pop with duplicate integers."""
    heap = [5, 3, 5, 1, 3, 1, 5]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1
    assert is_valid_heap(heap)

  def test_all_equal_integers(self):
    """Test pop with all equal integers."""
    heap = [5] * 10
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 5
    assert len(heap) == 9

# ============================================================================
# Float Tests
# ============================================================================

class TestFloatPop:
  """Test pop with float data."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_floats_min(self, n):
    """Test pop with random floats (min-heap)."""
    data = generate_floats(n)
    heap = data.copy()
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == min(data)
    assert is_valid_heap(heap)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_floats_max(self, n):
    """Test pop with random floats (max-heap)."""
    data = generate_floats(n)
    heap = data.copy()
    heapx.heapify(heap, max_heap=True)
    result = heapx.pop(heap, max_heap=True)
    assert result == max(data)
    assert is_valid_heap(heap, max_heap=True)

  def test_float_precision(self):
    """Test pop with high precision floats."""
    heap = [1.0000001, 1.0000002, 1.0, 1.0000003]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1.0
    assert is_valid_heap(heap)

  def test_float_special_values(self):
    """Test pop with special float values."""
    heap = [1.0, 0.0, -1.0, float('inf'), float('-inf')]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == float('-inf')
    assert is_valid_heap(heap)

# ============================================================================
# String Tests
# ============================================================================

class TestStringPop:
  """Test pop with string data."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_strings_min(self, n):
    """Test pop with random strings (min-heap)."""
    data = generate_strings(n)
    heap = data.copy()
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == min(data)
    assert is_valid_heap(heap)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_strings_max(self, n):
    """Test pop with random strings (max-heap)."""
    data = generate_strings(n)
    heap = data.copy()
    heapx.heapify(heap, max_heap=True)
    result = heapx.pop(heap, max_heap=True)
    assert result == max(data)
    assert is_valid_heap(heap, max_heap=True)

  def test_string_case_sensitivity(self):
    """Test pop with case-sensitive strings."""
    heap = ['Zebra', 'apple', 'Banana', 'cherry']
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == min(['Zebra', 'apple', 'Banana', 'cherry'])
    assert is_valid_heap(heap)

  def test_empty_strings(self):
    """Test pop with empty strings."""
    heap = ['', 'a', '', 'b', '']
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == ''
    assert is_valid_heap(heap)

# ============================================================================
# Tuple Tests
# ============================================================================

class TestTuplePop:
  """Test pop with tuple data."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_tuples_min(self, n):
    """Test pop with random tuples (min-heap)."""
    data = generate_tuples(n)
    heap = data.copy()
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == min(data)
    assert is_valid_heap(heap)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_random_tuples_max(self, n):
    """Test pop with random tuples (max-heap)."""
    data = generate_tuples(n)
    heap = data.copy()
    heapx.heapify(heap, max_heap=True)
    result = heapx.pop(heap, max_heap=True)
    assert result == max(data)
    assert is_valid_heap(heap, max_heap=True)

  def test_tuple_lexicographic(self):
    """Test pop with lexicographic tuple comparison."""
    heap = [(1, 'b'), (1, 'a'), (2, 'a'), (1, 'c')]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == (1, 'a')
    assert is_valid_heap(heap)


# ============================================================================
# N-ary Heap Tests (Arity Parameter)
# ============================================================================

class TestArityParameter:
  """Test pop with different arity values."""

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8, 16])
  @pytest.mark.parametrize("n", [20, 100])
  def test_various_arity_min(self, arity, n):
    """Test pop with various arity values (min-heap)."""
    data = generate_integers(n)
    heap = data.copy()
    heapx.heapify(heap, arity=arity)
    result = heapx.pop(heap, arity=arity)
    assert result == min(data)
    assert is_valid_heap(heap, max_heap=False, arity=arity)

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8, 16])
  @pytest.mark.parametrize("n", [20, 100])
  def test_various_arity_max(self, arity, n):
    """Test pop with various arity values (max-heap)."""
    data = generate_integers(n)
    heap = data.copy()
    heapx.heapify(heap, max_heap=True, arity=arity)
    result = heapx.pop(heap, max_heap=True, arity=arity)
    assert result == max(data)
    assert is_valid_heap(heap, max_heap=True, arity=arity)

  def test_unary_heap(self):
    """Test pop with arity=1 (sorted list)."""
    heap = [5, 3, 8, 1, 9]
    heapx.heapify(heap, arity=1)
    result = heapx.pop(heap, arity=1)
    assert result == 1
    assert heap == sorted([5, 3, 8, 9])

  def test_ternary_heap(self):
    """Test pop with arity=3."""
    heap = list(range(30, 0, -1))
    heapx.heapify(heap, arity=3)
    result = heapx.pop(heap, arity=3)
    assert result == 1
    assert is_valid_heap(heap, arity=3)

  def test_quaternary_heap(self):
    """Test pop with arity=4."""
    heap = list(range(20, 0, -1))
    heapx.heapify(heap, arity=4)
    result = heapx.pop(heap, arity=4)
    assert result == 1
    assert is_valid_heap(heap, arity=4)

  def test_small_heap_arity_2(self):
    """Test pop with small heap (n=10) and arity=2."""
    heap = list(range(10, 0, -1))
    heapx.heapify(heap, arity=2)
    result = heapx.pop(heap, arity=2)
    assert result == 1
    assert is_valid_heap(heap, arity=2)

  def test_small_heap_arity_3(self):
    """Test pop with small heap (n=10) and arity=3."""
    heap = list(range(10, 0, -1))
    heapx.heapify(heap, arity=3)
    result = heapx.pop(heap, arity=3)
    assert result == 1
    assert is_valid_heap(heap, arity=3)

  def test_small_heap_arity_4(self):
    """Test pop with small heap (n=10) and arity=4."""
    heap = list(range(10, 0, -1))
    heapx.heapify(heap, arity=4)
    result = heapx.pop(heap, arity=4)
    assert result == 1
    assert is_valid_heap(heap, arity=4)

# ============================================================================
# Custom Comparison Function Tests
# ============================================================================

class TestCustomComparison:
  """Test pop with custom comparison functions."""

  def test_absolute_value_comparison(self):
    """Test pop with absolute value comparison."""
    heap = [-5, 2, -8, 1, 9, -3]
    heapx.heapify(heap, cmp=abs)
    result = heapx.pop(heap, cmp=abs)
    assert abs(result) == 1

  def test_reverse_comparison(self):
    """Test pop with reverse comparison."""
    heap = [5, 2, 8, 1, 9]
    heapx.heapify(heap, cmp=lambda x: -x)
    result = heapx.pop(heap, cmp=lambda x: -x)
    assert result == 9

  def test_tuple_second_element(self):
    """Test pop comparing by tuple second element."""
    heap = [(1, 5), (2, 3), (3, 7), (4, 1)]
    heapx.heapify(heap, cmp=lambda x: x[1])
    result = heapx.pop(heap, cmp=lambda x: x[1])
    assert result[1] == 1

  def test_string_length_comparison(self):
    """Test pop comparing by string length."""
    heap = ['short', 'a', 'medium', 'verylongstring', 'mid']
    heapx.heapify(heap, cmp=len)
    result = heapx.pop(heap, cmp=len)
    assert len(result) == 1

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_custom_cmp_with_arity(self, n):
    """Test pop with custom comparison and various arities."""
    data = generate_integers(n)
    heap = data.copy()
    heapx.heapify(heap, cmp=abs, arity=3)
    result = heapx.pop(heap, cmp=abs, arity=3)
    assert abs(result) == min(abs(x) for x in data)

  def test_complex_key_function(self):
    """Test pop with complex key function."""
    heap = [{'val': 5}, {'val': 2}, {'val': 8}, {'val': 1}]
    heapx.heapify(heap, cmp=lambda x: x['val'])
    result = heapx.pop(heap, cmp=lambda x: x['val'])
    assert result['val'] == 1


# ============================================================================
# Bulk Pop Tests
# ============================================================================

class TestBulkPop:
  """Test bulk pop operations (n>1)."""

  def test_bulk_pop_n_equals_2(self):
    """Test popping 2 elements."""
    heap = [1, 3, 2, 7, 5, 4, 6]
    heapx.heapify(heap)
    results = heapx.pop(heap, n=2)
    assert results == [1, 2]
    assert is_valid_heap(heap)

  def test_bulk_pop_n_equals_5(self):
    """Test popping 5 elements."""
    heap = list(range(20, 0, -1))
    heapx.heapify(heap)
    results = heapx.pop(heap, n=5)
    assert results == [1, 2, 3, 4, 5]
    assert is_valid_heap(heap)

  def test_bulk_pop_all_elements(self):
    """Test popping all elements."""
    heap = [5, 2, 8, 1, 9]
    heapx.heapify(heap)
    results = heapx.pop(heap, n=5)
    assert results == sorted([5, 2, 8, 1, 9])
    assert len(heap) == 0

  def test_bulk_pop_more_than_size(self):
    """Test popping more elements than heap size."""
    heap = [5, 2, 8]
    heapx.heapify(heap)
    results = heapx.pop(heap, n=10)
    assert results == sorted([5, 2, 8])
    assert len(heap) == 0

  def test_bulk_pop_max_heap(self):
    """Test bulk pop from max-heap."""
    heap = [1, 2, 3, 4, 5]
    heapx.heapify(heap, max_heap=True)
    results = heapx.pop(heap, n=3, max_heap=True)
    assert results == [5, 4, 3]
    assert is_valid_heap(heap, max_heap=True)

  def test_bulk_pop_with_arity(self):
    """Test bulk pop with custom arity."""
    heap = list(range(50, 0, -1))
    heapx.heapify(heap, arity=3)
    results = heapx.pop(heap, n=10, arity=3)
    assert results == list(range(1, 11))
    assert is_valid_heap(heap, arity=3)

  def test_bulk_pop_with_key(self):
    """Test bulk pop with key function."""
    heap = [-5, 2, -8, 1, 9, -3, 7, -4, 6, -2]
    heapx.heapify(heap, cmp=abs)
    results = heapx.pop(heap, n=3, cmp=abs)
    assert [abs(x) for x in results] == [1, 2, 2]

  def test_bulk_pop_maintains_heap(self):
    """Test that bulk pop maintains heap property."""
    heap = list(range(100, 0, -1))
    heapx.heapify(heap)
    heapx.pop(heap, n=20)
    assert is_valid_heap(heap)

# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
  """Test edge cases and error conditions."""

  def test_pop_from_size_16_heap(self):
    """Test pop from heap of size 16 (boundary for small heap optimization)."""
    heap = list(range(16, 0, -1))
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1
    assert is_valid_heap(heap)

  def test_pop_from_size_17_heap(self):
    """Test pop from heap of size 17."""
    heap = list(range(17, 0, -1))
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1
    assert is_valid_heap(heap)

  def test_pop_from_size_15_heap(self):
    """Test pop from heap of size 15."""
    heap = list(range(15, 0, -1))
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1
    assert is_valid_heap(heap)

  def test_pop_large_range_integers(self):
    """Test pop with very large integers."""
    heap = [10**15, -10**15, 10**14, -10**14, 0]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == -10**15
    assert is_valid_heap(heap)

  def test_invalid_n_parameter(self):
    """Test pop with invalid n parameter."""
    heap = [1, 2, 3]
    with pytest.raises(ValueError):
      heapx.pop(heap, n=0)

  def test_invalid_arity_parameter(self):
    """Test pop with invalid arity parameter."""
    heap = [1, 2, 3]
    with pytest.raises(ValueError):
      heapx.pop(heap, arity=0)

  def test_invalid_cmp_parameter(self):
    """Test pop with invalid cmp parameter."""
    heap = [1, 2, 3]
    with pytest.raises(TypeError):
      heapx.pop(heap, cmp="not_callable")

  def test_pop_after_multiple_operations(self):
    """Test pop after multiple push/pop operations."""
    heap = []
    for i in range(20):
      heapx.push(heap, i)
    for _ in range(5):
      heapx.pop(heap)
    result = heapx.pop(heap)
    assert result == 5
    assert is_valid_heap(heap)

  def test_pop_with_duplicates(self):
    """Test pop with many duplicate elements."""
    heap = [5] * 10 + [3] * 10 + [7] * 10
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 3
    assert is_valid_heap(heap)

  def test_pop_alternating_values(self):
    """Test pop with alternating values."""
    heap = [1, 2] * 50
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1
    assert is_valid_heap(heap)


# ============================================================================
# Correctness Verification Tests
# ============================================================================

class TestCorrectnessVerification:
  """Verify correctness by extracting all elements."""

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_extract_all_min_heap(self, n):
    """Test extracting all elements from min-heap gives sorted order."""
    data = generate_integers(n)
    heap = data.copy()
    heapx.heapify(heap)
    
    result = []
    while heap:
      result.append(heapx.pop(heap))
    
    assert result == sorted(data)

  @pytest.mark.parametrize("n", [10, 100, 1000])
  def test_extract_all_max_heap(self, n):
    """Test extracting all elements from max-heap gives reverse sorted order."""
    data = generate_integers(n)
    heap = data.copy()
    heapx.heapify(heap, max_heap=True)
    
    result = []
    while heap:
      result.append(heapx.pop(heap, max_heap=True))
    
    assert result == sorted(data, reverse=True)

  @pytest.mark.parametrize("arity", [2, 3, 4, 5])
  def test_extract_all_various_arity(self, arity):
    """Test extracting all elements with various arities."""
    data = generate_integers(100)
    heap = data.copy()
    heapx.heapify(heap, arity=arity)
    
    result = []
    while heap:
      result.append(heapx.pop(heap, arity=arity))
    
    assert result == sorted(data)

  def test_extract_all_with_key(self):
    """Test extracting all elements with key function."""
    data = generate_integers(100)
    heap = data.copy()
    heapx.heapify(heap, cmp=abs)
    
    result = []
    while heap:
      result.append(heapx.pop(heap, cmp=abs))
    
    assert [abs(x) for x in result] == sorted([abs(x) for x in data])

  def test_interleaved_push_pop(self):
    """Test interleaved push and pop operations."""
    heap = []
    heapx.push(heap, 5)
    heapx.push(heap, 3)
    assert heapx.pop(heap) == 3
    heapx.push(heap, 1)
    heapx.push(heap, 7)
    assert heapx.pop(heap) == 1
    assert is_valid_heap(heap)

  def test_pop_maintains_invariant(self):
    """Test that pop always maintains heap invariant."""
    heap = generate_integers(100)
    heapx.heapify(heap)
    
    for _ in range(50):
      heapx.pop(heap)
      assert is_valid_heap(heap)

  def test_bulk_pop_correctness(self):
    """Test bulk pop returns elements in correct order."""
    heap = list(range(100, 0, -1))
    heapx.heapify(heap)
    results = heapx.pop(heap, n=50)
    assert results == list(range(1, 51))

# ============================================================================
# Stress Tests
# ============================================================================

class TestStressTests:
  """Stress tests with large datasets."""

  def test_very_large_heap(self):
    """Test pop with very large heap."""
    heap = generate_integers(10000)
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert is_valid_heap(heap)
    assert len(heap) == 9999

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_repeated_pop(self, n):
    """Test repeated pop operations."""
    heap = generate_integers(n)
    heapx.heapify(heap)
    
    for _ in range(min(n, 100)):
      heapx.pop(heap)
      assert is_valid_heap(heap)

  def test_all_combinations(self):
    """Test various combinations of parameters."""
    test_cases = [
      (False, None, 2),
      (True, None, 2),
      (False, None, 3),
      (True, None, 3),
      (False, None, 5),
      (True, None, 5),
    ]
    
    for max_heap, cmp, arity in test_cases:
      heap = generate_integers(50)
      heapx.heapify(heap, max_heap=max_heap, cmp=cmp, arity=arity)
      heapx.pop(heap, max_heap=max_heap, cmp=cmp, arity=arity)
      assert is_valid_heap(heap, max_heap=max_heap, arity=arity)
    
    # Test with key function separately (can't use is_valid_heap directly)
    heap = generate_integers(50)
    heapx.heapify(heap, cmp=abs, arity=2)
    heapx.pop(heap, cmp=abs, arity=2)
    # Verify heap property on transformed values
    for i in range(len(heap)):
      for j in range(1, 3):
        child = 2 * i + j
        if child < len(heap):
          assert abs(heap[i]) <= abs(heap[child])

  def test_random_operations(self):
    """Test random sequence of operations."""
    random.seed(42)
    heap = []
    
    for _ in range(1000):
      if random.random() < 0.7 or len(heap) == 0:
        heapx.push(heap, random.randint(1, 1000))
      else:
        heapx.pop(heap)
      
      if heap:
        assert is_valid_heap(heap)


# ============================================================================
# Boolean Tests
# ============================================================================

class TestBooleanPop:
  """Test pop with boolean data."""

  def test_pop_booleans(self):
    """Test popping from boolean heap."""
    heap = generate_booleans(50)
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert isinstance(result, bool)
    assert is_valid_heap(heap)

  def test_bulk_pop_booleans(self):
    """Test bulk pop from boolean heap."""
    heap = generate_booleans(50)
    heapx.heapify(heap)
    results = heapx.pop(heap, n=10)
    assert len(results) == 10
    assert is_valid_heap(heap)

# ============================================================================
# Bytes Tests
# ============================================================================

class TestBytesPop:
  """Test pop with bytes data."""

  def test_pop_bytes(self):
    """Test popping from bytes heap."""
    heap = generate_bytes(30)
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert isinstance(result, bytes)
    assert is_valid_heap(heap)

  def test_bulk_pop_bytes(self):
    """Test bulk pop from bytes heap."""
    heap = generate_bytes(30)
    heapx.heapify(heap)
    results = heapx.pop(heap, n=10)
    assert len(results) == 10
    assert is_valid_heap(heap)

# ============================================================================
# Bytearray Tests
# ============================================================================

class TestBytearrayPop:
  """Test pop with bytearray data."""

  def test_pop_bytearrays(self):
    """Test popping from bytearray heap."""
    heap = generate_bytearrays(30)
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert isinstance(result, bytearray)
    assert is_valid_heap(heap)

  def test_bulk_pop_bytearrays(self):
    """Test bulk pop from bytearray heap."""
    heap = generate_bytearrays(30)
    heapx.heapify(heap)
    results = heapx.pop(heap, n=10)
    assert len(results) == 10
    assert is_valid_heap(heap)

# ============================================================================
# List Tests
# ============================================================================

class TestListPop:
  """Test pop with list data."""

  def test_pop_lists(self):
    """Test popping from list heap."""
    heap = generate_lists(30)
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert isinstance(result, list)
    assert is_valid_heap(heap)

  def test_bulk_pop_lists(self):
    """Test bulk pop from list heap."""
    heap = generate_lists(30)
    heapx.heapify(heap)
    results = heapx.pop(heap, n=10)
    assert len(results) == 10
    assert is_valid_heap(heap)

# ============================================================================
# Mixed Type Tests
# ============================================================================

class TestMixedPop:
  """Test pop with mixed comparable types."""

  def test_pop_mixed(self):
    """Test popping from mixed int/float heap."""
    heap = generate_mixed(100)
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert isinstance(result, (int, float))
    assert is_valid_heap(heap)

  def test_bulk_pop_mixed(self):
    """Test bulk pop from mixed heap."""
    heap = generate_mixed(100)
    heapx.heapify(heap)
    results = heapx.pop(heap, n=20)
    assert len(results) == 20
    assert is_valid_heap(heap)

  def test_pop_mixed_max_heap(self):
    """Test popping from mixed max-heap."""
    heap = generate_mixed(100)
    heapx.heapify(heap, max_heap=True)
    result = heapx.pop(heap, max_heap=True)
    assert isinstance(result, (int, float))
    assert is_valid_heap(heap, max_heap=True)

# ============================================================================
# Performance Benchmark Tests
# ============================================================================

class TestPerformanceBenchmark:
  """Performance benchmarks comparing heapx vs heapq."""

  @pytest.mark.benchmark
  def test_performance_comparison(self, capsys):
    """Comprehensive performance comparison: heapx.pop vs heapq.heappop."""
    
    output = []
    output.append("\n" + "="*80)
    output.append("TIME EFFICIENCY COMPARISON: heapx.pop vs heapq.heappop")
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
        # Prepare heaps
        data = generate_integers(n, seed=r)
        
        heap_heapx = data.copy()
        heapx.heapify(heap_heapx)
        
        heap_heapq = data.copy()
        heapq.heapify(heap_heapq)
        
        # Measure heapx time (pop 1000 elements)
        start = time.perf_counter()
        for _ in range(min(1000, n)):
          heapx.pop(heap_heapx)
        heapx_times.append(time.perf_counter() - start)
        
        # Measure heapq time (pop 1000 elements)
        start = time.perf_counter()
        for _ in range(min(1000, n)):
          heapq.heappop(heap_heapq)
        heapq_times.append(time.perf_counter() - start)
      
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
      
      heap_heapx = data.copy()
      heapx.heapify(heap_heapx)
      heapx_mem = sys.getsizeof(heap_heapx)
      
      heap_heapq = data.copy()
      heapq.heapify(heap_heapq)
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
    output.append("\nMEMORY EFFICIENCY COMPARISON: heapx.pop vs heapq.heappop")
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
    heap = data.copy()
    heapx.heapify(heap, arity=arity)
    
    start = time.perf_counter()
    for _ in range(1000):
      heapx.pop(heap, arity=arity)
    elapsed = time.perf_counter() - start
    
    print(f"\nArity {arity}: {elapsed:.4f}s for 1000 pops from {n:,} element heap")

  @pytest.mark.benchmark
  def test_key_function_performance(self):
    """Test performance with key function."""
    n = 1_000_000
    data = generate_integers(n)
    heap = data.copy()
    heapx.heapify(heap, cmp=abs)
    
    start = time.perf_counter()
    for _ in range(1000):
      heapx.pop(heap, cmp=abs)
    elapsed = time.perf_counter() - start
    
    print(f"\nKey function (abs): {elapsed:.4f}s for 1000 pops from {n:,} element heap")

  @pytest.mark.benchmark
  def test_bulk_pop_performance(self):
    """Test bulk pop performance."""
    n = 100_000
    repetitions = 10
    
    times = []
    for _ in range(repetitions):
      data = generate_integers(n)
      heap = data.copy()
      heapx.heapify(heap)
      
      start = time.perf_counter()
      heapx.pop(heap, n=1000)
      times.append(time.perf_counter() - start)
    
    avg = mean(times)
    std = stdev(times) if len(times) > 1 else 0
    
    print(f"\nBulk pop (n=1000): {avg:.4f} ± {std:.4f}s from {n:,} element heap")

  @pytest.mark.benchmark
  def test_small_heap_performance(self):
    """Test performance with small heaps (n≤16)."""
    repetitions = 10000
    
    times = []
    for _ in range(repetitions):
      heap = list(range(16, 0, -1))
      heapx.heapify(heap)
      
      start = time.perf_counter()
      heapx.pop(heap)
      times.append(time.perf_counter() - start)
    
    avg = mean(times)
    std = stdev(times) if len(times) > 1 else 0
    
    print(f"\nSmall heap (n=16): {avg*1000000:.2f} ± {std*1000000:.2f} microseconds per pop")

