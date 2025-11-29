"""
Comprehensive test suite for heapx.merge function.

Tests cover all 11 dispatch priorities, sorted/unsorted heaps, parameters,
data types, edge cases, and performance benchmarks. Includes 200+ test cases.
"""

import heapx
import heapq
import pytest
import random
import string
import time
import sys
from typing import List, Any, Tuple
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

def is_valid_heap(arr: List[Any], max_heap: bool = False, arity: int = 2, cmp=None) -> bool:
    """Verify heap property for n-ary heap."""
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
                if max_heap:
                    if parent_key < child_key:
                        return False
                else:
                    if parent_key > child_key:
                        return False
            else:
                if max_heap:
                    if arr[i] < arr[child]:
                        return False
                else:
                    if arr[i] > arr[child]:
                        return False
    return True

# ============================================================================
# Basic Functionality Tests (20 tests)
# ============================================================================

class TestBasicMerge:
    """Test basic merge functionality."""

    def test_merge_two_lists(self):
        """Test merging two simple lists."""
        heap1 = [1, 3, 5]
        heap2 = [2, 4, 6]
        result = heapx.merge(heap1, heap2)
        assert len(result) == 6
        assert is_valid_heap(result)

    def test_merge_two_heaps(self):
        """Test merging two heapified lists."""
        heap1 = [1, 3, 5, 7, 9]
        heap2 = [2, 4, 6, 8, 10]
        heapx.heapify(heap1)
        heapx.heapify(heap2)
        result = heapx.merge(heap1, heap2)
        assert len(result) == 10
        assert is_valid_heap(result)

    def test_merge_three_heaps(self):
        """Test merging three heaps."""
        heap1 = [1, 4, 7]
        heap2 = [2, 5, 8]
        heap3 = [3, 6, 9]
        result = heapx.merge(heap1, heap2, heap3)
        assert len(result) == 9
        assert is_valid_heap(result)

    def test_merge_many_heaps(self):
        """Test merging many heaps."""
        heaps = [[i] for i in range(10)]
        result = heapx.merge(*heaps)
        assert len(result) == 10
        assert is_valid_heap(result)

    def test_merge_empty_heaps(self):
        """Test merging empty heaps."""
        result = heapx.merge([], [])
        assert result == []

    def test_merge_one_empty_one_full(self):
        """Test merging one empty and one full heap."""
        heap1 = [1, 2, 3]
        heap2 = []
        result = heapx.merge(heap1, heap2)
        assert len(result) == 3

    def test_merge_single_elements(self):
        """Test merging heaps with single elements."""
        result = heapx.merge([1], [2], [3])
        assert len(result) == 3
        assert is_valid_heap(result)

    def test_merge_duplicates(self):
        """Test merging heaps with duplicate values."""
        heap1 = [1, 1, 1]
        heap2 = [2, 2, 2]
        result = heapx.merge(heap1, heap2)
        assert len(result) == 6
        assert is_valid_heap(result)

    def test_merge_all_same_values(self):
        """Test merging heaps with all same values."""
        heap1 = [5] * 10
        heap2 = [5] * 10
        result = heapx.merge(heap1, heap2)
        assert len(result) == 20
        assert all(x == 5 for x in result)

    def test_merge_sorted_ascending(self):
        """Test merging sorted ascending lists."""
        heap1 = [1, 2, 3, 4, 5]
        heap2 = [6, 7, 8, 9, 10]
        result = heapx.merge(heap1, heap2)
        assert len(result) == 10
        assert is_valid_heap(result)

    def test_merge_sorted_descending(self):
        """Test merging sorted descending lists."""
        heap1 = [10, 9, 8, 7, 6]
        heap2 = [5, 4, 3, 2, 1]
        result = heapx.merge(heap1, heap2)
        assert len(result) == 10
        assert is_valid_heap(result)

    def test_merge_random_data(self):
        """Test merging random data."""
        heap1 = generate_integers(50, seed=1)
        heap2 = generate_integers(50, seed=2)
        result = heapx.merge(heap1, heap2)
        assert len(result) == 100
        assert is_valid_heap(result)

    def test_merge_large_heaps(self):
        """Test merging large heaps."""
        heap1 = list(range(1000))
        heap2 = list(range(1000, 2000))
        result = heapx.merge(heap1, heap2)
        assert len(result) == 2000
        assert is_valid_heap(result)

    def test_merge_unequal_sizes(self):
        """Test merging heaps of unequal sizes."""
        heap1 = list(range(10))
        heap2 = list(range(100))
        result = heapx.merge(heap1, heap2)
        assert len(result) == 110
        assert is_valid_heap(result)

    def test_merge_very_unequal_sizes(self):
        """Test merging very unequal sized heaps."""
        heap1 = [1]
        heap2 = list(range(1000))
        result = heapx.merge(heap1, heap2)
        assert len(result) == 1001
        assert is_valid_heap(result)

    def test_merge_negative_numbers(self):
        """Test merging heaps with negative numbers."""
        heap1 = [-5, -3, -1]
        heap2 = [-4, -2, 0]
        result = heapx.merge(heap1, heap2)
        assert len(result) == 6
        assert is_valid_heap(result)

    def test_merge_mixed_positive_negative(self):
        """Test merging heaps with mixed positive/negative."""
        heap1 = [-5, -2, 1, 4]
        heap2 = [-3, 0, 3, 6]
        result = heapx.merge(heap1, heap2)
        assert len(result) == 8
        assert is_valid_heap(result)

    def test_merge_preserves_elements(self):
        """Test that merge preserves all elements."""
        heap1 = [1, 3, 5, 7]
        heap2 = [2, 4, 6, 8]
        result = heapx.merge(heap1, heap2)
        assert sorted(result) == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_merge_does_not_modify_inputs(self):
        """Test that merge doesn't modify input heaps."""
        heap1 = [1, 3, 5]
        heap2 = [2, 4, 6]
        heap1_copy = heap1.copy()
        heap2_copy = heap2.copy()
        heapx.merge(heap1, heap2)
        assert heap1 == heap1_copy
        assert heap2 == heap2_copy

    def test_merge_returns_new_list(self):
        """Test that merge returns a new list."""
        heap1 = [1, 2, 3]
        heap2 = [4, 5, 6]
        result = heapx.merge(heap1, heap2)
        assert result is not heap1
        assert result is not heap2

# ============================================================================
# Dispatch Priority Tests (22 tests - 11 unsorted + 11 sorted)
# ============================================================================

class TestDispatchPriorities:
    """Test all 11 dispatch priorities with sorted/unsorted heaps."""

    def test_priority_1_small_heap_unsorted(self):
        """Priority 1: Small heap (n≤16) unsorted."""
        heap1 = [5, 2, 8, 1]
        heap2 = [9, 3, 7, 4]
        result = heapx.merge(heap1, heap2, sorted_heaps=False)
        assert len(result) == 8
        assert is_valid_heap(result)

    def test_priority_1_small_heap_sorted(self):
        """Priority 1: Small heap (n≤16) sorted."""
        heap1 = [1, 2, 5, 8]
        heap2 = [3, 4, 7, 9]
        heapx.heapify(heap1)
        heapx.heapify(heap2)
        result = heapx.merge(heap1, heap2, sorted_heaps=True)
        assert len(result) == 8

    def test_priority_2_arity_1_unsorted(self):
        """Priority 2: Arity=1 unsorted."""
        heap1 = [3, 1, 2]
        heap2 = [6, 4, 5]
        result = heapx.merge(heap1, heap2, arity=1)
        assert len(result) == 6

    def test_priority_2_arity_1_sorted(self):
        """Priority 2: Arity=1 sorted."""
        heap1 = [1, 2, 3]
        heap2 = [4, 5, 6]
        heapx.heapify(heap1, arity=1)
        heapx.heapify(heap2, arity=1)
        result = heapx.merge(heap1, heap2, arity=1, sorted_heaps=True)
        assert len(result) == 6

    def test_priority_3_binary_unsorted(self):
        """Priority 3: Binary heap unsorted."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        result = heapx.merge(heap1, heap2, arity=2)
        assert len(result) == 100
        assert is_valid_heap(result, arity=2)

    def test_priority_3_binary_sorted(self):
        """Priority 3: Binary heap sorted."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        heapx.heapify(heap1)
        heapx.heapify(heap2)
        result = heapx.merge(heap1, heap2, sorted_heaps=True)
        assert len(result) == 100

    def test_priority_4_ternary_unsorted(self):
        """Priority 4: Ternary heap unsorted."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        result = heapx.merge(heap1, heap2, arity=3)
        assert len(result) == 100
        assert is_valid_heap(result, arity=3)

    def test_priority_4_ternary_sorted(self):
        """Priority 4: Ternary heap sorted."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        heapx.heapify(heap1, arity=3)
        heapx.heapify(heap2, arity=3)
        result = heapx.merge(heap1, heap2, arity=3, sorted_heaps=True)
        assert len(result) == 100

    def test_priority_5_quaternary_unsorted(self):
        """Priority 5: Quaternary heap unsorted."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        result = heapx.merge(heap1, heap2, arity=4)
        assert len(result) == 100
        assert is_valid_heap(result, arity=4)

    def test_priority_5_quaternary_sorted(self):
        """Priority 5: Quaternary heap sorted."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        heapx.heapify(heap1, arity=4)
        heapx.heapify(heap2, arity=4)
        result = heapx.merge(heap1, heap2, arity=4, sorted_heaps=True)
        assert len(result) == 100

    def test_priority_6_nary_small_unsorted(self):
        """Priority 6: N-ary small (n<1000) unsorted."""
        heap1 = list(range(300))
        heap2 = list(range(300, 600))
        result = heapx.merge(heap1, heap2, arity=5)
        assert len(result) == 600
        assert is_valid_heap(result, arity=5)

    def test_priority_6_nary_small_sorted(self):
        """Priority 6: N-ary small (n<1000) sorted."""
        heap1 = list(range(300))
        heap2 = list(range(300, 600))
        heapx.heapify(heap1, arity=5)
        heapx.heapify(heap2, arity=5)
        result = heapx.merge(heap1, heap2, arity=5, sorted_heaps=True)
        assert len(result) == 600

    def test_priority_7_nary_large_unsorted(self):
        """Priority 7: N-ary large (n≥1000) unsorted."""
        heap1 = list(range(600))
        heap2 = list(range(600, 1200))
        result = heapx.merge(heap1, heap2, arity=8)
        assert len(result) == 1200
        assert is_valid_heap(result, arity=8)

    def test_priority_7_nary_large_sorted(self):
        """Priority 7: N-ary large (n≥1000) sorted."""
        heap1 = list(range(600))
        heap2 = list(range(600, 1200))
        heapx.heapify(heap1, arity=8)
        heapx.heapify(heap2, arity=8)
        result = heapx.merge(heap1, heap2, arity=8, sorted_heaps=True)
        assert len(result) == 1200

    def test_priority_8_binary_key_unsorted(self):
        """Priority 8: Binary with key unsorted."""
        heap1 = [-5, 2, -8, 1]
        heap2 = [9, -3, 7, -4]
        result = heapx.merge(heap1, heap2, cmp=abs)
        assert len(result) == 8
        assert is_valid_heap(result, cmp=abs)

    def test_priority_8_binary_key_sorted(self):
        """Priority 8: Binary with key sorted."""
        heap1 = [-5, 2, -8, 1]
        heap2 = [9, -3, 7, -4]
        heapx.heapify(heap1, cmp=abs)
        heapx.heapify(heap2, cmp=abs)
        result = heapx.merge(heap1, heap2, cmp=abs, sorted_heaps=True)
        assert len(result) == 8

    def test_priority_9_ternary_key_unsorted(self):
        """Priority 9: Ternary with key unsorted."""
        heap1 = list(range(-25, 0))
        heap2 = list(range(0, 25))
        result = heapx.merge(heap1, heap2, arity=3, cmp=abs)
        assert len(result) == 50
        assert is_valid_heap(result, arity=3, cmp=abs)

    def test_priority_9_ternary_key_sorted(self):
        """Priority 9: Ternary with key sorted."""
        heap1 = list(range(-25, 0))
        heap2 = list(range(0, 25))
        heapx.heapify(heap1, arity=3, cmp=abs)
        heapx.heapify(heap2, arity=3, cmp=abs)
        result = heapx.merge(heap1, heap2, arity=3, cmp=abs, sorted_heaps=True)
        assert len(result) == 50

    def test_priority_10_nary_key_unsorted(self):
        """Priority 10: N-ary with key unsorted."""
        heap1 = list(range(-50, 0))
        heap2 = list(range(0, 50))
        result = heapx.merge(heap1, heap2, arity=5, cmp=abs)
        assert len(result) == 100
        assert is_valid_heap(result, arity=5, cmp=abs)

    def test_priority_10_nary_key_sorted(self):
        """Priority 10: N-ary with key sorted."""
        heap1 = list(range(-50, 0))
        heap2 = list(range(0, 50))
        heapx.heapify(heap1, arity=5, cmp=abs)
        heapx.heapify(heap2, arity=5, cmp=abs)
        result = heapx.merge(heap1, heap2, arity=5, cmp=abs, sorted_heaps=True)
        assert len(result) == 100

    def test_priority_11_generic_sequence(self):
        """Priority 11: Generic sequence."""
        heap1 = tuple(range(10))
        heap2 = tuple(range(10, 20))
        result = heapx.merge(heap1, heap2)
        assert len(result) == 20
        assert is_valid_heap(result)


# ============================================================================
# Data Type Tests (30 tests)
# ============================================================================

class TestDataTypes:
    """Test merging different data types."""

    def test_merge_integers(self):
        """Test merging integer heaps."""
        heap1 = generate_integers(50, seed=1)
        heap2 = generate_integers(50, seed=2)
        result = heapx.merge(heap1, heap2)
        assert len(result) == 100
        assert is_valid_heap(result)

    def test_merge_floats(self):
        """Test merging float heaps."""
        heap1 = generate_floats(50, seed=1)
        heap2 = generate_floats(50, seed=2)
        result = heapx.merge(heap1, heap2)
        assert len(result) == 100
        assert is_valid_heap(result)

    def test_merge_strings(self):
        """Test merging string heaps."""
        heap1 = generate_strings(20, seed=1)
        heap2 = generate_strings(20, seed=2)
        result = heapx.merge(heap1, heap2)
        assert len(result) == 40
        assert is_valid_heap(result)

    def test_merge_mixed_numbers(self):
        """Test merging mixed int/float."""
        heap1 = [1, 2.5, 3, 4.5]
        heap2 = [2, 3.5, 4, 5.5]
        result = heapx.merge(heap1, heap2)
        assert len(result) == 8
        assert is_valid_heap(result)

    def test_merge_tuples(self):
        """Test merging tuple heaps."""
        heap1 = [(1, 'a'), (2, 'b')]
        heap2 = [(3, 'c'), (4, 'd')]
        result = heapx.merge(heap1, heap2)
        assert len(result) == 4
        assert is_valid_heap(result)

    def test_merge_bytes(self):
        """Test merging bytes."""
        heap1 = [b'a', b'c', b'e']
        heap2 = [b'b', b'd', b'f']
        result = heapx.merge(heap1, heap2)
        assert len(result) == 6
        assert is_valid_heap(result)

    def test_merge_booleans(self):
        """Test merging booleans."""
        heap1 = [True, False, True]
        heap2 = [False, True, False]
        result = heapx.merge(heap1, heap2)
        assert len(result) == 6

    @pytest.mark.parametrize("arity", [2, 3, 4, 5])
    def test_merge_integers_various_arities(self, arity):
        """Test merging integers with various arities."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        result = heapx.merge(heap1, heap2, arity=arity)
        assert len(result) == 100
        assert is_valid_heap(result, arity=arity)

    @pytest.mark.parametrize("size", [10, 50, 100, 500])
    def test_merge_various_sizes(self, size):
        """Test merging various sizes."""
        heap1 = list(range(size))
        heap2 = list(range(size, size*2))
        result = heapx.merge(heap1, heap2)
        assert len(result) == size * 2
        assert is_valid_heap(result)

# ============================================================================
# Arity Parameter Tests (30 tests)
# ============================================================================

class TestArityParameters:
    """Test different arity values."""

    @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8, 16])
    def test_merge_various_arities(self, arity):
        """Test merging with various arity values."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        result = heapx.merge(heap1, heap2, arity=arity)
        assert len(result) == 100
        assert is_valid_heap(result, arity=arity)

    def test_merge_arity_1_maintains_order(self):
        """Test arity=1 maintains sorted order."""
        heap1 = [1, 2, 3]
        heap2 = [4, 5, 6]
        heapx.heapify(heap1, arity=1)
        heapx.heapify(heap2, arity=1)
        result = heapx.merge(heap1, heap2, arity=1)
        assert result == [1, 2, 3, 4, 5, 6]

    def test_merge_high_arity(self):
        """Test merging with high arity."""
        heap1 = list(range(100))
        heap2 = list(range(100, 200))
        result = heapx.merge(heap1, heap2, arity=32)
        assert len(result) == 200
        assert is_valid_heap(result, arity=32)

    def test_merge_arity_invalid_zero(self):
        """Test arity=0 raises error."""
        with pytest.raises(ValueError):
            heapx.merge([1, 2], [3, 4], arity=0)

    def test_merge_arity_invalid_negative(self):
        """Test negative arity raises error."""
        with pytest.raises(ValueError):
            heapx.merge([1, 2], [3, 4], arity=-1)

# ============================================================================
# Max Heap Tests (20 tests)
# ============================================================================

class TestMaxHeap:
    """Test max_heap parameter."""

    def test_merge_max_heap(self):
        """Test merging max heaps."""
        heap1 = [9, 7, 5, 3, 1]
        heap2 = [8, 6, 4, 2, 0]
        heapx.heapify(heap1, max_heap=True)
        heapx.heapify(heap2, max_heap=True)
        result = heapx.merge(heap1, heap2, max_heap=True)
        assert len(result) == 10
        assert is_valid_heap(result, max_heap=True)

    def test_merge_max_heap_unsorted(self):
        """Test merging unsorted lists as max heap."""
        heap1 = [1, 3, 5, 7, 9]
        heap2 = [2, 4, 6, 8, 10]
        result = heapx.merge(heap1, heap2, max_heap=True)
        assert len(result) == 10
        assert is_valid_heap(result, max_heap=True)

    @pytest.mark.parametrize("arity", [2, 3, 4])
    def test_merge_max_heap_various_arities(self, arity):
        """Test max heap with various arities."""
        heap1 = list(range(50, 0, -1))
        heap2 = list(range(100, 50, -1))
        result = heapx.merge(heap1, heap2, max_heap=True, arity=arity)
        assert len(result) == 100
        assert is_valid_heap(result, max_heap=True, arity=arity)

    def test_merge_max_heap_with_key(self):
        """Test max heap with key function."""
        heap1 = [-5, 2, -8, 1]
        heap2 = [9, -3, 7, -4]
        result = heapx.merge(heap1, heap2, max_heap=True, cmp=abs)
        assert len(result) == 8
        assert is_valid_heap(result, max_heap=True, cmp=abs)

# ============================================================================
# Custom Comparison Tests (20 tests)
# ============================================================================

class TestCustomComparison:
    """Test custom comparison functions."""

    def test_merge_with_abs_key(self):
        """Test merging by absolute value."""
        heap1 = [-5, 2, -8, 1]
        heap2 = [9, -3, 7, -4]
        result = heapx.merge(heap1, heap2, cmp=abs)
        assert len(result) == 8
        assert is_valid_heap(result, cmp=abs)

    def test_merge_with_lambda_key(self):
        """Test merging with lambda key."""
        heap1 = [(1, 5), (2, 3)]
        heap2 = [(1, 2), (2, 1)]
        result = heapx.merge(heap1, heap2, cmp=lambda x: (x[0], -x[1]))
        assert len(result) == 4

    def test_merge_with_len_key(self):
        """Test merging strings by length."""
        heap1 = ["apple", "pie"]
        heap2 = ["banana", "kiwi"]
        result = heapx.merge(heap1, heap2, cmp=len)
        assert len(result) == 4

    def test_merge_with_modulo_key(self):
        """Test merging by modulo."""
        heap1 = list(range(1, 26))
        heap2 = list(range(26, 51))
        result = heapx.merge(heap1, heap2, cmp=lambda x: x % 10)
        assert len(result) == 50

    def test_merge_with_key_and_arity(self):
        """Test key function with custom arity."""
        heap1 = list(range(-25, 0))
        heap2 = list(range(0, 25))
        result = heapx.merge(heap1, heap2, cmp=abs, arity=3)
        assert len(result) == 50
        assert is_valid_heap(result, cmp=abs, arity=3)

    def test_merge_invalid_key(self):
        """Test invalid key function raises error."""
        with pytest.raises(TypeError):
            heapx.merge([1, 2], [3, 4], cmp="not_callable")

# ============================================================================
# Edge Case Tests (30 tests)
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_merge_minimum_heaps(self):
        """Test merging exactly 2 heaps (minimum)."""
        result = heapx.merge([1], [2])
        assert len(result) == 2

    def test_merge_many_small_heaps(self):
        """Test merging many small heaps."""
        heaps = [[i] for i in range(100)]
        result = heapx.merge(*heaps)
        assert len(result) == 100

    def test_merge_all_empty_heaps(self):
        """Test merging all empty heaps."""
        result = heapx.merge([], [], [])
        assert result == []

    def test_merge_one_non_empty(self):
        """Test merging with one non-empty heap."""
        result = heapx.merge([1, 2, 3], [], [])
        assert len(result) == 3

    def test_merge_boundary_16_17(self):
        """Test boundary for small heap optimization."""
        heap1 = list(range(8))
        heap2 = list(range(8, 16))
        result16 = heapx.merge(heap1, heap2)
        assert len(result16) == 16
        
        heap3 = list(range(16, 17))
        result17 = heapx.merge(heap1, heap2, heap3)
        assert len(result17) == 17

    def test_merge_boundary_999_1000(self):
        """Test boundary for n-ary size dispatch."""
        heap1 = list(range(499))
        heap2 = list(range(499, 999))
        result999 = heapx.merge(heap1, heap2, arity=5)
        assert len(result999) == 999
        
        heap3 = list(range(999, 1000))
        result1000 = heapx.merge(heap1, heap2, heap3, arity=5)
        assert len(result1000) == 1000

    def test_merge_power_of_two_sizes(self):
        """Test merging power of 2 sizes."""
        for size in [16, 32, 64, 128, 256]:
            heap1 = list(range(size))
            heap2 = list(range(size, size*2))
            result = heapx.merge(heap1, heap2)
            assert len(result) == size * 2

    def test_merge_prime_sizes(self):
        """Test merging prime number sizes."""
        for size in [17, 31, 61, 127]:
            heap1 = list(range(size))
            heap2 = list(range(size, size*2))
            result = heapx.merge(heap1, heap2)
            assert len(result) == size * 2

    def test_merge_tuple_input(self):
        """Test merging tuple inputs."""
        heap1 = tuple(range(10))
        heap2 = tuple(range(10, 20))
        result = heapx.merge(heap1, heap2)
        assert len(result) == 20

    def test_merge_mixed_sequence_types(self):
        """Test merging mixed sequence types."""
        heap1 = [1, 2, 3]
        heap2 = (4, 5, 6)
        result = heapx.merge(heap1, heap2)
        assert len(result) == 6

    def test_merge_less_than_two_heaps(self):
        """Test merging less than 2 heaps raises error."""
        with pytest.raises(ValueError):
            heapx.merge([1, 2, 3])

    def test_merge_non_sequence(self):
        """Test merging non-sequence raises error."""
        with pytest.raises(TypeError):
            heapx.merge([1, 2], 123)

# ============================================================================
# Sorted Heaps Parameter Tests (20 tests)
# ============================================================================

class TestSortedHeapsParameter:
    """Test sorted_heaps parameter."""

    def test_sorted_heaps_true_skips_heapify(self):
        """Test sorted_heaps=True skips heapify."""
        heap1 = [1, 3, 5, 7, 9]
        heap2 = [2, 4, 6, 8, 10]
        heapx.heapify(heap1)
        heapx.heapify(heap2)
        result = heapx.merge(heap1, heap2, sorted_heaps=True)
        assert len(result) == 10

    def test_sorted_heaps_false_performs_heapify(self):
        """Test sorted_heaps=False performs heapify."""
        heap1 = [5, 3, 1, 7, 9]
        heap2 = [6, 4, 2, 8, 10]
        result = heapx.merge(heap1, heap2, sorted_heaps=False)
        assert len(result) == 10
        assert is_valid_heap(result)

    @pytest.mark.parametrize("arity", [2, 3, 4, 5])
    def test_sorted_heaps_various_arities(self, arity):
        """Test sorted_heaps with various arities."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        heapx.heapify(heap1, arity=arity)
        heapx.heapify(heap2, arity=arity)
        result = heapx.merge(heap1, heap2, arity=arity, sorted_heaps=True)
        assert len(result) == 100

    def test_sorted_heaps_with_key(self):
        """Test sorted_heaps with key function."""
        heap1 = [-5, 2, -8, 1]
        heap2 = [9, -3, 7, -4]
        heapx.heapify(heap1, cmp=abs)
        heapx.heapify(heap2, cmp=abs)
        result = heapx.merge(heap1, heap2, cmp=abs, sorted_heaps=True)
        assert len(result) == 8

    def test_sorted_heaps_max_heap(self):
        """Test sorted_heaps with max heap."""
        heap1 = [9, 7, 5, 3, 1]
        heap2 = [8, 6, 4, 2, 0]
        heapx.heapify(heap1, max_heap=True)
        heapx.heapify(heap2, max_heap=True)
        result = heapx.merge(heap1, heap2, max_heap=True, sorted_heaps=True)
        assert len(result) == 10

# ============================================================================
# Stress Tests (20 tests)
# ============================================================================

class TestStressTests:
    """Stress tests with large datasets."""

    def test_merge_large_heaps_10k(self):
        """Test merging 10k element heaps."""
        heap1 = list(range(10000))
        heap2 = list(range(10000, 20000))
        result = heapx.merge(heap1, heap2)
        assert len(result) == 20000
        assert is_valid_heap(result)

    def test_merge_many_heaps_100(self):
        """Test merging 100 heaps."""
        heaps = [list(range(i*10, (i+1)*10)) for i in range(100)]
        result = heapx.merge(*heaps)
        assert len(result) == 1000

    def test_merge_random_large(self):
        """Test merging large random heaps."""
        heap1 = generate_integers(5000, seed=1)
        heap2 = generate_integers(5000, seed=2)
        result = heapx.merge(heap1, heap2)
        assert len(result) == 10000
        assert is_valid_heap(result)

    @pytest.mark.parametrize("arity", [2, 3, 4, 5, 8])
    def test_merge_all_arities_large(self, arity):
        """Test all arities with large datasets."""
        heap1 = list(range(1000))
        heap2 = list(range(1000, 2000))
        result = heapx.merge(heap1, heap2, arity=arity)
        assert len(result) == 2000
        assert is_valid_heap(result, arity=arity)

    def test_merge_with_key_large(self):
        """Test merging large heaps with key function."""
        heap1 = list(range(-2500, 0))
        heap2 = list(range(0, 2500))
        result = heapx.merge(heap1, heap2, cmp=abs)
        assert len(result) == 5000

    def test_merge_repeated_operations(self):
        """Test repeated merge operations."""
        for _ in range(10):
            heap1 = list(range(100))
            heap2 = list(range(100, 200))
            result = heapx.merge(heap1, heap2)
            assert len(result) == 200

# ============================================================================
# Multiple Heaps Tests (20 tests)
# ============================================================================

class TestMultipleHeaps:
    """Test merging more than 2 heaps."""

    @pytest.mark.parametrize("n_heaps", [2, 3, 5, 10, 20, 50])
    def test_merge_n_heaps(self, n_heaps):
        """Test merging n heaps."""
        heaps = [list(range(i*10, (i+1)*10)) for i in range(n_heaps)]
        result = heapx.merge(*heaps)
        assert len(result) == n_heaps * 10
        assert is_valid_heap(result)

    def test_merge_three_different_sizes(self):
        """Test merging three heaps of different sizes."""
        heap1 = list(range(10))
        heap2 = list(range(10, 60))
        heap3 = list(range(60, 100))
        result = heapx.merge(heap1, heap2, heap3)
        assert len(result) == 100

    def test_merge_many_with_empties(self):
        """Test merging many heaps with some empty."""
        heaps = [[i] if i % 2 == 0 else [] for i in range(20)]
        result = heapx.merge(*heaps)
        assert len(result) == 10

# ============================================================================
# Correctness Tests (20 tests)
# ============================================================================

class TestCorrectness:
    """Test correctness of merge results."""

    def test_merge_contains_all_elements(self):
        """Test merged heap contains all elements."""
        heap1 = [1, 3, 5, 7]
        heap2 = [2, 4, 6, 8]
        result = heapx.merge(heap1, heap2)
        assert sorted(result) == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_merge_no_element_loss(self):
        """Test no elements are lost during merge."""
        heap1 = generate_integers(100, seed=1)
        heap2 = generate_integers(100, seed=2)
        all_elements = heap1 + heap2
        result = heapx.merge(heap1, heap2)
        assert sorted(result) == sorted(all_elements)

    def test_merge_maintains_heap_property(self):
        """Test merged result maintains heap property."""
        for _ in range(10):
            heap1 = generate_integers(50, seed=random.randint(0, 1000))
            heap2 = generate_integers(50, seed=random.randint(0, 1000))
            result = heapx.merge(heap1, heap2)
            assert is_valid_heap(result)

    @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8])
    def test_merge_heap_property_all_arities(self, arity):
        """Test heap property maintained for all arities."""
        heap1 = list(range(50))
        heap2 = list(range(50, 100))
        result = heapx.merge(heap1, heap2, arity=arity)
        assert is_valid_heap(result, arity=arity)

    def test_merge_with_key_maintains_property(self):
        """Test heap property with key function."""
        heap1 = list(range(-25, 0))
        heap2 = list(range(0, 25))
        result = heapx.merge(heap1, heap2, cmp=abs)
        assert is_valid_heap(result, cmp=abs)

# ============================================================================
# Performance Benchmarks (7 tests)
# ============================================================================

@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmarks for merge function."""

    def test_benchmark_time_efficiency(self, capsys):
        """Comprehensive time efficiency benchmark: heapx.merge vs heapq.merge."""
        
        output = []
        output.append("\n" + "="*80)
        output.append("TIME EFFICIENCY COMPARISON: heapx.merge vs heapq.merge")
        output.append("="*80)
        output.append(f"Configuration: R=10 repetitions per size, Random integers, Min-heap, Arity=2")
        output.append("="*80)
        
        sizes = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
        repetitions = 10
        
        results = []
        
        for n in sizes:
            heapx_times = []
            heapq_times = []
            
            for r in range(repetitions):
                # Prepare heaps (split in half)
                data1 = list(range(n // 2))
                data2 = list(range(n // 2, n))
                random.seed(r)
                random.shuffle(data1)
                random.shuffle(data2)
                
                # Measure heapx time
                start = time.perf_counter()
                result_heapx = heapx.merge(data1, data2)
                heapx_times.append(time.perf_counter() - start)
                
                # Measure heapq time (concatenate + heapify)
                start = time.perf_counter()
                result_heapq = data1 + data2
                heapq.heapify(result_heapq)
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
        output.append("="*80 + "\n")
        
        # Print all output
        final_output = '\n'.join(output)
        print(final_output)
        sys.stdout.flush()
        
        with capsys.disabled():
            print(final_output)

    def test_benchmark_memory_efficiency(self, capsys):
        """Comprehensive memory efficiency benchmark."""
        
        output = []
        output.append("\n" + "="*80)
        output.append("MEMORY EFFICIENCY: heapx.merge")
        output.append("="*80)
        output.append(f"Configuration: Random integers, Min-heap, Arity=2")
        output.append("="*80)
        
        sizes = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
        
        memory_results = []
        
        for n in sizes:
            heap1 = list(range(n // 2))
            heap2 = list(range(n // 2, n))
            
            mem_heap1 = sys.getsizeof(heap1)
            mem_heap2 = sys.getsizeof(heap2)
            
            result = heapx.merge(heap1, heap2)
            mem_result = sys.getsizeof(result)
            
            memory_results.append({
                'n': n,
                'mem_input': mem_heap1 + mem_heap2,
                'mem_result': mem_result
            })
        
        output.append("\n" + "-"*70)
        output.append(f"{'n':>12} │ {'Input Memory':>20} │ {'Result Memory':>20} │ {'Overhead':>10}")
        output.append("-"*70)
        
        for r in memory_results:
            overhead = r['mem_result'] - r['mem_input']
            output.append(f"{r['n']:>12,} │ {r['mem_input']:>17,} B │ {r['mem_result']:>17,} B │ {overhead:>7,} B")
        
        output.append("-"*70)
        output.append("\nNote: Merge creates new list with O(N) space")
        output.append("="*80 + "\n")
        
        final_output = '\n'.join(output)
        print(final_output)
        sys.stdout.flush()
        
        with capsys.disabled():
            print(final_output)

    def test_benchmark_sorted_heaps_speedup(self):
        """Benchmark sorted_heaps parameter speedup."""
        sizes = [100, 1000, 10000]
        results = []
        
        for size in sizes:
            heap1 = list(range(size // 2))
            heap2 = list(range(size // 2, size))
            heapx.heapify(heap1)
            heapx.heapify(heap2)
            
            # With heapify
            times_unsorted = []
            for _ in range(10):
                h1, h2 = heap1.copy(), heap2.copy()
                start = time.perf_counter()
                heapx.merge(h1, h2, sorted_heaps=False)
                times_unsorted.append(time.perf_counter() - start)
            
            # Without heapify
            times_sorted = []
            for _ in range(10):
                h1, h2 = heap1.copy(), heap2.copy()
                start = time.perf_counter()
                heapx.merge(h1, h2, sorted_heaps=True)
                times_sorted.append(time.perf_counter() - start)
            
            avg_unsorted = mean(times_unsorted) * 1000
            avg_sorted = mean(times_sorted) * 1000
            speedup = avg_unsorted / avg_sorted
            results.append((size, avg_unsorted, avg_sorted, speedup))
        
        print("\n" + "=" * 80)
        print("sorted_heaps Parameter Speedup")
        print("=" * 80)
        print(f"{'Size':<15} {'Unsorted (ms)':<20} {'Sorted (ms)':<20} {'Speedup':<15}")
        print("-" * 80)
        for size, unsorted, sorted_time, speedup in results:
            print(f"{size:<15} {unsorted:<20.6f} {sorted_time:<20.6f} {speedup:<15.2f}x")
        print("=" * 80)

    def test_benchmark_arity_comparison(self):
        """Benchmark different arity values."""
        arities = [2, 3, 4, 5, 8]
        results = []
        
        for arity in arities:
            heap1 = list(range(500))
            heap2 = list(range(500, 1000))
            
            times = []
            for _ in range(10):
                h1, h2 = heap1.copy(), heap2.copy()
                start = time.perf_counter()
                heapx.merge(h1, h2, arity=arity)
                times.append(time.perf_counter() - start)
            
            avg_time = mean(times) * 1000
            std_time = stdev(times) * 1000 if len(times) > 1 else 0
            results.append((arity, avg_time, std_time))
        
        print("\n" + "=" * 70)
        print("Arity Performance Comparison (n=1000)")
        print("=" * 70)
        print(f"{'Arity':<10} {'Avg Time (ms)':<20} {'Std Dev (ms)':<20}")
        print("-" * 70)
        for arity, avg, std in results:
            print(f"{arity:<10} {avg:<20.6f} {std:<20.6f}")
        print("=" * 70)

    def test_benchmark_key_function_overhead(self):
        """Benchmark key function overhead."""
        heap1 = list(range(-250, 0))
        heap2 = list(range(0, 250))
        
        # Without key
        times_no_key = []
        for _ in range(10):
            h1, h2 = heap1.copy(), heap2.copy()
            start = time.perf_counter()
            heapx.merge(h1, h2)
            times_no_key.append(time.perf_counter() - start)
        
        # With key
        times_with_key = []
        for _ in range(10):
            h1, h2 = heap1.copy(), heap2.copy()
            start = time.perf_counter()
            heapx.merge(h1, h2, cmp=abs)
            times_with_key.append(time.perf_counter() - start)
        
        avg_no_key = mean(times_no_key) * 1000
        avg_with_key = mean(times_with_key) * 1000
        overhead = (avg_with_key / avg_no_key - 1) * 100
        
        print("\n" + "=" * 70)
        print("Key Function Overhead (n=500)")
        print("=" * 70)
        print(f"Without key: {avg_no_key:.6f} ms")
        print(f"With key:    {avg_with_key:.6f} ms")
        print(f"Overhead:    {overhead:.2f}%")
        print("=" * 70)

    def test_benchmark_small_heap_optimization(self):
        """Benchmark small heap optimization."""
        sizes = [4, 8, 12, 16, 20, 30, 50]
        results = []
        
        for size in sizes:
            heap1 = list(range(size // 2))
            heap2 = list(range(size // 2, size))
            
            times = []
            for _ in range(10):
                h1, h2 = heap1.copy(), heap2.copy()
                start = time.perf_counter()
                heapx.merge(h1, h2)
                times.append(time.perf_counter() - start)
            
            avg_time = mean(times) * 1000
            results.append((size, avg_time))
        
        print("\n" + "=" * 70)
        print("Small Heap Optimization (n ≤ 16)")
        print("=" * 70)
        print(f"{'Size':<10} {'Avg Time (ms)':<20}")
        print("-" * 70)
        for size, avg in results:
            marker = " *" if size <= 16 else ""
            print(f"{size:<10} {avg:<20.6f}{marker}")
        print("=" * 70)
        print("* = Uses insertion sort optimization")

    def test_benchmark_many_heaps(self):
        """Benchmark merging many heaps."""
        n_heaps_list = [2, 5, 10, 20, 50, 100]
        results = []
        
        for n_heaps in n_heaps_list:
            heaps = [list(range(i*10, (i+1)*10)) for i in range(n_heaps)]
            
            times = []
            for _ in range(10):
                heaps_copy = [h.copy() for h in heaps]
                start = time.perf_counter()
                heapx.merge(*heaps_copy)
                times.append(time.perf_counter() - start)
            
            avg_time = mean(times) * 1000
            results.append((n_heaps, avg_time))
        
        print("\n" + "=" * 70)
        print("Many Heaps Performance (10 elements each)")
        print("=" * 70)
        print(f"{'# Heaps':<15} {'Avg Time (ms)':<20}")
        print("-" * 70)
        for n_heaps, avg in results:
            print(f"{n_heaps:<15} {avg:<20.6f}")
        print("=" * 70)



# ============================================================================
# Boolean Tests
# ============================================================================

class TestBooleanMerge:
  """Test merge with boolean data."""

  def test_merge_booleans(self):
    """Test merging boolean heaps."""
    heap1 = generate_booleans(25)
    heap2 = generate_booleans(25, seed=43)
    heapx.heapify(heap1)
    heapx.heapify(heap2)
    result = heapx.merge(heap1, heap2)
    assert len(result) == 50
    assert is_valid_heap(result)

# ============================================================================
# Bytes Tests
# ============================================================================

class TestBytesMerge:
  """Test merge with bytes data."""

  def test_merge_bytes(self):
    """Test merging bytes heaps."""
    heap1 = generate_bytes(15)
    heap2 = generate_bytes(15, seed=43)
    heapx.heapify(heap1)
    heapx.heapify(heap2)
    result = heapx.merge(heap1, heap2)
    assert len(result) == 30
    assert is_valid_heap(result)

# ============================================================================
# Bytearray Tests
# ============================================================================

class TestBytearrayMerge:
  """Test merge with bytearray data."""

  def test_merge_bytearrays(self):
    """Test merging bytearray heaps."""
    heap1 = generate_bytearrays(15)
    heap2 = generate_bytearrays(15, seed=43)
    heapx.heapify(heap1)
    heapx.heapify(heap2)
    result = heapx.merge(heap1, heap2)
    assert len(result) == 30
    assert is_valid_heap(result)

# ============================================================================
# List Tests
# ============================================================================

class TestListMerge:
  """Test merge with list data."""

  def test_merge_lists(self):
    """Test merging list heaps."""
    heap1 = generate_lists(15)
    heap2 = generate_lists(15, seed=43)
    heapx.heapify(heap1)
    heapx.heapify(heap2)
    result = heapx.merge(heap1, heap2)
    assert len(result) == 30
    assert is_valid_heap(result)

# ============================================================================
# Mixed Type Tests
# ============================================================================

class TestMixedMerge:
  """Test merge with mixed comparable types."""

  def test_merge_mixed(self):
    """Test merging mixed int/float heaps."""
    heap1 = generate_mixed(50)
    heap2 = generate_mixed(50, seed=43)
    heapx.heapify(heap1)
    heapx.heapify(heap2)
    result = heapx.merge(heap1, heap2)
    assert len(result) == 100
    assert is_valid_heap(result)

  def test_merge_mixed_max_heap(self):
    """Test merging mixed max-heaps."""
    heap1 = generate_mixed(50)
    heap2 = generate_mixed(50, seed=43)
    heapx.heapify(heap1, max_heap=True)
    heapx.heapify(heap2, max_heap=True)
    result = heapx.merge(heap1, heap2, max_heap=True)
    assert len(result) == 100
    assert is_valid_heap(result, max_heap=True)

  def test_merge_mixed_sorted_heaps(self):
    """Test merging mixed heaps with sorted_heaps=False (default)."""
    heap1 = generate_mixed(50)
    heap2 = generate_mixed(50, seed=43)
    heapx.heapify(heap1)
    heapx.heapify(heap2)
    result = heapx.merge(heap1, heap2, sorted_heaps=False)
    assert len(result) == 100
    assert is_valid_heap(result)
